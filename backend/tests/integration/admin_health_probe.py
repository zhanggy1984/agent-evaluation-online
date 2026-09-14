"""§8.5 `GET /agents/{id}/health` 真库真 ES 探针（T-3.12 批 2a-2）。容器内运行：

    docker exec obs-backend python /app/tests/integration/admin_health_probe.py

形态照 `admin_agents_probe.py`：真库 AsyncSession 挂 `get_session` override
（`expire_on_commit=False` 与生产同参）+ httpx ASGITransport 直打端点 + 真 JWT + 真 ES
查询 + **真 Kafka**。

**为什么必须真基建**（单测替身做不到的）：
  - `FakeES` 只回放我手写的 doc ⇒ 只能证明「给我这种输入时算得对」，证明不了「链路上真能
    产生这种 doc」。本探针的 H-2/H-3 **先读 ES 真数据、再拿端点结果与之逐字段对齐**。
  - `dropped` 的**快照口径**只有在多条真心跳上才暴露：H-2 直接对比「ES 里最新一条心跳的
    dropped」与端点返回（若有人把口径改回「窗内求和」，这条立刻红）。

覆盖：
  H-1  鉴权双证：无 token → 401；真 viewer 角色行 → 403
  H-2  真实存量心跳：`last_seen_ts` **等于** ES 该 agent 最新心跳 ts（非「不为空」）、
       `dropped` **等于**最新一条的**快照**（非窗内求和）、`report_1min/5min` 与窗内真条数对齐
  H-3  走**真 Kafka（obs.selfmonitor）**造一条活心跳 → 端点应见 `report_1min>=1`、
       `last_seen_ts≈now`、`sdk_connected=true`（form A 之外的 source 才算 SDK 自报）
  H-4  空态：自建隔离 agent（无任何心跳）→ `last_seen_ts=null` + 全零 + `sdk_connected=false`
  H-5  未知 agent id → 400 ERR_CONFIG_0001（不伪装成「查询窗内无心跳上报」的空态）

**未覆盖（如实标注，不当作通过）**：
  - **form A（`source="consumer"`）心跳本批不现造**：consumer 的消费循环在**启动时**按
    `_enabled_agents()` 固定建 loop（`consumer/main.py:123-127`），新插入的 agent 不会被消费；
    要现造只能对既有 4 个真实 agent 发脏事件，那会**污染真实 agent 的进程内 dropped 计数**
    （1 条脏 JSON = 该 agent `schema` +1，且心跳窗内求和/快照都会被改写）。改为由 H-2 用
    **存量真实心跳**覆盖同一批字段（`last_seen_ts`/`report_*`/`dropped` 口径），
    「form A 心跳能被触发」这一条属 consumer 机制面，已由 `d6_probe.s2` 的 `hb_visible()` 覆盖。
  - `_HEALTH_SIZE=500` 的**截断分支**（需造 501 条心跳）——容量型，未做。

隔离：agent 名前缀 `admhb-`；ES 侧只删本探针那个 agent 名下的 doc；退出码全绿 0。
"""
import asyncio
import json
import sys
import time

sys.path.insert(0, "/app")

from aiokafka import AIOKafkaProducer  # noqa: E402
from elasticsearch import AsyncElasticsearch  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.models.user import User, UserSession  # noqa: E402
from app.store.es import index_patterns  # noqa: E402

FAILURES: list[str] = []
API = "/api/v1"
PREFIX = "admhb-"
ADMIN_USER = PREFIX + "admin"
VIEWER_USER = PREFIX + "viewer"
PW = "probe-pass-1234"
AGENT_EMPTY = PREFIX + "agent-empty"  # 永远没有心跳
AGENT_SDK = PREFIX + "agent-sdk"  # H-3 现造一条 SDK 心跳
UNKNOWN_ID = 2_000_000_001  # 真库不会有这个 id
_settings_cache: dict = {}


