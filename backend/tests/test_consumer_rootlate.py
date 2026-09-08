"""R-21 root-late DB 壳单测（consumer.state.root_late_complement）。

merge_trace_state 的 CAS 置位纯函数部分已在 test_consumer_state.py 覆盖；本文件测
DB 壳：行 + 字典（agent/dict_config/interface）→ analyzer.root_late_decision →
写 judgement_json.root_late。FakeAsyncSession 以 registry 注入各模型 ns 行，
行为最小集（列级 select 反查 + 等值匹配），不连真库。
"""
import pytest

from app.consumer.schema import EventModel
from app.consumer.state import root_late_complement
from app.models.agent import Agent, Interface
from app.models.config import DictConfig
from app.models.error_flow import TraceJudgeState
from _fakes import FakeAsyncSession, ns

IFACE = "POST /api/chat/{id}"


def _root_event(agent="good-question", trace_id="tr-1", status="error",
                error_type="llm_timeout"):
    """迟到 root 请求事件（apply_event 已置位 root_late_complement=1 后的输入形态）。"""
    return EventModel.model_validate({
        "schema_version": "1.0", "event_kind": "event", "trace_id": trace_id,
        "agent": agent, "agent_version": "2026.08.31-r47", "interface": IFACE,
        "node": "request", "seq": 0, "parent": None, "ts": 1785897600000,
        "duration_ms": 1200, "status": status, "error_type": error_type,
        "error_msg": "late root" if status == "error" else None,
        "input": {"q": "政策?"}, "output": None, "extra": {},
    })


def _row(agent="good-question", trace_id="tr-1", *, root_status="error",
         root_error_type="llm_timeout", llm_fact=0, judged=1, complement=1,
         root_ok=1, jj=None):
    """补判已 CAS 置位后的 trace_judge_state 行（judged=1 ∧ root_late_complement=1）。"""
    return ns(
        agent=agent, trace_id=trace_id, root_ok=root_ok, interface=IFACE,
        root_status=root_status, root_error_type=root_error_type,
        llm_fact_ok=llm_fact, judged=judged, root_late_complement=complement,
        judgement_json=jj if jj is not None else {"version": 1, "layer": "L2",
                                                  "candidate_error_sets": []},
    )


def _agent_row(name="good-question", aid=1, backflow_allow=1, enable=1):
    return ns(id=aid, name=name, backflow_allow=backflow_allow, enable=enable)


def _session(*, row, agent=None, iface_llm=None, backflow_flag=None):
    """registry 组装：字典行只在需要时注入（缺行 = 回退开启 / 字典门假）。"""
    registry = {TraceJudgeState: [row]}
    if agent is not None:
        registry[Agent] = [agent]
    if iface_llm is not None:
        registry[Interface] = [
            ns(id=1, agent_id=agent.id, interface=IFACE, llm=1 if iface_llm else 0)
        ]
    if backflow_flag is not None:
        registry[DictConfig] = [
            ns(agent_id=agent.id, config_key="backflow_enabled",
               config_value=backflow_flag)
        ]
    return FakeAsyncSession(registry=registry)


class TestRootLateComplement:
    @pytest.mark.asyncio
    async def test_llm_err_root_l1_hit_writes_payload(self):
        row = _row(root_error_type="llm_timeout")
        session = _session(row=row, agent=_agent_row())
        event = _root_event(error_type="llm_timeout")
        await root_late_complement(session, event)

        rl = row.judgement_json["root_late"]
        assert rl["hit"] is True and rl["layer"] == "L1"
        assert rl["error_type"] == "llm_timeout" and rl["status"] == "error"
        assert isinstance(rl["at"], str)
        # 不推翻已判：judged/candidates 不动，root_late 只挂载新键
        assert row.judged == 1
        assert row.judgement_json["layer"] == "L2"
        assert row.judgement_json["candidate_error_sets"] == []

    @pytest.mark.asyncio
    async def test_backflow_allow_off_blocks_even_L1(self):
        row = _row(root_error_type="llm_timeout")
        session = _session(row=row, agent=_agent_row(backflow_allow=0))
        await root_late_complement(session, _root_event(error_type="llm_timeout"))
        rl = row.judgement_json["root_late"]
        assert rl["hit"] is False and rl["layer"] == "none" and rl["error_type"] is None

    @pytest.mark.asyncio
    async def test_dict_backflow_enabled_false_blocks(self):
        # per-agent dict_config backflow_enabled=false → 关停，即使 agent.backflow_allow=1
        row = _row(root_error_type="llm_timeout")
        agent = _agent_row()
        session = _session(row=row, agent=agent, backflow_flag=False)
        await root_late_complement(session, _root_event(error_type="llm_timeout"))
        assert row.judgement_json["root_late"]["hit"] is False

    @pytest.mark.asyncio
    async def test_l2_via_dict_llm_true(self):
        # 迟到 root db_error + 判定期无 llm_fact + interface 字典 llm=1 → L2 命中（OR 门 dict 支）
        row = _row(root_error_type="db_error", llm_fact=0)
        agent = _agent_row()
        session = _session(row=row, agent=agent, iface_llm=True)
        await root_late_complement(session, _root_event(error_type="db_error"))
        rl = row.judgement_json["root_late"]
        assert rl["hit"] is True and rl["layer"] == "L2" and rl["error_type"] == "db_error"

    @pytest.mark.asyncio
    async def test_l2_both_gates_closed_miss(self):
        # dict llm=false 且 llm_fact=0 → L2 值域不过 OR 门，不产补判候选
        row = _row(root_error_type="db_error", llm_fact=0)
        agent = _agent_row()
        session = _session(row=row, agent=agent, iface_llm=False)
        await root_late_complement(session, _root_event(error_type="db_error"))
        assert row.judgement_json["root_late"]["hit"] is False

    @pytest.mark.asyncio
    async def test_timeout_root_without_error_type_miss(self):
        # timeout 无 error_type（§2.1）→ 值域表无可判，hit=False（status 仍落）
        row = _row(root_status="timeout", root_error_type=None)
        session = _session(row=row, agent=_agent_row())
        await root_late_complement(session, _root_event(status="timeout", error_type=None))
        rl = row.judgement_json["root_late"]
        assert rl["hit"] is False and rl["status"] == "timeout"

    @pytest.mark.asyncio
    async def test_judgement_json_none_bootstraps(self):
        # judge_scan 异常/兼容：行 judgement_json=None 时从 {} 起建，不崩不丢既有键
        row = _row(root_error_type="llm_rate_limit", jj=None)
        session = _session(row=row, agent=_agent_row())
        await root_late_complement(session, _root_event(error_type="llm_rate_limit"))
        assert row.judgement_json["root_late"]["error_type"] == "llm_rate_limit"

    @pytest.mark.asyncio
    async def test_noop_when_not_judged_or_bit_not_set(self):
        # 幂等柱：judged=0 / 补判位=0 / 行缺失 → 早退不动 judgement_json
        row = _row(judged=0)
        session = _session(row=row, agent=_agent_row())
        await root_late_complement(session, _root_event())
        assert "root_late" not in row.judgement_json

        row2 = _row(complement=0)
        session2 = _session(row=row2, agent=_agent_row())
        await root_late_complement(session2, _root_event())
        assert "root_late" not in row2.judgement_json
