"""平台账号域：`user` / `user_session`（detail §5.1①，§13.1 JWT/refresh 会话）。

- `user` 为 MySQL 保留字，用 quoted_name 强制反引号。
- 全仓不建物理外键（与 DDL 一致），agent 归属等逻辑引用由应用层保证。
"""
from datetime import datetime

from sqlalchemy import CHAR, Enum, Index, String, UniqueConstraint, quoted_name, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BIGINT_UX, DT3, TINYINT, TS_DEFAULT, TS_UPDATE, Base


class User(Base):
    """平台账号：独立体系，viewer/admin 两角色，不做独立 role 表。"""

    __tablename__ = quoted_name("user", True)

    id: Mapped[int] = mapped_column(BIGINT_UX, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)  # bcrypt
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[str] = mapped_column(
        Enum("admin", "viewer", name="user_role", native_enum=True),
        nullable=False,
        server_default=text("'viewer'"),
    )
    status: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_DEFAULT)
    updated_at: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_UPDATE)

    __table_args__ = (
        UniqueConstraint("username", name="uk_user_username"),
        {"comment": "平台账号（viewer/admin）"},
    )


class UserSession(Base):
    """登录会话：refresh token 吊销（只存 sha256 hash，不存明文）。"""

    __tablename__ = "user_session"

    id: Mapped[int] = mapped_column(BIGINT_UX, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT_UX, nullable=False)
    refresh_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)  # sha256(refresh_token)
    expires_at: Mapped[datetime] = mapped_column(DT3, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DT3, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_DEFAULT)

    __table_args__ = (
        UniqueConstraint("refresh_hash", name="uk_session_refresh"),
        Index("idx_session_user", "user_id"),
        {"comment": "登录会话（refresh token 吊销）"},
    )
