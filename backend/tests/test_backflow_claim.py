"""P2-4 backflow claim 状态机 + verify 判定内核单测（detail §7.6/§8.4，T-3.4）。

- route_verdict：§7.6 v1.5 R-2 映射 ①~⑤ + R-10/R-15 优先级 全分支（纯函数直打）。
- classify_error_type / env_na_types：R-19 环境级 5 + case 级 10 字面量护栏 + 未知从严 env。
- decide_k：K 序列折叠（相邻纯净 pass 才递增、跨缺版/污染断链、fail/na/截断终值）。
- normalize_fix_version：fix_version trim 归一。
- offline_client：MockTransport 级——Bearer + 多 status 参数 + 响应容错 + HTTP≥400 →
  OfflineReadError（读面失败语义，§16）。
- HTTP 鉴权负例（真实 deps 链 + FakeAsyncSession）：viewer 可触达 claim/不可触达
  fixed-review（ERR_AUTH_0002 403）、无 token 401、cluster 不存在 ERR_CLUSTER_0001(404)。
- 迁移守卫（DB-free raise 分支直打）：claim/ignore/reopen/fixed-review/needs-review-resolve
  非法状态·action·k 值域 → ERR_CLUSTER_0003；needs-review-resolve escalated = §16 只记录保留
  状态；batch resolve action 值域；run_recheck offline_base_url 空停轮。
  DB 写面语义（CAS/批事务/uk 幂等/回查收敛）留集成探针 claim_probe。
"""
import asyncio
from contextlib import contextmanager

import httpx
from _fakes import FakeAsyncSession, ns

from app.backflow import batches as batch_flow
from app.backflow import claim as claim_flow
from app.backflow.verify import (
    CASE_LEVEL_ERROR_TYPES,
    ENV_LEVEL_ERROR_TYPES,
    classify_error_type,
    decide_k,
    env_na_types,
    route_verdict,
)
from app.core.config import Settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.offline_client import OfflineClient, OfflineReadError
from app.core.security import create_access_token
from app.main import create_app

_MOCK_SECRET = "s3cret-evaluator"


def _settings(mock_secret=_MOCK_SECRET):
    return Settings(
        app_env="test", resource_env="dev",
        jwt_secret="mock-secret-" * 8,
        evaluator_service_secret=mock_secret,
    )


def _admin_user(role="admin"):
    return ns(id=1, username="admin1", display_name="管理员", password_hash="x",
              role=role, status=1)


def _admin_token(role="admin"):
    return create_access_token(_settings(), 1, role)


