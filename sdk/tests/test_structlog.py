"""structlog processor 单测（§11.3 sp 仓接入：JSONRenderer 前插转发器）。

processor 契约：原样返回 event_dict（不改 agent 日志流），只旁路发一份 log 事件。
sp 用 structlog PrintLogger 不经 stdlib root → 必须 processor 级转发（docstring 根因）。
"""
from __future__ import annotations

from _fakes import RecordingSink
from _schema_mirror import validate_event

import obs_sdk._state as st
from obs_sdk._context import enter, reset
from obs_sdk._events import now_ms
from obs_sdk._sink import EVENT_TOPIC
from obs_sdk._structlog import sdk_processor

PROCESS = {"agent": "smart-procurement", "agent_version": "1.0.0"}


def _proc(event_dict: dict) -> dict:
    return sdk_processor(object(), "info", event_dict)


def test_processor_forwards_span_log(monkeypatch):
    sink = RecordingSink()
    monkeypatch.setattr(st, "process", dict(PROCESS))
    monkeypatch.setattr(st, "sink", sink)

    enter("t0", "POST /api/po/parse", now_ms())
    out = _proc({"event": "指令已解析", "level": "info", "request_id": "req-9"})
    reset()

    assert out == {"event": "指令已解析", "level": "info", "request_id": "req-9"}  # 原样返回
    assert len(sink.events) == 1
    domain, ev = sink.events[0]
    assert domain == EVENT_TOPIC
    assert validate_event(ev) is None
    assert ev["node"] == "log" and ev["log_level"] == "INFO"  # 小写 level 归一
    assert ev["log_message"] == "指令已解析"
    assert ev["extra"] == {"request_id": "req-9"}  # structlog contextvar 白名单透传
    assert ev["trace_id"] == "t0"


def test_processor_ignores_out_of_span(monkeypatch):
    sink = RecordingSink()
    monkeypatch.setattr(st, "process", dict(PROCESS))
    monkeypatch.setattr(st, "sink", sink)
    event_dict = {"event": "游离启动日志", "level": "warning"}
    out = _proc(event_dict)
    assert sink.events == [] and out == event_dict


def test_processor_level_mapping_and_missing_event(monkeypatch):
    sink = RecordingSink()
    monkeypatch.setattr(st, "process", dict(PROCESS))
    monkeypatch.setattr(st, "sink", sink)
    enter("t0", "GET /x", now_ms())
    _proc({"event": "警告", "level": "warning"})
    _proc({"level": "trace"})  # 枚举外 + 无 event
    reset()
    evs = [ev for _, ev in sink.events]
    assert [ev["log_level"] for ev in evs] == ["WARNING", "INFO"]  # trace 归一 INFO
    assert evs[1]["log_message"] == ""  # 无 event 键 → 空消息
