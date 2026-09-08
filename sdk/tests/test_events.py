"""事件构造层单测：build_* 产物必须过消费端契约镜像 + 边界归一/截断语义。"""
from __future__ import annotations

import logging

from _schema_mirror import validate_event

from obs_sdk._context import TraceState, current, enter, reset
from obs_sdk._events import (
    EXTRA_ALLOWED,
    _filter_extra,
    _trunc_extra,
    build_heartbeat,
    build_llm_event,
    build_log_event,
    build_request_event,
    build_tool_event,
    levelno_to_log_level,
    normalize_route,
    now_ms,
)

CTX = {"agent": "good-question", "agent_version": "0.1.0",
       "trace_id": "t" * 32, "interface": "POST /api/chat/{id}"}


def _assert_pass(ev: dict) -> dict:
    reason = validate_event(ev)
    assert reason is None, f"事件应过消费端镜像校验: {reason}\n{ev}"
    return ev


# ---- build_request_event（seq=0/parent=null/duration 必填，§2.4） ----

def test_request_ok_shape():
    ev = _assert_pass(build_request_event(CTX, ts=1, duration_ms=88, status="ok"))
    assert ev["node"] == "request" and ev["event_kind"] == "event"
    assert ev["seq"] == 0 and ev["parent"] is None
    assert ev["duration_ms"] == 88 and ev["status"] == "ok"
    assert "output" not in ev  # 正文默认不采（§2.7）


def test_request_error_carries_type_and_msg():
    ev = _assert_pass(build_request_event(CTX, ts=1, duration_ms=5, status="error",
                                          error_type="Timeout", error_msg="上游超时"))
    assert ev["error_type"] == "Timeout" and ev["error_msg"] == "上游超时"


def test_request_output_lazy():
    assert "output" not in build_request_event(CTX, ts=1, duration_ms=1, status="ok")
    ev = _assert_pass(build_request_event(CTX, ts=1, duration_ms=1, status="ok",
                                          output={"answer": "x"}))
    assert ev["output"] == {"answer": "x"}


# ---- build_llm_event（必 duration/usage/model，§2.1） ----

def test_llm_ok_with_usage():
    usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    ev = _assert_pass(build_llm_event(CTX, seq=1, parent=0, ts=2, model="deepseek-chat",
                                      status="ok", duration_ms=120, usage=usage))
    assert ev["seq"] == 1 and ev["parent"] == 0
    assert ev["usage"] == usage and ev["model"] == "deepseek-chat"


def test_llm_usage_defaults_zero():
    ev = _assert_pass(build_llm_event(CTX, seq=1, parent=0, ts=2, model="m",
                                      status="error", duration_ms=3, usage=None,
                                      error_type="NetError"))
    assert ev["usage"] == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


# ---- build_tool_event（无 name 载体 → 不产伪造 extra，§11.1 v1） ----

def test_tool_event_no_name_forgery():
    ev = _assert_pass(build_tool_event(CTX, node="tool_call", seq=2, parent=0, ts=3,
                                       status="ok", duration_ms=42))
    assert ev["extra"] == {}  # schema 无 name 面，不得伪造 request_id 塞 tool 名


def test_db_error_event():
    ev = _assert_pass(build_tool_event(CTX, node="db", seq=2, parent=0, ts=3,
                                       status="error", duration_ms=7, error_type="ConnError"))
    assert ev["error_type"] == "ConnError"


# ---- build_log_event（字段面最窄，§4.2） ----

def test_log_event_minimal():
    ev = _assert_pass(build_log_event(CTX, seq=1, ts=4, log_level="WARNING",
                                      log_message="缓存未命中"))
    assert ev["node"] == "log" and ev["event_kind"] == "log" and ev["status"] == "ok"
    assert ev["parent"] is None
    for key in ("duration_ms", "input", "output", "usage", "model",
                "error_type", "error_msg"):
        assert key not in ev, f"log 行禁止带 {key}"


def test_log_message_truncated_to_8k():
    ev = build_log_event(CTX, seq=1, ts=4, log_level="INFO", log_message="x" * 9000)
    assert len(ev["log_message"]) == 8000
    assert validate_event(ev) is None


