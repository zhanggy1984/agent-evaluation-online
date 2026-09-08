"""D1 校验层单测：schema/组合语义 + extra 白名单（detail §2.1/§2.2/§2.9/§4.2）。

合法样本直接取自 §2.2 三份样例（request error 透传 / llm_call error / log 行）；
反例矩阵对齐 §4.2 校验明细 + X-1 拒绝路径（缺字段/类型错/多余未知字段/整体 null）。
"""
import pytest

from app.consumer.schema import EventModel
from app.consumer.validate import DropCode, validate_event


def req(**over):
    """§2.2① request 根节点（error 透传 L1 现场），字段合法。"""
    base = {
        "schema_version": "1.0", "event_kind": "event",
        "trace_id": "tr-9f2c1a", "agent": "good-question",
        "agent_version": "2026.08.31-r47",
        "interface": "POST /api/chat/{id}", "node": "request",
        "seq": 0, "parent": None, "ts": 1785897600000, "duration_ms": 3200,
        "status": "error", "error_type": "llm_timeout", "error_msg": "provider timeout (masked)",
        "input": {"session_id": "{id}"}, "output": None,
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "model": None, "log_level": None, "log_message": None, "extra": {},
    }
    base.update(over)
    return base


def llm_call(**over):
    """§2.2② llm_call 子节点（request ok + llm_call error 兜底现场）。"""
    base = {
        "schema_version": "1.0", "event_kind": "event",
        "trace_id": "tr-9f2c1a", "agent": "good-question", "agent_version": "2026.08.31-r47",
        "interface": "POST /api/chat/{id}", "node": "llm_call",
        "seq": 1, "parent": 0, "ts": 1785897600000, "duration_ms": 3000,
        "status": "error", "error_type": "llm_interface_business",
        "error_msg": "upstream 502 (masked)",
        "input": None, "output": None,
        "usage": {"prompt_tokens": 812, "completion_tokens": 0, "total_tokens": 812},
        "model": "deepseek-v3", "log_level": None, "log_message": None, "extra": {},
    }
    base.update(over)
    return base


def log_line(**over):
    """§2.2③ 日志行（占 seq 槽位，parent 可空）。"""
    base = {
        "schema_version": "1.0", "event_kind": "log",
        "trace_id": "tr-9f2c1a", "agent": "good-question", "agent_version": "2026.08.31-r47",
        "interface": "POST /api/chat/{id}", "node": "log",
        "seq": 2, "parent": None, "ts": 1785897600500,
        "status": "ok", "error_type": None, "error_msg": None,
        "input": None, "output": None, "usage": None, "model": None,
        "log_level": "WARNING", "log_message": "retry attempt=2", "extra": {},
    }
    base.update(over)
    return base


class TestValidSamples:
    """§2.2 三份样例 + 语义容忍边界全部通过。"""

    @pytest.mark.parametrize(
        "evt",
        [req(), llm_call(), log_line(),
         # 容忍边界：timeout 不强制 error_type；log 带 quality/retrieve_hit 非 null 占位仍过；
         # 未知 error_type（业务扩展"等"，§2.5 非闭合）宽容通过
         req(status="timeout", error_type=None, error_msg=None),
         llm_call(status="timeout", error_type=None, error_msg=None),
         log_line(quality={"level": "x"}, retrieve_hit={"hit_count": 1}),
         req(status="error", error_type="weird_biz_error"),
         # 非 llm/request 节点 duration 可空（§2.1 仅 request/llm_call ✅）
         llm_call(node="retrieve", seq=1, model=None, usage=None,
                  status="error", error_type="db_error", duration_ms=None),
         ],
    )
    def test_pass(self, evt):
        event, drop = validate_event(evt)
        assert drop is None
        assert isinstance(event, EventModel)

    def test_extra_allowed_keys_pass(self):
        evt = llm_call(extra={"request_id": "x", "sub_agent": "planner", "prompt_kind": "chat"})
        assert validate_event(evt)[1] is None


class TestRejectSchema:
    """结构/类型/枚举/组合语义 → dropped.schema（DropCode.SCHEMA）。"""

    @pytest.mark.parametrize(
        "evt",
        [
            None,  # 整体 null（X-1）
            [], "not-a-dict",  # 非 dict
            req(schema_version=None), req(schema_version="2.0"),  # 缺/不认版本
            req(trace_id=None), req(trace_id=""),  # 必填缺
            req(agent=None), req(node=None), req(status=None), req(ts=None), req(seq=None),
            req(status="ok", error_type="llm_timeout"),  # ok 带 error_type（互斥）
            req(status="unknown"),  # 枚举外
            req(node="whatever"),  # node 枚举外
            req(seq=-1),  # seq 负
            req(seq=1),  # request 必须 seq=0
            req(parent=0),  # request 必须 parent=null
            req(duration_ms=None),  # request 必填 duration
            req(interface=""), req(interface="not-an-http-path"),  # interface 格式（§4.2）
            req(ts="abc"),  # 类型错
            req(trace_id="x" * 65),  # 超长
            req(extra="nope"),  # extra 非对象
            req(surprise_key=1),  # 未知顶层字段（X-1 多余字段）
            llm_call(model=None),  # llm_call 必填 model
            llm_call(usage=None),  # llm_call 必填 usage
            llm_call(duration_ms=None),  # llm_call 必填 duration
            llm_call(node="llm_call", seq=1, parent=None),  # 非根无 parent
            llm_call(parent=999, node="request"),  # 冲突（组合后 request 语义）
            log_line(log_level=None),  # log 必填 log_level
            log_line(log_message=None),  # log 必填 log_message
            log_line(node="request", seq=3),  # log 只能 node=log
            log_line(status="error"),  # log status 只允许 ok
            log_line(input={"a": 1}),  # log 禁 input（§4.2）
            log_line(log_message="x" * 8001),  # 超 8K
            llm_call(node="log"),  # event_kind=event 禁 node=log
            llm_call(log_level="INFO", log_message="x"),  # event 禁 log 字段
        ],
    )
    def test_drop_schema(self, evt):
        event, drop = validate_event(evt)
        assert event is None
        assert drop is DropCode.SCHEMA


class TestRejectExtraKey:
    """extra 白名单外键（§2.9）→ dropped.extra_key。"""

    def test_unknown_extra_key_drop(self):
        evt = llm_call(extra={"not_whitelisted": 1})
        assert validate_event(evt) == (None, DropCode.EXTRA_KEY)

    def test_extra_key_with_valid_pass(self):
        evt = llm_call(extra={"task_id": "t1"})
        assert validate_event(evt)[1] is None