@contextmanager
def _enter(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client


# ---------- route_verdict：判定映射 ①~⑤ + R-10/R-15（纯函数） ----------


def test_route_fail_reopens():
    assert route_verdict(x_pf="fail") == {"action": "reopen"}


def test_route_na_needs_review_reason_na():
    d = route_verdict(x_pf="na", run_env_na=["circuit_open"])
    assert d == {"action": "needs_review", "reason": "na"}  # 环境级 na 也走 X=na 通道 ④


def test_route_missing():
    assert route_verdict(x_pf="missing") == {"action": "missing"}


def test_route_pure_pass_counts_k():
    assert route_verdict(x_pf="pass") == {"action": "count_k"}
    # run 内只有 case 级 na → 不污染，仍可判（映射 ②）
    assert route_verdict(x_pf="pass", run_env_na=["timeout"]) == {"action": "count_k"}


def test_route_pass_env_na_unclean():
    d = route_verdict(x_pf="pass", run_env_na=["circuit_open"])
    assert d == {"action": "unclean_run"}
    # 多个环境级 na → 仍 unclean
    assert route_verdict(x_pf="pass", run_env_na=["pool_error", "circuit_open"])[
        "action"] == "unclean_run"


def test_route_input_truncated_priority_duel():
    # R-15 双通道：input_truncated ∧ 环境级 na → 走截断单条（不入 unclean 批）
    d = route_verdict(x_pf="pass", input_truncated=True, run_env_na=["circuit_open"])
    assert d == {"action": "needs_review", "reason": "input_truncated"}
    # R-10：纯净 pass 也降级
    d2 = route_verdict(x_pf="pass", input_truncated=True)
    assert d2 == {"action": "needs_review", "reason": "input_truncated"}


# ---------- error_type 归类：R-19 字面量护栏（勿漂移） ----------


def test_error_type_env_level_literal():
    assert ENV_LEVEL_ERROR_TYPES == {
        "circuit_open", "interface_disabled", "scheduler_unexecuted",
        "http_client_error", "pool_error",
    }
    for et in ENV_LEVEL_ERROR_TYPES:
        assert classify_error_type(et) == "env"


def test_error_type_case_level_literal():
    assert CASE_LEVEL_ERROR_TYPES == {
        "timeout", "connect_error", "sse_parse_error", "http_error", "no_done",
        "body_too_large", "no_usage", "contract_error", "missing_assertion",
        "assertion_shape",
    }
    for et in CASE_LEVEL_ERROR_TYPES:
        assert classify_error_type(et) == "case"


def test_error_type_unknown_defaults_env():
    # 无标注新 error_type 默认从严 = 环境级（R-19 护栏）
    assert classify_error_type("brand_new_signal_loss") == "env"
    assert classify_error_type(None) == "env"


def test_env_na_types_filters_and_sorts():
    assert env_na_types(["timeout", "circuit_open", "no_done"]) == ["circuit_open"]
    assert env_na_types(None) == []
    assert env_na_types("circuit_open") == ["circuit_open"]  # 容错非容器入参


# ---------- decide_k：K 序列折叠（相邻纯净 + 断链 + 终值） ----------


def _fold(actions, claim_k=2):
    """便捷折叠：actions = route_verdict 决策 dict 序列，返回 terminal/未满 seq。"""
    seq = 0
    prev_pure = False
    for decision in actions:
        seq, prev_pure, terminal = decide_k(seq, prev_pure, decision, claim_k)
        if terminal is not None:
            return terminal
    return {"seq": seq}


def test_k_two_consecutive_pure_passes_fixed():
    t = _fold([{"action": "count_k"}, {"action": "count_k"}], claim_k=2)
    assert t["outcome"] == "passed" and t["seq"] == 2


def test_k_one_pass_k1_fixed_immediately():
    t = _fold([{"action": "count_k"}], claim_k=1)
    assert t["outcome"] == "passed"


def test_k_single_pass_k2_not_fixed():
    assert _fold([{"action": "count_k"}], claim_k=2) == {"seq": 1}


def test_k_fail_terminal_reopen_resets():
    t = _fold([{"action": "count_k"}, {"action": "reopen"}, {"action": "count_k"},
               {"action": "count_k"}])
    # fail → terminal（reopen），后续不计（映射① 即停扫）
    assert t["outcome"] == "reopened"


def test_k_na_terminal_needs_review():
    t = _fold([{"action": "count_k"}, {"action": "needs_review", "reason": "na"}])
    assert t == {"outcome": "needs_review", "reason": "na"}


def test_k_unclean_breaks_chain_then_two_pure_pass_fixed():
    # 污染断链（prev_pure=False，不清零），其后连续两纯净 pass 才 K 满
    acts = [{"action": "count_k"}, {"action": "unclean_run"}, {"action": "count_k"},
            {"action": "count_k"}]
    assert _fold(acts, claim_k=2)["outcome"] == "passed"


def test_k_unclean_then_single_pure_not_fixed():
    # 断链后仅一个纯净 pass → seq=1 未满（防跨污染假连续）
    acts = [{"action": "unclean_run"}, {"action": "count_k"}]
    assert _fold(acts, claim_k=2) == {"seq": 1}


def test_k_missing_also_breaks_adjacency():
    # 缺 case 行（missing）断链：后单纯净 pass 不可直接 K2 满
    assert _fold([{"action": "missing"}, {"action": "count_k"}], claim_k=2) == {"seq": 1}
    assert _fold([{"action": "missing"}, {"action": "count_k"}, {"action": "count_k"}],
                 claim_k=2)["outcome"] == "passed"


# ---------- claim：fix_version 归一 ----------


def test_normalize_fix_version_trims():
    assert claim_flow.normalize_fix_version("  1.4.0  ") == "1.4.0"
    assert claim_flow.normalize_fix_version("") == ""


# ---------- offline_client：传输级（Bearer + 参数 + 容错 + 读面失败） ----------


def _mock_offline(handler):
    return OfflineClient("http://offline.local", secret=_MOCK_SECRET,
                         transport=httpx.MockTransport(handler))


def _run(coro):
    return asyncio.run(coro)


def test_offline_client_sends_bearer_and_multi_status_params():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization")
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"runs": [{"run_id": "r1", "status": "completed"}]})

    async def go():
        c = _mock_offline(handler)
        try:
            return await c.list_runs(agent="agent-x", version="1.0")
        finally:
            await c.aclose()

    runs = _run(go())
    assert runs[0]["run_id"] == "r1"
    assert captured["auth"] == f"Bearer {_MOCK_SECRET}"
    assert "agent=agent-x" in captured["url"]
    assert "version=1.0" in captured["url"]
    # 终态 status 以多参数下传（list_runs 默认白名单）
    for s in ("completed", "partial_failed", "timeout", "cancelled"):
        assert f"status={s}" in captured["url"]


