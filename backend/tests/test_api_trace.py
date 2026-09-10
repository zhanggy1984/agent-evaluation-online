"""trace API 端点单测（detail §8.2/§8.8 鉴权 + §14.4 护栏）。

FakeES 替 ES 查询（录 body 断言检索护栏/正文开关）；FakeAsyncSession 替 dict_config 读
（无行 → 回退 seed 默认 7d/3000ms）。鉴权走真实 deps 链：签发 viewer/admin JWT →
require_viewer 放行、非 viewer 角色 403。
"""
import time
from contextlib import contextmanager

from _fakes import FakeAsyncSession, FakeES, es_hits, ns
from elasticsearch.exceptions import TransportError

from app.core.config import Settings
from app.core.db import get_session
from app.core.security import create_access_token
from app.main import create_app

_TRACE = "tr-9f2c1a"
_AGENT = "good-question"


def _settings():
    return Settings(app_env="test", resource_env="dev", jwt_secret="mock-secret-" * 8)


def _viewer(role="viewer"):
    return ns(id=1, username="alice", display_name="查看者", password_hash="x",
              role=role, status=1)


def _token(role="viewer"):
    return create_access_token(_settings(), 1, role)


def _fake_es(response=None, exc=None):
    return FakeES(response=response, exc=exc)


@contextmanager
def _enter(app, fake_es):
    """TestClient 上下文（lifespan 拉起后）把 state.es_query 换成 fake 再 yield。"""
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        app.state.es_query = fake_es
        yield client


def _auth_hdr(role="viewer"):
    return {"Authorization": f"Bearer {_token(role)}"}


# ---------- 鉴权（§8.8） ----------


def test_trace_list_denies_non_viewer_role():
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_viewer("ops")])
    with _enter(app, _fake_es()) as c:
        r = c.get("/api/v1/traces", headers=_auth_hdr("ops"))
    assert r.status_code == 403
    assert r.json()["code"] == "ERR_AUTH_0002"


def test_trace_list_denies_no_token():
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_viewer()])
    with _enter(app, _fake_es()) as c:
        r = c.get("/api/v1/traces")
    assert r.status_code == 401 and r.json()["code"] == "ERR_AUTH_0001"


# ---------- 列表（§8.2 检索护栏/正文开关） ----------


def test_trace_list_default_window_and_keyword_body_off():
    es = _fake_es(es_hits(1, [{"agent": _AGENT, "trace_id": _TRACE, "node": "request",
                               "status": "error", "error_msg": "数据库超时", "ts": 111}]))
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_viewer()])
    before = int(time.time() * 1000)
    with _enter(app, es) as c:
        r = c.get("/api/v1/traces", headers=_auth_hdr(),
                  params={"keyword": "超时", "agent": _AGENT})
    after = int(time.time() * 1000)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1 and body["items"][0]["trace_id"] == _TRACE
    # 检索面：keyword 走 multi_match；7d 缺省窗 = now - keyword_search_days(seed 7)
    _, q = es.calls[0]
    fields = q["query"]["bool"]["must"][0]["multi_match"]["fields"]
    assert "error_msg" in fields and "log_message" not in fields  # body_search=false
    gte = q["query"]["bool"]["filter"][-1]["range"]["ts"]["gte"]
    assert before - 7 * 86_400_000 - 5_000 <= gte <= after - 7 * 86_400_000


def test_trace_list_empty_page_when_no_hits():
    es = _fake_es(es_hits(0, []))
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_viewer()])
    with _enter(app, es) as c:
        r = c.get("/api/v1/traces", headers=_auth_hdr())
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_trace_list_guards_offset_over_200():
    # §14.4 深翻页上限：offset ≥ 200 → ERR_TRACE_0002（慢查询引导缩小范围）
    es = _fake_es(es_hits(0, []))
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_viewer()])
    with _enter(app, es) as c:
        r = c.get("/api/v1/traces", headers=_auth_hdr(),
                  params={"trace_id": _TRACE, "page": 21, "page_size": 20})
    assert r.status_code == 400 and r.json()["code"] == "ERR_TRACE_0002"
    assert es.calls == []  # 未触 ES：纯参数护栏


def test_trace_list_es_timeout_maps_400():
    es = _fake_es(exc=TransportError("模拟超时"))
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_viewer()])
    with _enter(app, es) as c:
        r = c.get("/api/v1/traces", headers=_auth_hdr(), params={"trace_id": _TRACE})
    assert r.status_code == 400 and r.json()["code"] == "ERR_TRACE_0002"


