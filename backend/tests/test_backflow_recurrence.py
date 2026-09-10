"""P2-6 backflow 后端最小增量单测（detail v1.19，T-3.7 / B1-B4）。

- recurrence_rows_py：blocked/claim 同键复发纯函数核全分支——mode=fixed 只计门控不过
  （reentry_gate_allows False）的 judged 行、mode=claim 全计；agent/root_input_hash/
  interface/error_type 同键；anchor 边界（ts==anchor 计）；latest_version 字典序 max；
  fix_version 空 → 不展示；judged=0 / 键不符 / error_type 未命中 一律跳过。
- cluster_reentry_observe：status∈{claim,fixed} 才现算，其余 None；fixed 无 fix_version
  / 无 fixed 锚 → None；锚 = conversion_record auto_fixed/fixed_review max ts（claim =
  claimed_at）——stub session 按目标实体回查行（列级 select 与整实体都走
  column_descriptions entity 判别）。
- API 层：_cluster_item 带 first_trace_id；_open_batches 用 JSON_CONTAINS(link_refs,
  cluster_id 字面量) 且 item 形状钉死；detail 端点（HTTP 正例）响应含 reentry_observe
  （claim 态现算值 / open 态 None）+ open_batches。
- claim R-5 版本预检（_claim_warning）：offline 未配 → None；fix_version 未见于已见版本
  → 「已见版本：…」提示；已见且 generation≤1 → None；generation>1 命中 completed run →
  reentry 提示；读面抛 OfflineReadError → None（best-effort）。
"""
import asyncio
from datetime import datetime, timedelta, timezone

from _fakes import FakeAsyncSession, ns

import app.api.backflow as backflow_api
from app.api.backflow import _claim_warning, _cluster_item, _open_batches
from app.backflow.recurrence import (
    _fixed_anchor,
    cluster_reentry_observe,
    recurrence_rows_py,
)
from app.core.config import Settings
from app.core.db import get_session
from app.core.offline_client import OfflineReadError
from app.core.security import create_access_token
from app.main import create_app
from app.models.error_flow import (
    ConversionRecord,
    ErrorCaseLink,
    ErrorCluster,
    NeedsReviewBatch,
    TraceJudgeState,
    VerifyRunRecord,
)

_MOCK_SECRET = "s3cret-evaluator"


def _settings(offline_base_url=""):
    return Settings(
        app_env="test", resource_env="dev",
        jwt_secret="mock-secret-" * 8,
        evaluator_service_secret=_MOCK_SECRET,
        offline_base_url=offline_base_url,
    )


def _admin_user(role="viewer"):
    return ns(id=1, username="u1", display_name="用户", password_hash="x",
              role=role, status=1)


def _token():
    return {"Authorization": f"Bearer {create_access_token(_settings(), 1, 'viewer')}"}


def _run(coro):
    return asyncio.run(coro)


def _dt(**kw):
    return datetime(**kw)


def _judgement(*error_types):
    return {"candidate_error_sets": [
        {"error_type": t} for t in error_types]}


def _judged_row(ts, *, agent="agent-x", interface="agent-x.iface", ihash="hash-1",
                error_type="timeout", version=None, judged=1):
    """recurrence_rows_py 输入 dict（等价 _row_dict 产物）。"""
    return {
        "ts": ts, "agent": agent, "interface": interface,
        "root_input_hash": ihash, "judged": judged,
        "judgement_json": _judgement(error_type),
        "version": version,
    }

# ---------- recurrence_rows_py：fixed 门控不过才计（矩阵对齐 reentry_gate_allows） ----------

_FIX = _dt(year=2026, month=1, day=5, hour=8)


def _fixed(rows, *, anchor=_FIX, fix="2026.01.05.build1", **kw):
    return recurrence_rows_py(
        rows, cluster_agent="agent-x", cluster_interface="agent-x.iface",
        cluster_error_type="timeout", cluster_input_hash="hash-1",
        anchor_ts=anchor, mode="fixed", fix_version=fix, **kw)


def test_fixed_counts_same_day_unequal_version():
    # 同日不等值（r100<r47 类乱序防误放行）→ 门控不过 → 计
    r = _fixed([_judged_row(_FIX, version="2026.01.05.build2")])
    assert r == {"count": 1, "latest_version": "2026.01.05.build2"}


def test_fixed_counts_cross_day_older_than_fix():
    r = _fixed([_judged_row(_FIX, version="2026.01.04.build1")])
    assert r["count"] == 1


