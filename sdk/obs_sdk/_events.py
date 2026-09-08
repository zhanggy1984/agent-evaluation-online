"""事件构造层：产出与消费端 consumer/schema.py EventModel 同形的 dict（schema_version=1.0）。

设计（why）：
- 消费端顶层 extra="forbid"，未知字段/白名单外 extra 键 → 整条丢弃（S-2 计数）。故 SDK 构造
  必须只产 schema 已知字段，extra 只透传白名单键（_filter_extra，越界键丢弃并计数——宁丢附带
  字段不丢整条）。
- log 行（event_kind=log）字段面最窄（禁 duration/input/output/usage/model/error_type/error_msg），
  与事件节点分开构造，防止把节点字段误带给 log 行被消费端整条丢。
- status 三态约束对齐 §4.2：error 必带 error_type、ok/timeout 必不带。
- 真正兜底校验在消费端（validate.py）；本层护栏目标是"SDK 自己产不坏事件"，字段全集是构造
  函数写死的，不是业务自由拼接。
"""
from __future__ import annotations

import logging
import time
from typing import Any

SCHEMA_VERSION = "1.0"

# 顶层长度上限（§2.1 与 consumer/schema.py 对齐，防 SDK 侧超限造无效事件）
MAX_TRACE_ID = 64
MAX_AGENT = 64
MAX_AGENT_VERSION = 64
MAX_INTERFACE = 256
MAX_MODEL = 128
MAX_ERROR_TYPE = 48
MAX_ERROR_MSG = 512

# extra 白名单（§2.9【实现约定】；白名单外键消费端整条丢，SDK 侧过滤保命）
EXTRA_ALLOWED = frozenset(
    {"request_id", "task_id", "job_id", "conv_id", "sub_agent", "prompt_kind"}
)

# logging levelno → log_level（consumer schema LogLevel 枚举）
_LOG_LEVEL_MAP = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "ERROR",  # CRITICAL 不在枚举 → 归一 ERROR（不可产枚举外值）
}
_DEFAULT_LOG_LEVEL = "INFO"

# ---- trace 上下文（事件公共字段来源；构造函数显式传入，便于单测纯函数） ----

# ctx 为 dict：{agent, agent_version, trace_id, interface}，来自 _context.py
TraceCtx = dict[str, str | None]


def _trunc(value: str | None, limit: int) -> str | None:
    """超长截断（§2.1 上限是消费端丢弃阈值，SDK 侧截断保通过）。"""
    if value is None:
        return None
    return value if len(value) <= limit else value[:limit]


def _filter_extra(extra: dict[str, Any] | None) -> dict[str, Any]:
    """只透传白名单键；越界键丢弃（宁丢附带字段不丢整条事件，见模块 docstring）。"""
    if not extra:
        return {}
    return {k: v for k, v in extra.items() if k in EXTRA_ALLOWED}


def _trunc_extra(extra: dict[str, Any] | None) -> dict[str, Any]:
    """白名单键值截断兜底：字符串值超 512 截断（值面护栏，键级不在此判断）。"""
    out = _filter_extra(extra)
    for k in list(out):
        v = out[k]
        if isinstance(v, str) and len(v) > 512:
            out[k] = v[:512]
    return out


def normalize_route(method: str, path: str) -> str:
    """路径归一为 `METHOD /path`（§11.1 动态段 → `{id}`）。

    启发式（v1 够用）：动态段 = 纯数字 / 含 `-` 的 UUID/雪花形 / ≥24 位长 token；其余保留。
    业务路由若是显式模板（如 `/api/chat/{session_id}`）已是 `{id}` 形，启发式不改它——
    花括号包裹的段原样保留（agent 中间件也可直接传归一后 interface 覆盖本函数）。
    """
    if not method or not path:
        return "METHOD /path"  # 不可为空的兜底；正常调用必传真实 method/path
    path = path or "/"
    segs = []
    for seg in path.split("/"):
        if seg == "" or "{" in seg:
            segs.append(seg)
            continue
        if seg.isdigit() or (len(seg) >= 24) or ("-" in seg and len(seg) >= 16):
            segs.append("{id}")
        else:
            segs.append(seg)
    return f"{method.upper()} {'/'.join(segs) or '/'}"


# ---- 各节点事件构造（参数来自 _context 的 span + 调用方现场；ts 由调用方传可测，缺省现打） ----

