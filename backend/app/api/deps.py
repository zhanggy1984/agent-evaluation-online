"""FastAPI 鉴权依赖（detail §8.8）：当前用户解析 + viewer 角色守卫。

- get_current_user：Authorization `Bearer <access>` → decode（security.decode_access_token）→
  查 `user` 表 → status==1 校验。查库保 role/status 最新（非纯 claims 信任）。
- require_viewer：role ∈ {viewer, admin}（admin 继承 viewer 最小权限；detail §8.1「viewer 可访问
  8.1~8.4，admin 才可 8.5/8.6」）。admin-only 路由后续（§8.5/§8.6）用 require_admin。
- 正文查看（body_search）在端点层另判，不在此。
"""
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


CurrentUser = Annotated[User, Depends(get_current_user)]
ViewerUser = Annotated[User, Depends(require_viewer)]