def check(name: str, ok: bool, detail: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        FAILURES.append(name)


def _settings() -> Settings:
    if "s" not in _settings_cache:
        _settings_cache["s"] = Settings(
            app_env="test", resource_env="dev", jwt_secret="probe-jwt-" + "0" * 40
        )
    return _settings_cache["s"]


def _hdr(jwt: str | None = None) -> dict:
    return {} if jwt is None else {"Authorization": f"Bearer {jwt}"}


def _jwt(uid: int, role: str) -> str:
    return create_access_token(_settings(), uid, role)


# ---------- ES 助手 ----------


async def _es_search(es, query: dict, *, size: int = 100, sort: list | None = None) -> list[dict]:
    body: dict = {"query": query, "size": size}
    if sort:
        body["sort"] = sort
    resp = await es.search(index=index_patterns(_settings()), body=body)
    return [h["_source"] for h in resp["hits"]["hits"]]


async def _heartbeats(es, agent: str) -> list[dict]:
    """该 agent 的全部心跳 doc（ts desc）。"""
    return await _es_search(
        es,
        {"bool": {"filter": [{"term": {"agent": agent}}, {"term": {"node": "heartbeat"}}]}},
        size=500,
        sort=[{"ts": {"order": "desc"}}],
    )


async def _drop_probe_docs(es, agent: str) -> None:
    await es.delete_by_query(
        index=index_patterns(_settings()),
        body={"query": {"term": {"agent": agent}}},
        refresh=True,
        conflicts="proceed",
    )


# ---------- 现场 ----------


async def _cleanup(engine) -> None:
    async with AsyncSession(engine) as s:
        aids = list(
            (await s.execute(select(Agent.id).where(Agent.name.like(PREFIX + "%"))))
            .scalars()
            .all()
        )
        if aids:
            await s.execute(delete(Agent).where(Agent.id.in_(aids)))
        uids = list(
            (await s.execute(select(User.id).where(User.username.like(PREFIX + "%"))))
            .scalars()
            .all()
        )
        if uids:
            await s.execute(delete(UserSession).where(UserSession.user_id.in_(uids)))
            await s.execute(delete(User).where(User.id.in_(uids)))
        await s.commit()


async def _seed(engine) -> tuple[int, int, int, int]:
    """返回 (admin_id, viewer_id, agent_empty, agent_sdk)。"""
    async with AsyncSession(engine, expire_on_commit=False) as s:
        admin = User(
            username=ADMIN_USER,
            password_hash=hash_password(PW),
            display_name="探针管理员",
            role="admin",
            status=1,
        )
        viewer = User(
            username=VIEWER_USER,
            password_hash=hash_password(PW),
            display_name="探针观察者",
            role="viewer",
            status=1,
        )
        s.add_all([admin, viewer])
        await s.flush()
        a_empty = Agent(
            name=AGENT_EMPTY, display_name="探针 agent（无心跳）", enable=1,
            backflow_allow=1, route_source="manual",
        )
        a_sdk = Agent(
            name=AGENT_SDK, display_name="探针 agent（SDK 心跳）", enable=1,
            backflow_allow=1, route_source="manual",
        )
        s.add_all([a_empty, a_sdk])
        await s.commit()
        return admin.id, viewer.id, a_empty.id, a_sdk.id


async def _pick_existing_agent_with_heartbeat(engine, es) -> tuple[str, int] | None:
    """从 ES 实有心跳里挑一个**真库 agent 表里存在**的（H-2 的取证对象）。

    不写死 `good-question`：dev 库的 agent 集合会变，写死会让探针在换库后静默跳过。
    """
    docs = await _es_search(
        es, {"term": {"node": "heartbeat"}}, size=500, sort=[{"ts": {"order": "desc"}}]
    )
    names: list[str] = []
    for d in docs:
        n = d.get("agent")
        if n and n not in names:
            names.append(n)
    if not names:
        return None
    async with AsyncSession(engine) as s:
        rows = (
            (await s.execute(select(Agent).where(Agent.name.in_(names)))).scalars().all()
        )
    by_name = {r.name: r.id for r in rows}
    for n in names:  # 按「最近有心跳」优先
        if n in by_name:
            return n, by_name[n]
    return None


# ---------- 场景 ----------


async def h1_auth(client, viewer_jwt: str, agent_empty: int) -> None:
    url = f"{API}/admin/agents/{agent_empty}/health"
    r = await client.get(url)
    check(
        "H-1a 无 token → 401 ERR_AUTH_0001",
        r.status_code == 401 and r.json()["code"] == "ERR_AUTH_0001",
        f"{r.status_code} {r.text[:80]}",
    )
    r = await client.get(url, headers=_hdr(viewer_jwt))
    check(
        "H-1b 真 viewer 角色行 → 403 ERR_AUTH_0002",
        r.status_code == 403 and r.json()["code"] == "ERR_AUTH_0002",
        f"{r.status_code} {r.text[:80]}",
    )


async def h2_real_heartbeats(es, client, admin_jwt: str, name: str, aid: int) -> None:
    """存量真实心跳：端点结果与 ES 真数据**逐字段对齐**（不是「非空即可」）。"""
    docs = await _heartbeats(es, name)
    if not docs:
        check("H-2a 存量心跳可取（前置）", False, f"ES 里 {name} 无心跳 doc —— 前置不成立")
        return
    ts_list = [int(d.get("ts") or 0) for d in docs]
    newest = docs[0]
    r = await client.get(f"{API}/admin/agents/{aid}/health", headers=_hdr(admin_jwt))
    body = r.json()
    check(
        "H-2a 200 且 last_seen_ts **等于** ES 最新心跳 ts（等于谁，非「不为空」）",
        r.status_code == 200 and body["last_seen_ts"] == max(ts_list),
        f"端点 {body.get('last_seen_ts')} vs ES 最新 {max(ts_list)}（doc 数 {len(docs)}）",
    )
    want = {k: int(v) for k, v in (newest.get("dropped") or {}).items()}
    check(
        "H-2b dropped **等于最新一条的快照**（若改回「窗内求和」此条必红）",
        body["dropped"] == want,
        f"端点 {body['dropped']} vs 最新快照 {want}；"
        f"窗内 {len(docs)} 条（求和口径会得 {_sum_dropped(docs)}）",
    )
    now_ms = int(time.time() * 1000)
    in_1min = sum(1 for ts in ts_list if now_ms - ts <= 60_000)
    in_5min = sum(1 for ts in ts_list if now_ms - ts <= 300_000)
    check(
        "H-2c report_1min/5min 与 ES 真条数一致",
        body["report_1min"] == in_1min and body["report_5min"] == in_5min,
        f"端点 {body['report_1min']}/{body['report_5min']} vs ES {in_1min}/{in_5min}",
    )
    check(
        "H-2d sdk_connected 与 ES 里 source 分布一致（form A 之外才算 SDK）",
        body["sdk_connected"] == any(
            d.get("source") and d.get("source") != "consumer" for d in docs
        ),
        f"sources={sorted({d.get('source') for d in docs})} → {body['sdk_connected']}",
    )


def _sum_dropped(docs: list[dict]) -> dict:
    out: dict[str, int] = {}
    for d in docs:
        for k, v in (d.get("dropped") or {}).items():
            out[k] = out.get(k, 0) + int(v)
    return out


async def h3_live_sdk_heartbeat(es, client, admin_jwt: str, settings: Settings, aid: int) -> None:
    """走**真 Kafka（`obs.selfmonitor`）**造一条活心跳 → 端点应见近 1 分钟上报。

    这是一条**端到端**取证：Kafka → consumer `_selfmonitor_loop` → ES → health 端点。
    只用隔离 agent 名（`admhb-`），不碰真实 agent 的计数。
    """
    now_ms = int(time.time() * 1000)
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap, max_request_size=1_048_576
    )
    await producer.start()
    try:
        await producer.send(
            settings.selfmonitor_topic,
            json.dumps({"agent": AGENT_SDK, "ts": now_ms, "probe": PREFIX}).encode("utf-8"),
        )
        await producer.flush()
    finally:
        await producer.stop()

    landed = []
    deadline = time.time() + 30
    while time.time() < deadline:
        landed = await _heartbeats(es, AGENT_SDK)
        if landed:
            break
        await asyncio.sleep(1)
    if not landed:
        check("H-3a SDK 心跳落 ES（前置）", False, "30s 内未见 ES 落 doc（consumer 在跑吗？）")
        return
    src = landed[0].get("source")
    check(
        "H-3a SDK 心跳经 consumer 透传落 ES（source=sdk，非 form A）",
        src == "sdk",
        f"source={src!r}",
    )
    r = await client.get(f"{API}/admin/agents/{aid}/health", headers=_hdr(admin_jwt))
    body = r.json()
    check(
        "H-3b 端点见 report_1min>=1（**活心跳**，该分支在存量数据上取不到）",
        r.status_code == 200 and body["report_1min"] >= 1,
        f"{r.status_code} report_1min={body.get('report_1min')}",
    )
    check(
        "H-3c last_seen_ts ≈ 刚发的 ts（秒级误差内）",
        body["last_seen_ts"] is not None and abs(body["last_seen_ts"] - now_ms) < 5_000,
        f"端点 {body.get('last_seen_ts')} vs 发出 {now_ms}",
    )
    check(
        "H-3d sdk_connected=true（该 agent 只有 SDK 心跳，无 form A）",
        body["sdk_connected"] is True,
        f"{body.get('sdk_connected')}",
    )


