"""structlog processor（§11.3 sp 列日志接入：processors 链在 JSONRenderer 前插本转发器）。

sp 用 structlog PrintLogger 不经 stdlib root → logging.Handler 收不到，需 processor 级转发。
插链位置由 sp 仓在 `setup_logging()` 内决定（detail §11.3 sp 注：JSONRenderer 前插）。

processor 契约（structlog）：
    processor(logger, method_name, event_dict) -> event_dict
本转发器不消费不修改 event_dict（原样返回给后续 JSONRenderer / 控制台），只旁路发一份 log 事件。
sp 自有 `request_id` 由 structlog contextvar 注入 event_dict → 若在白名单则透传 extra。
"""
from __future__ import annotations

from typing import Any

from obs_sdk import _state
from obs_sdk._context import current
from obs_sdk._events import EXTRA_ALLOWED, build_log_event, now_ms
from obs_sdk._sink import EVENT_TOPIC


def sdk_processor(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """structlog processor：旁路转发当前 request 上下文内日志；不修改原 event_dict。"""
    state = current()
    sink = _state.sink
    if state is None or sink is None:
        return event_dict  # 游离日志 / 未 init：只走 agent 原日志流
    try:
        ctx = dict(_state.process)
        ctx.update({"trace_id": state.trace_id, "interface": state.interface})
        level = str(event_dict.get("level", "info")).upper()
        if level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            level = "INFO"
        message = event_dict.get("event")
        extra = {k: v for k, v in event_dict.items() if k in EXTRA_ALLOWED}
        ev = build_log_event(
            ctx, seq=state.next_seq(), ts=now_ms(),
            log_level=level,
            log_message=str(message) if message is not None else "",
            extra=extra,
        )
        sink.emit(EVENT_TOPIC, ev)
    except Exception:
        pass  # 观测转发故障不影响 agent 业务日志流
    return event_dict
