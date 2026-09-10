"""analyzer classify L1/L2 判定单测（detail §2.5 值域 + §4.3/§6.1 判定规则）。

纯函数层：构造 TraceFacts/AgentContext 直测 decide / root_late_decision / effective_llm_fact /
build_judgement_json。覆盖 L1/L2 分支、OR 门控、cc 白名单关停、残 trace 子节点判定、
timeout 不带 error_type 出口、多候选归并、root-late 单事件补判、root_late_payload 落库形状。
"""
from app.analyzer.classify import (
    LLM_ERR_TYPES,
    AgentContext,
    TraceFacts,
    build_judgement_json,
    decide,
    effective_llm_fact,
    root_late_decision,
)


def _facts(root_ok=1, root_status="error", root_error_type=None, llm_fact=0,
           entries=(), interface="POST /api/chat"):
    return TraceFacts(
        root_ok=bool(root_ok),
        root_status=root_status,
        root_error_type=root_error_type,
        interface=interface,
        llm_fact_ok=bool(llm_fact),
        err_entries=tuple(entries),
    )


def _ctx(**kw):
    return AgentContext(**kw)


def _entry(error_type, count=1):
    return {"error_type": error_type, "error_msg": f"{error_type} 样例", "count": count}


# ---------- L1：root llm_* 透传 ----------


def test_root_llm_timeout_is_L1():
    d = decide(_facts(root_error_type="llm_timeout"), _ctx())
    assert d.layer == "L1"
    assert [(c.error_type, c.layer, c.evidence, c.count) for c in d.candidates] == [
        ("llm_timeout", "L1", "root", 1)
    ]
    assert d.gate["backflow_allow"] is True


def test_each_llm_err_type_is_L1():
    for et in sorted(LLM_ERR_TYPES):
        d = decide(_facts(root_error_type=et), _ctx())
        assert d.layer == "L1", et


# ---------- L2：L2 值域 + OR 门控（llm_fact ∨ interface.llm） ----------


def test_l2_via_llm_fact():
    # root=error db_error + llm_call 动态事实 → L2（OR 门 llm_fact 支）
    d = decide(_facts(root_error_type="db_error", llm_fact=1), _ctx())
    assert d.layer == "L2"


def test_l2_via_dict_llm_without_fact():
    # 无 llm_fact 但接口字典 llm=true（dict 门）→ L2
    d = decide(_facts(root_error_type="external_non_llm"), _ctx(interface_llm=True))
    assert d.layer == "L2"


def test_l2_both_gates_closed_is_none():
    # root db_error + 无 llm_fact + dict llm=false → none（门关不回流）
    d = decide(_facts(root_error_type="db_error"), _ctx(interface_llm=False))
    assert d.layer == "none" and d.candidates == []


def test_l2_dict_llm_missing_relies_on_fact():
    # interface_llm=None（interface 行缺/无 interface）且无 llm_fact → db_error 不回流
    d = decide(_facts(root_error_type="db_error"), _ctx(interface_llm=None))
    assert d.layer == "none"


# ---------- 白名单门（cc 双保险 + enable） ----------


def test_backflow_allow_off_blocks_even_L1():
    d = decide(_facts(root_error_type="llm_timeout"), _ctx(backflow_allow=False))
    assert d.layer == "none" and d.candidates == []
    assert d.gate["backflow_allow"] is False


def test_backflow_enabled_off_blocks():
    d = decide(_facts(root_error_type="llm_timeout"), _ctx(backflow_enabled=False))
    assert d.layer == "none"


def test_agent_missing_blocks():
    d = decide(_facts(root_error_type="llm_timeout"), _ctx(agent_exists=False))
    assert d.layer == "none" and d.gate["agent_exists"] is False


# ---------- 残 trace：root 未达按已有子节点判 ----------