async def h4_empty_state(client, admin_jwt: str, aid: int) -> None:
    r = await client.get(f"{API}/admin/agents/{aid}/health", headers=_hdr(admin_jwt))
    body = r.json()
    check(
        "H-4 无心跳 agent → last_seen_ts=null + 全零 + sdk_connected=false"
        "（§9.1「查询窗内无心跳上报」判据的载体）",
        r.status_code == 200
        and body["last_seen_ts"] is None
        and body["report_1min"] == 0
        and body["report_5min"] == 0
        and body["dropped"] == {}
        and body["sdk_connected"] is False,
        f"{r.status_code} {body}",
    )


async def h5_unknown_agent(client, admin_jwt: str) -> None:
    r = await client.get(f"{API}/admin/agents/{UNKNOWN_ID}/health", headers=_hdr(admin_jwt))
    check(
        "H-5 未知 agent id → 400 ERR_CONFIG_0001（不伪装成「查询窗内无心跳上报」的空态）",
        r.status_code == 400 and r.json()["code"] == "ERR_CONFIG_0001",
        f"{r.status_code} {r.text[:80]}",
    )


async def main() -> None:
    db = Settings()
    engine = create_async_engine(db.sqlalchemy_url)
    app = create_app(_settings())
    app.state.settings = _settings()  # ASGITransport 不跑 lifespan ⇒ 手挂（同 admin_probe）
    es = AsyncElasticsearch(_settings().es_url)
    # ASGITransport 不跑 lifespan ⇒ client 与 settings 都要手挂（同 admin_probe）
    app.state.es_query = es

    async def _override_session():
        async with AsyncSession(engine, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    try:
        await _cleanup(engine)
        admin_id, viewer_id, a_empty, a_sdk = await _seed(engine)
        admin_jwt = _jwt(admin_id, "admin")
        viewer_jwt = _jwt(viewer_id, "viewer")
        picked = await _pick_existing_agent_with_heartbeat(engine, es)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://probe") as client:
            await h1_auth(client, viewer_jwt, a_empty)
            await h4_empty_state(client, admin_jwt, a_empty)
            await h5_unknown_agent(client, admin_jwt)
            if picked is None:
                print("[SKIP] H-2：ES 里没有「真库 agent 表里存在」的心跳 doc（前置不成立）")
            else:
                await h2_real_heartbeats(es, client, admin_jwt, picked[0], picked[1])
            # Kafka/ES 地址取**容器内真实配置**（`Settings()` 读环境），不是 `_settings()`
            # 那个只为签 JWT 的测试配置（它的 kafka_bootstrap 默认值指向宿主 localhost）。
            await h3_live_sdk_heartbeat(es, client, admin_jwt, db, a_sdk)
    finally:
        await _drop_probe_docs(es, AGENT_SDK)
        await es.close()
        await _cleanup(engine)
        await engine.dispose()
    print("\n===== admin_health_probe 结果 =====")
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} 项失败 → {FAILURES}")
        sys.exit(1)
    print("全绿：§8.5 health 端点（真 ES 对齐 / 真 Kafka 活心跳 / 空态 / 鉴权 / 未知 id）")


if __name__ == "__main__":
    asyncio.run(main())
