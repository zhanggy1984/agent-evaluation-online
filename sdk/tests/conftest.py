"""sdk 单测公共夹具。

铁律（why）：obs_sdk 是进程级单例（_state.process/sink），后台 flusher/heartbeat 是真 daemon
线程；dev 环境有真 Kafka broker。任一测试路径漏打桩 → 事件发进 dev.obs.agent topic 污染联调库。
故 autouse 三层防线：
1. KafkaProducer 打桩（obs_sdk._sink 模块级名字 → FakeProducer），Sink 内建 producer 恒为替身；
2. Sink.start 置 no-op —— init 后无后台线程，事件留在内存队列，由 shutdown 终刷 / 手动 flush 触发；
3. 每测试前后重置 _state + 摘下 stdlib ObsLogHandler（init 会 attach 到 root，泄漏则跨测试累积）。
"""
from __future__ import annotations

import logging

import pytest
from _fakes import FakeProducer

import obs_sdk
from obs_sdk._logging import ObsLogHandler


def _detach_stdlib_handlers() -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        if isinstance(handler, ObsLogHandler):
            root.removeHandler(handler)


@pytest.fixture(autouse=True)
def _sdk_env(monkeypatch):
    obs_sdk.shutdown()
    _detach_stdlib_handlers()
    FakeProducer.instances.clear()
    monkeypatch.setattr("obs_sdk._sink.KafkaProducer", FakeProducer)
    monkeypatch.setattr("obs_sdk._sink.Sink.start", lambda self: None)  # init 不启后台线程
    yield
    obs_sdk.shutdown()
    _detach_stdlib_handlers()