# ---------- 详情（§8.2 正文保护/截断/404） ----------


def _evt_source(seq=0, node="request", status="ok", **extra):
    base = {"agent": _AGENT, "trace_id": _TRACE, "event_kind": "event", "seq": seq,
            "node": node, "interface": "POST /api/chat", "status": status,
            "ts": 1000 + seq, "parent": None, "branch": None}
    base.update(extra)
    return base


def test_trace_detail_ok_blank_body_by_default():
    src = _evt_source(seq=0, input='{"q":"hi"}', output="ok")
    es = _fake_es(es_hits(1, [src]))
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_viewer()])
    with _enter(app, es) as c:
        r = c.get(f"/api/v1/traces/{_AGENT}/{_TRACE}", headers=_auth_hdr())
    assert r.status_code == 200
    detail = r.json()
    assert detail["agent"] == _AGENT and detail["total"] == 1 and detail["truncated"] is False
    row = detail["events"][0]
    assert row["seq"] == 0 and row["input"] is None and row["output"] is None  # 正文置空


def test_trace_detail_body_search_true_returns_body():
    src = _evt_source(seq=0, input='{"q":"hi"}', output='{"answer":"ok"}')
    es = _fake_es(es_hits(1, [src]))
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_viewer()])
    with _enter(app, es) as c:
        r = c.get(f"/api/v1/traces/{_AGENT}/{_TRACE}", headers=_auth_hdr(),
                  params={"body_search": "true"})
    assert r.status_code == 200
    assert r.json()["events"][0]["input"] == '{"q":"hi"}'


def test_trace_detail_not_found_404():
    es = _fake_es(es_hits(0, []))
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_viewer()])
    with _enter(app, es) as c:
        r = c.get(f"/api/v1/traces/{_AGENT}/tr-missing", headers=_auth_hdr())
    assert r.status_code == 404
    assert r.json()["code"] == "ERR_TRACE_0001"


def test_trace_detail_truncated_when_over_500():
    # §8.2 单 trace ≤500：store 报 total=501（>500）→ truncated=True，且 detail 仍有行可回
    es = _fake_es({"hits": {"total": {"value": 501, "relation": "eq"},
                            "hits": [{"_source": _evt_source(seq=0)}]}})
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_viewer()])
    with _enter(app, es) as c:
        r = c.get(f"/api/v1/traces/{_AGENT}/{_TRACE}", headers=_auth_hdr())
    assert r.status_code == 200
    assert r.json()["truncated"] is True
    # 详情查询 event_kind=event（log 行不进详情，走 /logs）
    assert {"term": {"event_kind": "event"}} in es.calls[0][1]["query"]["bool"]["must"]


# ---------- 日志懒加载（§8.2） ----------


def test_trace_logs_paginated_and_body_blanked():
    srcs = [{"agent": _AGENT, "trace_id": _TRACE, "event_kind": "log", "seq": 1,
             "ts": 1001, "log_level": "INFO", "log_message": "start=1"},]
    es = _fake_es(es_hits(1, srcs))
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_viewer()])
    with _enter(app, es) as c:
        r = c.get(f"/api/v1/traces/{_AGENT}/{_TRACE}/logs", headers=_auth_hdr(),
                  params={"page": 2, "page_size": 50})
    assert r.status_code == 200
    page = r.json()
    assert page["total"] == 1 and page["page"] == 2
    assert page["items"][0]["log_message"] is None  # 正文默认置空
    assert {"term": {"event_kind": "log"}} in es.calls[0][1]["query"]["bool"]["must"]
    assert es.calls[0][1]["from"] == 50 and es.calls[0][1]["size"] == 50


def test_trace_logs_body_search_true_returns_message():
    srcs = [{"agent": _AGENT, "trace_id": _TRACE, "event_kind": "log", "seq": 1,
             "ts": 1001, "log_level": "ERROR", "log_message": "connection refused"}]
    es = _fake_es(es_hits(1, srcs))
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_viewer()])
    with _enter(app, es) as c:
        r = c.get(f"/api/v1/traces/{_AGENT}/{_TRACE}/logs", headers=_auth_hdr(),
                  params={"body_search": "true"})
    assert r.status_code == 200
    assert r.json()["items"][0]["log_message"] == "connection refused"
