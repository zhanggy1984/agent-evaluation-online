"""平台配置：`dict_config`（detail §5.1⑧，§10 生效键清单）。

agent_id NULL = 全局键；per-agent 键覆盖同名全局键。uk_dc(agent_id, config_key) 对
NULL 全局行不约束唯一（MySQL 唯一索引 NULL 语义），同名全局键去重由应用/seed 保证。
"""
from datetime import datetime

from sqlalchemy import JSON, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BIGINT_UX, DT3, TS_UPDATE, Base


class DictConfig(Base):
    """平台配置键值（v1 生效键见 §10；wordlist_version = 本表 version 列）。"""

    __tablename__ = "dict_config"

    id: Mapped[int] = mapped_column(BIGINT_UX, primary_key=True, autoincrement=True)
    agent_id: Mapped[int | None] = mapped_column(BIGINT_UX, nullable=True, comment="NULL=全局")
    config_key: Mapped[str] = mapped_column(String(64), nullable=False)
    config_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    # 变更 +1；fallback_utterance 的 version 即词表 wordlist_version（随 D19 固化）
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_ts: Mapped[datetime] = mapped_column(DT3, nullable=False, server_default=TS_UPDATE)

    __table_args__ = (
        UniqueConstraint("agent_id", "config_key", name="uk_dc"),
        {"comment": "平台配置（v1 键清单见 §10）"},
    )
