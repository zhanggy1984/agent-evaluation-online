"""v1.23 第 2/3 刀 单测：结果推送接收面 + 「结果未达」标记（detail §8.7/§8.9/§9.3）。

- POST /backflow/regression-results 鉴权（evaluator 静态 secret，缺失/错误/未配置 → ERR_PULL_0001）
  与载荷校验（schema_version 非 1.0 → ERR_PULL_0004；pass_fail='na' 缺 error_type →
  ERR_PULL_0002；run_status 只收终态值域 → 422；prev_terminal_version 必填、值可为 null）。
- 落库语义：非白名单 case_type 丢行计数（载荷仍原样留档）、空数组合法、重复推送幂等
  （uk_verify_run，零写）、orphan（无现行 link）落哨兵行 link_id=0 留档但不推进判定、
  conversion_record action=regression_result + actor_user_id=NULL（系统动作）。
- case_pass 派生（link.case_id 命中行；na/缺行 → NULL）——**已非判定输入**，仅读面对账位。
- 第 3 刀落库即判的**接线**（判定内核本体的覆盖在 verify 直测 + claim_probe/push_probe 真库）：
  cluster 非 claim（或不存在）→ 不调 judge_link（数据照落）；cluster=claim → 调判定；
  links_advanced 只在判定 outcome ∈ TERMINAL_OUTCOMES 时列该 link。judge_link 在单测里打桩
  （FakeAsyncSession 无 scalars，跑不了真链），断的是**调用条件与响应语义**。
- _result_overdue 三态（claim **TTL 回退现场**锚 conv(action='claim_ttl_expire') + fix_version
  非空 + 无结果行、且不在有效 claim 期内 / assembled 超 N 天 / 都没超）+ 有结果行不命中
  + 阈值边界 + 详情端点接线（逐字文案）。
- 载荷字段校验：finished_ts 非 ISO8601 → ERR_PULL_0002(400)；重复推送 cases_dropped 与首次一致。

注：FakeAsyncSession 的 flush 是 no-op（不回填自增 id），凡断言 run_record_id 的用例走
_IdBackfillSession（仅补 flush 回填，其余同 Fake）。真实写面语义（唯一键冲突/CAS 竞态/
判定收敛）留给集成探针。
"""
import asyncio
from datetime import datetime, timedelta, timezone

from _fakes import FakeAsyncSession, ns

import app.api.backflow as backflow_api
from app.api.backflow import (
    ORPHAN_LINK_ID,
    OVERDUE_CAPTION,
    _case_pass_of,
    _result_overdue,
)
from app.backflow.claim import CLAIM_TTL_DEFAULT_DAYS
from app.core.config import Settings
from app.core.db import get_session
from app.main import create_app
from app.models.error_flow import (
    ConversionRecord,
    ErrorCaseLink,
    ErrorCluster,
    NeedsReviewBatch,
    TraceJudgeState,
    VerifyRunRecord,
)

_URL = "/api/v1/backflow/regression-results"
_MOCK_SECRET = "s3cret-evaluator"  # 测试 mock 凭证（非真实部署值）


def _settings(mock_secret=_MOCK_SECRET):
    return Settings(
        app_env="test", resource_env="dev",
        jwt_secret="mock-secret-" * 8,
        evaluator_service_secret=mock_secret,
    )


def _app(session=None, mock_secret=_MOCK_SECRET):
    from fastapi.testclient import TestClient

    app = create_app(_settings(mock_secret=mock_secret))
    app.dependency_overrides[get_session] = lambda: session or FakeAsyncSession()
    return TestClient(app)


def _hdr(token=_MOCK_SECRET):
    return {"Authorization": f"Bearer {token}"}


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _body(**over):
    body = dict(
        schema_version="1.0", agent="agent-x", agent_version="1.5.0",
        run_id="run-1", run_status="completed",
        agent_latest_version="1.5.0", prev_terminal_version=None,
        finished_ts="2026-01-05T08:00:00Z",
        cases=[{"case_id": "c-1", "case_type": "regression_error",
                "pass_fail": "pass"}],
    )
    body.update(over)
    return body


class _IdBackfillSession(FakeAsyncSession):
    """补 flush 自增回填（FakeAsyncSession.flush 为 no-op → 响应 run_record_id 恒 None）。"""

    def __init__(self, **kw):
        super().__init__(**kw)
        self._ids = iter(range(900, 990))

    async def flush(self):
        for obj in self.added:
            if isinstance(obj, VerifyRunRecord) and getattr(obj, "id", None) is None:
                obj.id = next(self._ids)