def test_fixed_skips_cross_day_newer_version():
    # 新日期（跨日新版本）→ 门控放行 → 不入本簇 blocked 计数
    r = _fixed([_judged_row(_FIX, version="2026.01.06.build1")])
    assert r == {"count": 0, "latest_version": None}


def test_fixed_skips_exact_equal_version():
    r = _fixed([_judged_row(_FIX, version="2026.01.05.build1")])
    assert r == {"count": 0, "latest_version": None}


def test_fixed_non_date_literal_unequal_counts():
    # 非 YYYY.MM.DD 形态 → 不透明字面量等值比较；不等 → 门控不过 → 计
    r = _fixed([_judged_row(_FIX, version="1.5.0")], fix="1.4.0")
    assert r == {"count": 1, "latest_version": "1.5.0"}


def test_fixed_version_none_row_counts():
    # 无版本证据（gate 恒 False）→ 计；latest 不收录 None
    rows = [_judged_row(_FIX, version=None), _judged_row(_FIX, version="1.5.0")]
    r = _fixed(rows, fix="1.4.0")   # "1.5.0" 非日期形态且不等值 → 门控不过也计
    assert r == {"count": 2, "latest_version": "1.5.0"}


def test_fixed_mixed_matrix():
    # 门控放行者（同值/跨日新版本）不计，门控不过者（同日不等值/跨日早）计
    rows = [
        _judged_row(_FIX, version="2026.01.05.build1"),   # 同值 → 不计
        _judged_row(_FIX, version="2026.01.06.build1"),   # 跨日新 → 不计
        _judged_row(_FIX, version="2026.01.05.build3"),   # 同日不等值 → 计
        _judged_row(_FIX, version="2026.01.04.build9"),   # 跨日早 → 计
    ]
    r = _fixed(rows)
    assert r["count"] == 2
    assert r["latest_version"] == "2026.01.05.build3"  # 字典序 max（build3 > 01.04.build9）


def test_fixed_fix_version_empty_never_counts():
    # 无门控基础 → 一律跳过（后续同值判断根本不发生）
    rows = [_judged_row(_FIX, version="1.5.0")]
    assert recurrence_rows_py(
        rows, cluster_agent="agent-x", cluster_interface="agent-x.iface",
        cluster_error_type="timeout", cluster_input_hash="hash-1",
        anchor_ts=_FIX, mode="fixed", fix_version=None) == \
        {"count": 0, "latest_version": None}


# ---------- recurrence_rows_py：claim 全计 + 锚边界 + 键过滤 ----------


def test_claim_counts_all_after_anchor_including_unknown_version():
    anchor = _FIX
    rows = [
        _judged_row(anchor + timedelta(hours=1), version="1.1.0"),
        _judged_row(anchor + timedelta(hours=2), version="1.3.0"),
        _judged_row(anchor + timedelta(hours=3), version=None),  # 无法判门控 → 仍在观察
    ]
    r = recurrence_rows_py(
        rows, cluster_agent="agent-x", cluster_interface="agent-x.iface",
        cluster_error_type="timeout", cluster_input_hash="hash-1",
        anchor_ts=anchor, mode="claim")
    assert r == {"count": 3, "latest_version": "1.3.0"}


def test_anchor_boundary_inclusive_and_before_excluded():
    rows = [
        _judged_row(_FIX - timedelta(seconds=1), version="0.9.0"),  # 锚前 → 不计
        _judged_row(_FIX, version="1.0.0"),                          # ts==锚 → 计
        _judged_row(_FIX + timedelta(hours=1), version="2.0.0"),
    ]
    r = recurrence_rows_py(
        rows, cluster_agent="agent-x", cluster_interface="agent-x.iface",
        cluster_error_type="timeout", cluster_input_hash="hash-1",
        anchor_ts=_FIX, mode="claim")
    assert r["count"] == 2 and r["latest_version"] == "2.0.0"


def test_claim_skips_judged_zero_and_key_mismatch():
    rows = [
        _judged_row(_FIX, judged=0),                              # judged=0 → 不计
        _judged_row(_FIX, agent="other-agent"),                   # agent 不符
        _judged_row(_FIX, ihash="other-hash"),                    # root_input_hash 不符
        _judged_row(_FIX, interface="other.iface"),               # interface 不符
    ]
    r = recurrence_rows_py(
        rows, cluster_agent="agent-x", cluster_interface="agent-x.iface",
        cluster_error_type="timeout", cluster_input_hash="hash-1",
        anchor_ts=_FIX, mode="claim")
    assert r == {"count": 0, "latest_version": None}


