"""stdlib logging.Handler（§11.1 默认日志接入；gq/cs/cc 用）。

emit 规则（why）：
- 只转发**request 上下文内**的日志行——无 trace_id 的游离日志不发观测（consumer schema log 行
  顶层 trace_id 必填，游离日志无归属 trace，发了也过不了校验）。游离日志仍走 agent 自身业务流。
- seq 从请求级计数器取（§11.1 节点与日志行共用一把计数），保证事件顺序可还原。
- 只带 log_level/log_message + extra 白名单；不把 record 的 exc_info 等节点字段误带进 log 行
  （log 行字段面最窄，带错整条被消费端丢，_events.build_log_event 已护栏）。
"""
from __future__ import annotations

import logging

from obs_sdk import _state
from obs_sdk._context import current
from obs_sdk._events import build_log_event, levelno_to_log_level, now_ms
from obs_sdk._sink import EVENT_TOPIC


class ObsLogHandler(logging.Handler):
    """转发 request 上下文内日志为 log 事件（attach 到业务 root logger 后自动生效）。"""

    def emit(self, record: logging.LogRecord) -> None:
        state = current()
        sink = _state.sink
        if state is None or sink is None:
            return  # 游离日志 / SDK 未 init：不上报（docstring）
        try:
            ctx = dict(_state.process)
            ctx.update({"trace_id": state.trace_id, "interface": state.interface})
            ev = build_log_event(
                ctx, seq=state.next_seq(), ts=now_ms(),
                log_level=levelno_to_log_level(record.levelno),
                log_message=record.getMessage(),
            )
            sink.emit(EVENT_TOPIC, ev)
        except Exception:
            self.handleError(record)  # 上报故障只影响观测，不炸业务日志链


def attach_stdlib_handler() -> logging.Handler:
    """attach root logger 并返回（agent 可在 init 后显式挂到自己的 logger）。"""
    handler = ObsLogHandler()
    handler.setLevel(logging.INFO)  # DEBUG 行不上报（消费端 LogLevel 枚举有 DEBUG，但量级控制）
    logging.getLogger().addHandler(handler)
    return handler