def test_residual_subnode_llm_err_is_L1():
    # 残 trace（root_ok=0）子节点 llm_call 透传 llm_timeout → L1 evidence subnode
    d = decide(_facts(root_ok=0, entries=[_entry("llm_timeout")]), _ctx())
    assert d.layer == "L1"
    assert d.candidates[0].evidence == "subnode"


def test_residual_subnode_l2_requires_fact_or_dict():
    d = decide(
        _facts(root_ok=0, llm_fact=1, entries=[_entry("redis_error")]), _ctx()
    )
    assert d.layer == "L2"
    closed = decide(
        _facts(root_ok=0, entries=[_entry("redis_error")]), _ctx(interface_llm=False)
    )
    assert closed.layer == "none"


# ---------- 兜底吸收：request ok 时子节点错误已被业务吸收，不回流（T-3.10，§6.1） ----------


def test_ok_request_absorbed_llm_err_not_candidate():
    # 兜底吸收现场（request ok + llm_call error）→ 不产 L1/L2 候选（L3 二期，§6.1）
    d = decide(
        _facts(root_status="ok", root_error_type=None, entries=[_entry("llm_timeout")]),
        _ctx(),
    )
    assert d.layer == "none"
    assert d.candidates == []


def test_ok_request_absorbed_l2_err_not_candidate():
    # 兜底吸收不止 llm 一类：L2 值域的 DB 子错即使过 OR 门也不产候选
    d = decide(
        _facts(
            root_status="ok",
            root_error_type=None,
            llm_fact=1,
            entries=[_entry("db_error")],
        ),
        _ctx(interface_llm=True),
    )
    assert d.layer == "none"
    assert d.candidates == []


def test_timeout_root_subnode_still_candidate():
    # 防修过头：门控只切 root_status=="ok"，timeout root 的子节点候选维持既有行为
    # （§6.1 step5 与 step4 的交界歧义 = T-3.10 显式标注未决、本批不触碰）
    d = decide(
        _facts(root_status="timeout", root_error_type=None, entries=[_entry("llm_timeout")]),
        _ctx(),
    )
    assert d.layer == "L1"
    assert d.candidates[0].evidence == "subnode"


# ---------- 出口：非回流值域 / timeout 无 error_type ----------


def test_auth_error_root_not_reflow():
    d = decide(_facts(root_error_type="auth_error"), _ctx())
    assert d.layer == "none"


def test_timeout_root_without_error_type_not_candidate():
    # timeout 不带 error_type（§2.1）→ root 不产候选；无 error 子节点 → none
    d = decide(_facts(root_status="timeout", root_error_type=None), _ctx())
    assert d.layer == "none"


# ---------- 候选归并 / llm_fact 重算 ----------


def test_multi_candidates_root_l1_plus_subnode_l2():
    d = decide(
        _facts(root_error_type="llm_timeout", entries=[_entry("db_error", 2)]),
        _ctx(),
    )
    got = {(c.error_type, c.layer, c.evidence, c.count) for c in d.candidates}
    assert got == {("llm_timeout", "L1", "root", 1), ("db_error", "L2", "subnode", 2)}


def test_same_error_type_root_plus_subnode_merged():
    d = decide(
        _facts(root_error_type="llm_timeout", entries=[_entry("llm_timeout", 2)]),
        _ctx(),
    )
    assert len(d.candidates) == 1
    c = d.candidates[0]
    assert (c.layer, c.evidence, c.count) == ("L1", "root", 3)  # root1 + 子节点2


def test_effective_llm_fact_recomputes_from_entries():
    # 累积列=0 但 err_summary 含 llm_* error（非 llm_call 节点透传漏置位场景）
    f = _facts(root_error_type="db_error", entries=[_entry("llm_other")])
    assert effective_llm_fact(f) is True
    # db_error root 因此过 OR 门成 L2 候选；同时 llm_other 子节点自身即 L1 透传现场 → layer L1
    d = decide(f, _ctx())
    assert d.layer == "L1"
    assert {c.error_type for c in d.candidates} == {"db_error", "llm_other"}
    assert next(c for c in d.candidates if c.error_type == "db_error").layer == "L2"