def _added(session, model):
    return [o for o in session.added if isinstance(o, model)]


def _pending_link(**over):
    base = dict(id=30, cluster_id=10, payload_id="p-1", case_id="c-1",
                case_type="regression_error", offline_status="active",
                verify_status="pending", invalidate_reason=None,
                assembled_ts=datetime.now(timezone.utc).replace(tzinfo=None))
    base.update(over)
    return ns(**base)


# ---------- 鉴权（§8.8：evaluator 静态 secret，非平台 JWT） ----------


def test_push_requires_evaluator_secret():
    with _app() as c:
        assert c.post(_URL, json=_body()).status_code == 401
        r = c.post(_URL, headers=_hdr("wrong"), json=_body())
        assert r.status_code == 401 and r.json()["code"] == "ERR_PULL_0001"


def test_push_fail_closed_when_secret_unset():
    # 未配置 evaluator_service_secret → 全 401（与 pull/* 同守卫，fail-closed）
    with _app(mock_secret="") as c:
        r = c.post(_URL, headers=_hdr("anything"), json=_body())
        assert r.status_code == 401 and r.json()["code"] == "ERR_PULL_0001"


def test_push_rejects_wrong_schema_version():
    with _app() as c:
        r = c.post(_URL, headers=_hdr(), json=_body(schema_version="2.0"))
        assert r.status_code == 400 and r.json()["code"] == "ERR_PULL_0004"


def test_push_run_status_only_terminal_values():
    # 只推终态（原 B-1(c) 值集），running 等非终态由 pydantic 拦下（422）
    with _app() as c:
        r = c.post(_URL, headers=_hdr(), json=_body(run_status="running"))
        assert r.status_code == 422


def test_push_rejects_non_iso8601_finished_ts():
    # finished_ts 是后续刀「版本恢复防假连续」判定的时间锚，脏串在入口拒单（ERR_PULL_0002）
    with _app() as c:
        for bad in ("not-a-timestamp", "2026-13-45T99:99:99Z", ""):
            r = c.post(_URL, headers=_hdr(), json=_body(finished_ts=bad))
            assert r.status_code == 400 and r.json()["code"] == "ERR_PULL_0002", bad
            assert "finished_ts" in r.json()["message"], r.json()
        # 合法 ISO8601 三形态（Z / 显式偏移 / 无时区）放行
        for ok in ("2026-01-05T08:00:00Z", "2026-01-05T08:00:00+00:00",
                   "2026-01-05T08:00:00"):
            assert c.post(_URL, headers=_hdr(), json=_body(finished_ts=ok)).status_code == 200


# ---------- 载荷校验：R-22 / 丢行 / 空数组 ----------


def test_push_prev_terminal_version_required_but_nullable():
    """第 3 刀新字段：**必填但值可为 null**（漏带 → 422，判据失效；null = 首次无前序）。

    为什么必填：缺行中断判据「prev_terminal_version 非空且本地无该版本」在字段缺失时静默
    退化为「永不中断」——与「漏带水位字段则该条守卫失效」同性质的失效模式，必须在入口挡。
    """
    with _app() as c:
        body = _body()
        body.pop("prev_terminal_version")
        assert c.post(_URL, headers=_hdr(), json=body).status_code == 422  # 漏带 → 拒
        assert c.post(_URL, headers=_hdr(), json=_body(prev_terminal_version=None)
                      ).status_code == 200  # 显式 null → 合法
        assert c.post(_URL, headers=_hdr(), json=_body(prev_terminal_version="1.4.0")
                      ).status_code == 200


def test_push_na_without_error_type_rejected():
    cases = [{"case_id": "c-1", "case_type": "regression_error", "pass_fail": "na"}]
    with _app() as c:
        r = c.post(_URL, headers=_hdr(), json=_body(cases=cases))
        assert r.status_code == 400 and r.json()["code"] == "ERR_PULL_0002"
        # 带 error_type 则放行（na 合法：case 级 infra 无法判定）
        cases[0]["error_type"] = "timeout"
        r2 = c.post(_URL, headers=_hdr(), json=_body(cases=cases))
        assert r2.status_code == 200


