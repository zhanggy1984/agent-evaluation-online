"""P2-3 backflow 单测（detail §7.2/§7.3/§7.4/§8.7/§8.8）：ack 矩阵 + requeue 守卫 + 鉴权负例。

- ack_decide：§7.3 前置矩阵全分支（draft/active/invalidated + R2 例外 gate link 现行
  invalidate_reason + 幂等 noop + 未知 action）——纯函数直打。
- requeue_guard_errors：R-24 守卫链各分支 + 防抖 5min 边界（纯函数直打）。
- cursor / since_ts ISO：encode/decode roundtrip + naive UTC 归一（纯函数直打）。
- HTTP 鉴权负例（真实 deps 链 + FakeAsyncSession，仿 test_api_trace）：/pull 缺/错/
  未配置 secret → ERR_PULL_0001；schema_version 不符 → ERR_PULL_0002；case_type 非白名单
  → 空集；坏 next_token/since_ts → ERR_PULL_0002；ack 未知 payload → ERR_PULL_0003；
  backflow 非 admin → ERR_AUTH_0002、link 不存在 → ERR_CLUSTER_0001。
  DB 写面语义（多行扫/分页/CAS 竞态）留给集成探针 pull_probe（FakeAsyncSession 装不下）。
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from _fakes import FakeAsyncSession, ns

from app.backflow.ack import _iso_to_naive, ack_decide, decode_cursor, encode_cursor
from app.backflow.requeue import requeue_guard_errors
from app.core.config import Settings
from app.core.db import get_session
from app.core.security import create_access_token
from app.main import create_app

_PAYLOAD = "pl-2f9c1a"
_MOCK_SECRET = "s3cret-evaluator"  # 测试 mock 凭证（非真实部署值）


def _settings(mock_secret=_MOCK_SECRET):
    return Settings(
        app_env="test", resource_env="dev",
        jwt_secret="mock-secret-" * 8,
        evaluator_service_secret=mock_secret,
    )


def _ns_link(**over):
    base = dict(
        id=1, cluster_id=1, payload_id=_PAYLOAD, case_id=None,
        case_type="regression_error", offline_status="invalidated",
        verify_status="pending", invalidate_reason="online_content_gap",
        invalidated_by=2, payload_json="{}",
        assembled_ts=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=6),
    )
    base.update(over)
    return ns(**base)


@contextmanager
def _enter(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client


def _eval_hdr(token=_MOCK_SECRET):
    return {"Authorization": f"Bearer {token}"}


def _admin_user(role="admin"):
    return ns(id=1, username="admin1", display_name="管理员", password_hash="x",
              role=role, status=1)


def _admin_token():
    return create_access_token(_settings(), 1, "admin")


# ---------- ack_decide：§7.3 前置矩阵（纯函数） ----------


def test_ack_draft_matrix():
    # assembled → draft 放行（case_id 可选）；已 draft → noop；active/invalidated → 违规
    assert ack_decide("assembled", "draft", current_reason=None,
                      has_case_id=False, reason=None)[0] == "apply"
    assert ack_decide("draft", "draft", current_reason=None,
                      has_case_id=False, reason=None)[0] == "noop"
    assert ack_decide("active", "draft", current_reason=None,
                      has_case_id=False, reason=None)[0] == "violation"
    assert ack_decide("invalidated", "draft", current_reason="manual_invalidate",
                      has_case_id=False, reason=None)[0] == "violation"


def test_ack_active_requires_case_id():
    # assembled/draft → active 必带 case_id；缺 → 违规，detail 提示 case_id
    outcome, target, detail = ack_decide(
        "assembled", "active", current_reason=None, has_case_id=False, reason=None
    )
    assert outcome == "violation" and "case_id" in detail
    assert ack_decide("assembled", "active", current_reason=None,
                      has_case_id=True, reason=None) == ("apply", "active", None)
    assert ack_decide("draft", "active", current_reason="manual_invalidate",
                      has_case_id=True, reason=None)[0] == "apply"
    # 已 active → noop（幂等 E-15，即使缺 case_id 也不报错）
    assert ack_decide("active", "active", current_reason=None,
                      has_case_id=False, reason=None)[0] == "noop"


def test_ack_active_from_invalidated_r2_gate_on_stored_reason():
    # R2 例外 gate link 现行 invalidate_reason=offline_cap_gap（重扫自愈回写），仍需 case_id
    ok = ack_decide("invalidated", "active", current_reason="offline_cap_gap",
                    has_case_id=True, reason=None)
    assert ok == ("apply", "active", None)
    # 缺 case_id → 违规
    outcome, _, detail = ack_decide("invalidated", "active",
                                    current_reason="offline_cap_gap",
                                    has_case_id=False, reason=None)
    assert outcome == "violation" and "case_id" in detail
    # 现行 reason ≠ offline_cap_gap（online_content_gap / manual_invalidate / None）→ 违规
    for stored in ("online_content_gap", "manual_invalidate", None):
        outcome, _, detail = ack_decide("invalidated", "active",
                                        current_reason=stored,
                                        has_case_id=True, reason=None)
        assert outcome == "violation" and "requeue" in detail


def test_ack_invalidated_requires_structured_reason():
    # assembled/draft → invalidated 必带结构化 reason（值域内码）
    assert ack_decide("assembled", "invalidated", current_reason=None,
                      has_case_id=False, reason="online_content_gap") == (
        "apply", "invalidated", None)
    assert ack_decide("draft", "invalidated", current_reason=None,
                      has_case_id=True, reason="manual_invalidate")[0] == "apply"
    # 缺 reason / 坏码 → 违规
    for bad_reason in (None, "not_a_code"):
        outcome, _, detail = ack_decide("assembled", "invalidated",
                                        current_reason=None, has_case_id=False,
                                        reason=bad_reason)
        assert outcome == "violation"
    # 已 invalidated → noop（幂等，当前==目标）
    assert ack_decide("invalidated", "invalidated", current_reason="offline_cap_gap",
                      has_case_id=False, reason="offline_cap_gap")[0] == "noop"
    # active → invalidated 不允许（active 后不提供人工驳回，走 superseded+reopen）
    assert ack_decide("active", "invalidated", current_reason=None,
                      has_case_id=False, reason="manual_invalidate")[0] == "violation"


def test_ack_unknown_action():
    outcome, _, _ = ack_decide("assembled", "claimed", current_reason=None,
                               has_case_id=False, reason=None)
    assert outcome == "violation"


def test_ack_illegal_transition_reports_message():
    # draft → … 之外的状态迁移给可读 message（非硬崩）
    _, _, detail = ack_decide("assembled", "active", current_reason=None,
                              has_case_id=False, reason=None)
    assert "case_id" in detail


# ---------- requeue_guard_errors：§7.4 R-24 守卫链（纯函数） ----------


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_requeue_guard_passes_open_cluster_after_debounce():
    now = _now()
    link = _ns_link(assembled_ts=now - timedelta(minutes=6))
    cluster = ns(status="open")
    assert requeue_guard_errors(link, cluster, now=now) is None


def test_requeue_guard_status_checks():
    now = _now()
    cluster = ns(status="open")
    assert "仅 invalidated" in requeue_guard_errors(
        _ns_link(offline_status="assembled"), cluster, now=now)
    assert "verify_status=pending" in requeue_guard_errors(
        _ns_link(verify_status="passed"), cluster, now=now)
    # cluster 缺失 / closed（fixed/inactive）→ 禁（需 superseded+reopen 重建）
    assert "cluster 不存在" in requeue_guard_errors(_ns_link(), None, now=now)
    for closed in ("fixed", "inactive"):
        msg = requeue_guard_errors(
            _ns_link(), ns(status=closed), now=now)
        assert "closed" in msg and "superseded" in msg


def test_requeue_guard_debounce_boundary():
    now = _now()
    cluster = ns(status="needs_review")
    # 恰 <5min → 拦（锚 = assembled_ts）；恰 =5min → 放（>= 5min 语义）
    just_below = now - timedelta(minutes=5) + timedelta(seconds=1)
    assert "防抖" in requeue_guard_errors(_ns_link(assembled_ts=just_below), cluster, now=now)
    exactly = now - timedelta(minutes=5)
    assert requeue_guard_errors(_ns_link(assembled_ts=exactly), cluster, now=now) is None
    assert requeue_guard_errors(_ns_link(assembled_ts=now), cluster, now=now) is not None


# ---------- pull cursor / since_ts（纯函数） ----------


def test_cursor_roundtrip():
    ts = datetime(2026, 9, 9, 1, 2, 3, 123456)
    cur = encode_cursor(ts, 42)
    assert decode_cursor(cur) == (ts.replace(tzinfo=None), 42)


def test_since_ts_iso_parses_to_naive_utc():
    dt = _iso_to_naive("2026-09-09T01:02:03.123456Z")
    assert dt == datetime(2026, 9, 9, 1, 2, 3, 123456) and dt.tzinfo is None
    dt2 = _iso_to_naive("2026-09-09T01:02:03.123+00:00")
    assert dt2 == datetime(2026, 9, 9, 1, 2, 3, 123000) and dt2.tzinfo is None


# ---------- HTTP 鉴权负例（真实 deps 链 + FakeAsyncSession，DB 前置判定在 auth 后） ----------


def _pull_app(session=None, mock_secret=_MOCK_SECRET):
    app = create_app(_settings(mock_secret=mock_secret))
    app.dependency_overrides[get_session] = lambda: session or FakeAsyncSession()
    return app


def test_pull_requires_evaluator_secret():
    with _enter(_pull_app()) as c:
        assert c.post("/api/v1/pull/payloads", json={}).status_code == 401
        r = c.post("/api/v1/pull/payloads", headers=_eval_hdr("wrong"))
        assert r.status_code == 401 and r.json()["code"] == "ERR_PULL_0001"


def test_pull_fail_closed_when_secret_unset():
    # 未配置 evaluator_service_secret → /pull/* 全 401（fail-closed，不因无拉取而放开）
    with _enter(_pull_app(mock_secret="")) as c:
        r = c.post("/api/v1/pull/payloads", headers=_eval_hdr("anything"))
        assert r.status_code == 401 and r.json()["code"] == "ERR_PULL_0001"


def _pull_body(**over):
    body = dict(schema_version="1.0", case_type="regression_error", limit=100)
    body.update(over)
    return body


def test_pull_rejects_wrong_schema_version():
    with _enter(_pull_app()) as c:
        r = c.post("/api/v1/pull/payloads", headers=_eval_hdr(),
                   json=_pull_body(schema_version="2.0"))
        assert r.status_code == 400 and r.json()["code"] == "ERR_PULL_0002"


def test_pull_unknown_case_type_returns_empty_200():
    # §12 加固/X-5：case_type 非白名单 → 200 空集而非全量泄漏（不触 DB）
    with _enter(_pull_app()) as c:
        r = c.post("/api/v1/pull/payloads", headers=_eval_hdr(),
                   json=_pull_body(case_type="random_access"))
        assert r.status_code == 200 and r.json() == {"payloads": [], "next_token": None}


def test_pull_bad_cursor_or_since_ts_400():
    with _enter(_pull_app()) as c:
        r = c.post("/api/v1/pull/payloads", headers=_eval_hdr(),
                   json=_pull_body(next_token="@@not-base64@@"))
        assert r.status_code == 400 and r.json()["code"] == "ERR_PULL_0002"
        r2 = c.post("/api/v1/pull/payloads", headers=_eval_hdr(),
                    json=_pull_body(since_ts="not-a-timestamp"))
        assert r2.status_code == 400 and r2.json()["code"] == "ERR_PULL_0002"


def test_pull_ack_unknown_payload_404():
    # apply_ack SELECT 定位未知 payload → ERR_PULL_0003（FakeAsyncSession 无行 → 未知）
    with _enter(_pull_app()) as c:
        r = c.post("/api/v1/pull/ack", headers=_eval_hdr(),
                   json={"payload_id": "pl-nonexistent", "action": "draft"})
        assert r.status_code == 404 and r.json()["code"] == "ERR_PULL_0003"


def test_pull_ack_missing_body_field_422():
    with _enter(_pull_app()) as c:
        r = c.post("/api/v1/pull/ack", headers=_eval_hdr(),
                   json={"payload_id": _PAYLOAD})
        assert r.status_code == 422  # action 必填（pydantic）


def test_backflow_requires_admin():
    # viewer token → ERR_AUTH_0002(403)；无 token → 401
    app = _pull_app()
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(
        users=[_admin_user(role="viewer")])
    viewer_hdr = {"Authorization": f"Bearer {create_access_token(_settings(), 1, 'viewer')}"}
    with _enter(app) as c:
        r = c.post("/api/v1/backflow/links/1/invalidate", headers=viewer_hdr, json={})
        assert r.status_code == 403 and r.json()["code"] == "ERR_AUTH_0002"
        r2 = c.post("/api/v1/backflow/links/1/invalidate", json={})
        assert r2.status_code == 401


def test_backflow_link_not_found_404():
    # admin 到位后 link 不存在 → ERR_CLUSTER_0001（FakeAsyncSession.get 非白名单模型 → None）
    app = _pull_app()
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_admin_user()])
    hdr = {"Authorization": f"Bearer {_admin_token()}"}
    with _enter(app) as c:
        r = c.post("/api/v1/backflow/links/999/invalidate", headers=hdr, json={})
        assert r.status_code == 404 and r.json()["code"] == "ERR_CLUSTER_0001"
        r2 = c.post("/api/v1/backflow/links/999/requeue", headers=hdr)
        assert r2.status_code == 404 and r2.json()["code"] == "ERR_CLUSTER_0001"
