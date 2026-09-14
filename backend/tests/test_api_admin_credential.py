"""§8.5 `GET /agents/{id}/credential` 单测（批 2b）：脱敏读面契约。

**本文件验什么 / 不验什么**（判据边界，防把绿读大）：
- ✅ 验：鉴权（401/403）、未知 agent → 400、**无凭证行 → 200 + `credential=null`**、
  有行时的字段集、以及本批最核心的两条契约——**响应体里不出现 secret** 与
  **端点连 `secret_cipher` 这一列都不读**（`_BoomCredential` 钉住）。
- ❌ 不验：**真实 `agent_credential` 行的读回**——替身行是我手写的 `SimpleNamespace`，
  只证明「给我这种输入时算得对」。真库读回由 `tests/integration/admin_credential_probe.py`
  走 MySQL 取证（含「临时造一行 → 读 → 删净」）。
- ❌ 不验：`rotate`。**本批不存在该端点**（§8.5 `:1138` 的三个动作全在 infra，已下移
  T-5.3，2026-09-14 拍板）。

**「脱敏」的口径 = 不回传、且不读取**（`AgentCredentialOut` 文档详述）：`secret_cipher`
存的是密文，对密文做掩码零信息价值；正确做法是这条列根本不进查询/不进响应。
`test_response_never_carries_secret` 与 `test_endpoint_never_reads_secret_cipher` 是这条
口径的两条护栏——前者防「回传」，后者防「读了再抹」（后者更严：读了就可能在日志/异常里漏）。
"""
from contextlib import contextmanager
from datetime import datetime

from _fakes import FakeAsyncSession, FakeES, ns

from app.core.config import Settings
from app.core.db import get_session
from app.core.security import create_access_token
from app.main import create_app
from app.models.agent import Agent, AgentCredential

_AGENT_ID = 7
_AGENT_NAME = "good-question"


def _settings():
    return Settings(app_env="test", resource_env="dev", jwt_secret="mock-secret-" * 8)


def _user(role="admin"):
    return ns(
        id=1,
        username="root",
        display_name="管理员",
        password_hash="x",
        role=role,
        status=1,
        created_at=None,
    )


def _agent(aid=_AGENT_ID, name=_AGENT_NAME):
    return ns(
        id=aid,
        name=name,
        display_name=name.upper(),
        base_url=None,
        enable=1,
        backflow_allow=1,
        route_source="auto_register",
    )


class _BoomCredential:
    """`secret_cipher` 一被读就**炸**：钉住「端点连这一列都不读」。

    这是比 `assert "secret" not in body` 更强的那条断言——后者只防「回传」，本条防
    「读了再抹」。读了就可能在日志、审计 detail、异常栈里漏出去，而**不读即不可能漏**。
    """

    def __init__(self, **kw):
        self.__dict__.update(kw)

    @property
    def secret_cipher(self):  # pragma: no cover - 正常路径下永不触发
        raise AssertionError(
            "端点读取了 secret_cipher——脱敏应当是「不读取」而非「读了再抹」"
        )


def _cred(
    agent_id=_AGENT_ID,
    kafka_username="obs-gq",
    topic="dev.obs.agent.good-question",
    active=1,
    rotated_at=None,
    created_at=datetime(2026, 9, 14, 12, 0, 0),
):
    """**可读的**凭证替身：`secret_cipher` 是可读的假值（用于「回传面」那条断言）。"""
    return ns(
        id=1,
        agent_id=agent_id,
        kafka_username=kafka_username,
        secret_cipher="gAAAAA-fake-cipher-not-a-real-secret",
        topic=topic,
        active=active,
        rotated_at=rotated_at,
        created_at=created_at,
    )


def _hdr(role="admin"):
    return {"Authorization": f"Bearer {create_access_token(_settings(), 1, role)}"}


@contextmanager
def _enter(session):
    """TestClient（**必须 with**——`app.state.settings` 在 lifespan 里挂）。"""
    from fastapi.testclient import TestClient

    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        # 本端点不碰 ES；仍挂替身以免 lifespan 之后的任何默认路径打到真 ES。
        app.state.es_query = FakeES(response={})
        yield client


def _session(agents=(), creds=(), role="admin"):
    return FakeAsyncSession(
        users=[_user(role)],
        registry={Agent: list(agents), AgentCredential: list(creds)},
    )


