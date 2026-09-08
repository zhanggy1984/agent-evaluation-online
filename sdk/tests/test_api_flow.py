"""public API 端到端流（init → 埋点 → shutdown 终刷 → FakeProducer 收包断言）。

conftest 已把 KafkaProducer 打桩为 FakeProducer 且 Sink.start 置 no-op：事件停留在内存队列，
shutdown(flush) 终刷后从 FakeProducer.sent 读取真实发送序列（topic + json bytes），
逐条过消费端镜像。
"""
from __future__ import annotations

import json

import pytest
from _fakes import FakeProducer
from _schema_mirror import validate_event

import obs_sdk

TOPIC = "dev.obs.agent.good-question"
AGENT = "good-question"


@pytest.fixture()
def sdk_ready():
    obs_sdk.init(AGENT, kafka_servers="nohost:1", topic=TOPIC,
                 log_mode="structlog", heartbeat=False)
    yield
    obs_sdk.shutdown()


def _flush_sent():
    obs_sdk.shutdown()
    if not FakeProducer.instances:  # 全程无事件 → producer 从未惰性建
        return []
    producer = FakeProducer.instances[-1]
    return [(topic, json.loads(payload.decode("utf-8"))) for topic, payload in producer.sent]


# ---- init 装配护栏 ----

def test_init_requires_args():
    with pytest.raises(ValueError):
        obs_sdk.init("", kafka_servers="x:1", topic="t")
    with pytest.raises(ValueError):
        obs_sdk.init(AGENT, kafka_servers="", topic="t")


def test_init_singleton_guard(sdk_ready):
    with pytest.raises(RuntimeError):
        obs_sdk.init(AGENT, kafka_servers="x:1", topic="t")


def test_is_initialized_after_shutdown(sdk_ready):
    assert obs_sdk.is_initialized()
    obs_sdk.shutdown()
    assert not obs_sdk.is_initialized()
    assert obs_sdk._state.sink is None and obs_sdk._state.process == {}


# ---- 完整 request 埋点流（§11.1：seq 共用、request 锚点、interface 归一） ----

def test_full_request_flow(sdk_ready):
    obs_sdk.begin_request(method="POST", path="/api/chat/9f8e7d6c-5b4a-3210-9abc-8d7e6f5a4b3c")
    obs_sdk.record_llm("deepseek-chat", "ok", duration_ms=120,
                       usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    obs_sdk.log("INFO", "显式日志", extra={"task_id": "t-1", "not_allowed": 1})
    obs_sdk.record_tool("web_search", "error", duration_ms=42, error_type="HTTP_500")
    obs_sdk.end_request("ok")

    sent = _flush_sent()
    # 事件入队顺序 = llm/log/tool 先（各自 seq1/2/3），request 锚点在 end_request 时产出
    assert len(sent) == 4
    assert all(topic == TOPIC for topic, _ in sent)
    llm, log_ev, tool, request = [ev for _, ev in sent]

    for ev in sent:
        r = validate_event(ev[1])
        assert r is None, f"发送事件应过镜像: {r}\n{ev[1]}"

    trace = {ev["trace_id"] for _, ev in sent}
    assert len(trace) == 1, "同一次 request 全链共享 trace_id"
    interface = {ev["interface"] for _, ev in sent}
    assert interface == {"POST /api/chat/{id}"}  # uuid 动态段归一

    assert request["node"] == "request" and request["seq"] == 0 and request["parent"] is None
    assert llm["seq"] == 1 and log_ev["seq"] == 2 and tool["seq"] == 3  # 节点/日志共用一把计数
    assert llm["parent"] == 0 and tool["parent"] == 0   # 子节点父引用 request
    assert log_ev["parent"] is None                      # §2.2③ 日志行可游离挂接
    assert tool["node"] == "tool_call" and tool["status"] == "error"
    assert tool["error_type"] == "HTTP_500"
    assert log_ev["extra"] == {"task_id": "t-1"}  # not_allowed 被白名单过滤


def test_error_end_request_with_type(sdk_ready):
    obs_sdk.begin_request(method="GET", path="/health")
    obs_sdk.record_llm("m", "error", duration_ms=3, error_type="NetErr")
    obs_sdk.end_request("error", error_type="AppError", error_msg="boom")
    sent = _flush_sent()
    llm, request = [ev for _, ev in sent]
    assert llm["status"] == "error" and llm["error_type"] == "NetErr"
    assert request["status"] == "error" and request["error_type"] == "AppError"
    assert request["error_msg"] == "boom"


# ---- 护栏：不产游离/非法事件（宁缺保真） ----

def test_span_guards_produce_nothing(sdk_ready):
    obs_sdk.record_llm("m", "ok", duration_ms=1)          # 无 request 上下文 → 不产
    obs_sdk.end_request("ok")                              # 同上
    obs_sdk.begin_request(method="GET", path="/x")
    obs_sdk.end_request("error")                           # error 缺 error_type → 丢弃 + reset
    obs_sdk.record_llm("m", "ok", duration_ms=1)           # ctx 已 reset → 不产
    sent = _flush_sent()
    assert sent == []


def test_non_error_cannot_carry_error_type(sdk_ready):
    obs_sdk.begin_request(method="GET", path="/x")
    obs_sdk.record_llm("m", "ok", duration_ms=1, error_type="Noise")
    obs_sdk.end_request("ok", error_type="Noise")
    sent = _flush_sent()
    assert sent, "应有事件产出（error_type 被忽略而非整条丢）"
    for _, ev in sent:
        assert "error_type" not in ev or ev["error_type"] is None


# ---- interface 覆盖 / 心跳 topic ----

def test_interface_override(sdk_ready):
    obs_sdk.begin_request(interface="POST /api/chat/static")
    obs_sdk.end_request("ok")
    sent = _flush_sent()
    assert sent[0][1]["interface"] == "POST /api/chat/static"


def test_heartbeat_to_selfmonitor(sdk_ready):
    obs_sdk.begin_request(method="GET", path="/x")
    obs_sdk.end_request("ok")
    obs_sdk.heartbeat()
    sent = _flush_sent()
    hb = [ev for _, ev in sent if "agent" in ev and "ts" in ev and "node" not in ev]
    assert len(hb) == 1
    assert hb[0]["agent"] == AGENT
    hb_topic = [topic for topic, ev in sent if "node" not in ev]
    assert hb_topic == ["dev.obs.selfmonitor"]  # §3.6 env 逆推