def test_claim_interface_blank_matches_any_interface():
    # cluster.interface 为空 → interface 不做等值过滤
    rows = [_judged_row(_FIX, interface="anything.iface", version="1.0.0")]
    r = recurrence_rows_py(
        rows, cluster_agent="agent-x", cluster_interface="",
        cluster_error_type="timeout", cluster_input_hash="hash-1",
        anchor_ts=_FIX, mode="claim")
    assert r["count"] == 1


def test_error_type_must_hit_candidate_set():
    rows = [
        _judged_row(_FIX, error_type="assertion_shape", version="1.0.0"),
        _judged_row(_FIX, version="1.0.0"),                       # 命中 timeout
    ]
    r = recurrence_rows_py(
        rows, cluster_agent="agent-x", cluster_interface="agent-x.iface",
        cluster_error_type="timeout", cluster_input_hash="hash-1",
        anchor_ts=_FIX, mode="claim")
    assert r["count"] == 1


def test_dirty_judgement_json_tolerated():
    # judgement_json 脏（None / candidate_error_sets 非容器）→ 空集合 → 不命中不计
    rows = [_judged_row(_FIX, version="1.0.0"), _judged_row(_FIX, version="1.0.0")]
    rows[0]["judgement_json"] = None
    rows[1]["judgement_json"] = {"candidate_error_sets": "bad"}
    r = recurrence_rows_py(
        rows, cluster_agent="agent-x", cluster_interface="agent-x.iface",
        cluster_error_type="timeout", cluster_input_hash="hash-1",
        anchor_ts=_FIX, mode="claim")
    assert r == {"count": 0, "latest_version": None}


def test_anchor_none_skips_all():
    rows = [_judged_row(_FIX, version="1.0.0")]
    r = recurrence_rows_py(
        rows, cluster_agent="agent-x", cluster_interface="agent-x.iface",
        cluster_error_type="timeout", cluster_input_hash="hash-1",
        anchor_ts=None, mode="claim")
    assert r == {"count": 0, "latest_version": None}


# ---------- cluster_reentry_observe：status/锚/门控路由（stub session） ----------


class _ScalarRows:
    def __init__(self, items):
        self.items = list(items)

    def all(self):
        return self.items


class _ObserveSession:
    """scalars 按目标实体回查（列级 select 与整实体都经 column_descriptions entity）。"""

    def __init__(self, by_entity):
        self._by = by_entity

    async def scalars(self, stmt, params=None):
        ent = None
        if stmt is not None:
            ent = stmt.column_descriptions[0].get("entity")
        return _ScalarRows(self._by.get(ent, []))


def _raw_judged(ts, *, agent="agent-x", interface="agent-x.iface", ihash="hash-1",
                error_type="timeout", version="1.5.0", judged=1):
    return ns(root_ts=ts, updated_ts=ts, agent=agent, interface=interface,
              root_input_hash=ihash, judged=judged,
              judgement_json=_judgement(error_type),
              err_summary_json={"agent_version": version} if version else {})


def _observe_cluster(**over):
    base = dict(id=10, agent="agent-x", interface="agent-x.iface", status="claim",
                error_type="timeout", input_hash="hash-1", fix_version="1.4.0",
                claimed_at=_FIX, claimed_by="u1", claim_k=2)
    base.update(over)
    return ns(**base)


def test_observe_non_relevant_status_none():
    for st in ("open", "needs_review", "inactive"):
        cl = _observe_cluster(status=st)
        assert _run(cluster_reentry_observe(_ObserveSession({}), cl)) is None


def test_observe_fixed_without_fix_version_none():
    cl = _observe_cluster(status="fixed", fix_version="")
    assert _run(cluster_reentry_observe(_ObserveSession({}), cl)) is None


def test_observe_fixed_without_anchor_none():
    # 无 auto_fixed/fixed_review conv → 锚 None → 不展示
    cl = _observe_cluster(status="fixed", fix_version="1.4.0")
    sess = _ObserveSession({ConversionRecord: [], TraceJudgeState: []})
    assert _run(cluster_reentry_observe(sess, cl)) is None