def test_push_duplicate_case_id_rejected():
    # 同一 case 两条结果 = 载荷自相矛盾：`_case_pass_of` 只取首条命中行，静默取首条会按任意
    # 一条收敛（且 run 落库、link 终态只读，不可回改），offline 侧拼装 bug 被掩盖 → 整单拒。
    cases = [
        {"case_id": "c-dup", "case_type": "regression_error", "pass_fail": "pass"},
        {"case_id": "c-dup", "case_type": "regression_error", "pass_fail": "fail",
         "error_type": "timeout"},
    ]
    session = _IdBackfillSession()
    with _app(session) as c:
        r = c.post(_URL, headers=_hdr(), json=_body(cases=cases))
        assert r.status_code == 400 and r.json()["code"] == "ERR_PULL_0002"
        body = r.json()
        # 消息带重复值 + **首次**出现下标（首条下标 0 是假值，实现须用 is not None 判）
        assert "c-dup" in body["message"] and "cases[0]" in body["message"], body
        assert not _added(session, VerifyRunRecord)  # 零落库
        assert not _added(session, ConversionRecord)
        # 反证：case_id 互不相同的多行（含非白名单行）→ 200，去重不误伤行级多行/丢行策略
        ok = [
            {"case_id": "c-1", "case_type": "regression_error", "pass_fail": "pass"},
            {"case_id": "c-2", "case_type": "random_access", "pass_fail": "fail"},
        ]
        r2 = c.post(_URL, headers=_hdr(), json=_body(cases=ok))
        assert r2.status_code == 200 and r2.json()["cases_dropped"] == 1


def test_push_empty_cases_legal_run_level_row():
    # 空数组合法：落 run 级行、case_pass=NULL（§8.7）
    session = _IdBackfillSession()
    with _app(session) as c:
        r = c.post(_URL, headers=_hdr(), json=_body(cases=[]))
        assert r.status_code == 200
        assert r.json() == {"accepted": True, "duplicated": False,
                            "run_record_id": 900, "links_advanced": [],
                            "cases_dropped": 0}
    rec = _added(session, VerifyRunRecord)[0]
    assert rec.case_pass is None and rec.run_id == "run-1"
    assert rec.bound_version == "1.5.0" and rec.run_status == "completed"


def test_push_drops_non_whitelist_case_type():
    cases = [
        {"case_id": "c-1", "case_type": "regression_error", "pass_fail": "pass"},
        {"case_id": "c-2", "case_type": "random_access", "pass_fail": "fail"},
    ]
    session = _IdBackfillSession()
    with _app(session) as c:
        r = c.post(_URL, headers=_hdr(), json=_body(trigger_signal_id=10, cases=cases))
        assert r.status_code == 200
        assert r.json()["cases_dropped"] == 1  # 丢该行 + 计数，不整体拒单
    # 只有一行 verify_run_record（丢行不产行）；但 raw_json 原样留档整个载荷（含被丢行）
    assert len(_added(session, VerifyRunRecord)) == 1
    raw = _added(session, VerifyRunRecord)[0].raw_json
    assert [c["case_type"] for c in raw["cases"]] == ["regression_error", "random_access"]
    assert raw["agent_latest_version"] == "1.5.0"          # 零 DDL 承载的水位字段
    assert raw["prev_terminal_version"] is None            # 缺行中断判据的输入（第 3 刀）
    assert "bound_version_first_seen" not in raw           # 本批删除：必填却零读取点（(e)）
    assert raw["finished_ts"] == "2026-01-05T08:00:00Z"
    assert raw["schema_version"] == "1.0"


def test_push_all_cases_dropped_still_200():
    cases = [{"case_id": "c-9", "case_type": "random_access", "pass_fail": "fail"}]
    with _app() as c:
        r = c.post(_URL, headers=_hdr(), json=_body(cases=cases))
        assert r.status_code == 200 and r.json()["cases_dropped"] == 1


# ---------- 落库：命中现行 link / 孤儿 / 幂等 ----------


class _GetRegistrySession(_IdBackfillSession):
    """get 亦按 registry 回行（第 3 刀判定链要按 link.cluster_id 重读 cluster）。"""

    async def get(self, model, pk):
        row = next((r for r in self.registry.get(model, [])
                    if getattr(r, "id", None) == pk), None)
        return row if row is not None else await super().get(model, pk)


def _cluster(status="claim", cid=10):
    return ns(id=cid, status=status, claim_k=2, input_truncated=0,
              fix_version="1.5.0", agent="agent-x")