_URL = f"/api/v1/admin/agents/{_AGENT_ID}/credential"


# ---------- 鉴权 ----------


def test_credential_requires_auth():
    with _enter(_session([_agent()])) as c:
        r = c.get(_URL)
    assert r.status_code == 401
    assert r.json()["code"] == "ERR_AUTH_0001"


def test_credential_forbids_viewer():
    with _enter(_session([_agent()], role="viewer")) as c:
        r = c.get(_URL, headers=_hdr("viewer"))
    assert r.status_code == 403
    assert r.json()["code"] == "ERR_AUTH_0002"


# ---------- 接线 ----------


def test_credential_unknown_agent_is_400():
    """未知 id ⇒ 400（不是 `credential=null`）：否则笔误的 id 会被伪装成「有 agent 但没发凭证」。

    这两者处置动作完全不同——前者是查 id，后者是催 infra 发放。
    """
    with _enter(_session([])) as c:
        r = c.get(_URL, headers=_hdr())
    assert r.status_code == 400
    assert r.json()["code"] == "ERR_CONFIG_0001"


def test_credential_absent_row_is_200_with_null():
    """**无凭证行 ⇒ 200 + `credential=null`**：未发凭证是合法状态，不是 404。

    dev 库该表 0 行（2026-09-14 实测）⇒ 这是本环境**唯一的真实态**。
    """
    with _enter(_session([_agent()])) as c:
        r = c.get(_URL, headers=_hdr())
    assert r.status_code == 200
    body = r.json()
    assert body["agent_id"] == _AGENT_ID
    assert body["credential"] is None


def test_credential_with_row_returns_metadata():
    cred = _cred(active=0, rotated_at=None)
    with _enter(_session([_agent()], [cred])) as c:
        r = c.get(_URL, headers=_hdr())
    body = r.json()
    assert body["agent_id"] == _AGENT_ID
    item = body["credential"]
    assert item == {
        "kafka_username": "obs-gq",
        "topic": "dev.obs.agent.good-question",
        "active": 0,
        "rotated_at": None,
        "created_at": "2026-09-14T12:00:00",
    }, "字段集即契约：多一个少一个都算改契约"


def test_credential_is_scoped_to_agent():
    """只回**本 agent** 的行：另一 agent 的凭证不得串台（替身按 `agent_id` 等值匹配）。"""
    other = _cred(agent_id=99, kafka_username="obs-other")
    with _enter(_session([_agent()], [other])) as c:
        r = c.get(_URL, headers=_hdr())
    assert r.status_code == 200
    assert r.json()["credential"] is None, "agent 7 无行 ⇒ 不得回出 agent 99 的凭证"


# ---------- 核心口径：不泄漏 / 不读取 ----------


def test_response_never_carries_secret():
    """**契约护栏**：即使库里有 `secret_cipher`，响应体的任何层级都不得出现它。

    用原始文本判（而非 `body.get("secret_cipher")`）——后者只查顶层键，漏掉嵌套与改名。
    """
    with _enter(_session([_agent()], [_cred()])) as c:
        r = c.get(_URL, headers=_hdr())
    raw = r.text
    assert "secret" not in raw.lower(), f"响应体出现 secret 字样：{raw}"
    assert "gAAAAA-fake-cipher" not in raw, "密文值泄漏到响应体"


def test_endpoint_never_reads_secret_cipher():
    """**更严的一条**：端点连 `secret_cipher` 这一列都不读（一读就炸，见 `_BoomCredential`）。

    为什么这条值得单独钉：`test_response_never_carries_secret` 只能证明「这次没回传」，
    证明不了「以后也不会」——比如有人先 `cred.secret_cipher` 取值再决定「要不要脱敏」，
    那时密文已进了进程内存与可能的日志。**不读即不可能漏。**
    """
    boom = _BoomCredential(
        id=1,
        agent_id=_AGENT_ID,
        kafka_username="obs-gq",
        topic="dev.obs.agent.good-question",
        active=1,
        rotated_at=None,
        created_at=datetime(2026, 9, 14, 12, 0, 0),
    )
    with _enter(_session([_agent()], [boom])) as c:
        r = c.get(_URL, headers=_hdr())
    assert r.status_code == 200
    assert r.json()["credential"]["kafka_username"] == "obs-gq"