def test_offline_client_tolerates_missing_keys_and_http_error():
    def ok(request):
        return httpx.Response(200, json={})  # 缺 runs/versions 键 → [] 容错

    def bad(request):
        return httpx.Response(500, json={})  # HTTP ≥400 → OfflineReadError（不退避重试）

    async def go_list():
        c = _mock_offline(ok)
        try:
            return await c.list_runs(agent="a"), await c.agent_versions(agent="a")
        finally:
            await c.aclose()

    assert _run(go_list()) == ([], [])

    async def go_bad():
        c = _mock_offline(bad)
        try:
            await c.list_runs(agent="a")
        finally:
            await c.aclose()

    try:
        _run(go_bad())
        assert False, "应抛 OfflineReadError"
    except OfflineReadError:
        pass


def test_offline_client_network_error_after_retry_raises():
    # httpx 网络异常（无 transport → 连接失败）连续重试后 OfflineReadError
    async def go():
        c = OfflineClient("http://127.0.0.1:1", secret=_MOCK_SECRET)
        try:
            await c.list_runs(agent="a")
        finally:
            await c.aclose()

    try:
        _run(go())
        assert False, "应抛 OfflineReadError"
    except OfflineReadError:
        pass


# ---------- HTTP 鉴权负例（真实 deps 链 + FakeAsyncSession） ----------


def _app(session):
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: session
    return app


def test_backflow_write_requires_auth():
    # 无 token → 401；viewer token 可触达 claim（cluster 不存在 → 404 而非 403）
    app = _app(FakeAsyncSession(users=[_admin_user(role="viewer")]))
    viewer_hdr = {"Authorization": f"Bearer {_admin_token('viewer')}"}
    with _enter(app) as c:
        assert c.post("/api/v1/backflow/clusters/1/claim", json={
            "fix_version": "1.4.0"}).status_code == 401
        r = c.post("/api/v1/backflow/clusters/999/claim",
                   headers=viewer_hdr, json={"fix_version": "1.4.0"})
        assert r.status_code == 404 and r.json()["code"] == "ERR_CLUSTER_0001"


def test_backflow_fixed_review_admin_only():
    app = _app(FakeAsyncSession(users=[_admin_user(role="viewer")]))
    viewer_hdr = {"Authorization": f"Bearer {_admin_token('viewer')}"}
    with _enter(app) as c:
        r = c.post("/api/v1/backflow/clusters/1/fixed-review",
                   headers=viewer_hdr, json={"approve": True})
        assert r.status_code == 403 and r.json()["code"] == "ERR_AUTH_0002"
    # admin 到位后 cluster 不存在 → 404（FakeAsyncSession.get 非白名单模型 → None）
    app2 = _app(FakeAsyncSession(users=[_admin_user()]))
    with _enter(app2) as c:
        r = c.post("/api/v1/backflow/clusters/999/fixed-review",
                   headers={"Authorization": f"Bearer {_admin_token()}"},
                   json={"approve": True})
        assert r.status_code == 404 and r.json()["code"] == "ERR_CLUSTER_0001"


def test_backflow_read_overview_requires_auth():
    with _enter(_app(FakeAsyncSession())) as c:
        assert c.get("/api/v1/backflow/overview").status_code == 401


# ---------- 迁移守卫（DB-free raise 分支直打；写面语义留 claim_probe） ----------