def _stub_judge(monkeypatch, *, outcome="pending", calls=None):
    """打桩 judge_link：只验接线（真链走 claim_probe/push_probe 真库）。"""
    async def fake(session, *, cluster, link):
        if calls is not None:
            calls.append((cluster.id, link.id))
        return {"outcome": outcome, "reason": "stub"}
    monkeypatch.setattr(backflow_api, "judge_link", fake)


def test_push_lands_row_and_writes_conversion(monkeypatch):
    session = _GetRegistrySession(registry={ErrorCaseLink: [_pending_link()],
                                            ErrorCluster: [_cluster()]})
    calls: list = []
    _stub_judge(monkeypatch, outcome="pending", calls=calls)
    cases = [
        {"case_id": "c-1", "case_type": "regression_error", "pass_fail": "pass"},
        {"case_id": "c-2", "case_type": "regression_error", "pass_fail": "fail"},
    ]
    with _app(session) as c:
        r = c.post(_URL, headers=_hdr(), json=_body(trigger_signal_id=10, cases=cases))
        assert r.status_code == 200
        # 判定跑了（cluster=claim）但未收敛终态 → links_advanced 空（第 3 刀语义收窄）
        assert calls == [(10, 30)]
        assert r.json()["links_advanced"] == []
        assert r.json()["duplicated"] is False
    rec = _added(session, VerifyRunRecord)[0]
    assert rec.link_id == 30
    assert rec.case_pass == 1  # 命中 link.case_id 的行（c-1 pass）→ 1
    assert rec.raw_json["prev_terminal_version"] is None
    conv = _added(session, ConversionRecord)[0]
    assert conv.action == "regression_result"
    assert conv.cluster_id == 10 and conv.link_id == 30
    assert conv.actor_user_id is None  # 系统动作（offline 推送），非人工
    assert "run-1" in conv.detail and "dropped=0" in conv.detail


def test_push_links_advanced_only_on_terminal_migration(monkeypatch):
    # 响应语义 = 「真正发生终态迁移的 link」（passed/failed/superseded 三类）
    for outcome, expected in (("fixed_auto", [30]), ("reopened", [30]),
                              ("needs_review", [30]), ("gap", []),
                              ("unclean_batch", []), ("no_progress", [])):
        session = _GetRegistrySession(
            registry={ErrorCaseLink: [_pending_link()], ErrorCluster: [_cluster()]})
        _stub_judge(monkeypatch, outcome=outcome)
        with _app(session) as c:
            r = c.post(_URL, headers=_hdr(), json=_body(trigger_signal_id=10))
        assert r.status_code == 200, outcome
        assert r.json()["links_advanced"] == expected, outcome


def test_push_skips_judgment_when_cluster_not_claim(monkeypatch):
    """守卫：cluster 非 claim（或已不存在）→ 不调判定，但数据照落。

    为什么必须挡：`_find_current_link` 只按 link.verify_status=pending 查——needs_review
    resolve↔reopen 过渡、TTL 认领失效、admin invalidate 都可能在非 claim 簇上留下 pending
    link；不挡就会对已 fixed/needs_review 的簇写终态迁移（越权改状态）。
    """
    for row in (_cluster(status="fixed"), _cluster(status="needs_review"),
                _cluster(status="inactive"), None):
        registry = {ErrorCaseLink: [_pending_link()]}
        if row is not None:
            registry[ErrorCluster] = [row]
        session = _GetRegistrySession(registry=registry)
        calls: list = []
        _stub_judge(monkeypatch, calls=calls)
        with _app(session) as c:
            r = c.post(_URL, headers=_hdr(), json=_body(trigger_signal_id=10))
        assert r.status_code == 200, row
        assert calls == [], row
        assert r.json()["links_advanced"] == [], row
        assert len(_added(session, VerifyRunRecord)) == 1  # 留档不受影响
        assert len(_added(session, ConversionRecord)) == 1


