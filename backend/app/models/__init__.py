"""models：SQLAlchemy ORM（detail §5.1 全表 ①~⑩，与 DDL 一一对应）。

import 各模型模块触发 Base.metadata 注册，供 alembic autogenerate / create_all 使用。
"""
from app.models import agent, config, error_flow, user  # noqa: F401  # 注册副作用
from app.models.agent import Agent, AgentCredential, Interface
from app.models.base import Base
from app.models.config import DictConfig
from app.models.error_flow import (
    ConversionRecord,
    ErrorCaseLink,
    ErrorCluster,
    NeedsReviewBatch,
    TraceJudgeState,
    VerifyRunRecord,
)
from app.models.user import User, UserSession

__all__ = [
    "Base",
    "Agent",
    "AgentCredential",
    "Interface",
    "DictConfig",
    "ConversionRecord",
    "ErrorCaseLink",
    "ErrorCluster",
    "NeedsReviewBatch",
    "TraceJudgeState",
    "VerifyRunRecord",
    "User",
    "UserSession",
]
