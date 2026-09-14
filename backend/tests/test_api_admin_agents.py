"""§8.5 字典面单测（批 2a-1）：`GET /agents`、`toggle`、接口列表、接口补标。

**替身边界（明写，防误读为「已验完」）**：
- `FakeAsyncSession` 按等值匹配**只取首行** ⇒ 多行列表语义**不在覆盖内**（如「多个 agent
  各自的 `interface_count`」、>`_INTERFACE_MAX` 的截断分支）——由真库探针覆盖。
- 唯一键冲突、`updated_by` 在真库的落库语义、截断上限：单测验不了，由
  `tests/integration/admin_agents_probe.py` 在真 MySQL 上验。
- `GET /agents/{id}/health` **不在本文件**：它读 ES 事件 index（验证面不同），单独一批。

**起 client 必须用 `with`**：`app.state.settings` 是在 lifespan 里挂的（`main.py:37`），
不用 `with` 则 lifespan 不跑 ⇒ 解码 token 时读 state 直接 `AttributeError`
（同 `test_api_admin.py` 的 `with _client(session)[0] as c:` 惯例）。
"""
from datetime import datetime

import pytest
from _fakes import FakeAsyncSession, ns

from app.core.config import Settings
from app.core.db import get_session
from app.core.security import create_access_token
from app.main import create_app
from app.models.agent import Agent, Interface
from app.models.error_flow import ConversionRecord

_AGENT_ID = 7
_IFACE_ID = 11
_TS = datetime(2026, 9, 14, 10, 0, 0)


def _settings():
    return Settings(app_env="test", resource_env="dev", jwt_secret="mock-secret-" * 8)


def _user(role="admin", username="root"):
    return ns(
        id=1,
        username=username,
        display_name="管理员",
        password_hash="x",
        role=role,
        status=1,
        created_at=None,
    )


def _agent(enable=1, name="agent-a", aid=_AGENT_ID):
    return ns(
        id=aid,
        name=name,
        display_name=name.upper(),
        base_url=None,
        enable=enable,
        backflow_allow=1,
        route_source="auto_register",
    )


def _iface(llm=0, llm_source="config", llm_suspect=0, body_search=0, agent_id=_AGENT_ID):
    return ns(
        id=_IFACE_ID,
        agent_id=agent_id,
        interface="GET /api/x",
        method="GET",
        path="/api/x",
        llm=llm,
        llm_source=llm_source,
        llm_suspect=llm_suspect,
        body_search=body_search,
        status=1,
        first_seen_ts=_TS,
        last_seen_ts=_TS,
        updated_by=None,
    )


def _audits(session):
    return [o for o in session.added if isinstance(o, ConversionRecord)]


def _client(session):
    """返回**已进 lifespan 上下文**的 TestClient（`with _client(…) as c:` 用）。"""
    from fastapi.testclient import TestClient

    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def _hdr(role="admin"):
    return {"Authorization": f"Bearer {create_access_token(_settings(), 1, role)}"}


def _session(agents=(), ifaces=(), role="admin"):
    """`users=` 必须带上 `sub=1` 的账号：`get_current_user` 走 `session.get(User,…)` 查库取角色。"""
    return FakeAsyncSession(
        users=[_user(role)],
        registry={Agent: list(agents), Interface: list(ifaces)},
    )


# ---------- 鉴权（§8.8：401/403 双证） ----------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/admin/agents"),
        ("post", f"/api/v1/admin/agents/{_AGENT_ID}/toggle"),
        ("get", f"/api/v1/admin/agents/{_AGENT_ID}/interfaces"),
        ("put", f"/api/v1/admin/interfaces/{_IFACE_ID}"),
    ],
)
def test_endpoints_require_auth(method, path):
    """四个端点无 token ⇒ 401 `ERR_AUTH_0001`（缺鉴权面）。"""
    with _client(_session([_agent()], [_iface()])) as c:
        r = getattr(c, method)(path, **({"json": {}} if method == "put" else {}))
    assert r.status_code == 401
    assert r.json()["code"] == "ERR_AUTH_0001"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/admin/agents"),
        ("post", f"/api/v1/admin/agents/{_AGENT_ID}/toggle"),
        ("get", f"/api/v1/admin/agents/{_AGENT_ID}/interfaces"),
        ("put", f"/api/v1/admin/interfaces/{_IFACE_ID}"),
    ],
)
def test_endpoints_forbid_viewer(method, path):
    """viewer 角色 ⇒ 403 `ERR_AUTH_0002`（角色门控面；角色查库取，不信任 claims）。"""
    s = _session([_agent()], [_iface()], role="viewer")
    with _client(s) as c:
        r = getattr(c, method)(
            path, headers=_hdr("viewer"), **({"json": {}} if method == "put" else {})
        )
    assert r.status_code == 403
    assert r.json()["code"] == "ERR_AUTH_0002"


# ---------- GET /agents ----------


def test_list_agents_returns_dict_row_with_interface_count():
    """清单来自 MySQL 字典面（非 ES），并带该 agent 的接口条数。"""
    with _client(_session([_agent()], [_iface()])) as c:
        r = c.get("/api/v1/admin/agents", headers=_hdr())
    assert r.status_code == 200
    assert r.json() == [
        {
            "id": _AGENT_ID,
            "name": "agent-a",
            "display_name": "AGENT-A",
            "enable": 1,
            "backflow_allow": 1,
            "route_source": "auto_register",
            "base_url": None,
            "interface_count": 1,
        }
    ]


# ---------- POST /agents/{id}/toggle ----------


