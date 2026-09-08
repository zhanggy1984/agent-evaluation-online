"""consumer 事件 schema（detail §2.1 顶层字段规格 + §2.5 error_type + §2.9 extra 白名单）。

v1 error-only 契约要点（why）：
- 顶层 extra="forbid"：未知顶层字段 = "多余未知字段"（X-1）→ 整条丢弃。
- `error_type` 值域非闭合（§2.5 全集 + `auth_error/validation_error 等`业务扩展）→ 本层只做
  "status=error 必填 + 长度 ≤48"，不做闭合枚举拒绝；L1/L2 值域筛归回流层 classify（§6.1）。
- `quality`/`retrieve_hit` 二期占位字段：声明可空、不校验不消费（§2.8 勿实现勿误传）。
- 值/枚举级（缺失/类型错/枚举外）由 pydantic 直接抛 ValidationError；跨字段组合语义
  （event_kind×node、request 锚点、log 白名单、必填依赖）在 model_validator 判 ValueError。
  两者统一由 validate.py 归并成 dropped.schema 计数。
"""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EventKind = Literal["event", "log"]
# node 全集（§2.1/§2.3）：log 只配 event_kind=log；事件节点枚举剔除 log 由组合校验兜底
Node = Literal["request", "llm_call", "tool_call", "retrieve", "db", "redis", "log"]
Status = Literal["ok", "error", "timeout"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

# 长度上限（§2.1）：error_msg≤512、log_message≤8K、interface≤256、trace_id≤64
MAX_TRACE_ID = 64
MAX_AGENT = 64
MAX_INTERFACE = 256
MAX_MODEL = 128
MAX_ERROR_TYPE = 48
MAX_ERROR_MSG = 512
MAX_LOG_MSG = 8000

# extra 白名单（§2.9【实现约定】）；白名单外键整条丢弃并计数（validate.py 分型 extra_key）
EXTRA_ALLOWED = frozenset(
    {"request_id", "task_id", "job_id", "conv_id", "sub_agent", "prompt_kind"}
)

# 事件节点（event_kind=event 允许）；log 行独立
EVENT_NODES = ("request", "llm_call", "tool_call", "retrieve", "db", "redis")


class UsageModel(BaseModel):
    """usage（§2.1：非负 int ×3）。"""

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class EventModel(BaseModel):
    """顶层事件信封。字段即 §2.1 表；必填无默认（缺失 → pydantic ValidationError）。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]  # 必填：缺失或非 1.0 → pydantic 类型不匹配直接丢（§2.1）
    event_kind: EventKind
    trace_id: str = Field(min_length=1, max_length=MAX_TRACE_ID)
    agent: str = Field(min_length=1, max_length=MAX_AGENT)
    agent_version: str | None = Field(default=None, max_length=64)
    interface: str = Field(min_length=1, max_length=MAX_INTERFACE)
    node: Node
    seq: int = Field(ge=0)
    branch: int | None = Field(default=None, ge=0)
    parent: int | None = Field(default=None, ge=0)
    ts: int = Field(ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    status: Status
    error_type: str | None = Field(default=None, max_length=MAX_ERROR_TYPE)
    error_msg: str | None = Field(default=None, max_length=MAX_ERROR_MSG)
    input: Any = None
    output: Any = None
    usage: UsageModel | None = None
    model: str | None = Field(default=None, max_length=MAX_MODEL)
    quality: Any = None  # 二期占位：恒缺省、不消费（§2.8）
    retrieve_hit: Any = None
    log_level: LogLevel | None = None
    log_message: str | None = Field(default=None, max_length=MAX_LOG_MSG)
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_semantics(self) -> "EventModel":
        """跨字段组合语义（§4.2/§2.3/§2.4）。任一违反 → ValueError → dropped.schema。"""
        is_log = self.event_kind == "log"
        # log 行：node=log + 只允许 log 特有字段 + status 恒 ok（log 非节点状态载体）
        if is_log:
            if self.node != "log":
                raise ValueError("event_kind=log 只允许 node=log")
            if self.log_level is None or self.log_message is None:
                raise ValueError("event_kind=log 必填 log_level/log_message")
            if self.status != "ok":
                raise ValueError("log 行 status 只允许 ok")
            if self.duration_ms is not None or self.input is not None or self.output is not None:
                raise ValueError(
                    "log 行禁止带 duration/input/output（§4.2 仅 log_level/log_message）"
                )
            if self.usage is not None or self.model is not None:
                raise ValueError("log 行禁止带 usage/model")
            if self.error_type is not None or self.error_msg is not None:
                raise ValueError("log 行禁止带 error_type/error_msg")
        else:
            if self.node == "log":
                raise ValueError("event_kind=event 不允许 node=log")
            if self.log_level is not None or self.log_message is not None:
                raise ValueError("事件节点禁止带 log_level/log_message")
        # request 锚点（§2.4）：seq=0 + parent=null
        if self.node == "request":
            if self.seq != 0 or self.parent is not None:
                raise ValueError("request 节点必须 seq=0 且 parent=null（§2.4）")
            if self.duration_ms is None:
                raise ValueError("request 节点必填 duration_ms")
        # 非根子节点 parent 必填（log 除外——日志行可游离挂接，§2.2③ parent=null）
        elif self.node != "log" and self.parent is None:
            raise ValueError("子节点必填 parent（父 seq 引用）")
        # llm_call 必填 duration/usage/model（§2.1 llm_call ✅ 列）
        if self.node == "llm_call":
            if self.duration_ms is None:
                raise ValueError("llm_call 必填 duration_ms")
            if self.usage is None or self.model is None:
                raise ValueError("llm_call 必填 usage/model")
        # status=error → error_type 必填；非 error/timeout 不带 error_type（三态互斥）
        if self.status == "error" and self.error_type is None:
            raise ValueError("status=error 必填 error_type")
        if self.status != "error" and self.error_type is not None:
            raise ValueError("仅 status=error 允许 error_type")
        # interface 归一化格式：`METHOD /path`（§4.2 非 HTTP 路径/空 → 丢弃）
        if not _is_http_interface(self.interface):
            raise ValueError(f"interface 非法格式（须 `METHOD /path`）：{self.interface!r}")
        return self


def _is_http_interface(value: str) -> bool:
    """interface 归一格式：HTTP 动词 + 空格 + 非空 path（`{id}` 归一为 SDK 义务，不复核）。"""
    if " " not in value:
        return False
    method, path = value.split(" ", 1)
    return method.isalpha() and method.isupper() and len(path) > 0
