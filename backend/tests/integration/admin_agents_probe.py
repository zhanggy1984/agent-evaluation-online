"""§8.5 字典面真库集成探针（T-3.12 批 2a-1）。容器内运行：

    docker exec obs-backend python /app/tests/integration/admin_agents_probe.py

形态照 `admin_probe.py`：真库 AsyncSession 挂 `get_session` override（**`expire_on_commit=False`
必须与生产同参**，否则「commit 后读属性」这类生产可用的写法在此炸 MissingGreenlet，属假红）
+ httpx ASGITransport 直打端点 + 真 JWT、真角色行。

**为什么必须真库**（单测替身做不到的）：
  - `FakeAsyncSession` 按等值匹配**只取首行** ⇒ 多行列表语义（`interface_count` 真值、
    「另一 agent 的接口不出现」）在单测里根本验不了；
  - 唯一键 `uk_interface(agent_id, interface)`、`llm_source` **原生 MySQL ENUM** 的读写往返
    （写 `manual` 回读是否仍是 `manual`）；
  - `session.get()` 走真主键、`updated_by` 真落库；
  - 审计行在 `conversion_record` 的真落库（`cluster_id` NULL、`actor_user_id` 取真 id）。

覆盖：
  G-1  鉴权双证：无 token → 401 ERR_AUTH_0001；**真 viewer 角色行** → 403 ERR_AUTH_0002
  G-2  `GET /agents` 是 **MySQL 字典面**（判据性：**含 enable=0 的 agent**，ES 观测面不含）
       + `interface_count` 与真库逐一对齐
  G-3  `toggle`：翻转 + **落库回读** + 审计行（action/actor/cluster_id NULL）+ 再翻回
  G-4  接口列表：**只含本 agent**（另一 agent 的接口必须不出现）+ `truncated`
  G-5  `PUT /interfaces/{id}`：llm 补标 + `llm_suspect` 解除 + `llm_source` ENUM 往返 +
       审计（**等于谁**，非「不为 0」）+ 非法 `llm_source` 400 + **多余 `interface` 字段被忽略**
       （证明「改串无入参载体」这一裁定的实际行为）+ **空改动不写审计**

**未覆盖（如实标注，不是通过）**：`_INTERFACE_MAX=500` 的**截断分支**——需造 501 行，
探针不做；该分支由「上限 + `truncated` 字段存在」这一结构性事实承担，**未做容量型取证**。

隔离：用户名前缀 `admga-`、agent 名前缀 `admga-`、接口串前缀 `admga-`；开头/结尾清理；
**只在自己造的 agent 上改 `enable`**（不碰 dev 库既有行 ⇒ 无漂移需还原）。退出码全绿 0。
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.agent import Agent, Interface  # noqa: E402
from app.models.error_flow import ConversionRecord  # noqa: E402
from app.models.user import User, UserSession  # noqa: E402

FAILURES: list[str] = []
API = "/api/v1"
PREFIX = "admga-"
ADMIN_USER = PREFIX + "admin"
VIEWER_USER = PREFIX + "viewer"
PW = "probe-pass-1234"
AGENT_ON = PREFIX + "agent-on"
AGENT_OFF = PREFIX + "agent-off"
IFACE_ON = PREFIX + "iface-on"
IFACE_OFF = PREFIX + "iface-off"
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
    """直接签发（登录链已由批 1 的 A-7 真登录验过）；角色仍以**库内行**为准（deps 查库取）。"""
    return create_access_token(_settings(), uid, role)


# ---------- 现场 ----------


async def _cleanup(engine) -> None:
    async with AsyncSession(engine) as s:
        aids = list(
            (await s.execute(select(Agent.id).where(Agent.name.like(PREFIX + "%")))).scalars().all()
        )
        if aids:
            await s.execute(delete(Interface).where(Interface.agent_id.in_(aids)))
            await s.execute(delete(Agent).where(Agent.id.in_(aids)))
        uids = list(
            (await s.execute(select(User.id).where(User.username.like(PREFIX + "%"))))
            .scalars()
            .all()
        )
        if uids:
            await s.execute(delete(UserSession).where(UserSession.user_id.in_(uids)))
            await s.execute(delete(User).where(User.id.in_(uids)))
        # 只清本探针写的审计行（detail 里必含 admga- 前缀）
        await s.execute(
            delete(ConversionRecord).where(ConversionRecord.detail.like("%" + PREFIX + "%"))
        )
        await s.commit()


async def _seed(engine) -> tuple[int, int, int, int, int]:
    """返回 (admin_id, viewer_id, agent_on, agent_off, iface_on)。

    agent_off 的 `enable=0` 是 **G-2 的判据载体**：它必须出现在 `/admin/agents` 里
    ——ES 观测面（`/metrics/agents`，近 7d 有流量）永远不会返回它。
    """
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
        a_on = Agent(
            name=AGENT_ON, display_name="探针 agent（启用）", enable=1, backflow_allow=1,
            route_source="manual",
        )
        a_off = Agent(
            name=AGENT_OFF, display_name="探针 agent（停用）", enable=0, backflow_allow=1,
            route_source="manual",
        )
        s.add_all([a_on, a_off])
        await s.flush()
        i_on = Interface(
            agent_id=a_on.id, interface=IFACE_ON, method="POST", path="/admga/x",
            llm=0, llm_source="config", llm_suspect=1, body_search=0, status=1,
        )
        i_off = Interface(
            agent_id=a_off.id, interface=IFACE_OFF, method="GET", path="/admga/y",
            llm=0, llm_source="config", llm_suspect=0, body_search=0, status=1,
        )
        s.add_all([i_on, i_off])
        await s.commit()
        return admin.id, viewer.id, a_on.id, a_off.id, i_on.id


# ---------- 场景 ----------


async def g1_auth(client, viewer_jwt: str) -> None:
    r = await client.get(f"{API}/admin/agents")
    check(
        "G-1a 无 token → 401 ERR_AUTH_0001",
        r.status_code == 401 and r.json()["code"] == "ERR_AUTH_0001",
        f"{r.status_code} {r.text[:80]}",
    )
    r = await client.get(f"{API}/admin/agents", headers=_hdr(viewer_jwt))
    check(
        "G-1b 真 viewer 角色行 → 403 ERR_AUTH_0002",
        r.status_code == 403 and r.json()["code"] == "ERR_AUTH_0002",
        f"{r.status_code} {r.text[:80]}",
    )


async def g2_agents_dict(engine, client, admin_jwt: str, agent_on: int, agent_off: int) -> None:
    r = await client.get(f"{API}/admin/agents", headers=_hdr(admin_jwt))
    body = r.json()
    by_id = {a["id"]: a for a in body}
    check(
        "G-2a 200 且为 MySQL 字典面（含 enable=0 的 agent——ES 观测面不含）",
        r.status_code == 200 and by_id.get(agent_off, {}).get("enable") == 0,
        f"{r.status_code} 共 {len(body)} 个 agent；"
        f"停用者 enable={by_id.get(agent_off, {}).get('enable')!r}",
    )
    async with AsyncSession(engine) as s:
        truth = len(
            (
                await s.execute(select(Interface.id).where(Interface.agent_id == agent_on))
            )
            .scalars()
            .all()
        )
    got = by_id.get(agent_on, {}).get("interface_count")
    check(
        "G-2b interface_count 与真库一致（等于真值，非「不为 0」）",
        got == truth,
        f"接口数 {got} vs 真库 {truth}",
    )
    check(
        "G-2c 字典行字段齐（route_source/backflow_allow/display_name）",
        by_id.get(agent_on, {}).get("route_source") == "manual"
        and by_id.get(agent_on, {}).get("backflow_allow") == 1
        and by_id.get(agent_on, {}).get("display_name") == "探针 agent（启用）",
        f"{by_id.get(agent_on)}",
    )


async def g3_toggle(engine, client, admin_jwt: str, admin_id: int, agent_on: int) -> None:
    r = await client.post(f"{API}/admin/agents/{agent_on}/toggle", headers=_hdr(admin_jwt))
    check(
        "G-3a toggle 200 且 enable 1→0",
        r.status_code == 200 and r.json()["enable"] == 0,
        f"{r.status_code} {r.text[:80]}",
    )
    async with AsyncSession(engine) as s:
        row = await s.get(Agent, agent_on)
        check(
            "G-3b 落库回读 enable=0",
            row is not None and row.enable == 0,
            f"enable={row and row.enable}",
        )
        recs = (
            (
                await s.execute(
                    select(ConversionRecord).where(
                        ConversionRecord.action == "agent_toggle",
                        ConversionRecord.detail.like("%" + AGENT_ON + "%"),
                    )
                )
            )
            .scalars()
            .all()
        )
    check(
        "G-3c 审计行已落：actor=真 admin id / cluster_id NULL / detail 含 enable 1→0",
        len(recs) == 1
        and recs[0].actor_user_id == admin_id
        and recs[0].cluster_id is None
        and "enable 1→0" in recs[0].detail,
        f"{len(recs)} 行：{recs[0].detail if recs else '—'}",
    )
    r = await client.post(f"{API}/admin/agents/{agent_on}/toggle", headers=_hdr(admin_jwt))
    check(
        "G-3d 再翻回 1（语义是翻转，不是置 0）",
        r.status_code == 200 and r.json()["enable"] == 1,
        f"{r.status_code} enable={r.json().get('enable')}",
    )


async def g4_ifaces(client, admin_jwt: str, agent_on: int, agent_off: int) -> None:
    r = await client.get(f"{API}/admin/agents/{agent_on}/interfaces", headers=_hdr(admin_jwt))
    body = r.json()
    names = {i["interface"] for i in body["items"]}
    check(
        "G-4a 200 且**只含本 agent** 的接口（另一 agent 的不出现）",
        r.status_code == 200 and names == {IFACE_ON} and IFACE_OFF not in names,
        f"{r.status_code} {sorted(names)}",
    )
    check("G-4b truncated=False（未触上限）", body["truncated"] is False, f"{body['truncated']}")
    item = next((i for i in body["items"] if i["interface"] == IFACE_ON), {})
    check(
        "G-4c 字段齐（method/path/llm_source/status/first_seen_ts）",
        item.get("method") == "POST"
        and item.get("path") == "/admga/x"
        and item.get("llm_source") == "config"
        and item.get("status") == 1
        and item.get("first_seen_ts") is not None,
        f"{item}",
    )
    r2 = await client.get(f"{API}/admin/agents/{agent_off}/interfaces", headers=_hdr(admin_jwt))
    check(
        "G-4d 另一 agent 的列表里只有它自己的接口",
        {i["interface"] for i in r2.json()["items"]} == {IFACE_OFF},
        f"{sorted(i['interface'] for i in r2.json()['items'])}",
    )


async def g5_put(engine, client, admin_jwt: str, admin_id: int, iface_on: int) -> None:
    def _recs(s, rows):
        return [r for r in rows if r.action == "interface_dict_change"]

    r = await client.put(
        f"{API}/admin/interfaces/{iface_on}",
        headers=_hdr(admin_jwt),
        json={"llm": 1, "llm_source": "manual"},
    )
    body = r.json()
    check(
        "G-5a 200 且 llm=1 / llm_source=manual",
        r.status_code == 200 and body.get("llm") == 1 and body.get("llm_source") == "manual",
        f"{r.status_code} llm={body.get('llm')} src={body.get('llm_source')}",
    )
    check(
        "G-5b llm_suspect 1→0（人工确认解除疑似）",
        body.get("llm_suspect") == 0,
        f"{body.get('llm_suspect')}",
    )
    async with AsyncSession(engine) as s:
        row = await s.get(Interface, iface_on)
        check(
            "G-5c 落库回读：llm_source ENUM 往返 + updated_by = 真管理员名",
            (row.llm, row.llm_source, row.llm_suspect, row.updated_by)
            == (1, "manual", 0, ADMIN_USER),
            f"llm={row.llm} src={row.llm_source!r} suspect={row.llm_suspect} by={row.updated_by!r}",
        )
        rows = (
            (
                await s.execute(
                    select(ConversionRecord).where(
                        ConversionRecord.detail.like("%" + IFACE_ON + "%")
                    )
                )
            )
            .scalars()
            .all()
        )
        recs = _recs(s, rows)
    check(
        "G-5d 审计行：action=interface_dict_change / actor=真 admin id / 含 suspect 变更",
        len(recs) == 1
        and recs[0].actor_user_id == admin_id
        and recs[0].cluster_id is None
        and "llm_suspect 1→0" in recs[0].detail
        and "llm 0→1" in recs[0].detail,
        f"{len(recs)} 行：{recs[0].detail if recs else '—'}",
    )

    r = await client.put(
        f"{API}/admin/interfaces/{iface_on}", headers=_hdr(admin_jwt), json={"llm_source": "config"}
    )
    check(
        "G-5e 非法 llm_source（非 manual）→ 400 ERR_CONFIG_0001",
        r.status_code == 400 and r.json()["code"] == "ERR_CONFIG_0001",
        f"{r.status_code} {r.text[:80]}",
    )

    r = await client.put(
        f"{API}/admin/interfaces/{iface_on}",
        headers=_hdr(admin_jwt),
        json={"interface": "admga-hacked", "llm": 1},
    )
    check(
        "G-5f 多余字段 `interface` 被忽略 ⇒ 串不变（证明「改串无入参载体」）",
        r.status_code == 200 and r.json()["interface"] == IFACE_ON,
        f"{r.status_code} interface={r.json().get('interface')!r}",
    )

    r = await client.put(
        f"{API}/admin/interfaces/{iface_on}", headers=_hdr(admin_jwt), json={"llm": 1}
    )
    async with AsyncSession(engine) as s:
        rows = (
            (
                await s.execute(
                    select(ConversionRecord).where(
                        ConversionRecord.detail.like("%" + IFACE_ON + "%")
                    )
                )
            )
            .scalars()
            .all()
        )
    check(
        "G-5g 空改动不写审计（审计行数仍为 1，未随「点了没改」增长）",
        r.status_code == 200 and len(_recs(s, rows)) == 1,
        f"{r.status_code} 审计 {len(_recs(s, rows))} 行",
    )


async def main() -> None:
    db = Settings()
    engine = create_async_engine(db.sqlalchemy_url)
    app = create_app(_settings())
    app.state.settings = _settings()  # ASGITransport 不跑 lifespan ⇒ 手挂（同 admin_probe）

    async def _override_session():
        # expire_on_commit=False = 与生产 `core/db.get_session` 同参
        async with AsyncSession(engine, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    try:
        await _cleanup(engine)
        admin_id, viewer_id, agent_on, agent_off, iface_on = await _seed(engine)
        admin_jwt = _jwt(admin_id, "admin")
        viewer_jwt = _jwt(viewer_id, "viewer")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://probe") as client:
            await g1_auth(client, viewer_jwt)
            await g2_agents_dict(engine, client, admin_jwt, agent_on, agent_off)
            await g3_toggle(engine, client, admin_jwt, admin_id, agent_on)
            await g4_ifaces(client, admin_jwt, agent_on, agent_off)
            await g5_put(engine, client, admin_jwt, admin_id, iface_on)
    finally:
        await _cleanup(engine)
        await engine.dispose()
    print("\n===== admin_agents_probe 结果 =====")
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} 项失败 → {FAILURES}")
        sys.exit(1)
    print(
        "全绿：§8.5 字典面四端点"
        "（读 MySQL 字典 / toggle+审计 / 接口列表按 agent / 补标+ENUM 往返）"
    )


if __name__ == "__main__":
    asyncio.run(main())
