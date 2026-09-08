"""stdlib logging.Handler 单测（§11.1 默认日志接入）。

规则：只转发 request 上下文内日志行（无 trace 归属的游离日志不上报，docstring）；字段面最窄。
"""
from __future__ import annotations

import logging

from _fakes import RecordingSink
from _schema_mirror import validate_event

import obs_sdk
import obs_sdk._state as st
from obs_sdk._context import enter, reset
from obs_sdk._events import now_ms
from obs_sdk._logging import ObsLogHandler
from obs_sdk._sink import EVENT_TOPIC

PROCESS = {"agent": "good-question", "agent_version": "0.2.0"}


def _record(levelno: int = logging.INFO, msg: str = "m") -> logging.LogRecord:
    return logging.LogRecord("obs_sdk.test", levelno, __file__, 1, msg, None, None)


def test_handler_forwards_only_inside_request(monkeypatch):
    sink = RecordingSink()
    monkeypatch.setattr(st, "process", dict(PROCESS))
    monkeypatch.setattr(st, "sink", sink)
    handler = ObsLogHandler()

    handler.emit(_record(logging.INFO, "游离日志"))
    assert sink.events == [], "无 request 上下文（无 trace_id）的日志不上报"

    enter("t0", "GET /health", now_ms())
    handler.emit(_record(logging.WARNING, "缓存未命中"))
    reset()
    assert len(sink.events) == 1
    domain, ev = sink.events[0]
    assert domain == EVENT_TOPIC
    assert validate_event(ev) is None
    assert ev["node"] == "log" and ev["log_level"] == "WARNING"
    assert ev["log_message"] == "缓存未命中"
    assert ev["trace_id"] == "t0" and ev["agent"] == "good-question"
    assert "duration_ms" not in ev and "usage" not in ev  # 字段面最窄


def test_handler_seq_shared_with_nodes(monkeypatch):
    """节点与日志行共用一把 seq 计数器（§11.1）——经真实 emit 顺序验证。"""
    sink = RecordingSink()
    monkeypatch.setattr(st, "process", dict(PROCESS))
    monkeypatch.setattr(st, "sink", sink)
    handler = ObsLogHandler()
    enter("t0", "GET /x", now_ms())
    # 模拟 record_llm 落一条节点（seq=1）
    obs_sdk.record_llm("m", "ok", duration_ms=5)
    handler.emit(_record(logging.INFO, "第二行"))
    reset()
    node_ev = [ev for _, ev in sink.events if ev["node"] != "log"]
    log_ev = [ev for _, ev in sink.events if ev["node"] == "log"]
    assert node_ev[0]["seq"] == 1 and log_ev[0]["seq"] == 2


def test_critical_normalizes_to_error(monkeypatch):
    sink = RecordingSink()
    monkeypatch.setattr(st, "process", dict(PROCESS))
    monkeypatch.setattr(st, "sink", sink)
    enter("t0", "GET /x", now_ms())
    ObsLogHandler().emit(_record(logging.CRITICAL, "崩"))
    reset()
    assert sink.events[0][1]["log_level"] == "ERROR"  # 枚举外归一（消费端 LogLevel 无 CRITICAL）


def test_init_stdlib_attaches_handler_to_root():
    """init(log_mode=stdlib) 自动挂 root；ctx 内业务日志自动成事件（经真实队列）。

    KafkaProducer/Sink.start 已由 conftest autouse 打桩（事件不真发，只断言入队）。
    SDK 前提（§11.1）：agent 自身日志体系已装配（root INFO 级）；这里模拟真实装配。
    """
    root = logging.getLogger()
    prev = root.level
    root.setLevel(logging.INFO)  # 默认 WARNING 会拦 info → 到不了 handler
    obs_sdk.init("good-question", kafka_servers="nohost:1", topic="dev.obs.agent.good-question",
                 heartbeat=False)
    try:
        root_has_handler = any(isinstance(h, ObsLogHandler) for h in root.handlers)
        assert root_has_handler, "stdlib 模式 init 应自动挂 ObsLogHandler 到 root"
        sink = obs_sdk._state.sink
        assert sink is not None
        enter("t0", "GET /x", now_ms())
        logging.getLogger("obs_sdk.test_biz").info("业务日志")
        reset()
        assert sink._queue.qsize() == 1, "ctx 内业务日志应成 1 条 log 事件"
        ev = sink._queue.get_nowait()[1]
        assert validate_event(ev) is None and ev["node"] == "log"
    finally:
        obs_sdk.shutdown()
        root.setLevel(prev)


def test_init_stdlib_extra_loggers_attaches_to_named_logger():
    """init(extra_loggers=[...]) 把同一 handler 挂到 propagate=False 命名 logger（v0.1.1，§11.3 cs）。

    场景：agent 自有 logger（如 cs "cs"）propagate=False → root handler 收不到该 logger 日志；
    extra_loggers 点名后其 ctx 内业务日志才成 log 事件。验证挂在命名 logger 上且 root 也有。
    """
    root = logging.getLogger()
    prev = root.level
    root.setLevel(logging.INFO)
    named = logging.getLogger("cs")          # 模拟 cs：logger 名即 agent 业务 logger
    named.propagate = False                   # root 收不到，须 extra_loggers 点名
    obs_sdk.init("customer-service", kafka_servers="nohost:1",
                 topic="dev.obs.agent.customer-service", heartbeat=False,
                 extra_loggers=["cs"])
    try:
        cs_has_handler = any(isinstance(h, ObsLogHandler) for h in named.handlers)
        root_has_handler = any(isinstance(h, ObsLogHandler) for h in root.handlers)
        assert cs_has_handler, "extra_loggers 应把 ObsLogHandler 挂到点名 logger 上"
        assert root_has_handler, "root 默认挂接不受 extra_loggers 影响"
        sink = obs_sdk._state.sink
        enter("t0", "GET /x", now_ms())
        named.info("cs 业务日志")
        reset()
        assert sink._queue.qsize() == 1, "propagate=False 命名 logger 的 ctx 内日志应成事件"
        ev = sink._queue.get_nowait()[1]
        assert validate_event(ev) is None and ev["node"] == "log"
        assert ev["agent"] == "customer-service"
    finally:
        obs_sdk.shutdown()
        named.propagate = True
        root.setLevel(prev)
