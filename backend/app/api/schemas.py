"""API 请求/响应 pydantic 模型（detail §8；分页口径 §1.5 = {items, total, page, page_size}）。

auth 面（§8.1）本轮最小闭环；trace 面响应模型随 §8.2 在 app/api/trace.py 内联（事件行字段多，
与 ES 文档同构），通用分页包装放这里。
"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

# ---------- auth（§8.1） ----------


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    role: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserOut


# ---------- 通用分页（§1.5） ----------

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """分页包装：{items, total, page, page_size}（detail §1.5 / CONTRIBUTING）。"""

    items: list[T]
    total: int
    page: int
    page_size: int
