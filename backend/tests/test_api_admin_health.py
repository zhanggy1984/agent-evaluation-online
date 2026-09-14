"""§8.5 `GET /agents/{id}/health` 单测（批 2a-2）：聚合面 + 端点接线。

**本文件验什么 / 不验什么**（判据边界，防把绿读大）：
- ✅ 验：`summarize_heartbeats` 的聚合语义（含**「取最新快照而非窗内求和」**这条核心口径）、
  端点接线（用 `row.name` 查 ES、未知 agent → 400、ES 超时 → 400、查询 body 形状）。
- ❌ 不验：**ES 真会返回这些 doc** —— `FakeES` 只按给定 response 回放，「链路上真能产生心跳」
  由 `tests/integration/admin_agents_probe.py` 走 Kafka + 真 ES 取证（本文件喂什么就验什么，
  喂的是我手写的 doc ⇒ 只证明「给我这种输入时算得对」）。
- ❌ 不验：截断（size=500 超限）——需造 501 条心跳，属容量型，未做。

**dropped 口径是本批最容易写错的地方**：心跳 doc 里的 `dropped` 是 consumer 进程内**累计快照**
（`consumer/main.py:87`），窗内多条心跳写的是同一个数 ⇒ 求和会把同一个数重复相加。
`test_summarize_dropped_is_latest_snapshot_not_sum` 就是钉这条的回归护栏。
"""
import time
from contextlib import contextmanager

from _fakes import FakeAsyncSession, FakeES, ns
from elasticsearch.exceptions import TransportError

from app.core import dict_config
from app.core.config import Settings
from app.core.db import get_session
from app.core.security import create_access_token
from app.main import create_app
from app.models.agent import Agent
from app.models.config import DictConfig
from app.store import es as es_store

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


def _hb_resp(sources):
    return es_hits_heartbeat(sources)


def es_hits_heartbeat(sources):
    """ES search 响应形状（心跳面只用 hits.hits[]._source）。"""
    return {
        "hits": {
            "total": {"value": len(sources), "relation": "eq"},
            "hits": [{"_source": s} for s in sources],
        }
    }


def _hdr(role="admin"):
    return {"Authorization": f"Bearer {create_access_token(_settings(), 1, role)}"}


@contextmanager
def _enter(session, fake_es):
    """TestClient（**必须 with**——`app.state.settings` 在 lifespan 里挂）+ 换 ES fake。"""
    from fastapi.testclient import TestClient

    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: session
    # dict_config 有模块级 ttl 缓存（60s）——不清则跨用例串键值（`test_..._lookback_...` 会串）
    dict_config._cache.clear()  # noqa: SLF001
    with TestClient(app) as client:
        app.state.es_query = fake_es
        yield client


def _session(agents=(), role="admin", configs=()):
    return FakeAsyncSession(
        users=[_user(role)],
        registry={Agent: list(agents), DictConfig: list(configs)},
    )


_HEALTH_URL = f"/api/v1/admin/agents/{_AGENT_ID}/health"


# ---------- 纯函数：聚合语义 ----------


def test_summarize_empty_is_not_connected():
    """无心跳 ⇒ `last_seen_ts=None`（前端据此出「查询窗内无心跳上报」，§9.1 判据）。"""
    out = es_store.summarize_heartbeats([], now_ms=1_000_000)
    assert out == {
        "last_seen_ts": None,
        "report_1min": 0,
        "report_5min": 0,
        "dropped": {},
        "sdk_connected": False,
    }


def test_summarize_dropped_is_latest_snapshot_not_sum():
    """**核心口径回归护栏**：`dropped` 取最新一条心跳的快照，不是窗内求和。

    若有人改回「求和」，本用例立即红：旧写法会得 `schema=7`（5+2），新写法得 `2`。
    """
    docs = [
        {"ts": 900_000, "dropped": {"schema": 5}, "source": "consumer"},
        {"ts": 990_000, "dropped": {"schema": 2}, "source": "consumer"},
    ]
    out = es_store.summarize_heartbeats(docs, now_ms=1_000_000)
    assert out["dropped"] == {"schema": 2}, "取的是最大 ts 那条的快照"
    assert out["last_seen_ts"] == 990_000


def test_summarize_window_counts_boundary():
    """`report_1min`/`report_5min` = 窗内条数，边界含端点（<= 60s / <= 300s）。"""
    now = 1_000_000
    docs = [
        {"ts": now - 60_000, "dropped": {}, "source": "consumer"},  # 恰在 1min 边界内
        {"ts": now - 60_001, "dropped": {}, "source": "consumer"},  # 出 1min，仍在 5min
        {"ts": now - 300_000, "dropped": {}, "source": "consumer"},  # 恰在 5min 边界内
        {"ts": now - 300_001, "dropped": {}, "source": "consumer"},  # 出 5min
    ]
    out = es_store.summarize_heartbeats(docs, now_ms=now)
    assert out["report_1min"] == 1
    assert out["report_5min"] == 3


def test_summarize_sdk_connected_only_for_non_form_a():
    """`sdk_connected` = 存在 form A（`source="consumer"`）之外的心跳（SDK 自报透传）。"""
    form_a = [{"ts": 990_000, "dropped": {}, "source": "consumer"}]
    assert es_store.summarize_heartbeats(form_a, now_ms=1_000_000)["sdk_connected"] is False
    with_sdk = form_a + [{"ts": 991_000, "dropped": {}, "source": "sdk"}]
    assert es_store.summarize_heartbeats(with_sdk, now_ms=1_000_000)["sdk_connected"] is True