def test_effective_llm_fact_includes_root_err_type():
    # root 自身 error_type 即 llm_* 透传 → 显式 LLM 证据（state.py 列只在 llm_call 置位，须判侧补）
    f = _facts(root_error_type="llm_timeout", entries=[_entry("db_error", 1)])
    assert effective_llm_fact(f) is True
    d = decide(f, _ctx())
    assert d.layer == "L1"
    assert next(c for c in d.candidates if c.error_type == "db_error").layer == "L2"


# ---------- judgement_json 落库形状 ----------


def test_build_judgement_json_shape():
    f = _facts(root_error_type="llm_timeout", entries=[_entry("db_error", 1)])
    d = decide(f, _ctx())
    j = build_judgement_json(f, d, now_ms=1_700_000_000_000)
    assert j["version"] == 1 and j["layer"] == "L1"
    assert j["root"] == {"ok": True, "status": "error", "error_type": "llm_timeout"}
    assert j["llm_fact_ok"] is True  # root llm_timeout 本身即 llm 证据
    assert j["gate"]["backflow_allow"] is True
    assert len(j["candidate_error_sets"]) == 2
    assert j["root_late"] is None
    assert isinstance(j["decided_at"], str)


# ---------- root-late 单事件补判（R-21） ----------


def test_root_late_llm_err_hit_L1():
    f = _facts(root_ok=1, root_error_type="llm_rate_limit", llm_fact=0)
    r = root_late_decision(f, _ctx())
    assert r.hit is True and r.layer == "L1" and r.error_type == "llm_rate_limit"


def test_root_late_l2_requires_frozen_fact_or_dict():
    f = _facts(root_ok=1, root_error_type="db_error", llm_fact=1)
    assert root_late_decision(f, _ctx()).layer == "L2"
    closed = root_late_decision(
        _facts(root_ok=1, root_error_type="db_error", llm_fact=0), _ctx(interface_llm=False)
    )
    assert closed.hit is False and closed.layer == "none"


def test_root_late_timeout_no_error_type_misses():
    r = root_late_decision(
        _facts(root_ok=1, root_status="timeout", root_error_type=None), _ctx()
    )
    assert r.hit is False and r.layer == "none"


# ---------- root_late_payload 落库形状（R-21，consumer 内联写 judgement_json.root_late） ----------


def test_root_late_payload_shape_hit():
    """命中形状逐键断言：此前只经 build_judgement_json(root_late=None) 间接覆盖。

    该 dict 由 consumer 内联写入、T-3.6 聚类按 `hit/layer/error_type` 取数——字段名漂移
    不会让任何既有用例变红，故单列直测。
    """
    from app.analyzer.classify import root_late_payload

    r = root_late_decision(_facts(root_error_type="llm_timeout"), _ctx())
    p = root_late_payload(r, "error", now_ms=1_700_000_000_000)
    assert set(p) == {"hit", "layer", "error_type", "status", "at"}
    assert p["hit"] is True and p["layer"] == "L1" and p["error_type"] == "llm_timeout"
    assert p["status"] == "error"
    assert isinstance(p["at"], str) and p["at"].startswith("2023-11-14")  # now_ms 冻结可复现


def test_root_late_payload_shape_miss_keeps_status_verbatim():
    """未命中：hit=False + layer=none + error_type=None；status 原样带出（审计留 root 态）。"""
    from app.analyzer.classify import root_late_payload

    r = root_late_decision(_facts(root_status="timeout", root_error_type=None), _ctx())
    p = root_late_payload(r, "timeout", now_ms=1_700_000_000_000)
    assert p["hit"] is False and p["layer"] == "none" and p["error_type"] is None
    assert p["status"] == "timeout"
    # 同一 now_ms 入参 → 同一时刻串（at 可复现，非 now()）
    assert p["at"] == root_late_payload(r, "timeout", now_ms=1_700_000_000_000)["at"]