def test_push_orphan_archives_without_advancing():
    # trigger_signal_id 有值但查不到现行 link（关联断裂）→ 仍落库留档、不推进判定
    session = _IdBackfillSession()
    with _app(session) as c:
        r = c.post(_URL, headers=_hdr(), json=_body(trigger_signal_id=999))
        assert r.status_code == 200
        assert r.json()["links_advanced"] == []
        assert r.json()["run_record_id"] == 900  # 哨兵行确有 id
    rec = _added(session, VerifyRunRecord)[0]
    assert rec.link_id == ORPHAN_LINK_ID == 0  # 见 api 常量注释：UNSIGNED 自增永不分配 0
    assert rec.case_pass is None
    conv = _added(session, ConversionRecord)[0]
    assert conv.cluster_id is None and conv.link_id == ORPHAN_LINK_ID
    assert conv.action == "regression_result" and conv.actor_user_id is None
    assert "orphan" in conv.detail


def test_push_duplicate_is_idempotent():
    # 同 link_id + run_id 已有行 → 200 duplicated=true，零写（不落库、不写 conv）
    session = FakeAsyncSession(registry={
        ErrorCaseLink: [_pending_link()],
        VerifyRunRecord: [ns(id=77, link_id=30, run_id="run-1")],
    })
    with _app(session) as c:
        r = c.post(_URL, headers=_hdr(), json=_body(trigger_signal_id=10))
        assert r.status_code == 200
        assert r.json() == {"accepted": True, "duplicated": True, "run_record_id": 77,
                            "links_advanced": [], "cases_dropped": 0}
    assert session.added == []


def test_push_duplicate_keeps_cases_dropped_same_as_first():
    # cases_dropped 口径 = 载荷校验产物，与是否落库正交：重试（响应丢失后重推）必须拿到与
    # 首次一致的答案，否则 offline 会误判「没丢数据」。
    cases = [
        {"case_id": "c-1", "case_type": "regression_error", "pass_fail": "pass"},
        {"case_id": "c-2", "case_type": "random_access", "pass_fail": "fail"},
    ]
    session = _IdBackfillSession(registry={ErrorCaseLink: [_pending_link()]})
    with _app(session) as c:
        r1 = c.post(_URL, headers=_hdr(), json=_body(trigger_signal_id=10, cases=cases))
        assert r1.status_code == 200 and r1.json()["duplicated"] is False
        assert r1.json()["cases_dropped"] == 1
        # 模拟重放：首推已落库的行进入下一次的现行查询面（Fake 不消费 session.added）
        session.registry[VerifyRunRecord] = _added(session, VerifyRunRecord)
        r2 = c.post(_URL, headers=_hdr(), json=_body(trigger_signal_id=10, cases=cases))
        assert r2.status_code == 200 and r2.json()["duplicated"] is True
        assert r2.json()["cases_dropped"] == r1.json()["cases_dropped"] == 1
        assert r2.json()["links_advanced"] == [] and r2.json()["run_record_id"] == 900
    assert len(_added(session, VerifyRunRecord)) == 1  # 零新增行
    assert len(_added(session, ConversionRecord)) == 1


def test_push_orphan_same_run_idempotent_on_sentinel():
    # 孤儿行的幂等键同样是 uk_verify_run(link_id=0, run_id)：重复推不重建行
    session = FakeAsyncSession(registry={
        VerifyRunRecord: [ns(id=88, link_id=ORPHAN_LINK_ID, run_id="run-1")],
    })
    with _app(session) as c:
        r = c.post(_URL, headers=_hdr(), json=_body(trigger_signal_id=999))
        assert r.status_code == 200
        assert r.json()["duplicated"] is True and r.json()["run_record_id"] == 88
        assert r.json()["links_advanced"] == []
    assert session.added == []


# ---------- case_pass 派生（纯函数） ----------


def _case(case_id, pf, et=None):
    return ns(case_id=case_id, pass_fail=pf, error_type=et)


def test_case_pass_derivation():
    link = _pending_link(case_id="c-1")
    assert _case_pass_of(link, [_case("c-1", "pass")]) == 1
    assert _case_pass_of(link, [_case("c-1", "fail")]) == 0
    assert _case_pass_of(link, [_case("c-1", "na", "timeout")]) is None  # na → NULL
    assert _case_pass_of(link, [_case("c-2", "pass")]) is None           # 缺行 → NULL
    assert _case_pass_of(_pending_link(case_id=None), [_case("c-1", "pass")]) is None
    assert _case_pass_of(None, [_case("c-1", "pass")]) is None           # orphan


# ---------- 「结果未达」标记三态（§8.7 保活 / §9.3 文案） ----------


def _overdue_cluster(**over):
    base = dict(id=10, status="open", claimed_at=None, claim_due_ts=None,
                fix_version=None)
    base.update(over)
    return ns(**base)