def test_log_level_invalid_normalizes():
    ev = build_log_event(CTX, seq=1, ts=4, log_level="TRACE", log_message="m")
    assert ev["log_level"] == "INFO"
    assert validate_event(ev) is None


# ---- extra 白名单（§2.9：越界键丢键不丢条，值超长截断） ----

def test_extra_whitelist_filter():
    out = _filter_extra({"request_id": "r1", "task_id": "t2", "hack": 1})
    assert out == {"request_id": "r1", "task_id": "t2"}
    assert _filter_extra(None) == {}


def test_extra_long_value_truncated():
    out = _trunc_extra({"request_id": "r" * 600, "conv_id": "c"})
    assert len(out["request_id"]) == 512 and out["conv_id"] == "c"
    assert set(out) == {"request_id", "conv_id"}


def test_extra_allowed_set_matches_contract():
    assert EXTRA_ALLOWED == frozenset(
        {"request_id", "task_id", "job_id", "conv_id", "sub_agent", "prompt_kind"})


# ---- normalize_route（§11.1：动态段 → {id}） ----

def test_normalize_route_preserves_static():
    assert normalize_route("GET", "/health") == "GET /health"
    assert normalize_route("post", "/api/v1/users/list") == "POST /api/v1/users/list"


def test_normalize_route_dynamic_to_id():
    assert normalize_route("GET", "/api/chat/12345") == "GET /api/chat/{id}"
    uuid_path = "9f8e7d6c-5b4a-3210-9abc-8d7e6f5a4b3c"
    assert normalize_route("GET", f"/api/users/{uuid_path}") == "GET /api/users/{id}"
    assert normalize_route("GET", "/api/sessions/" + "a" * 24) == "GET /api/sessions/{id}"


def test_normalize_route_keeps_template_braces():
    assert normalize_route("GET", "/api/chat/{session_id}") == "GET /api/chat/{session_id}"


def test_normalize_route_guard():
    assert normalize_route("", "") == "METHOD /path"


# ---- 截断（§2.1 上限是消费端丢弃阈值，SDK 先截断保通过） ----

def test_long_fields_truncated():
    ctx = dict(CTX, trace_id="t" * 100, interface="GET /" + "x" * 300)
    ev = build_request_event(ctx, ts=1, duration_ms=1, status="ok")
    assert len(ev["trace_id"]) == 64 and len(ev["interface"]) == 256
    assert validate_event(ev) is None


def test_levelno_mapping():
    assert levelno_to_log_level(logging.INFO) == "INFO"
    assert levelno_to_log_level(logging.CRITICAL) == "ERROR"  # 枚举外归一
    assert levelno_to_log_level(999) == "INFO"


def test_heartbeat_shape():
    assert build_heartbeat("good-question", 123) == {"agent": "good-question", "ts": 123}


# ---- TraceState seq（§11.1：request=0 不占计数，节点/日志共用递增） ----

def test_trace_state_seq_increment():
    state = TraceState(trace_id="t", interface="GET /", start_ms=now_ms())
    assert state.next_seq() == 1
    assert state.next_seq() == 2
    assert state.next_seq() == 3


def test_enter_reset_context():
    enter("t0", "GET /x", 1)
    assert current() is not None and current().trace_id == "t0"
    reset()
    assert current() is None


# ---- 镜像自检：校验器本身能抓负面（防恒真） ----

def test_mirror_rejects_bad_events():
    assert validate_event({"node": "request"}) is not None
    req = build_request_event(CTX, ts=1, duration_ms=1, status="ok")
    req["seq"] = 5  # request 必须 seq=0
    assert validate_event(req) is not None
    log = build_log_event(CTX, seq=1, ts=1, log_level="INFO", log_message="m")
    log["duration_ms"] = 1  # log 行禁止带 duration
    assert validate_event(log) is not None
    zero = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    llm = build_llm_event(CTX, seq=1, parent=0, ts=1, model="m", status="ok",
                          duration_ms=1, usage=zero)
    llm["usage"] = None  # llm_call 必填 usage
    assert validate_event(llm) is not None
    bad = build_request_event(CTX, ts=1, duration_ms=1, status="ok")
    bad["hacker_field"] = 1  # 未知顶层字段
    assert validate_event(bad) is not None
