"""§8.5 凭证**脱敏读面**真库集成探针（T-3.12 批 2b）。容器内运行：

    docker exec obs-backend python /app/tests/integration/admin_credential_probe.py

形态照 `admin_agents_probe.py`：真库 AsyncSession 挂 `get_session` override
（**`expire_on_commit=False` 必须与生产同参**）+ httpx ASGITransport 直打端点 + 真 JWT、真角色行。

**为什么必须真库**（单测替身做不到的）：
  - `agent_credential` 是一张**真表**，本批之前**全仓零读写方**、dev 库 **0 行**（2026-09-14 实测）
    ——「有行时读得对」这条**在单测里只能靠我手写的 `SimpleNamespace`**，真列往返（`topic`、
    `active`、`rotated_at`/`created_at` 的 DATETIME 序列化）只有真库能验；
  - 「未发凭证 ⇒ null」这条**必须有对照组**才叫判据：**恒返 null 的端点**与**正确的端点**在
    单 agent 场景下输出完全一样 ⇒ 本探针**同时造一个「有凭证」的 agent**做对照（C-2 的判据载体）。

覆盖：
  C-1  鉴权双证：无 token → 401 ERR_AUTH_0001；**真 viewer 角色行** → 403 ERR_AUTH_0002
  C-2  **有/无凭证的对照**：agent_a（无行）⇒ `credential=null`；agent_b（有行）⇒ 非 null
       —— 二者同时成立才排除「端点恒返 null」这一假绿
  C-3  有行时字段与**真库逐一对齐**（等于真值，非「不为 0」）
  C-4  **脱敏**：响应体**不出现** `secret_cipher` 的真值（用真库取出的值反查，不是查关键词）
  C-5  未知 agent id ⇒ 400 ERR_CONFIG_0001（不得伪装成「没发凭证」）

**未覆盖（如实标注，不是通过）**：
  - `rotate`：**本批不存在该端点**（§8.5 `:1138` 的三个动作全在 infra，已下移 T-5.3）⇒ 无用例可写。
  - `Fernet` 加解密：本批**不经过**该路径（端点连 `secret_cipher` 列都不读）⇒ 不验，也无从验
    （全仓无实现）。`secret_cipher` 在本探针里只是一个**普通字符串**，不代表真加密语义已成立。

隔离：agent 名前缀 `probec-`、`kafka_username` 前缀 `probec-`、用户前缀 `probec-`；
开头/结尾清理；退出码全绿 0。
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
from app.models.agent import Agent, AgentCredential  # noqa: E402
from app.models.user import User, UserSession  # noqa: E402

FAILURES: list[str] = []
API = "/api/v1"
PREFIX = "probec-"
ADMIN_USER = PREFIX + "admin"
VIEWER_USER = PREFIX + "viewer"
PW = "probe-pass-1234"
AGENT_NO_CRED = PREFIX + "agent-nocred"  # C-2 的空态侧
AGENT_WITH_CRED = PREFIX + "agent-cred"  # C-2/C-3 的对照侧
TOPIC = "dev.obs.agent." + AGENT_WITH_CRED
CIPHER_VALUE = PREFIX + "cipher-must-never-6a1f9c-appear"  # 真值：响应里出现即泄密
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
            (
                await s.execute(select(Agent.id).where(Agent.name.like(PREFIX + "%")))
            )
            .scalars()
            .all()
        )
        if aids:
            # 先删凭证行再删 agent（本表无 FK，但顺序上先子后父，防将来补 FK 时静默失效）
            await s.execute(delete(AgentCredential).where(AgentCredential.agent_id.in_(aids)))
            await s.execute(delete(Agent).where(Agent.id.in_(aids)))
        # 兜底：按 kafka_username 前缀清（防上一轮 agent 已删、凭证行成孤儿）
        await s.execute(
            delete(AgentCredential).where(AgentCredential.kafka_username.like(PREFIX + "%"))
        )
        uids = list(
            (
                await s.execute(select(User.id).where(User.username.like(PREFIX + "%")))
            )
            .scalars()
            .all()
        )
        if uids:
            await s.execute(delete(UserSession).where(UserSession.user_id.in_(uids)))
            await s.execute(delete(User).where(User.id.in_(uids)))
        await s.commit()


async def _seed(engine) -> tuple[int, int, int, int]:
    """返回 (admin_id, viewer_id, agent_nocred, agent_cred)。

    **agent_nocred 与 agent_cred 必须成对**：C-2 的判据是「一个有、一个没有」——
    只有「没有」那一侧的话，「端点恒返 null」也会全绿。
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
        a_nocred = Agent(
            name=AGENT_NO_CRED,
            display_name="探针 agent（无凭证）",
            enable=1,
            backflow_allow=1,
            route_source="manual",
        )
        a_cred = Agent(
            name=AGENT_WITH_CRED,
            display_name="探针 agent（有凭证）",
            enable=1,
            backflow_allow=1,
            route_source="manual",
        )
        s.add_all([a_nocred, a_cred])
        await s.flush()
        s.add(
            AgentCredential(
                agent_id=a_cred.id,
                kafka_username=PREFIX + "obs-cred",
                secret_cipher=CIPHER_VALUE,
                topic=TOPIC,
                active=1,
                rotated_at=None,
            )
        )
        await s.commit()
        return admin.id, viewer.id, a_nocred.id, a_cred.id


# ---------- 场景 ----------