def _expire_conv(ts, **over):
    """claim_ttl_job 回退现场的唯一持久证据（_expire_batch CAS 成功时必写）。"""
    base = dict(id=1, cluster_id=10, link_id=None, action="claim_ttl_expire",
                detail="claim TTL 超窗 → open", ts=ts)
    base.update(over)
    return ns(**base)


def _run_overdue(cluster, links, runs, convs=()):
    return asyncio.run(
        _result_overdue(FakeAsyncSession(), cluster, links, runs, list(convs)))


def _round_start(days=20):
    """本轮等待起点（link 组装时刻）：早于回退 conv 的 ts，conditions ⑤ 成立。

    真实链 = 组装 → offline 认领 → TTL 超窗 → claim_ttl_job 回退写 conv，回退只可能发生在
    本轮开始之后；故 claim 分支的正例造数必须让 assembled_ts 早于 conv.ts。
    """
    return _now() - timedelta(days=days)


def test_result_overdue_claim_after_ttl_expire_without_results():
    # claim 分支新判据（v1.23 第 3 刀）：conv(claim_ttl_expire) + fix_version 非空 + anchor 无 run
    # + 不在有效 claim 期 → 命中；since_ts = 该 conv 的 ts（claimed_at 已被回退清空，作不了锚）。
    # 多条回退记录（回退→再 claim→再超窗）时取**最新**一条，且不依赖入参顺序。
    now = _now()
    expire_ts = now - timedelta(days=1)
    cluster = _overdue_cluster(status="open", fix_version="v9")  # 回退后：claimed_at/due 已清
    link = _pending_link(offline_status="active", assembled_ts=_round_start())
    older = _expire_conv(expire_ts - timedelta(days=2), id=1)
    newer = _expire_conv(expire_ts, id=2)
    out = _run_overdue(cluster, [link], [], [older, newer])
    assert out["hit"] is True and out["kind"] == "claim"
    assert out["since_ts"] == expire_ts.isoformat()
    assert out["caption"] == OVERDUE_CAPTION == "回查结果未达（疑似 offline 停摆），人工核查"


def test_result_overdue_claim_suppressed_in_active_claim_window():
    # ④ 抑制：TTL 回退后**再次 claim**（人工处置中，旧 conv 仍在库）→ 不得误报 offline 停摆
    now = _now()
    cluster = _overdue_cluster(status="claim", claimed_at=now,
                               claim_due_ts=now + timedelta(days=13), fix_version="v9")
    link = _pending_link(offline_status="active", assembled_ts=_round_start())
    convs = [_expire_conv(now - timedelta(days=2))]
    assert _run_overdue(cluster, [link], [], convs)["hit"] is False
    # 一旦再次超窗（回退前一刻），同一现场即命中——边界恰在 claim_due_ts
    cluster.claim_due_ts = now - timedelta(seconds=1)
    out = _run_overdue(cluster, [link], [], convs)
    assert out["hit"] is True and out["kind"] == "claim"


def test_result_overdue_claim_needs_expire_conv_not_due_ts():
    # 旧判据（超 claim_due_ts ∧ 无 run）不再命中：TTL 回退会清 claimed_at/due（60s 内必清），
    # 故「超窗 claim」本身不是持久证据——没有 conv 就不标记（原判据在此恒假 = 探测落空）
    now = _now()
    cluster = _overdue_cluster(status="claim", claimed_at=now - timedelta(days=15),
                               claim_due_ts=now - timedelta(days=1), fix_version="v9")
    link = _pending_link(offline_status="active")
    assert _run_overdue(cluster, [link], [])["hit"] is False


def test_result_overdue_claim_without_fix_version_not_hit():
    # ② fix_version 空 = 无门控基础（非 claim 语义造数），回退现场也不标记
    now = _now()
    cluster = _overdue_cluster(status="open", fix_version=None)
    link = _pending_link(offline_status="active")
    convs = [_expire_conv(now - timedelta(days=1))]
    assert _run_overdue(cluster, [link], [], convs)["hit"] is False


def test_result_overdue_claim_without_anchor_not_hit():
    # ③ anchor 不存在（无 link）→ 无「等谁的结果」可言，不标记
    now = _now()
    cluster = _overdue_cluster(status="open", fix_version="v9")
    assert _run_overdue(cluster, [], [], [_expire_conv(now - timedelta(days=1))])["hit"] is False


