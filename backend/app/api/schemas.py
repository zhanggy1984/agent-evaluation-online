"""API 请求/响应 pydantic 模型（detail §8；分页口径 §1.5 = {items, total, page, page_size}）。

auth 面（§8.1）本轮最小闭环；trace 面响应模型随 §8.2 在 app/api/trace.py 内联（事件行字段多，
与 ES 文档同构），通用分页包装放这里。
"""
from datetime import datetime
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


# ---------- admin 系统管理（§8.6） ----------


class ConfigItem(BaseModel):
    """配置项。`version` 为 0 且 `is_default=True` = 库内无行、此处回显 seed 默认值。"""

    agent_id: int | None = None
    key: str
    value: Any
    version: int
    updated_by: str | None = None
    updated_ts: datetime | None = None
    is_default: bool = False


class ConfigUpdateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    value: Any
    agent_id: int | None = None  # 缺省 = 全局键；给了 = per-agent 键


class UserAdminOut(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    role: str
    status: int
    created_at: datetime | None = None


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    # 最小口令规则 = 长度 8~64；不做复杂度要求（v1 单团队内部系统，复杂度规则易成摆设）
    password: str = Field(min_length=8, max_length=64)
    display_name: str | None = Field(default=None, max_length=64)
    role: str = "viewer"


class UserUpdateRequest(BaseModel):
    """字段缺省 = 不修改（None 不代表清空）；`password` 给了 = 重置口令并撤销该用户全部会话。"""

    display_name: str | None = Field(default=None, max_length=64)
    role: str | None = None
    status: int | None = None
    password: str | None = Field(default=None, min_length=8, max_length=64)


# ---------- admin · agent 与接口字典（§8.5） ----------


class AgentAdminOut(BaseModel):
    """agent 字典行——**MySQL 字典面**，非 §8.3 的 ES 观测面 `/metrics/agents`
    （后者只返回「近 7d 有流量的 agent 名」，零流量/已禁用的 agent 在其中不可见）。"""

    id: int
    name: str
    display_name: str
    enable: int
    backflow_allow: int
    route_source: str
    base_url: str | None = None
    interface_count: int = 0


class InterfaceAdminOut(BaseModel):
    id: int
    agent_id: int
    interface: str
    method: str | None = None
    path: str | None = None
    llm: int
    llm_source: str | None = None
    llm_suspect: int
    body_search: int
    status: int
    first_seen_ts: datetime
    last_seen_ts: datetime
    updated_by: str | None = None


class InterfaceListOut(BaseModel):
    items: list[InterfaceAdminOut]
    truncated: bool = False


class InterfaceUpdateRequest(BaseModel):
    """字段缺省 = 不修改。

    ⚠️ **`interface` 串不可改**：它是唯一键列 `uk_interface(agent_id, interface)`
    （`models/agent.py:70`），改它等于换实体；且 §8.5 的入参定义（detail `:1129`）
    里**本就没有该字段**——文档括注要求的「改 interface 串须记审计」无入参载体。
    """

    llm: int | None = None
    llm_source: str | None = None
    body_search: int | None = None


class AgentHealthOut(BaseModel):
    """agent 上报健康卡（§8.5）：聚合 ES 事件 index 的 `node=heartbeat` doc。

    无心跳 ⇒ `last_seen_ts=None` ⇒ 前端出「未接入 SDK」（§9.1 据此区分「未接入 vs 无流量」）。

    ⚠️ **不含 `spool_pending`**：detail §3.6（`:432`）定义的心跳 body 含该字段，但**双端都无
    写入方**——平台侧 `consumer/main.py:76-83` 构造的 doc 是 `{node, agent, ts, dropped, source}`，
    SDK 侧 `grep spool_pending sdk/obs_sdk/*.py` 零命中（2026-09-14 取证）。照批 1「token version」
    先例：按实机实现，订正文字，不为契约造字段。
    """

    agent_id: int
    last_seen_ts: int | None = None
    report_1min: int = 0
    report_5min: int = 0
    dropped: dict[str, int] = Field(default_factory=dict)
    sdk_connected: bool = False


# ---------- 通用分页（§1.5） ----------

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """分页包装：{items, total, page, page_size}（detail §1.5 / CONTRIBUTING）。"""

    items: list[T]
    total: int
    page: int
    page_size: int
