"""obs_sdk（detail §11.1 v1 API）：agent 观测上报 SDK。

用法（agent 仓接入，§11.2 Step 1）：
    import obs_sdk
    obs_sdk.init("good-question", kafka_servers="localhost:39092",
                 topic="dev.obs.agent.good-question")
    # FastAPI 中间件：begin_request(method, path) ... end_request(status)
    # LLM 调用包装：裸调用异常「先记 error 再抛」（§2.4 前提）：
    #     try: ...; obs_sdk.record_llm(model, "ok", duration_ms=.., usage=..)
    #     except Exception as e: obs_sdk.record_llm(model, "error",
    #                 error_type="..", error_msg=str(e), duration_ms=..); raise
    # structlog 仓：链上插 obs_sdk.structlog_processor()
    obs_sdk.shutdown()

事件由本包构造（对齐 consumer/schema.py EventModel）；真正校验兜底在消费端（S-2 丢弃计数）。
agent_version 从环境变量 AGENT_VERSION 注入（缺失则事件不带该字段）。
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Optional

from obs_sdk import _state
from obs_sdk._context import ProcessCtx, current, enter, reset
from obs_sdk._events import (
    EXTRA_ALLOWED,
    MAX_MODEL,
    build_heartbeat,
    build_llm_event,
    build_request_event,
    build_tool_event,
    normalize_route,
    now_ms,
)
from obs_sdk._logging import attach_stdlib_handler
from obs_sdk._sink import EVENT_TOPIC, HB_TOPIC, Sink
from obs_sdk._structlog import sdk_processor

logger = logging.getLogger("obs_sdk")

__all__ = [
    "init", "shutdown", "begin_request", "end_request", "record_llm", "record_tool",
    "record_db", "record_redis", "heartbeat", "log", "structlog_processor",
    "is_initialized", "EXTRA_ALLOWED",  # EXTRA_ALLOWED 重导出：agent 拼 extra 白名单键用
]

_OK_STATUSES = ("ok", "error", "timeout")
_initialized = False


def is_initialized() -> bool:
    return _initialized


def init(agent: str, *, kafka_servers: str, topic: str,
         spool_dir: str | None = "/var/lib/obs-sdk",  # §11.1 权威签名；None=显式关补传降级
         sasl_username: Optional[str] = None, sasl_password: Optional[str] = None,
         flush_batch: int = 500, flush_interval_s: float = 2.0,
         log_mode: str = "stdlib", heartbeat: bool = True,
         extra_loggers: Optional[list[str]] = None) -> None:
    """装配（detail §11.1）。agent 名 = 消费白名单名（DB agent.name，全名）；topic 必传完整
    `{env}.obs.agent.<name>`。必须在 agent 自身日志体系装配后调用（stdlib attach root /
    structlog 由仓在链上插 processor）。重复 init 抛错（进程单例）。

    stdlib 模式下默认把 handler 挂到 root logger；对 `propagate=False` 的自有命名 logger
    （root handler 收不到，如 cs 的 `"cs"`）需经 `extra_loggers` 显式点名，同一 handler
    一并挂到这些 logger 上（v0.1.1 新增；仅 stdlib 模式生效，structlog 忽略）。"""
    global _initialized
    if _initialized:
        raise RuntimeError("obs_sdk.init 已调用（进程级单例，勿重复初始化）")
    if not agent or not kafka_servers or not topic:
        raise ValueError("init 必传 agent / kafka_servers / topic")
    if log_mode not in ("stdlib", "structlog"):
        raise ValueError("log_mode 仅支持 stdlib / structlog")

    _state.process = {"agent": agent, "agent_version": os.environ.get("AGENT_VERSION")}
    # SASL 凭据 dict 展开传入（Sink 侧 None=PLAINTEXT）；dev 无 SASL 则不传保持默认
    sasl_kwargs = None
    if sasl_username:
        sasl_kwargs = {"sasl_username": sasl_username, "sasl_password": sasl_password or ""}
    sink = Sink(kafka_servers, agent=agent, agent_topic=topic,
                flush_batch=flush_batch, flush_interval_s=flush_interval_s,
                spool_dir=spool_dir, heartbeat=heartbeat, **(sasl_kwargs or {}))
    sink.start()
    _state.sink = sink
    if log_mode == "stdlib":
        handler = attach_stdlib_handler()
        for name in extra_loggers or ():
            logging.getLogger(name).addHandler(handler)  # propagate=False logger 才需点名（§11.3 cs）
    _initialized = True
    logger.info("obs_sdk init", extra={"agent": agent, "topic": topic,
                                       "log_mode": log_mode})


def shutdown() -> None:
    """收尾：终刷剩余事件后关线程（FastAPI lifespan shutdown 钩子调用）。"""
    global _initialized
    if _state.sink is not None:
        _state.sink.stop(flush=True)
        _state.sink = None
    _state.process = {}
    _initialized = False


def _require_span(what: str):
    """当前请求上下文；无则告警并返回 None（漏 begin_request 是业务接入 bug，不产游离事件）。"""
    state = current()
    if state is None:
        logger.warning("obs_sdk.%s 缺 request 上下文（begin_request 未包？事件不产）", what)
    return state


def begin_request(*, method: str = "GET", path: str = "/", trace_id: Optional[str] = None,
                  interface: Optional[str] = None) -> None:
    """request 入口（FastAPI 中间件调用）：建 trace 上下文 + 起算 duration。

    interface 缺省由 (method, path) 经 normalize_route 归一；业务路由已是模板（显式含 `{}`）
    时建议直接传归一 interface 覆盖启发式。v1 正文默认不采集（§2.7 逐接口评估，#8）。
    """
    st = current()
    if st is not None:
        logger.warning("obs_sdk.begin_request 嵌套 request（前一个未 end？覆盖旧上下文）")
        reset()
    interface = interface or normalize_route(method, path)
    enter(trace_id or uuid.uuid4().hex, interface, now_ms())


def end_request(status: str, *, error_type: Optional[str] = None,
                error_msg: Optional[str] = None, output: Any = None,
                duration_ms: Optional[int] = None, extra: dict[str, Any] | None = None) -> None:
    """request 出口（中间件 finally）：算 duration 产 request 事件（seq=0 锚点）。"""
    state = _require_span("end_request")
    if state is None or _state.sink is None:
        return
    if status not in _OK_STATUSES:
        logger.warning("end_request status 非法（%r），按 error 计", status)
        status = "error"
    if status == "error" and not error_type:
        logger.error("end_request status=error 但缺 error_type（埋点 bug，事件不产保真）")
        reset()
        return
    if status != "error" and error_type:
        logger.warning("end_request status=%s 却带 error_type，忽略", status)
        error_type = None
    duration = duration_ms if duration_ms is not None else max(0, now_ms() - state.start_ms)
    ctx: ProcessCtx = dict(_state.process)
    ctx.update({"trace_id": state.trace_id, "interface": state.interface})
    ev = build_request_event(ctx, ts=state.start_ms, duration_ms=duration, status=status,
                             error_type=error_type, error_msg=error_msg,
                             output=output, extra=extra)
    _state.sink.emit(EVENT_TOPIC, ev)
    reset()


def record_llm(model: str, status: str, *, duration_ms: int, error_type: Optional[str] = None,
               error_msg: Optional[str] = None, usage: dict | None = None,
               extra: dict[str, Any] | None = None) -> None:
    """llm_call 记录（每逻辑调用一条，§11.1）。duration_ms 必传（消费端 llm_call 必填）。
    裸调用「先记 error 再抛」由 agent 包装点保证（§2.4 前提）。"""
    state = _require_span("record_llm")
    if state is None or _state.sink is None:
        return
    if status not in _OK_STATUSES or not model or duration_ms is None:
        logger.error("record_llm 参数非法（model/status/duration 必填），事件不产")
        return
    if status == "error" and not error_type:
        logger.error("record_llm status=error 但缺 error_type（埋点 bug，事件不产保真）")
        return
    if status != "error" and error_type:
        error_type = None  # 非 error 禁带（三态互斥）
    if model and len(model) > MAX_MODEL:
        model = model[:MAX_MODEL]
    ctx: ProcessCtx = dict(_state.process)
    ctx.update({"trace_id": state.trace_id, "interface": state.interface})
    ev = build_llm_event(ctx, seq=state.next_seq(), parent=0, ts=now_ms(),
                         model=model, status=status, duration_ms=duration_ms,
                         usage=usage, error_type=error_type, error_msg=error_msg,
                         extra=extra)
    _state.sink.emit(EVENT_TOPIC, ev)


def record_tool(name: str, status: str, duration_ms: int, *,
                error_type: Optional[str] = None) -> None:
    """tool_call 子节点（v1 只记基本调用，§11.1）。schema tool_call 无 name 字段面——
    name 仅本地计数/日志，事件带 node/status/duration（不伪造 extra 键防整条被消费端丢）。"""
    _record_subnode("tool_call", status, duration_ms, error_type, name)


def record_db(status: str, duration_ms: int, *, error_type: Optional[str] = None) -> None:
    _record_subnode("db", status, duration_ms, error_type, "db")


def record_redis(status: str, duration_ms: int, *, error_type: Optional[str] = None) -> None:
    _record_subnode("redis", status, duration_ms, error_type, "redis")


def _record_subnode(node: str, status: str, duration_ms: int,
                    error_type: Optional[str], name: str) -> None:
    state = _require_span(f"record_{name}")
    if state is None or _state.sink is None:
        return
    if status not in _OK_STATUSES or duration_ms is None:
        logger.error("record_%s 参数非法，事件不产", name)
        return
    if status == "error" and not error_type:
        logger.error("record_%s status=error 缺 error_type，事件不产保真", name)
        return
    ctx: ProcessCtx = dict(_state.process)
    ctx.update({"trace_id": state.trace_id, "interface": state.interface})
    ev = build_tool_event(ctx, node=node, seq=state.next_seq(), parent=0, ts=now_ms(),
                          status=status, duration_ms=duration_ms, error_type=error_type)
    _state.sink.emit(EVENT_TOPIC, ev)


def log(level: str, message: str, *, extra: dict[str, Any] | None = None) -> None:
    """显式 log 行（非 logging 链路场景；logging handler/structlog processor 已覆盖主流）。"""
    state = _require_span("log")
    if state is None or _state.sink is None:
        return
    from obs_sdk._events import build_log_event
    ctx: ProcessCtx = dict(_state.process)
    ctx.update({"trace_id": state.trace_id, "interface": state.interface})
    ev = build_log_event(ctx, seq=state.next_seq(), ts=now_ms(),
                         log_level=level.upper(), log_message=message, extra=extra)
    _state.sink.emit(EVENT_TOPIC, ev)


def heartbeat() -> None:
    """显式心跳（§11.1；init(heartbeat=True) 已由后台线程 1/min 自动发，此 API 供手动/测试）。"""
    if _state.sink is None:
        return
    _state.sink.emit(HB_TOPIC, build_heartbeat(_state.process.get("agent") or "", now_ms()))


def structlog_processor(logger_: Any, method_name: str, event_dict: dict) -> dict:
    """structlog processor（sp 仓插链用；模块函数避免 import 期绑定）。"""
    return sdk_processor(logger_, method_name, event_dict)
