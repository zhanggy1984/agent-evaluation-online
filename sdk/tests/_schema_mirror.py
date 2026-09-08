"""消费端契约镜像校验（单测用）。

source of truth = `backend/app/consumer/schema.py`（EventModel，schema_version=1.0）。
SDK 是独立包（agent 侧安装），单测不 import backend 源码保持独立性，故在此镜像消费端规则：
凡本校验 PASS 的事件，消费端 pydantic 校验必收（字段全集/枚举/长度/组合语义同 schema.py）；
镜像与 backend 若漂移，D6 集成（S-2 丢弃计数）会暴露——两处都该对 §2.1 表负责。
"""
from __future__ import annotations

from typing import Any

# 顶层字段全集（schema.py EventModel，extra="forbid"）——SDK 构造不得越界
TOP_FIELDS = frozenset({
    "schema_version", "event_kind", "trace_id", "agent", "agent_version", "interface",
    "node", "seq", "branch", "parent", "ts", "duration_ms", "status", "error_type",
    "error_msg", "input", "output", "usage", "model", "quality", "retrieve_hit",
    "log_level", "log_message", "extra",
})
NODES = frozenset({"request", "llm_call", "tool_call", "retrieve", "db", "redis", "log"})
STATUS = frozenset({"ok", "error", "timeout"})
LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})
# extra 白名单（§2.9【实现约定】）；白名单外键消费端整条丢弃
EXTRA_ALLOWED = frozenset(
    {"request_id", "task_id", "job_id", "conv_id", "sub_agent", "prompt_kind"}
)
# 长度上限（§2.1）
MAX = {"trace_id": 64, "agent": 64, "agent_version": 64, "interface": 256,
       "error_type": 48, "error_msg": 512, "log_message": 8000, "model": 128}


def _bad(reason: str) -> str:
    return reason


def _str_bad(value: Any, limit: int) -> bool:
    """字符串类字段非法（非 str / 超长）。None 视为合法（schema 可空字段）。"""
    if value is None:
        return False
    return not isinstance(value, str) or len(value) > limit


def _int_bad(value: Any) -> bool:
    """非负 int 校验（bool 是 int 子类，须排除——schema ge=0 对 bool 也放行但语义要真 int）。"""
    return not isinstance(value, int) or isinstance(value, bool) or value < 0


def validate_event(ev: Any) -> str | None:
    """镜像 EventModel 校验。PASS → None；违反 → 原因串（消费端该条会 dropped.schema）。"""
    if not isinstance(ev, dict) or not ev:
        return _bad("非 dict 或空事件")
    unknown = set(ev) - TOP_FIELDS
    if unknown:
        return _bad(f"未知顶层字段: {sorted(unknown)}")
    if ev.get("schema_version") != "1.0":
        return _bad("schema_version 非 1.0")
    if ev.get("event_kind") not in ("event", "log"):
        return _bad("event_kind 非法")
    node = ev.get("node")
    if node not in NODES:
        return _bad(f"node 非法: {node!r}")
    status = ev.get("status")
    if status not in STATUS:
        return _bad(f"status 非法: {status!r}")
    for key in ("trace_id", "agent", "interface"):
        v = ev.get(key)
        if not isinstance(v, str) or not v or len(v) > MAX[key]:
            return _bad(f"{key} 缺失/空/超长")
    for key in ("seq", "ts"):
        if _int_bad(ev.get(key)):
            return _bad(f"{key} 非非负 int")
    for key, limit in (("agent_version", MAX["agent_version"]), ("model", MAX["model"]),
                       ("error_type", MAX["error_type"]), ("error_msg", MAX["error_msg"]),
                       ("log_message", MAX["log_message"])):
        if _str_bad(ev.get(key), limit):
            return _bad(f"{key} 超长/非 str")
    # extra 白名单过滤（§2.9：白名单外键 → 整条丢）
    extra = ev.get("extra")
    if not isinstance(extra, dict):
        return _bad("extra 非 dict")
    bad_extra = set(extra) - EXTRA_ALLOWED
    if bad_extra:
        return _bad(f"extra 白名单外键: {sorted(bad_extra)}")
    # log 行（event_kind=log）：字段面最窄
    is_log = ev.get("event_kind") == "log"
    if is_log:
        if node != "log":
            return _bad("event_kind=log 只允许 node=log")
        if ev.get("log_level") not in LOG_LEVELS or ev.get("log_message") is None:
            return _bad("log 行必填 log_level/log_message")
        if status != "ok":
            return _bad("log 行 status 只允许 ok")
        for key in ("duration_ms", "input", "output", "usage", "model", "error_type", "error_msg"):
            if ev.get(key) is not None:
                return _bad(f"log 行禁止带 {key}")
    else:
        if node == "log":
            return _bad("event_kind=event 不允许 node=log")
        if ev.get("log_level") is not None or ev.get("log_message") is not None:
            return _bad("事件节点禁止带 log_level/log_message")
    # request 锚点（§2.4）
    if node == "request":
        if ev.get("seq") != 0 or ev.get("parent") is not None:
            return _bad("request 必须 seq=0 且 parent=null")
        if ev.get("duration_ms") is None:
            return _bad("request 必填 duration_ms")
    elif not is_log and ev.get("parent") is None:
        return _bad("子节点必填 parent")
    # llm_call 必填 duration/usage/model（§2.1）
    if node == "llm_call":
        if ev.get("duration_ms") is None or ev.get("model") is None or ev.get("usage") is None:
            return _bad("llm_call 必填 duration_ms/usage/model")
        usage = ev["usage"]
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            v = usage.get(k) if isinstance(usage, dict) else None
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                return _bad(f"usage.{k} 缺失/非非负 int")
    # duration 若有必非负
    if ev.get("duration_ms") is not None and _int_bad(ev["duration_ms"]):
        return _bad("duration_ms 非非负 int")
    # status↔error_type 三态互斥（§4.2）
    if status == "error" and not ev.get("error_type"):
        return _bad("status=error 必填 error_type")
    if status != "error" and ev.get("error_type") is not None:
        return _bad("仅 status=error 允许 error_type")
    # interface 归一格式 `METHOD /path`（§4.2）
    if _bad_interface(ev.get("interface")):
        return _bad("interface 非法格式（须 `METHOD /path`）")
    return None


def _bad_interface(value: Any) -> bool:
    if not isinstance(value, str) or " " not in value:
        return True
    method, path = value.split(" ", 1)
    return not (method.isalpha() and method.isupper() and len(path) > 0)
