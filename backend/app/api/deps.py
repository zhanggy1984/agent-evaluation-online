"""FastAPI 鉴权依赖（detail §8.8）：平台用户 JWT（viewer/admin）+ 平台间 evaluator 服务凭证。

- get_current_user：Authorization `Bearer <access>` → decode（security.decode_access_token）→
  查 `user` 表 → status==1 校验。查库保 role/status 最新（非纯 claims 信任）。
- require_viewer / require_admin：viewer ∈ {viewer, admin}；admin-only 路由（§8.5/§8.6 +
  §8.4 backflow 人工动作）用 require_admin。
- require_evaluator：**平台间 /pull/* 专用（§8.8 独立签发路径，不接平台 JWT）**——校验
  Authorization `Bearer <evaluator_service_secret>`（预共享静态 secret，offline 部署同持）；
  未配置/不符 → ERR_PULL_0001(401)，fail-closed。
- 正文查看（body_search）在端点层另判，不在此。
"""
import secrets
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models.user import User

_SESSION = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(request: Request, session: _SESSION) -> User:
    authz = request.headers.get("Authorization", "")
    if not authz.startswith("Bearer "):
        raise AppError("ERR_AUTH_0001", "凭证缺失（需 Bearer access token）", http=401)
    bearer = authz[len("Bearer "):].strip()  # 请求头解析出的凭证串（运行时传入，非硬编码）
    claims = decode_access_token(request.app.state.settings, bearer)
    user = await session.get(User, int(claims["sub"]))
    if user is None or user.status != 1:
        raise AppError("ERR_AUTH_0001", "账号不存在或已停用", http=401)
    return user


async def require_viewer(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role not in ("viewer", "admin"):
        raise AppError("ERR_AUTH_0002", "角色不足（需要 viewer 及以上）", http=403)
    return user


async def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise AppError("ERR_AUTH_0002", "角色不足（需要 admin）", http=403)
    return user


async def require_evaluator(request: Request) -> None:
    """平台间服务凭证守卫（§8.8）：/pull/* 仅收 evaluator 凭证，不接平台 JWT。"""
    authz = request.headers.get("Authorization", "")
    if not authz.startswith("Bearer "):
        raise AppError("ERR_PULL_0001", "evaluator 凭证缺失", http=401)
    presented = authz[len("Bearer "):].strip()
    expected = request.app.state.settings.evaluator_service_secret
    if not expected or not secrets.compare_digest(presented, expected):
        raise AppError("ERR_PULL_0001", "evaluator 凭证无效", http=401)


CurrentUser = Annotated[User, Depends(get_current_user)]
ViewerUser = Annotated[User, Depends(require_viewer)]
AdminUser = Annotated[User, Depends(require_admin)]
EvaluatorUser = Annotated[None, Depends(require_evaluator)]