def test_result_overdue_claim_with_result_row_not_hit():
    # 有 verify_run_record（结果已达）→ 不标记，即使回退现场 + fix_version 齐备
    now = _now()
    cluster = _overdue_cluster(status="open", fix_version="v9")
    link = _pending_link(offline_status="active")
    runs = [ns(id=1, link_id=30, run_id="run-1")]
    assert _run_overdue(cluster, [link], runs,
                        [_expire_conv(now - timedelta(days=1))])["hit"] is False


def test_result_overdue_claim_needs_pending_anchor():
    # ③ 锚点必须是**现行 pending link**（不吃 links[0] 兜底）：cluster 离开「等结果」态时
    # link 必被终结——fixed_review(approve=True) → passed、ignore → superseded
    # （claim.py:246 / backflow.py ignore）。此时回退 conv/fix_version 仍在、anchor_runs 空，
    # 少 pending 谓词就会在已 fixed / 已 inactive 的簇上误报「offline 停摆」。
    now = _now()
    convs = [_expire_conv(now - timedelta(days=1))]
    for status, verify in (("fixed", "passed"), ("inactive", "superseded")):
        cluster = _overdue_cluster(status=status, fix_version="v9")
        # assembled_ts 拨到本轮起点之前让 ⑤ 成立：否则 ⑤ 会替 ③ 挡下命中，护栏测不到 ③
        link = _pending_link(offline_status="active", verify_status=verify,
                             assembled_ts=_round_start())
        out = _run_overdue(cluster, [link], [], convs)
        # 回归护栏：去掉 ③ 的 pending 谓词后本断言必转红（真库对照见 push_probe S-10/S-11）
        assert out["hit"] is False and out["kind"] is None, (status, verify, out)
    # 同现场把 link 保持 pending（即 cluster 仍在等结果）→ 命中（防上面两条因链路不通而假绿）
    cluster = _overdue_cluster(status="open", fix_version="v9")
    assert _run_overdue(
        cluster, [_pending_link(offline_status="active", assembled_ts=_round_start())],
        [], convs)["hit"] is True


def test_result_overdue_claim_needs_this_round_expire():
    # ⑤ 本轮性：回退记录必须落在**本轮等待开始之后**。cluster 回退 open 后被重新组装时
    # （reopen / invalidate→requeue → assemble_job 装配全新 pending link），fix_version 与
    # 上一轮那条 claim_ttl_expire conv 都还在（reopen_cluster 只置 status，不清二者），
    # 新 link 零 run → ①②③④ 全成立，但 since_ts 会是几十天前的陈旧回退时刻 → 误报停摆。
    # ③ 的 pending 谓词挡不住（link 真 pending，只是换了一条新的），故必须有 ⑤。
    now = _now()
    stale_convs = [_expire_conv(now - timedelta(days=30))]
    cluster = _overdue_cluster(status="open", fix_version="v9")
    fresh = _pending_link(offline_status="active",
                          assembled_ts=now.replace(microsecond=0))
    out = _run_overdue(cluster, [fresh], [], stale_convs)
    # 回归护栏：去掉条件 ⑤ 后本断言必转红（真库对照见 push_probe S-12）
    assert out["hit"] is False and out["kind"] is None, out
    # 正例（防上面因链路不通假绿）：回退落在本轮起点**之后**（S-7 形态：20 天前组装、1 天前
    # 超窗回退）→ 命中。注意命中的前提是 assembled_ts < expire.ts，不是「回退越新越命中」
    aged = _pending_link(offline_status="active", assembled_ts=_round_start())
    out2 = _run_overdue(cluster, [aged], [], [_expire_conv(now - timedelta(days=1))])
    assert out2["hit"] is True and out2["kind"] == "claim", out2
    # 未组装（assembled_ts=None）也抑制：offline 还没有可跑的东西，报「停摆」是误诊
    # （该现场归 assembled 分支，不由 claim 分支背）
    unassembled = _pending_link(offline_status="active", assembled_ts=None)
    assert _run_overdue(cluster, [unassembled], [], stale_convs)["hit"] is False


