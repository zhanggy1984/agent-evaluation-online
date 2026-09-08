"""平台登录与会话（detail §8.1）：POST /auth/login、/auth/refresh、/auth/logout、GET /auth/me。

- **最小闭环边界（2026-09-08 阶段 1 收尾批显式标注）**：失败锁定为进程内计数（backend 容器
  uvicorn --workers 1 单实例前提；重启清零可接受）；不做 token-version 列迁移 / admin user CRUD
  （属 §8.6 后续面）——本面由 refresh 会话吊销（UserSession.revoked_at）+ 账号 status 校验 +
  access 15min 短效覆盖最小闭环。缺口显式化而非静默。
- refresh 轮换：旧 session 吊销 + 新 access/refresh 重签（吊销即时生效；§8.1「token version」
  在本最小面 = session 行级吊销）。
- 时间口径：MySQL DATETIME3 无时区，统一存 naive UTC（datetime.now(timezone.utc) 去 tz）。
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.api.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
from app.core.db import get_session
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.models.user import User, UserSession

router = APIRouter(prefix="/auth", tags=["auth"])

_Session = Annotated[AsyncSession, Depends(get_session)]

# 失败锁定（§13.2：5 次/15min）：username → 失败时间戳列表。进程内、单实例语义。
_LOCK_MAX_FAILS = 5
_LOCK_WINDOW_S = 900
_login_fails: dict[str, list[float]] = {}


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _check_locked(username: str) -> None:
    now = time.time()
    recent = [t for t in _login_fails.get(username, []) if now - t < _LOCK_WINDOW_S]
    _login_fails[username] = recent
    if len(recent) >= _LOCK_MAX_FAILS:
        raise AppError("ERR_AUTH_0003", "登录失败次数过多，已锁定 15 分钟", http=423)


def _record_fail(username: str) -> None:
    _login_fails.setdefault(username, []).append(time.time())


def _reset_fails(username: str) -> None:
    _login_fails.pop(username, None)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, session: _Session) -> dict:
    username = body.username.strip()
    _check_locked(username)

    settings = request.app.state.settings
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or user.status != 1 or not verify_password(body.password, user.password_hash):
        # 不区分「用户不存在/停用/口令错」：统一口径防账号枚举（§13.2 失败计数按 username）
        _record_fail(username)
        raise AppError("ERR_AUTH_0001", "用户名或密码错误", http=401)

    _reset_fails(username)

    access = create_access_token(settings, user.id, user.role)
    refresh = generate_refresh_token()
    session.add(
        UserSession(
            user_id=user.id,
            refresh_hash=hash_refresh_token(refresh),
            expires_at=_utcnow_naive() + timedelta(days=settings.jwt_refresh_days),
        )
    )
    await session.commit()
    return {
        "access_token": access,
        "refresh_token": refresh,
        "user": UserOut(
            id=user.id, username=user.username, display_name=user.display_name, role=user.role
        ),
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, request: Request, session: _Session) -> dict:
    settings = request.app.state.settings
    r_hash = hash_refresh_token(body.refresh_token)
    result = await session.execute(select(UserSession).where(UserSession.refresh_hash == r_hash))
    row = result.scalar_one_or_none()
    now = _utcnow_naive()
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        raise AppError("ERR_AUTH_0001", "refresh token 无效或已过期", http=401)

    user = await session.get(User, row.user_id)
    if user is None or user.status != 1:
        raise AppError("ERR_AUTH_0001", "账号不存在或已停用", http=401)

    # 轮换：吊销旧会话 + 签发新 access/refresh（单会话语义：旧 refresh 即刻失效）
    row.revoked_at = now
    new_refresh = generate_refresh_token()
    session.add(
        UserSession(
            user_id=user.id,
            refresh_hash=hash_refresh_token(new_refresh),
            expires_at=now + timedelta(days=settings.jwt_refresh_days),
        )
    )
    await session.commit()
    return {
        "access_token": create_access_token(settings, user.id, user.role),
        "refresh_token": new_refresh,
        "user": UserOut(
            id=user.id, username=user.username, display_name=user.display_name, role=user.role
        ),
    }


@router.post("/logout", status_code=204)
async def logout(body: LogoutRequest, user: CurrentUser, session: _Session) -> None:
    r_hash = hash_refresh_token(body.refresh_token)
    result = await session.execute(
        select(UserSession).where(
            UserSession.refresh_hash == r_hash, UserSession.user_id == user.id
        )
    )
    row = result.scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        row.revoked_at = _utcnow_naive()
        await session.commit()


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut(
        id=user.id, username=user.username, display_name=user.display_name, role=user.role
    )