async def c1_auth(client, viewer_jwt: str, agent_id: int) -> None:
    url = f"{API}/admin/agents/{agent_id}/credential"
    r = await client.get(url)
    check(
        "C-1a 无 token → 401 ERR_AUTH_0001",
        r.status_code == 401 and r.json()["code"] == "ERR_AUTH_0001",
        f"{r.status_code} {r.text[:80]}",
    )
    r = await client.get(url, headers=_hdr(viewer_jwt))
    check(
        "C-1b 真 viewer 角色行 → 403 ERR_AUTH_0002",
        r.status_code == 403 and r.json()["code"] == "ERR_AUTH_0002",
        f"{r.status_code} {r.text[:80]}",
    )


async def c2_control(client, admin_jwt: str, agent_nocred: int, agent_cred: int) -> None:
    """**本探针的核心**：有/无两侧同时成立，才排除「端点恒返 null」。"""
    r_no = await client.get(
        f"{API}/admin/agents/{agent_nocred}/credential", headers=_hdr(admin_jwt)
    )
    body_no = r_no.json()
    check(
        "C-2a 无凭证行 ⇒ 200 且 credential=null（合法态，不是 404）",
        r_no.status_code == 200 and body_no.get("credential") is None,
        f"{r_no.status_code} {r_no.text[:120]}",
    )

    r_yes = await client.get(
        f"{API}/admin/agents/{agent_cred}/credential", headers=_hdr(admin_jwt)
    )
    body_yes = r_yes.json()
    check(
        "C-2b 【对照】有凭证行 ⇒ 非 null —— 两侧同时成立才排除「恒返 null」的假绿",
        r_yes.status_code == 200 and body_yes.get("credential") is not None,
        f"{r_yes.status_code} credential={body_yes.get('credential')!r}",
    )


async def c3_fields_match_db(engine, client, admin_jwt: str, agent_cred: int) -> None:
    async with AsyncSession(engine) as s:
        row = (
            await s.execute(select(AgentCredential).where(AgentCredential.agent_id == agent_cred))
        ).scalar_one()
        truth = {
            "kafka_username": row.kafka_username,
            "topic": row.topic,
            "active": row.active,
            "rotated_at": row.rotated_at,
        }
    r = await client.get(f"{API}/admin/agents/{agent_cred}/credential", headers=_hdr(admin_jwt))
    item = r.json()["credential"]
    check(
        "C-3a kafka_username / topic / active 与真库逐字一致（等于真值，非「不为空」）",
        item["kafka_username"] == truth["kafka_username"]
        and item["topic"] == truth["topic"]
        and item["active"] == truth["active"],
        f"HTTP {item['kafka_username']!r}/{item['topic']!r}/active={item['active']} "
        f"vs 库 {truth['kafka_username']!r}/{truth['topic']!r}/active={truth['active']}",
    )
    check(
        "C-3b rotated_at=null 原样透传（未轮换过，不得捏造时间）",
        item["rotated_at"] is None and truth["rotated_at"] is None,
        f"HTTP {item['rotated_at']!r} vs 库 {truth['rotated_at']!r}",
    )
    check(
        "C-3c created_at 为服务端默认列，已由真库回填（非 null、非占位）",
        isinstance(item["created_at"], str) and len(item["created_at"]) >= 19,
        f"created_at={item['created_at']!r}",
    )


async def c4_no_secret_leak(client, admin_jwt: str, agent_cred: int) -> None:
    """用**真库的密文值**反查响应体，而不是查 `"secret"` 关键词。

    关键词判据会被「改个字段名」绕过；真值反查不会——它是「这条数据有没有出去」的直接证据。
    """
    r = await client.get(f"{API}/admin/agents/{agent_cred}/credential", headers=_hdr(admin_jwt))
    raw = r.text
    check(
        "C-4a 响应体不含真库 secret_cipher 的真值（真值反查，非关键词）",
        CIPHER_VALUE not in raw,
        f"密文值{'未' if CIPHER_VALUE not in raw else '**已**'}出现在响应体",
    )
    check(
        "C-4b 响应体连 'secret' 字样都没有（键名也不得泄漏该列存在）",
        "secret" not in raw.lower(),
        f"{raw[:160]}",
    )


async def c5_unknown_agent(client, admin_jwt: str) -> None:
    r = await client.get(f"{API}/admin/agents/2147483600/credential", headers=_hdr(admin_jwt))
    check(
        "C-5 未知 agent id ⇒ 400 ERR_CONFIG_0001（不得伪装成「没发凭证」）",
        r.status_code == 400 and r.json()["code"] == "ERR_CONFIG_0001",
        f"{r.status_code} {r.text[:100]}",
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
        admin_id, viewer_id, agent_nocred, agent_cred = await _seed(engine)
        admin_jwt = _jwt(admin_id, "admin")
        viewer_jwt = _jwt(viewer_id, "viewer")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://probe") as client:
            await c1_auth(client, viewer_jwt, agent_cred)
            await c2_control(client, admin_jwt, agent_nocred, agent_cred)
            await c3_fields_match_db(engine, client, admin_jwt, agent_cred)
            await c4_no_secret_leak(client, admin_jwt, agent_cred)
            await c5_unknown_agent(client, admin_jwt)
    finally:
        await _cleanup(engine)
        await engine.dispose()
    print("\n===== admin_credential_probe 结果 =====")
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} 项失败 → {FAILURES}")
        sys.exit(1)
    print("全绿：§8.5 凭证脱敏读面（401/403 / 有-无对照 / 字段等于真值 / 真值反查不泄漏）")


if __name__ == "__main__":
    asyncio.run(main())
