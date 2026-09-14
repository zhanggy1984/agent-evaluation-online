"""admin 系统管理面单测（detail §8.6）：鉴权边界 / 配置写入校验与 version 自增 / 审计 / 禁用吊销。

**替身边界（明写，防误读为「已验完」）**：
- `FakeAsyncSession` 按等值匹配只取首行，多行列表语义**不在单测覆盖内**（真库探针覆盖）。
- 真库特有分支（唯一键冲突、`NULL` 不去重的 upsert 语义）**单测验不了**——由
  `tests/integration/admin_probe.py` 在真 MySQL 上验。
"""
import bcrypt
import pytest
from _fakes import FakeAsyncSession, ns

from app.core.config import Settings
from app.core.db import get_session
from app.core.security import create_access_token, hash_password, verify_password
from app.main import create_app
from app.models.agent import Agent
from app.models.config import DictConfig
from app.models.error_flow import ConversionRecord
from app.models.user import User as _User

_AGENT_ID = 7


def _settings():
    return Settings(app_env="test", resource_env="dev", jwt_secret="mock-secret-" * 8)


def _user(uid=1, role="admin", username="root", status=1):
    return ns(
        id=uid,
        username=username,
        display_name="管理员",
        password_hash="x",
        role=role,
        status=status,
        created_at=None,
    )


def _calls(session, model):
    return [o for o in session.added if isinstance(o, model)]