def test_observe_fixed_anchor_from_fixed_conversion_and_gate():
    conv_ts = _dt(year=2026, month=1, day=5, hour=8)
    cl = _observe_cluster(status="fixed", fix_version="2026.01.05.build1")
    rows = [
        ns(root_ts=conv_ts + timedelta(hours=1), updated_ts=None,
           agent="agent-x", interface="agent-x.iface", root_input_hash="hash-1",
           judged=1, judgement_json=_judgement("timeout"),
           err_summary_json={"agent_version": "2026.01.05.build2"}),  # 同日不等值 → 计
        ns(root_ts=conv_ts + timedelta(hours=2), updated_ts=None,
           agent="agent-x", interface="agent-x.iface", root_input_hash="hash-1",
           judged=1, judgement_json=_judgement("timeout"),
           err_summary_json={"agent_version": "2026.01.06.build1"}),  # 跨日新 → 不计
    ]
    sess = _ObserveSession({ConversionRecord: [conv_ts], TraceJudgeState: rows})
    out = _run(cluster_reentry_observe(sess, cl))
    assert out["mode"] == "fixed" and out["count"] == 1
    assert out["latest_version"] == "2026.01.05.build2"
    assert out["since_ts"] == conv_ts


def test_observe_fixed_prefers_latest_conversion_ts():
    conv_ts = _dt(year=2026, month=1, day=5, hour=8)
    cl = _observe_cluster(status="fixed", fix_version="2026.01.05.build1")
    rows = [ns(root_ts=conv_ts, updated_ts=None, agent="agent-x",
               interface="agent-x.iface", root_input_hash="hash-1", judged=1,
               judgement_json=_judgement("timeout"),
               err_summary_json={"agent_version": "2026.01.05.build2"})]
    sess = _ObserveSession({ConversionRecord: [conv_ts, conv_ts + timedelta(hours=3)],
                            TraceJudgeState: rows})
    out = _run(cluster_reentry_observe(sess, cl))
    # 锚取 max ts（conv_ts+3h）→ 行在锚前 → 不计
    assert out["count"] == 0 and out["since_ts"] == conv_ts + timedelta(hours=3)


def test_observe_claim_counts_after_claimed_at():
    anchor = _dt(year=2026, month=1, day=1, hour=0)
    cl = _observe_cluster(status="claim", claimed_at=anchor, fix_version="1.4.0")
    rows = [
        _raw_judged(anchor - timedelta(days=1), version="old"),   # 锚前不计
        _raw_judged(anchor + timedelta(hours=1), version="1.2.0"),
        _raw_judged(anchor + timedelta(hours=2), version="1.3.0"),
    ]
    sess = _ObserveSession({TraceJudgeState: rows})
    out = _run(cluster_reentry_observe(sess, cl))
    assert out["mode"] == "claim" and out["count"] == 2
    assert out["latest_version"] == "1.3.0" and out["since_ts"] == anchor


def test_fixed_anchor_picks_max_of_fixed_actions():
    # 只认 auto_fixed/fixed_review；其余 action（claim/needs_review_resolve）不算锚
    anchor = _dt(year=2026, month=1, day=5, hour=8)
    sess = _ObserveSession({ConversionRecord: [anchor, anchor + timedelta(hours=2)]})
    assert _run(_fixed_anchor(sess, 10)) == anchor + timedelta(hours=2)


# ---------- API 层：_cluster_item / _open_batches ----------


def test_cluster_item_carries_first_trace_id():
    cl = ns(id=1, agent="agent-x", interface="agent-x.iface", layer="L1",
            error_type="timeout", error_msg="m", input_hash="hash-1",
            first_trace_id="tr-trace-9", input_truncated=0, generation=1,
            count=3, status="open", first_ts=_FIX, latest_ts=_FIX,
            fix_version=None, claimed_by=None, claimed_at=None,
            claim_due_ts=None, claim_k=2, needs_review_reason=None)
    item = _cluster_item(cl, link=None)
    assert item["cluster_id"] == 1
    assert item["first_trace_id"] == "tr-trace-9"   # P2-6 列表「代表 trace」跳转源