def test_toggle_flips_enable_and_writes_audit():
    """翻转 `enable` 并落审计（`agent_toggle`）——含「谁改的」。"""
    s = _session([_agent(enable=1)])
    with _client(s) as c:
        r = c.post(f"/api/v1/admin/agents/{_AGENT_ID}/toggle", headers=_hdr())
    assert r.status_code == 200
    assert r.json()["enable"] == 0
    assert s.registry[Agent][0].enable == 0

    rows = _audits(s)
    assert len(rows) == 1
    assert rows[0].action == "agent_toggle"
    assert rows[0].cluster_id is None
    assert rows[0].actor_user_id == 1
    assert "enable 1→0" in rows[0].detail
    assert s.commits == 1


def test_toggle_back_to_enabled():
    """再翻一次回 1（验证语义是「翻转」而非「置 0」）。"""
    s = _session([_agent(enable=0)])
    with _client(s) as c:
        r = c.post(f"/api/v1/admin/agents/{_AGENT_ID}/toggle", headers=_hdr())
    assert r.json()["enable"] == 1
    assert "enable 0→1" in _audits(s)[0].detail


def test_toggle_unknown_agent_rejected():
    """id 不存在 ⇒ 400 `ERR_CONFIG_0001`，且**不写审计、不提交**。"""
    s = _session([])
    with _client(s) as c:
        r = c.post("/api/v1/admin/agents/999/toggle", headers=_hdr())
    assert r.status_code == 400
    assert r.json()["code"] == "ERR_CONFIG_0001"
    assert _audits(s) == []
    assert s.commits == 0


# ---------- GET /agents/{id}/interfaces ----------


def test_list_interfaces_returns_dict_fields():
    with _client(_session([_agent()], [_iface(llm=1, llm_source="manual")])) as c:
        r = c.get(f"/api/v1/admin/agents/{_AGENT_ID}/interfaces", headers=_hdr())
    assert r.status_code == 200
    body = r.json()
    assert body["truncated"] is False
    assert body["items"][0]["interface"] == "GET /api/x"
    assert body["items"][0]["llm_source"] == "manual"
    assert body["items"][0]["agent_id"] == _AGENT_ID


def test_list_interfaces_empty_for_other_agent():
    """按 `agent_id` 过滤：别的 agent 的接口不出现（等值条件不匹配 ⇒ 替身返回空）。"""
    with _client(_session([_agent()], [])) as c:
        r = c.get("/api/v1/admin/agents/77/interfaces", headers=_hdr())
    assert r.status_code == 200
    assert r.json() == {"items": [], "truncated": False}


# ---------- PUT /interfaces/{id} ----------


def test_put_interface_confirm_llm_clears_suspect_and_audits():
    """`llm=1` 连带清 `llm_suspect`（疑似漏标告警由人工确认解除）+ 落审计。"""
    s = _session(ifaces=[_iface(llm=0, llm_suspect=1)])
    with _client(s) as c:
        r = c.put(
            f"/api/v1/admin/interfaces/{_IFACE_ID}",
            headers=_hdr(),
            json={"llm": 1, "llm_source": "manual"},
        )
    assert r.status_code == 200
    assert r.json()["llm"] == 1
    assert r.json()["llm_suspect"] == 0
    assert r.json()["llm_source"] == "manual"

    row = s.registry[Interface][0]
    assert (row.llm, row.llm_suspect, row.llm_source) == (1, 0, "manual")
    assert row.updated_by == "root"  # 由 deps 从 DB 取的管理员用户名

    audits = _audits(s)
    assert len(audits) == 1
    assert audits[0].action == "interface_dict_change"
    assert "llm_suspect 1→0" in audits[0].detail


def test_put_interface_body_search_only():
    """只改 `body_search` 不动 llm 面（字段缺省 = 不修改）。"""
    s = _session(ifaces=[_iface(llm=0, llm_suspect=1)])
    with _client(s) as c:
        r = c.put(
            f"/api/v1/admin/interfaces/{_IFACE_ID}", headers=_hdr(), json={"body_search": 1}
        )
    assert r.status_code == 200
    assert r.json()["body_search"] == 1
    assert r.json()["llm_suspect"] == 1  # 未确认 llm ⇒ 疑似态保留
    assert "llm_suspect" not in _audits(s)[0].detail


def test_put_interface_no_change_writes_no_audit():
    """空改动不写审计（否则审计表被「点了但没改」的行淹掉），但仍返回当前态。"""
    s = _session(ifaces=[_iface(llm=1)])
    with _client(s) as c:
        r = c.put(f"/api/v1/admin/interfaces/{_IFACE_ID}", headers=_hdr(), json={"llm": 1})
    assert r.status_code == 200
    assert r.json()["llm"] == 1
    assert _audits(s) == []
    assert s.commits == 0


@pytest.mark.parametrize(
    ("payload", "msg"),
    [
        ({"llm_source": "auto_observed"}, "本端点只接受 manual"),
        ({"llm": 2}, "llm 非法"),
        ({"body_search": -1}, "body_search 非法"),
    ],
)
def test_put_interface_rejects_bad_values(payload, msg):
    """非法取值 / 非人工来源 ⇒ 400，且不落库、不写审计。"""
    s = _session(ifaces=[_iface()])
    with _client(s) as c:
        r = c.put(f"/api/v1/admin/interfaces/{_IFACE_ID}", headers=_hdr(), json=payload)
    assert r.status_code == 400
    assert r.json()["code"] == "ERR_CONFIG_0001"
    assert msg in r.json()["message"]
    assert s.registry[Interface][0].llm == 0  # 未被改动
    assert _audits(s) == []


def test_put_interface_unknown_id_rejected():
    s = _session(ifaces=[])
    with _client(s) as c:
        r = c.put("/api/v1/admin/interfaces/999", headers=_hdr(), json={"llm": 1})
    assert r.status_code == 400
    assert "接口不存在" in r.json()["message"]
