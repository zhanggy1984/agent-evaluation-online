"""trace 上下文（§11.1 内部）：ctxvar 承载当前 request span。

- agent/agent_version 属进程级（同一进程一个 agent，init 固化），不随请求变。
- trace_id/interface/seq/起始时刻 随请求：FastAPI async 多请求并发，用 contextvar 让
  logging Handler / record_llm 读到当前请求的 trace 状态（不同 task 各携各的）。
- seq 计数（§11.1 节点与日志行共用一把计数器）：request 锚点固定 seq=0 不占计数器，
  llm_call/tool/log 从 1 起原子自增。并发子分支（branch）v1 不暴露（§11.1 branch() 二期语义）。
"""
from __future__ import annotations

import itertools
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator, Optional

ProcessCtx = dict[str, str | None]  # {agent, agent_version}：init 固化，进程级


@dataclass
class TraceState:
    """单次 request span 的请求级状态。"""

    trace_id: str
    interface: str  # 归一后 `METHOD /path`
    start_ms: int
    _seq: Iterator[int] = field(default_factory=lambda: itertools.count(1))

    def next_seq(self) -> int:
        """节点与日志共用递增（§11.1）；request=0 不占此计数。"""
        return next(self._seq)


_cv: ContextVar[Optional[TraceState]] = ContextVar("obs_sdk_trace", default=None)


def current() -> Optional[TraceState]:
    return _cv.get()


def enter(trace_id: str, interface: str, start_ms: int) -> TraceState:
    """进入新 request span（覆盖旧值——SDK 禁止嵌套 request，nesting 是业务 bug）。"""
    state = TraceState(trace_id=trace_id, interface=interface, start_ms=start_ms)
    _cv.set(state)
    return state


def reset() -> None:
    _cv.set(None)
