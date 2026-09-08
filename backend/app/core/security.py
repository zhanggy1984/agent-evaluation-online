"""平台 JWT 签发/校验 + 口令 bcrypt（detail §8.1/§8.8/§13.1）。

- access：短效 JWT（settings.jwt_access_minutes=15，HS256），claims `sub`=user.id/`role`/`exp`。
- refresh：不透明随机串，仅存 sha256 到 user_session（明文不可复现，吊销走 session 行）。
- 角色守卫与失败锁定不在此层：守卫在 api/deps.py，失败锁定在 api/auth.py（进程内，单 worker
  语义，backend 容器 uvicorn --workers 1 前提，§13.2）。
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import Settings
from app.core.errors import AppError

_ALG = "HS256"


def verify_password(plain: str, password_hash: str) -> bool:
    """口令校验（bcrypt；hash 为 seed 落库的 str 形态）。"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False  # hash 非法形态：按不匹配处理，不抛 500


def create_access_token(settings: Settings, user_id: int, role: str) -> str:
    """签发短效 access JWT。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=settings.jwt_access_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALG)


def decode_access_token(settings: Settings, token: str) -> dict:
    """校验并解码 access JWT；无效/过期 → ERR_AUTH_0001。"""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[_ALG])
    except jwt.InvalidTokenError as exc:
        raise AppError("ERR_AUTH_0001", "凭证缺失/过期/吊销", http=401) from exc


def generate_refresh_token() -> str:
    """新 refresh 不透明串（每次登录/轮换新值）。"""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """refresh 存库形态：sha256 hex（CHAR(64)，不存明文，§13.1）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