def _base(ctx: TraceCtx, *, node: str, seq: int, parent: int | None, ts: int,
          event_kind: str = "event") -> dict[str, Any]:
    """公共字段信封（必填项 + ctx 里取 agent/version/interface）。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "event_kind": event_kind,
        "trace_id": _trunc(ctx["trace_id"], MAX_TRACE_ID),
        "agent": _trunc(ctx["agent"], MAX_AGENT),
        "agent_version": _trunc(ctx.get("agent_version") or None, MAX_AGENT_VERSION),
        "interface": _trunc(ctx["interface"], MAX_INTERFACE),
        "node": node,
        "seq": seq,
        "parent": parent,
        "ts": ts,
    }


def build_request_event(ctx: TraceCtx, *, ts: int, duration_ms: int, status: str,
                        error_type: str | None = None, error_msg: str | None = None,
                        output: Any = None, extra: dict[str, Any] | None = None) -> dict:
    """request 锚点：seq=0 + parent=null + duration_ms 必填（§2.4）。"""
    ev = _base(ctx, node="request", seq=0, parent=None, ts=ts)
    ev.update({"duration_ms": duration_ms, "status": status,
               "extra": _trunc_extra(extra)})
    if output is not None:  # v1 正文默认不采（§2.7 逐接口评估 #8），显式传才落键
        ev["output"] = output
    if status == "error":
        ev["error_type"] = _trunc(error_type, MAX_ERROR_TYPE)
        ev["error_msg"] = _trunc(error_msg, MAX_ERROR_MSG)
    return ev


def build_llm_event(ctx: TraceCtx, *, seq: int, parent: int, ts: int, model: str,
                    status: str, duration_ms: int, usage: dict | None,
                    error_type: str | None = None, error_msg: str | None = None,
                    extra: dict[str, Any] | None = None) -> dict:
    """llm_call：必 duration/usage/model（§2.1）；usage 缺省以全 0 占位（错误态无计费信息）。"""
    ev = _base(ctx, node="llm_call", seq=seq, parent=parent, ts=ts)
    usage0 = usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    ev.update({"model": _trunc(model, MAX_MODEL), "status": status,
               "duration_ms": duration_ms, "usage": usage0, "extra": _trunc_extra(extra)})
    if status == "error":
        ev["error_type"] = _trunc(error_type, MAX_ERROR_TYPE)
        ev["error_msg"] = _trunc(error_msg, MAX_ERROR_MSG)
    return ev


def build_tool_event(ctx: TraceCtx, *, node: str, seq: int, parent: int, ts: int,
                     status: str, duration_ms: int,
                     error_type: str | None = None) -> dict:
    """tool_call/db/redis 子节点（v1 record_tool/record_db 共用；无 usage/model 面）。

    schema Node 枚举没有 name 载体、extra 白名单也不含 tool 名（§2.9）——tool 名放不进事件，
    塞进 request_id 会污染业务检索 → v1 该面节点不产 extra 键（name 仅 agent 本地日志/计数）。
    """
    ev = _base(ctx, node=node, seq=seq, parent=parent, ts=ts)
    ev.update({"status": status, "duration_ms": duration_ms, "extra": {}})
    if status == "error":
        ev["error_type"] = _trunc(error_type, MAX_ERROR_TYPE)
    return ev


def build_log_event(ctx: TraceCtx, *, seq: int, ts: int, log_level: str, log_message: str,
                    extra: dict[str, Any] | None = None) -> dict:
    """log 行（event_kind=log，node=log）：字段面最窄——status 恒 ok、禁节点字段（§4.2）。"""
    level = log_level if log_level in ("DEBUG", "INFO", "WARNING", "ERROR") else _DEFAULT_LOG_LEVEL
    ev = _base(ctx, node="log", seq=seq, parent=None, ts=ts, event_kind="log")
    ev.update({"status": "ok", "log_level": level,
               "log_message": (log_message or "")[:8000], "extra": _trunc_extra(extra)})
    return ev


def levelno_to_log_level(levelno: int) -> str:
    """logging levelno → LogLevel 枚举值（枚举外归一；CRITICAL→ERROR）。"""
    return _LOG_LEVEL_MAP.get(levelno, _DEFAULT_LOG_LEVEL)


def build_heartbeat(agent: str, ts: int) -> dict:
    """SDK 心跳（§3.6 观测信号，obs.selfmonitor）：消费端 _selfmonitor_loop 只取 agent/ts。"""
    return {"agent": agent, "ts": ts}


def now_ms() -> int:
    return int(time.time() * 1000)