class _IdBackfillSession(FakeAsyncSession):
    """补 commit 自增回填（FakeAsyncSession.commit 不触发 DB 赋值 → 响应里的 id 恒 None）。

    照 `tests/test_backflow_push.py::_IdBackfillSession` 的既有先例：**只回填 id**，不代表
    替身支持真库写语义（唯一键冲突等仍由真库探针覆盖）。
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self._ids = iter(range(900, 990))

    async def commit(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None and hasattr(obj, "id"):
                obj.id = next(self._ids)
        await super().commit()


def _client(session):
    """TestClient + get_session 覆盖（替身）；返回 (client, app) 供断言。"""
    from fastapi.testclient import TestClient

    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app), app


def _hdr(uid=1, role="admin"):
    return {"Authorization": f"Bearer {create_access_token(_settings(), uid, role)}"}


# ---------- 鉴权（§8.8：401/403 双证） ----------


def test_admin_denies_no_token():
    session = FakeAsyncSession(users=[_user()])
    with _client(session)[0] as c:
        r = c.get("/api/v1/admin/configs")
    assert r.status_code == 401
    assert r.json()["code"] == "ERR_AUTH_0001"


def test_admin_denies_viewer_role():
    """viewer 打 admin 端点 → 403 ERR_AUTH_0002（role 查库取，不信任 claims）。"""
    session = FakeAsyncSession(users=[_user(role="viewer", username="alice")])
    with _client(session)[0] as c:
        r = c.get("/api/v1/admin/users", headers=_hdr(role="viewer"))
    assert r.status_code == 403
    assert r.json()["code"] == "ERR_AUTH_0002"


def test_admin_denies_forged_admin_claim_but_viewer_in_db():
    """claims 写 admin、库里是 viewer ⇒ 仍 403（deps 查库保 role 最新）。"""
    session = FakeAsyncSession(users=[_user(role="viewer", username="alice")])
    with _client(session)[0] as c:
        r = c.put(
            "/api/v1/admin/configs",
            headers=_hdr(role="admin"),
            json={"key": "claim_ttl_days", "value": 14},
        )
    assert r.status_code == 403


# ---------- 配置写入（§8.6） ----------


def test_put_config_rejects_unknown_key():
    session = FakeAsyncSession(users=[_user()])
    with _client(session)[0] as c:
        r = c.put(
            "/api/v1/admin/configs", headers=_hdr(), json={"key": "no_such_key", "value": 1}
        )
    assert r.status_code == 400
    assert r.json()["code"] == "ERR_CONFIG_0001"


def test_put_config_rejects_global_key_as_per_agent():
    """键清单按作用域分置：全局键当 per-agent 写 → 拒（不建二期键、不越作用域）。"""
    session = FakeAsyncSession(users=[_user()])
    with _client(session)[0] as c:
        r = c.put(
            "/api/v1/admin/configs",
            headers=_hdr(),
            json={"key": "claim_ttl_days", "value": 14, "agent_id": _AGENT_ID},
        )
    assert r.status_code == 400 and r.json()["code"] == "ERR_CONFIG_0001"


def test_put_config_rejects_shape_mismatch():
    session = FakeAsyncSession(users=[_user()])
    with _client(session)[0] as c:
        r = c.put(
            "/api/v1/admin/configs",
            headers=_hdr(),
            json={"key": "claim_ttl_days", "value": "14"},
        )
    assert r.status_code == 400 and r.json()["code"] == "ERR_CONFIG_0001"


def test_put_config_rejects_bool_for_int_key():
    """bool 是 int 子类：True 不得当成 1 落库。"""
    session = FakeAsyncSession(users=[_user()])
    with _client(session)[0] as c:
        r = c.put(
            "/api/v1/admin/configs",
            headers=_hdr(),
            json={"key": "claim_ttl_days", "value": True},
        )
    assert r.status_code == 400


def test_put_config_existing_row_bumps_version_and_audits():
    """有行 → version + 1；审计 action=config_change 且 detail 含键名与两侧摘要。"""
    row = DictConfig(agent_id=None, config_key="claim_ttl_days", config_value=14, version=3)
    session = FakeAsyncSession(users=[_user()], registry={DictConfig: [row]})
    with _client(session)[0] as c:
        r = c.put(
            "/api/v1/admin/configs", headers=_hdr(), json={"key": "claim_ttl_days", "value": 21}
        )
    assert r.status_code == 200
    assert r.json()["version"] == 4
    assert row.config_value == 21
    assert row.updated_by == "root"
    audits = _calls(session, ConversionRecord)
    assert len(audits) == 1
    assert audits[0].action == "config_change"
    assert audits[0].actor_user_id == 1
    assert audits[0].cluster_id is None  # 配置变更无 cluster
    assert "claim_ttl_days" in audits[0].detail and "14" in audits[0].detail


def test_put_config_missing_row_inserts_version_1():
    session = FakeAsyncSession(users=[_user()], registry={DictConfig: []})
    with _client(session)[0] as c:
        r = c.put(
            "/api/v1/admin/configs",
            headers=_hdr(),
            json={"key": "rollup_late_k_h", "value": 3},
        )
    assert r.status_code == 200
    assert r.json()["version"] == 1
    assert [o.config_key for o in _calls(session, DictConfig)] == ["rollup_late_k_h"]


def test_put_config_per_agent_wordlist_is_not_special_cased():
    """词表键走同一路径（不特判）：version 自增即 D19 wordlist_version；空表合法（fail-closed）。"""
    row = DictConfig(
        agent_id=_AGENT_ID, config_key="fallback_utterance", config_value=["旧话术"], version=1
    )
    session = FakeAsyncSession(
        users=[_user()], registry={DictConfig: [row], Agent: [ns(id=_AGENT_ID)]}
    )
    with _client(session)[0] as c:
        r = c.put(
            "/api/v1/admin/configs",
            headers=_hdr(),
            json={"key": "fallback_utterance", "value": ["新话术", "兜底"], "agent_id": _AGENT_ID},
        )
    assert r.status_code == 200
    assert r.json()["version"] == 2
    assert row.config_value == ["新话术", "兜底"]

    with _client(session)[0] as c:
        r2 = c.put(
            "/api/v1/admin/configs",
            headers=_hdr(),
            json={"key": "fallback_utterance", "value": [], "agent_id": _AGENT_ID},
        )
    assert r2.status_code == 200  # 空表合法：fail-closed 载体，不拦


def test_put_config_rejects_unknown_agent():
    session = FakeAsyncSession(users=[_user()], registry={DictConfig: [], Agent: []})
    with _client(session)[0] as c:
        r = c.put(
            "/api/v1/admin/configs",
            headers=_hdr(),
            json={"key": "timeout_ms", "value": 1000, "agent_id": _AGENT_ID},
        )
    assert r.status_code == 400 and r.json()["code"] == "ERR_CONFIG_0001"


def test_audit_detail_truncates_long_wordlist_with_marker():
    """超长词表：detail 不得超 1024，且必须**显式标出截断**（防读者把截断值当全值）。"""
    words = ["话术" * 40 + str(i) for i in range(50)]
    row = DictConfig(
        agent_id=_AGENT_ID, config_key="fallback_utterance", config_value=["旧"], version=1
    )
    session = FakeAsyncSession(
        users=[_user()], registry={DictConfig: [row], Agent: [ns(id=_AGENT_ID)]}
    )
    with _client(session)[0] as c:
        r = c.put(
            "/api/v1/admin/configs",
            headers=_hdr(),
            json={"key": "fallback_utterance", "value": words, "agent_id": _AGENT_ID},
        )
    assert r.status_code == 200
    detail = _calls(session, ConversionRecord)[0].detail
    assert len(detail) <= 1024
    assert "截断" in detail


def test_list_configs_fills_defaults_for_missing_rows():
    """缺行的 v1 键按 seed 默认值补位并标 is_default（前端才能渲染全量）。"""
    session = FakeAsyncSession(users=[_user()], registry={DictConfig: []})
    with _client(session)[0] as c:
        r = c.get("/api/v1/admin/configs", headers=_hdr())
    assert r.status_code == 200
    items = {i["key"]: i for i in r.json()}
    assert items["claim_ttl_days"]["is_default"] is True
    assert items["claim_ttl_days"]["version"] == 0
    # 只返回 v1 生效键（二期键不建）
    assert "no_such_key" not in items


# ---------- 账号 CRUD（§8.6） ----------


def test_create_user_rejects_duplicate_username():
    session = FakeAsyncSession(users=[_user(), _user(uid=2, role="viewer", username="alice")])
    with _client(session)[0] as c:
        r = c.post(
            "/api/v1/admin/users",
            headers=_hdr(),
            json={"username": "alice", "password": "abcd1234", "role": "viewer"},
        )
    assert r.status_code == 400 and r.json()["code"] == "ERR_CONFIG_0001"


def test_create_user_rejects_short_password_and_bad_role():
    session = FakeAsyncSession(users=[_user()])
    with _client(session)[0] as c:
        r = c.post(
            "/api/v1/admin/users",
            headers=_hdr(),
            json={"username": "bob", "password": "short", "role": "viewer"},
        )
        assert r.status_code == 422  # schema 层最小规则：长度 8~64
        r2 = c.post(
            "/api/v1/admin/users",
            headers=_hdr(),
            json={"username": "bob", "password": "abcd1234", "role": "ops"},
        )
    assert r2.status_code == 400


def test_create_user_hashes_password():
    session = _IdBackfillSession(users=[_user()], registry={_User: []})
    with _client(session)[0] as c:
        r = c.post(
            "/api/v1/admin/users",
            headers=_hdr(),
            json={"username": "bob", "password": "abcd1234", "role": "viewer"},
        )
    assert r.status_code == 201
    assert r.json()["id"] == 900
    created = _calls(session, _User)[0]
    assert created.password_hash != "abcd1234"  # 明文绝不落库
    assert verify_password("abcd1234", created.password_hash)
    assert "password" not in r.json()  # 出参不回口令（含 hash）


def test_disable_user_sets_status_0_and_revokes_all_sessions():
    """禁用 = status=0 + 撤销该用户全部未撤销会话（两半，缺一不可）。"""
    target = _user(uid=2, role="viewer", username="alice")
    live = ns(id=20, user_id=2, refresh_hash="h1", revoked_at=None)
    session = FakeAsyncSession(users=[_user(), target], sessions=[live], registry={_User: []})
    with _client(session)[0] as c:
        r = c.put("/api/v1/admin/users/2", headers=_hdr(), json={"status": 0})
    assert r.status_code == 200
    assert r.json()["status"] == 0
    assert target.status == 0
    assert live.revoked_at is not None


def test_reset_password_revokes_sessions_too():
    target = _user(uid=2, role="viewer", username="alice")
    live = ns(id=20, user_id=2, refresh_hash="h1", revoked_at=None)
    session = FakeAsyncSession(users=[_user(), target], sessions=[live], registry={_User: []})
    with _client(session)[0] as c:
        r = c.put("/api/v1/admin/users/2", headers=_hdr(), json={"password": "newpass123"})
    assert r.status_code == 200
    assert live.revoked_at is not None
    assert verify_password("newpass123", target.password_hash)


def test_cannot_disable_or_demote_self():
    """自锁防护：停用自己 / 改自己角色 → 拒（否则 admin 面无恢复入口）。"""
    session = FakeAsyncSession(users=[_user(), _user(uid=9, role="viewer", username="alice")])
    with _client(session)[0] as c:
        r1 = c.put("/api/v1/admin/users/1", headers=_hdr(), json={"status": 0})
        r2 = c.put("/api/v1/admin/users/1", headers=_hdr(), json={"role": "viewer"})
    assert r1.status_code == 400 and r2.status_code == 400
    assert _user().status == 1  # 未被改（此处仅断言构造值，实体由上面两条 400 拦住）


def test_update_user_missing_target_and_bad_status():
    session = FakeAsyncSession(users=[_user()])
    with _client(session)[0] as c:
        r = c.put("/api/v1/admin/users/404", headers=_hdr(), json={"status": 0})
        assert r.status_code == 400
        assert (
            c.put("/api/v1/admin/users/1", headers=_hdr(), json={"status": 7}).status_code == 400
        )


def test_update_user_none_means_unchanged():
    """字段缺省 = 不修改（None 不代表清空）——防误用为「置空」语义。"""
    target = _user(uid=2, role="viewer", username="alice")
    target.display_name = "旧名"
    session = FakeAsyncSession(users=[_user(), target], sessions=[], registry={_User: []})
    with _client(session)[0] as c:
        r = c.put("/api/v1/admin/users/2", headers=_hdr(), json={"role": "admin"})
    assert r.status_code == 200
    assert target.role == "admin"
    assert target.display_name == "旧名"


# ---------- 口令哈希（core/security 唯一入口） ----------


def test_hash_password_is_bcrypt_and_roundtrips():
    h = hash_password("abcd1234")
    assert h.startswith("$2") and h != "abcd1234"
    assert verify_password("abcd1234", h)
    assert not verify_password("wrong", h)
    assert bcrypt.checkpw(b"abcd1234", h.encode("utf-8"))  # seed 落库形态（str）可被 checkpw 读


@pytest.mark.parametrize("plain", ["a" * 8, "含中文的口令1234"])
def test_hash_password_accepts_utf8(plain):
    assert verify_password(plain, hash_password(plain))
