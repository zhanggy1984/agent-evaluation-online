"""auth API 端点单测（detail §8.1/§13.1/§13.2）。

FakeAsyncSession 替换 DB 读（等值 select/get 语义对齐 auth.py 用法）——不连真 MySQL。
覆盖：登录正/误/锁定/停用、防枚举统一口径、refresh 轮换吊销即时生效、logout 幂等、
me 回显 + 401 分支（deps.get_current_user 独立测试在 test_api_trace.py 内补）。
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest

from _fakes import FakeAsyncSession, ns
from app.api import auth as auth_api
from app.core.config import Settings
from app.core.db import get_session
from app.core.security import create_access_token, hash_refresh_token
from app.main import create_app

PASSWORD = "Admin@12345"
HASH = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()


def _future():
    # MySQL DATETIME3 无时区：naive UTC（auth._utcnow_naive 同口径）
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7)


def _settings():
    return Settings(app_env="test", resource_env="dev", jwt_secret="mock-secret-" * 8)


@pytest.fixture(autouse=True)
def _reset_lock():
    # 失败锁定为模块级进程内状态（§13.2 单实例语义）：每测清空防串扰
    auth_api._login_fails.clear()
    yield
    auth_api._login_fails.clear()


def _client(fake_session):
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: fake_session
    from fastapi.testclient import TestClient
    return TestClient(app)


def _user_row(uid=1, username="admin", role="admin", status=1):
    return ns(id=uid, username=username, display_name="平台管理员",
              password_hash=HASH, role=role, status=status)


def test_login_ok_returns_tokens_and_session():
    fake = FakeAsyncSession(users=[_user_row()])
    with _client(fake) as c:
        r = c.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["username"] == "admin" and body["user"]["role"] == "admin"
    # 建了 refresh 会话行（hash 存库，明文不出库）
    assert len(fake.added) == 1
    assert len(fake.added[0].refresh_hash) == 64
    assert fake.commits == 1


def test_login_wrong_password_and_unknown_username_same_message():
    # §13.2 防枚举：口令错 / 用户不存在 / 停用 统一「用户名或密码错误」
    fake = FakeAsyncSession(users=[_user_row()])
    with _client(fake) as c:
        bad_pw = c.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        no_user = c.post("/api/v1/auth/login", json={"username": "ghost", "password": PASSWORD})
    for r in (bad_pw, no_user):
        assert r.status_code == 401
        assert r.json() == {"code": "ERR_AUTH_0001", "message": "用户名或密码错误"}


def test_login_disabled_account_denied():
    fake = FakeAsyncSession(users=[_user_row(status=0)])
    with _client(fake) as c:
        r = c.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert r.status_code == 401 and r.json()["code"] == "ERR_AUTH_0001"


def test_login_lockout_after_5_fails_15min():
    # §13.2：5 次/15min → 第 6 次（即使口令对）423 ERR_AUTH_0003
    fake = FakeAsyncSession(users=[_user_row()])
    with _client(fake) as c:
        for _ in range(5):
            assert c.post("/api/v1/auth/login",
                          json={"username": "admin", "password": "wrong"}).status_code == 401
        locked = c.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert locked.status_code == 423
    assert locked.json() == {"code": "ERR_AUTH_0003", "message": "登录失败次数过多，已锁定 15 分钟"}


def test_refresh_rotates_and_revokes_old():
    # §8.1 refresh 轮换：新 refresh 返回，旧 session 吊销（旧值即刻失效）
    fake = FakeAsyncSession(
        users=[_user_row()],
        sessions=[ns(id=9, user_id=1,
                     refresh_hash=hash_refresh_token("orig-refresh"),
                     expires_at=_future(), revoked_at=None)],
    )
    with _client(fake) as c:
        r = c.post("/api/v1/auth/refresh", json={"refresh_token": "orig-refresh"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    # 旧 session 已吊销 + 新增轮换后 session
    assert fake.sessions[0].revoked_at is not None
    assert len(fake.added) == 1


def test_refresh_revoked_token_rejected():
    fake = FakeAsyncSession(
        users=[_user_row()],
        sessions=[ns(id=9, user_id=1,
                     refresh_hash=hash_refresh_token("revoked-token"),
                     expires_at=ns(), revoked_at=ns())],
    )
    with _client(fake) as c:
        r = c.post("/api/v1/auth/refresh", json={"refresh_token": "revoked-token"})
    assert r.status_code == 401 and r.json()["code"] == "ERR_AUTH_0001"


def test_me_returns_current_user():
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_user_row()])
    token = create_access_token(_settings(), 1, "admin")
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        r = c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"id": 1, "username": "admin", "display_name": "平台管理员", "role": "admin"}


def test_me_requires_bearer_token():
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_user_row()])
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        no_header = c.get("/api/v1/auth/me")
        bad_token = c.get("/api/v1/auth/me", headers={"Authorization": "Bearer mock-junk"})
    assert no_header.status_code == 401 and no_header.json()["code"] == "ERR_AUTH_0001"
    assert bad_token.status_code == 401 and bad_token.json()["code"] == "ERR_AUTH_0001"


def test_logout_idempotent_revokes():
    fake = FakeAsyncSession(
        users=[_user_row()],
        sessions=[ns(id=9, user_id=1,
                     refresh_hash=hash_refresh_token("orig-refresh"),
                     expires_at=_future(), revoked_at=None)],
    )
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: fake
    token = create_access_token(_settings(), 1, "admin")
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        first = c.post("/api/v1/auth/logout", json={"refresh_token": "orig-refresh"},
                       headers={"Authorization": f"Bearer {token}"})
        second = c.post("/api/v1/auth/logout", json={"refresh_token": "orig-refresh"},
                        headers={"Authorization": f"Bearer {token}"})
    assert first.status_code == 204
    assert second.status_code == 204  # 幂等：已吊销再次注销不报错
    assert fake.sessions[0].revoked_at is not None