def test_open_batches_json_contains_and_item_shape():
    captured = {}
    rows = [ns(id=7, run_id="run-9", agent="agent-x", bound_version="1.4.0",
               error_type="unclean", link_refs=[{"link_id": 30, "cluster_id": 10,
                                                 "case_id": "c1"}])]

    class _S:
        async def scalars(self, stmt, params=None):
            captured["sql"] = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            return _ScalarRows(rows)

    out = _run(_open_batches(_S(), cluster_id=10))
    # SQL 侧 JSON_CONTAINS(link_refs, {"cluster_id": <numeric 字面量>}) 钉字段（非 orm 反查）
    assert "json_contains" in captured["sql"]
    assert '"cluster_id": 10' in captured["sql"]
    assert "status" in captured["sql"] and "open" in captured["sql"]
    assert len(out) == 1
    assert set(out[0]) == {"batch_id", "run_id", "agent", "bound_version",
                           "error_type", "ref_count"}
    assert out[0]["batch_id"] == 7 and out[0]["ref_count"] == 1


def test_open_batches_ref_count_is_link_ref_len():
    rows = [ns(id=1, run_id="r", agent="a", bound_version="1", error_type="e",
               link_refs=[{"cluster_id": 10}, {"cluster_id": 10}])]

    class _S:
        async def scalars(self, stmt, params=None):
            return _ScalarRows(rows)

    out = _run(_open_batches(_S(), cluster_id=10))
    assert out[0]["ref_count"] == 2


# ---------- HTTP 正例：detail 端点 response 组装（reentry_observe/open_batches 接线） ----------


class _DetailSession(FakeAsyncSession):
    """detail 端点正例：scalars 按实体回全部行；get 支持 registry 内模型（ErrorCluster…）。"""

    def __init__(self, *, rows=None, users=()):
        super().__init__(users=users)
        self._rows = dict(rows or {})

    async def scalars(self, stmt, params=None):
        ent = None
        if stmt is not None:
            ent = stmt.column_descriptions[0].get("entity")
        return _ScalarRows(self._rows.get(ent, []))

    async def get(self, model, pk):
        if model in self._rows:
            return next((r for r in self._rows[model] if getattr(r, "id", None) == pk),
                        None)
        return await super().get(model, pk)


def _detail_claim_cluster_rows():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    claimed_at = now - timedelta(days=2, hours=1)   # waiting_days = (2d+ε)//86400 → 2
    cluster = ns(id=10, agent="agent-x", interface="agent-x.iface", layer="L1",
                 error_type="timeout", error_msg="response timeout",
                 input_hash="hash-1", first_trace_id="tr-t1", input_truncated=0,
                 generation=1, count=5, status="claim",
                 first_ts=claimed_at, latest_ts=claimed_at, fix_version="1.4.0",
                 claimed_by="u1", claimed_at=claimed_at,
                 claim_due_ts=claimed_at + timedelta(days=14), claim_k=2,
                 needs_review_reason=None)
    link = ns(id=30, payload_id="p-1", case_id="c-1", case_type="case",
              offline_status="active", verify_status="pending",
              assembled_ts=claimed_at, invalidate_reason=None)
    run = ns(id=1, run_id="run-9", bound_version="1.4.0", case_pass=1,
             run_status="completed", verified_ts=claimed_at + timedelta(hours=1),
             raw_json={})
    conv = ns(id=1, action="claim", detail="认领", closed_by="u1",
              actor_user_id=1, ts=claimed_at)
    recur = _raw_judged(now - timedelta(days=1), version="1.5.0")  # ≥ claimed_at
    batch = ns(id=7, run_id="run-9", agent="agent-x", bound_version="1.4.0",
               error_type="unclean",
               link_refs=[{"link_id": 30, "cluster_id": 10, "case_id": "c-1"}])
    rows = {
        ErrorCluster: [cluster], ErrorCaseLink: [link],
        VerifyRunRecord: [run], ConversionRecord: [conv],
        TraceJudgeState: [recur], NeedsReviewBatch: [batch],
    }
    return rows, claimed_at


def test_detail_claim_response_carries_reentry_observe_and_open_batches():
    rows, claimed_at = _detail_claim_cluster_rows()
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: _DetailSession(
        users=[_admin_user()], rows=rows)
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        d = c.get("/api/v1/backflow/clusters/10", headers=_token()).json()
    assert d["cluster_id"] == 10
    # 复发观察（claim 态现算）+ 挂起批徽标（open_batches）接线
    assert d["reentry_observe"]["mode"] == "claim"
    assert d["reentry_observe"]["count"] == 1
    assert d["reentry_observe"]["latest_version"] == "1.5.0"
    assert d["reentry_observe"]["since_ts"] == claimed_at.isoformat()
    assert d["open_batches"] == [{"batch_id": 7, "run_id": "run-9", "agent": "agent-x",
                                  "bound_version": "1.4.0", "error_type": "unclean",
                                  "ref_count": 1}]
    # 既有 P2-4 字段零破坏
    assert d["links"][0]["verify_status"] == "pending"
    assert d["verify_runs"][0]["run_status"] == "completed"
    assert d["conversions"][0]["action"] == "claim"
    assert d["waiting_days"] == 2
    assert d["first_trace_id"] == "tr-t1"


