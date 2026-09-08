"""agent 字典域：`agent` / `interface` / `agent_credential`（detail §5.1②③⑨）。

agent.name 是事件 agent 字段取值源（同串约束在应用层）；backflow_allow 为回流
白名单（cc=0，D18）。物理外键不建，与 DDL 一致。
"""
from datetime import datetime

from sqlalchemy import Enum, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BIGINT_UX, DT3, TINYINT, TS_DEFAULT, TS_UPDATE, Base


class Agent(Base):
    """agent 字典：自发现注册行 + 回流白名单。"""

    __tablename__ = "agent"

    id: Mapped[int] = mapped_column(BIGINT_UX, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enable: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("1"))
    route_source: Mapped[str] = mapped_column(
        Enum(
            "fastapi", "openapi", "manual", "auto_register",
            name="route_source", native_enum=True,
        ),
        nullable=False,
        server_default=text("'auto_register'"),
    )
    backflow_allow: Mapped[int] = mapped_column(
        TINYINT, nullable=False, server_default=text("1")
    )  # 维度3 回流白名单（cc=0）
    created_at: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_DEFAULT)
    updated_at: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_UPDATE)

    __table_args__ = (
        UniqueConstraint("name", name="uk_agent_name"),
        {"comment": "agent 字典"},
    )


class Interface(Base):
    """接口字典：事件自动注册 + llm 补标；interface 串 = 事件 interface 字段同串。"""

    __tablename__ = "interface"

    id: Mapped[int] = mapped_column(BIGINT_UX, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(BIGINT_UX, nullable=False)
    interface: Mapped[str] = mapped_column(String(256), nullable=False)
    method: Mapped[str | None] = mapped_column(String(8), nullable=True)
    path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    llm: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("0"))
    llm_source: Mapped[str | None] = mapped_column(
        Enum("config", "manual", "auto_observed", name="llm_source", native_enum=True),
        nullable=True,
    )  # llm 标记来源（config/manual/auto_observed）
    # 疑似漏标：接口字典 llm 判定观察窗内待复核
    llm_suspect: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("0"))
    body_search: Mapped[int] = mapped_column(
        TINYINT, nullable=False, server_default=text("0")
    )  # 正文可检索/可查看开关（默认关）
    status: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("1"))
    first_seen_ts: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_DEFAULT)
    last_seen_ts: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_DEFAULT)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("agent_id", "interface", name="uk_interface"),
        Index("idx_interface_llm", "agent_id", "llm", "llm_suspect"),
        {"comment": "接口字典（事件自动注册 + llm 补标）"},
    )


class AgentCredential(Base):
    """每 agent Kafka 上报凭证：SASL principal + 加密密码（§13.2 加密与轮换）。"""

    __tablename__ = "agent_credential"

    id: Mapped[int] = mapped_column(BIGINT_UX, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(BIGINT_UX, nullable=False)
    kafka_username: Mapped[str] = mapped_column(String(64), nullable=False)  # SASL principal
    secret_cipher: Mapped[str] = mapped_column(String(512), nullable=False)  # 加密后密码
    topic: Mapped[str] = mapped_column(String(128), nullable=False)  # obs.agent.<name>
    active: Mapped[int] = mapped_column(TINYINT, nullable=False, server_default=text("1"))
    rotated_at: Mapped[datetime | None] = mapped_column(DT3, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_DEFAULT)

    __table_args__ = (
        UniqueConstraint("agent_id", name="uk_cred_agent"),
        {"comment": "每 agent Kafka 凭证"},
    )