def _assert_code(coro, code):
    try:
        _run(coro)
    except AppError as e:
        assert e.code == code, f"期望 {code}，实得 {e.code}"
        return e
    raise AssertionError(f"应抛 AppError({code})，未抛")


def test_claim_guard_rejects_non_open():
    sess = FakeAsyncSession()
    _assert_code(claim_flow.claim_cluster(
        sess, ns(id=1, status="claim"), fix_version="1.4.0", note=None, k=2, actor_id=1),
        "ERR_CLUSTER_0003")


def test_claim_guard_rejects_empty_fix_version():
    sess = FakeAsyncSession()
    _assert_code(claim_flow.claim_cluster(
        sess, ns(id=1, status="open"), fix_version="   ", note=None, k=2, actor_id=1),
        "ERR_CLUSTER_0003")


def test_claim_guard_rejects_k_out_of_range():
    # k 显式传入跳过 dict_config 读 → 值域 {1,2} 超域在触 DB 前即 400
    sess = FakeAsyncSession()
    cl = ns(id=1, status="open")
    for bad in (0, 3, 99):
        _assert_code(claim_flow.claim_cluster(
            sess, cl, fix_version="1.4.0", note=None, k=bad, actor_id=1),
            "ERR_CLUSTER_0003")


def test_ignore_guard_rejects_non_open():
    sess = FakeAsyncSession()
    _assert_code(claim_flow.ignore_cluster(
        sess, ns(id=2, status="claim"), actor_id=1), "ERR_CLUSTER_0003")


def test_reopen_guard_rejects_non_reopenable():
    sess = FakeAsyncSession()
    # 可 reopen 源 = fixed/inactive/needs_review；claim/open 拒绝
    _assert_code(claim_flow.reopen_cluster(
        sess, ns(id=3, status="claim"), note=None, actor_id=1), "ERR_CLUSTER_0003")


def test_fixed_review_guard_rejects_non_claim():
    sess = FakeAsyncSession()
    _assert_code(claim_flow.fixed_review(
        sess, ns(id=4, status="fixed"), approve=True, actor_id=1), "ERR_CLUSTER_0003")


def test_needs_review_resolve_guard_rejects_bad_state_and_action():
    sess = FakeAsyncSession()
    # 非 needs_review 源 → 拒
    _assert_code(claim_flow.needs_review_resolve_single(
        sess, ns(id=5, status="claim", needs_review_reason="na"),
        action="reopen_cluster", note=None, actor_id=1), "ERR_CLUSTER_0003")
    # action 超域 → 拒
    _assert_code(claim_flow.needs_review_resolve_single(
        sess, ns(id=5, status="needs_review", needs_review_reason="na"),
        action="delete", note=None, actor_id=1), "ERR_CLUSTER_0003")


def test_needs_review_resolve_escalated_record_only():
    # §16 通道 v1：只写 conv 保留状态（无 CAS → FakeAsyncSession.add 可验整条语义）
    sess = FakeAsyncSession()
    cl = ns(id=7, status="needs_review", needs_review_reason="reentry_same_version")
    out = _run(claim_flow.needs_review_resolve_single(
        sess, cl, action="escalated", note="待研发评估", actor_id=1))
    assert out == {"cluster_id": 7, "status": "needs_review", "action": "escalated"}
    assert len(sess.added) == 1
    rec = sess.added[0]
    assert rec.action == "needs_review_resolve" and rec.actor_user_id == 1
    assert rec.detail and "escalated" in rec.detail and len(rec.detail) <= 1024


def test_batch_resolve_rejects_bad_action():
    sess = FakeAsyncSession()
    # action 值域校验在 _load_batch 前（DB-free）
    _assert_code(batch_flow.resolve_batch(
        sess, batch_id=1, action="delete_all", actor_id=1), "ERR_CLUSTER_0003")


# ---------- worker recheck：offline 未配停轮（E-7 安全默认，触 DB 前返回 0） ----------


def test_recheck_offline_unset_stops_round():
    from app.worker.recheck_job import run_recheck

    # offline_base_url 空 → 停轮返回 0；engine=None 证明未触 DB
    assert _run(run_recheck(None, ns(offline_base_url=""))) == 0