def test_summarize_dirty_dropped_values_skipped():
    """脏 `dropped` 值跳过而非整体失败（心跳是自监控面，不该因一条脏数据全灭）。"""
    docs = [{"ts": 990_000, "dropped": {"schema": "oops", "mask": 3}, "source": "consumer"}]
    out = es_store.summarize_heartbeats(docs, now_ms=1_000_000)
    assert out["dropped"] == {"mask": 3}


# ---------- 端点：鉴权 ----------


def test_health_requires_auth():
    with _enter(_session([_agent()]), FakeES(response=_hb_resp([]))) as c:
        r = c.get(_HEALTH_URL)
    assert r.status_code == 401
    assert r.json()["code"] == "ERR_AUTH_0001"


def test_health_forbids_viewer():
    with _enter(_session([_agent()], role="viewer"), FakeES(response=_hb_resp([]))) as c:
        r = c.get(_HEALTH_URL, headers=_hdr("viewer"))
    assert r.status_code == 403
    assert r.json()["code"] == "ERR_AUTH_0002"


# ---------- 端点：接线 ----------


def test_health_empty_state():
    """窗内无心跳 ⇒ 全零 + `last_seen_ts=null`（HTTP 层空态）。"""
    with _enter(_session([_agent()]), FakeES(response=_hb_resp([]))) as c:
        r = c.get(_HEALTH_URL, headers=_hdr())
    assert r.status_code == 200
    body = r.json()
    assert body["agent_id"] == _AGENT_ID
    assert body["last_seen_ts"] is None
    assert body["report_1min"] == 0 and body["report_5min"] == 0
    assert body["sdk_connected"] is False


def test_health_with_heartbeats():
    now = int(time.time() * 1000)
    docs = [
        {"ts": now - 120_000, "dropped": {"schema": 1}, "source": "consumer"},
        {"ts": now - 30_000, "dropped": {"schema": 4}, "source": "consumer"},
    ]
    with _enter(_session([_agent()]), FakeES(response=_hb_resp(docs))) as c:
        r = c.get(_HEALTH_URL, headers=_hdr())
    body = r.json()
    assert body["last_seen_ts"] == now - 30_000
    assert body["report_1min"] == 1
    assert body["report_5min"] == 2
    assert body["dropped"] == {"schema": 4}


def test_health_queries_es_by_agent_name_not_id():
    """**防回归**：ES 的 `agent` 字段是 agent 名（`good-question` 这类），不是 MySQL 主键。

    用 id 去查会得到一个恒空的查询（表现为「所有 agent 都无心跳」）——这条断言钉住它。
    """
    fake = FakeES(response=_hb_resp([]))
    with _enter(_session([_agent(aid=99, name="named-agent")]), fake) as c:
        c.get("/api/v1/admin/agents/99/health", headers=_hdr())
    _, body = fake.calls[0]
    filt = body["query"]["bool"]["filter"]
    assert {"term": {"agent": "named-agent"}} in filt
    assert {"term": {"node": "heartbeat"}} in filt, "health 要**含**心跳（与检索面排除相反）"


def test_health_unknown_agent_is_400():
    """未知 id ⇒ 400（不是「窗内无心跳」的空态）：否则笔误的 id 会被伪装成「有这个 agent」。"""
    with _enter(_session([]), FakeES(response=_hb_resp([]))) as c:
        r = c.get(_HEALTH_URL, headers=_hdr())
    assert r.status_code == 400
    assert r.json()["code"] == "ERR_CONFIG_0001"


def test_health_es_timeout_is_400():
    fake = FakeES(exc=TransportError("模拟心跳查询超时"))
    with _enter(_session([_agent()]), fake) as c:
        r = c.get(_HEALTH_URL, headers=_hdr())
    assert r.status_code == 400
    assert r.json()["code"] == "ERR_CONFIG_0001"


def test_health_lookback_defaults_to_seven_days():
    """无配置行 ⇒ 回溯窗 7 天（= seed `keyword_search_days` 默认，与检索面同键）。

    ⚠️ **「配置值真能改窗」这条分支不在本文件覆盖内**（如实标注，勿读成已验）：
    替身的列级 select 走 `execute` 时返回**整行**而非列属性（`_fakes.py:33-38`：`execute`
    直接把 row 交给 `scalar_one_or_none`，`_return_value` 只被 `scalar()` 用，2026-09-14
    实测），`get_global_int` 于是拿到非 int ⇒ 恒回退默认。要让替身支持须改共享基建
    （`_fakes.py` 是跨批共用件），不属本批，另议。端点侧本批只新增「传哪个键」这一件事。
    """
    now = int(time.time() * 1000)
    fake = FakeES(response=_hb_resp([]))
    with _enter(_session([_agent()]), fake) as c:
        c.get(_HEALTH_URL, headers=_hdr())
    _, body = fake.calls[0]
    gte = body["query"]["bool"]["filter"][1]["range"]["ts"]["gte"]
    assert abs((now - gte) - 7 * 86_400_000) < 5_000, "允许毫秒级调用间隔误差"