def test_detail_open_cluster_reentry_observe_none():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    first_ts = now - timedelta(days=1)
    cluster = ns(id=11, agent="agent-x", interface="agent-x.iface", layer="L1",
                 error_type="timeout", error_msg="m", input_hash="hash-1",
                 first_trace_id="tr-t2", input_truncated=0, generation=1, count=1,
                 status="open", first_ts=first_ts, latest_ts=first_ts,
                 fix_version=None, claimed_by=None, claimed_at=None,
                 claim_due_ts=None, claim_k=2, needs_review_reason=None)
    rows = {ErrorCluster: [cluster], ErrorCaseLink: [], VerifyRunRecord: [],
            ConversionRecord: [], TraceJudgeState: [], NeedsReviewBatch: []}
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: _DetailSession(
        users=[_admin_user()], rows=rows)
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        d = c.get("/api/v1/backflow/clusters/11", headers=_token()).json()
    assert d["status"] == "open"
    assert d["reentry_observe"] is None     # 非 claim/fixed 态 → 不现算
    assert d["open_batches"] == []


# ---------- claim R-5 版本预检：_claim_warning 分支 ----------


class _FakeOffline:
    """OfflineClient 替身：只读面可注入 + aclose 空操作。"""

    def __init__(self, base_url, *, secret="", timeout_s=None):  # mock 替身
        self.versions = []
        self.runs = []

    async def agent_versions(self, *, agent, window_days=14):
        if isinstance(self.versions, Exception):
            raise self.versions
        return self.versions

    async def list_runs(self, *, agent, version=None):
        return self.runs

    async def aclose(self):
        pass


def _patch_claim_warning(monkeypatch, *, versions=None, runs=None, raise_err=None,
                         offline_base_url="http://offline.local"):
    fake = _FakeOffline("http://offline.local")
    fake.versions = raise_err if raise_err else (versions or [])
    fake.runs = runs or []
    monkeypatch.setattr(backflow_api, "OfflineClient", lambda *a, **kw: fake)
    monkeypatch.setattr(backflow_api, "get_settings",
                        lambda: _settings(offline_base_url=offline_base_url))
    return fake


def test_claim_warning_offline_unset_is_none(monkeypatch):
    monkeypatch.setattr(backflow_api, "get_settings", lambda: _settings())
    assert _run(_claim_warning("agent-x", 1, "1.4.0")) is None


def test_claim_warning_fix_version_not_seen(monkeypatch):
    _patch_claim_warning(monkeypatch, versions=[{"version": "1.3.0"},
                                                {"version": "1.3.1"}])
    w = _run(_claim_warning("agent-x", 1, "1.4.0"))
    assert w is not None and "未观测到 agent-x@1.4.0" in w
    assert "已见版本" in w and "1.3.0" in w and "1.3.1" in w


def test_claim_warning_fix_version_seen_generation1_none(monkeypatch):
    _patch_claim_warning(monkeypatch, versions=[{"version": "1.4.0"}])
    assert _run(_claim_warning("agent-x", 1, " 1.4.0 ")) is None  # trim 后精确成员


def test_claim_warning_generation_gt1_completed_run_hits(monkeypatch):
    # R-7 沿用：同版本已有 completed run + generation>1 → reentry 提示
    _patch_claim_warning(monkeypatch, versions=[{"version": "1.4.0"}],
                         runs=[{"run_id": "r1", "status": "completed"}])
    w = _run(_claim_warning("agent-x", 2, "1.4.0"))
    assert w is not None and "reentry" in w


def test_claim_warning_generation_gt1_no_completed_none(monkeypatch):
    _patch_claim_warning(monkeypatch, versions=[{"version": "1.4.0"}],
                         runs=[{"run_id": "r1", "status": "running"}])
    assert _run(_claim_warning("agent-x", 2, "1.4.0")) is None


def test_claim_warning_offline_read_error_is_none(monkeypatch):
    _patch_claim_warning(monkeypatch, raise_err=OfflineReadError("boom"))
    assert _run(_claim_warning("agent-x", 1, "1.4.0")) is None