def test_result_overdue_assembled_over_threshold():
    # assembled 态 link 超「已待 N 天」（N = claim_ttl_days，两标记共用同一阈值）
    now = _now()
    assembled_ts = now - timedelta(days=CLAIM_TTL_DEFAULT_DAYS, hours=1)
    link = _pending_link(offline_status="assembled")
    link.assembled_ts = assembled_ts
    out = _run_overdue(_overdue_cluster(), [link], [])
    assert out["hit"] is True and out["kind"] == "assembled"
    assert out["since_ts"] == assembled_ts.isoformat()
    assert out["caption"] == OVERDUE_CAPTION


def test_result_overdue_assembled_threshold_boundary():
    now = _now()
    link = _pending_link(offline_status="assembled")
    link.assembled_ts = now - timedelta(days=CLAIM_TTL_DEFAULT_DAYS)     # 恰满 N 天 → 命中
    assert _run_overdue(_overdue_cluster(), [link], [])["hit"] is True
    link.assembled_ts = now - timedelta(days=CLAIM_TTL_DEFAULT_DAYS - 1)  # 未满 → 不命中
    assert _run_overdue(_overdue_cluster(), [link], [])["hit"] is False


def test_result_overdue_none_overdue():
    # 都没超（claim 未到 due、assembled 刚组装）→ hit False，kind/since/caption 全 None
    now = _now()
    cluster = _overdue_cluster(status="claim", claimed_at=now - timedelta(days=1),
                               claim_due_ts=now + timedelta(days=13))
    link = _pending_link(offline_status="assembled")
    link.assembled_ts = now - timedelta(hours=1)
    assert _run_overdue(cluster, [link], []) == {
        "hit": False, "kind": None, "since_ts": None, "caption": None}


def test_result_overdue_active_link_not_marked():
    # assembled 分支只认 assembled（active = offline 已建 case，等的是 run 不是拉取）
    now = _now()
    link = _pending_link(offline_status="active")
    link.assembled_ts = now - timedelta(days=99)
    assert _run_overdue(_overdue_cluster(), [link], [])["hit"] is False


# ---------- 详情端点接线（逐字文案进响应） ----------


class _Rows:
    def __init__(self, items):
        self.items = list(items)

    def all(self):
        return self.items


class _DetailSession(FakeAsyncSession):
    """detail 端点正例：scalars 按实体回行、get 走 registry（仿 test_backflow_recurrence）。"""

    def __init__(self, *, rows=None, users=()):
        super().__init__(users=users)
        self._rows = dict(rows or {})

    async def scalars(self, stmt, params=None):
        ent = None if stmt is None else stmt.column_descriptions[0].get("entity")
        return _Rows(self._rows.get(ent, []))

    async def get(self, model, pk):
        if model in self._rows:
            return next((r for r in self._rows[model]
                         if getattr(r, "id", None) == pk), None)
        return await super().get(model, pk)


def _detail_rows(assembled_ts):
    now = _now()
    cluster = ns(id=10, agent="agent-x", interface="agent-x.iface", layer="L1",
                 error_type="timeout", error_msg="response timeout",
                 input_hash="hash-1", first_trace_id="tr-t1", input_truncated=0,
                 generation=1, count=5, status="open", first_ts=now - timedelta(days=30),
                 latest_ts=now, fix_version=None, claimed_by=None, claimed_at=None,
                 claim_due_ts=None, claim_k=2, needs_review_reason=None)
    link = _pending_link(offline_status="assembled")
    link.assembled_ts = assembled_ts
    return {
        ErrorCluster: [cluster], ErrorCaseLink: [link], VerifyRunRecord: [],
        ConversionRecord: [], TraceJudgeState: [], NeedsReviewBatch: [],
    }


def test_detail_carries_result_overdue_caption():
    session = _DetailSession(rows=_detail_rows(_now() - timedelta(days=30)))
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: session
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        # 详情读面走 viewer JWT（push 端点才是 evaluator 凭证）
        from app.core.security import create_access_token

        hdr = {"Authorization": f"Bearer {create_access_token(_settings(), 1, 'viewer')}"}
        session.users = [ns(id=1, username="u1", display_name="用户",
                            password_hash="x", role="viewer", status=1)]
        d = c.get("/api/v1/backflow/clusters/10", headers=hdr).json()
    assert d["result_overdue"]["hit"] is True
    assert d["result_overdue"]["kind"] == "assembled"
    assert d["result_overdue"]["caption"] == "回查结果未达（疑似 offline 停摆），人工核查"
    # 既有详情字段零破坏
    assert d["waiting_days"] >= 29 and d["links"][0]["link_id"] == 30
