"""admin 系统管理面（§8.6）真库集成探针（T-3.12 批 1）。容器内运行：

    docker exec obs-backend python /app/tests/integration/admin_probe.py

形态 = HTTP 级（照 `claim_probe.py` 骨架）：真库 AsyncSession 挂 `get_session` override +
httpx ASGITransport 打端点，**真 JWT、真账号、真口令登录**。

**为什么必须真库**（单测替身做不到的）：
  - `uk_dc(agent_id, config_key)` / `uk_user_username` 真唯一键语义；
  - MySQL 唯一索引对 NULL **不去重**（全局键 upsert 的「先查后插」正确性）；
  - 写侧与**组装读侧**贯通（`resolve_fallback_wordlist` 读到的 version 是否真随写入自增）；
  - `dict_config` 60s 进程内缓存的 `invalidate_cache()` 是否真生效（写后立读，不能等 60s）；
  - 真实 viewer 账号的 401/403 双层边界（**闭合 F-20**：既有 viewer 门控项是用
    localStorage 角色覆盖验的，从未用真账号验过）。

覆盖：
  A-1  鉴权双证：无 token → 401 ERR_AUTH_0001；真 viewer 账号 → 403 ERR_AUTH_0002
  A-2  配置读面：v1 全局键全量、缺行键 is_default=true
  A-3  配置写：version +1 + 落库回读 + 审计行（action/actor/cluster_id NULL/detail）
  A-4  非法写法：未知键 / 形状不符 / 越作用域 / 未知 agent → 400 ERR_CONFIG_0001
  A-5  写后立读：`invalidate_cache()` 真生效（全局键不经 60s 缓存读到新值）
  A-6  词表贯通：per-agent 写入 → `resolve_fallback_wordlist` 读到新词与新 version（D19）
  A-7  账号 CRUD + **真登录**：建 viewer → 登录拿 token → admin 端点 403 / viewer 端点 200
  A-8  禁用即时生效：status=0 + 会话吊销 → 旧 access 401、旧 refresh 401
  A-9  重置口令：旧口令登录失败、新口令成功（并连带吊销）
  A-10 自锁防护：停用自己 / 改自己角色 → 400；用户名重复 → 400

隔离：用户名前缀 `admp-`、agent 前缀 `admp-`；开头/结尾清理（user/session/agent/dc/conv）
并把**改过的配置键还原为探针前的原值**（探针不得留下 dev 库配置漂移）。退出码全绿 0。
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.converter.no_fallback_cfg import resolve_fallback_wordlist  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.core.dict_config import get_global_config, invalidate_cache  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.models.config import DictConfig  # noqa: E402
from app.models.error_flow import ConversionRecord  # noqa: E402
from app.models.user import User, UserSession  # noqa: E402

FAILURES: list[str] = []
API = "/api/v1"
UPREFIX = "admp-"
APREFIX = "admp-"
ADMIN_USER = UPREFIX + "admin"
# A-1b 用的「已存在 viewer」（仅造 token 验 403，不经 API 建）；A-7 走 API 建真实 viewer 账号
VIEWER_AUTH_USER = UPREFIX + "viewer-auth"
VIEWER_USER = UPREFIX + "viewer"
VIEWER_PW = "probe-pass-1234"
NEW_PW = "probe-pass-5678"
# 被探针改写的配置键（清理时还原为原值/原 version）
TOUCH_KEY = "claim_ttl_days"
_WORD_AGENT = APREFIX + "wl"
_original: dict = {}


def check(name: str, ok: bool, detail: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        FAILURES.append(name)


def _hdr(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


# ---------- 基建 ----------


async def _cleanup(engine) -> None:
    async with AsyncSession(engine) as s:
        uids = select(User.id).where(User.username.like(UPREFIX + "%"))
        # 审计行须在删 user 之前清（actor_user_id 指向探针 admin）
        await s.execute(
            delete(ConversionRecord).where(ConversionRecord.actor_user_id.in_(uids))
        )
        await s.execute(delete(UserSession).where(UserSession.user_id.in_(uids)))
        await s.execute(delete(User).where(User.username.like(UPREFIX + "%")))
        ag = select(Agent.id).where(Agent.name.like(APREFIX + "%"))
        await s.execute(delete(DictConfig).where(DictConfig.agent_id.in_(ag)))
        await s.execute(delete(Agent).where(Agent.name.like(APREFIX + "%")))
        await s.commit()


async def _cleanup_config(engine) -> None:
    """还原被探针改写的全局配置键（无原值则删行）——探针不留配置漂移。"""
    async with AsyncSession(engine) as s:
        row = (
            await s.execute(
                select(DictConfig).where(
                    DictConfig.config_key == TOUCH_KEY, DictConfig.agent_id.is_(None)
                )
            )
        ).scalar_one_or_none()
        orig = _original.get(TOUCH_KEY)
        if orig is None:
            if row is not None:
                await s.delete(row)
        elif row is None:
            s.add(
                DictConfig(
                    agent_id=None,
                    config_key=TOUCH_KEY,
                    config_value=orig["value"],
                    version=orig["version"],
                )
            )
        else:
            row.config_value, row.version = orig["value"], orig["version"]
        await s.commit()
        invalidate_cache()


async def _ensure_users(engine) -> tuple[int, int]:
    async with AsyncSession(engine) as s:
        ids = {}
        for name, role in ((ADMIN_USER, "admin"), (VIEWER_AUTH_USER, "viewer")):
            u = User(username=name, password_hash="x" * 60, role=role, status=1)
            s.add(u)
            await s.flush()
            ids[name] = u.id
        await s.commit()
        return ids[ADMIN_USER], ids[VIEWER_AUTH_USER]


async def _seed_word_agent(engine) -> int:
    async with AsyncSession(engine) as s:
        a = Agent(
            name=_WORD_AGENT,
            display_name=_WORD_AGENT,
            base_url=None,
            enable=1,
            route_source="auto_register",
            backflow_allow=1,
        )
        s.add(a)
        await s.flush()
        aid = a.id
        await s.commit()
        return aid


def _token(uid: int, role: str) -> str:
    from app.core.security import create_access_token

    return create_access_token(_settings(), uid, role)


_settings_cache: dict = {}


def _settings() -> Settings:
    if "s" not in _settings_cache:
        _settings_cache["s"] = Settings(
            app_env="test", resource_env="dev", jwt_secret="probe-jwt-" + "0" * 40
        )
    return _settings_cache["s"]


# ---------- 场景 ----------


async def a1_auth(engine, client, viewer_jwt) -> None:
    r = await client.get(f"{API}/admin/configs")
    check("A-1a 无 token → 401", r.status_code == 401 and r.json()["code"] == "ERR_AUTH_0001",
          f"{r.status_code} {r.text[:80]}")
    r = await client.get(f"{API}/admin/configs", headers=_hdr(viewer_jwt))
    check("A-1b 真 viewer 账号 → 403", r.status_code == 403 and r.json()["code"] == "ERR_AUTH_0002",
          f"{r.status_code} {r.text[:80]}")


async def a2_read(engine, client, token) -> None:
    r = await client.get(f"{API}/admin/configs", headers=_hdr(token))
    body = r.json()
    keys = {i["key"] for i in body}
    check("A-2a 配置读 200 且为 v1 全局键全量", r.status_code == 200 and TOUCH_KEY in keys,
          f"{r.status_code} 键数={len(body)}")
    check("A-2b 只返回 v1 生效键（无二期键）", "no_such_key" not in keys, f"{sorted(keys)[:4]}…")
    # 原值存档（清理时还原）
    async with AsyncSession(engine) as s:
        row = (
            await s.execute(
                select(DictConfig).where(
                    DictConfig.config_key == TOUCH_KEY, DictConfig.agent_id.is_(None)
                )
            )
        ).scalar_one_or_none()
        _original[TOUCH_KEY] = (
            None if row is None else {"value": row.config_value, "version": row.version}
        )
    item = next(i for i in body if i["key"] == TOUCH_KEY)
    check(
        "A-2c 缺行键按 seed 默认补位并标 is_default",
        item["is_default"] is (item["version"] == 0),
        f"version={item['version']} is_default={item['is_default']}",
    )


async def a3_write(engine, client, token, admin_id) -> None:
    before = await client.get(f"{API}/admin/configs", headers=_hdr(token))
    old = next(i for i in before.json() if i["key"] == TOUCH_KEY)
    r = await client.put(
        f"{API}/admin/configs", headers=_hdr(token), json={"key": TOUCH_KEY, "value": 21}
    )
    check("A-3a 全局键写入 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
    check("A-3b version 自增恰 +1", r.json()["version"] == old["version"] + 1,
          f"{old['version']} → {r.json()['version']}")

    async with AsyncSession(engine) as s:
        row = (
            await s.execute(
                select(DictConfig).where(
                    DictConfig.config_key == TOUCH_KEY, DictConfig.agent_id.is_(None)
                )
            )
        ).scalar_one_or_none()
        check("A-3c 值真落库", row is not None and row.config_value == 21,
              f"db={None if row is None else row.config_value}")
        check("A-3d updated_by 落当前 admin", row is not None and row.updated_by == ADMIN_USER,
              f"{None if row is None else row.updated_by}")
        conv = (
            await s.execute(
                select(ConversionRecord)
                .where(ConversionRecord.action == "config_change")
                .order_by(ConversionRecord.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        check(
            "A-3e 审计行（action/actor/cluster_id NULL/detail 含键名与旧→新）",
            conv is not None
            and conv.actor_user_id == admin_id
            and conv.cluster_id is None
            and TOUCH_KEY in (conv.detail or "")
            and str(old["version"]) in (conv.detail or ""),
            f"{None if conv is None else conv.detail}",
        )


async def a4_rejects(engine, client, token) -> None:
    cases = [
        ("A-4a 未知键", {"key": "no_such_key", "value": 1}),
        ("A-4b 形状不符（int 键给 str）", {"key": TOUCH_KEY, "value": "21"}),
        ("A-4c bool 混入 int 键", {"key": TOUCH_KEY, "value": True}),
        ("A-4d 全局键越作用域写", {"key": TOUCH_KEY, "value": 21, "agent_id": 1}),
        (
            "A-4e 未知 agent 写 per-agent 键",
            {"key": "timeout_ms", "value": 1000, "agent_id": 999999},
        ),
    ]
    for name, body in cases:
        r = await client.put(f"{API}/admin/configs", headers=_hdr(token), json=body)
        check(name, r.status_code == 400 and r.json()["code"] == "ERR_CONFIG_0001",
              f"{r.status_code} {r.text[:80]}")


async def a5_cache_invalidated(engine, client, token) -> None:
    """写后**立读**必须是新值：证明 `invalidate_cache()` 生效，而非读到 60s 旧缓存。"""
    async with AsyncSession(engine) as s:
        await get_global_config(s, TOUCH_KEY, 14)  # 先填充缓存（旧值）
    r = await client.put(
        f"{API}/admin/configs", headers=_hdr(token), json={"key": TOUCH_KEY, "value": 28}
    )
    async with AsyncSession(engine) as s:
        v = await get_global_config(s, TOUCH_KEY, 14)
    check("A-5 写后立读为新值（缓存已清）", r.status_code == 200 and v == 28, f"读到 {v}")


async def a6_wordlist(engine, client, token, agent_id: int) -> None:
    r = await client.put(
        f"{API}/admin/configs",
        headers=_hdr(token),
        json={"key": "fallback_utterance", "value": ["抱歉，暂时无法回答"], "agent_id": agent_id},
    )
    check("A-6a per-agent 词表写入 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
    async with AsyncSession(engine) as s:
        words, ver = await resolve_fallback_wordlist(s, agent_name=_WORD_AGENT)
        check(
            "A-6b 组装读侧读到新词 + 新 version（D19 wordlist_version）",
            words == ["抱歉，暂时无法回答"] and ver == r.json()["version"],
            f"words={words} version={ver}",
        )
    r2 = await client.put(
        f"{API}/admin/configs",
        headers=_hdr(token),
        json={"key": "fallback_utterance", "value": ["再见"], "agent_id": agent_id},
    )
    async with AsyncSession(engine) as s:
        _, ver2 = await resolve_fallback_wordlist(s, agent_name=_WORD_AGENT)
        check("A-6c 二次写入 version 再 +1（单调）", ver2 == r2.json()["version"] == ver + 1,
              f"{ver} → {ver2}")
    r3 = await client.put(
        f"{API}/admin/configs",
        headers=_hdr(token),
        json={"key": "fallback_utterance", "value": [], "agent_id": agent_id},
    )
    check("A-6d 空词表合法（fail-closed 载体）", r3.status_code == 200, f"{r3.status_code}")


async def a7_viewer_real_login(engine, client, viewer_id, admin_jwt) -> dict:
    """真实 viewer 账号闭环：建号 → 真登录 → 边界（admin 403 / viewer 200）。"""
    r = await client.post(
        f"{API}/admin/users",
        headers=_hdr(admin_jwt),
        json={"username": VIEWER_USER, "password": VIEWER_PW, "role": "viewer",
              "display_name": "探针查看者"},
    )
    check("A-7a 建 viewer 账号 201", r.status_code == 201, f"{r.status_code} {r.text[:120]}")
    new_id = r.json()["id"]  # 用**API 建出来的**账号 id（不是 a1 用的那个 viewer-auth）
    check("A-7b 出参不回口令", "password" not in r.text and "hash" not in r.text, r.text[:80])
    r = await client.post(
        f"{API}/auth/login", json={"username": VIEWER_USER, "password": VIEWER_PW}
    )
    check("A-7c 新账号真登录成功（口令哈希可校验）", r.status_code == 200, f"{r.status_code}")
    tok = r.json()["access_token"]
    rtok = r.json()["refresh_token"]
    check(
        "A-7d 登录返回 viewer 角色",
        r.json()["user"]["role"] == "viewer",
        r.json()["user"]["role"],
    )

    r = await client.get(f"{API}/admin/users", headers=_hdr(tok))
    check("A-7e 真 viewer 打 admin 端点 → 403", r.status_code == 403, f"{r.status_code}")
    r = await client.get(f"{API}/backflow/overview", headers=_hdr(tok))
    check("A-7f 真 viewer 打 viewer 端点 → 200", r.status_code == 200, f"{r.status_code}")
    return {"access": tok, "refresh": rtok, "id": new_id}


async def a8_disable(engine, client, admin_jwt, tokens) -> None:
    viewer_id = tokens["id"]
    r = await client.put(
        f"{API}/admin/users/{viewer_id}", headers=_hdr(admin_jwt), json={"status": 0}
    )
    check(
        "A-8a 禁用 200 且 status=0",
        r.status_code == 200 and r.json()["status"] == 0 and r.json()["id"] == viewer_id,
        f"{r.status_code} {r.text[:80]}",
    )
    async with AsyncSession(engine) as s:
        live = (
            await s.execute(
                select(UserSession).where(
                    UserSession.user_id == viewer_id, UserSession.revoked_at.is_(None)
                )
            )
        ).scalars().all()
        check("A-8b 该用户全部会话被吊销（第二半）", len(live) == 0, f"未吊销 {len(live)} 条")
    r = await client.get(f"{API}/backflow/overview", headers=_hdr(tokens["access"]))
    check("A-8c 旧 access 立即 401（status 校验）", r.status_code == 401, f"{r.status_code}")
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh"]})
    check(
        "A-8d 旧 refresh 立即 401（会话已吊销）", r.status_code == 401, f"{r.status_code}"
    )


async def a9_reset_password(engine, client, admin_jwt, tokens) -> None:
    r = await client.put(
        f"{API}/admin/users/{tokens['id']}",
        headers=_hdr(admin_jwt),
        json={"status": 1, "password": NEW_PW},
    )
    check("A-9a 启用 + 重置口令 200", r.status_code == 200 and r.json()["status"] == 1,
          f"{r.status_code}")
    r = await client.post(
        f"{API}/auth/login", json={"username": VIEWER_USER, "password": VIEWER_PW}
    )
    check("A-9b 旧口令登录失败", r.status_code == 401, f"{r.status_code}")
    r = await client.post(
        f"{API}/auth/login", json={"username": VIEWER_USER, "password": NEW_PW}
    )
    check("A-9c 新口令登录成功", r.status_code == 200, f"{r.status_code}")


async def a10_guards(engine, client, admin_jwt, admin_id) -> None:
    r = await client.put(
        f"{API}/admin/users/{admin_id}", headers=_hdr(admin_jwt), json={"status": 0}
    )
    check("A-10a 停用自己 → 400（防锁死）", r.status_code == 400, f"{r.status_code}")
    r = await client.put(
        f"{API}/admin/users/{admin_id}", headers=_hdr(admin_jwt), json={"role": "viewer"}
    )
    check("A-10b 改自己角色 → 400（防锁死）", r.status_code == 400, f"{r.status_code}")
    r = await client.post(
        f"{API}/admin/users",
        headers=_hdr(admin_jwt),
        json={"username": VIEWER_USER, "password": VIEWER_PW, "role": "viewer"},
    )
    check("A-10c 用户名重复 → 400", r.status_code == 400 and r.json()["code"] == "ERR_CONFIG_0001",
          f"{r.status_code} {r.text[:80]}")
    r = await client.post(
        f"{API}/admin/users",
        headers=_hdr(admin_jwt),
        json={"username": UPREFIX + "short", "password": "123", "role": "viewer"},
    )
    check("A-10d 口令过短 → 422（schema 最小规则）", r.status_code == 422, f"{r.status_code}")


async def main() -> None:
    db = Settings()
    engine = create_async_engine(db.sqlalchemy_url)
    app = create_app(_settings())
    app.state.settings = _settings()

    async def _override_session():
        # expire_on_commit=False = 与生产 `core/db.get_session` 同参（探针不得比生产更严：
        # 默认 True 会让「commit 后读属性」这类生产可用的写法在此炸 MissingGreenlet，属假红）
        async with AsyncSession(engine, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    try:
        await _cleanup(engine)
        await _cleanup_config(engine)
        admin_id, viewer_id = await _ensure_users(engine)
        agent_id = await _seed_word_agent(engine)
        admin_jwt = _token(admin_id, "admin")
        viewer_jwt = _token(viewer_id, "viewer")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://probe"
        ) as client:
            await a1_auth(engine, client, viewer_jwt)
            await a2_read(engine, client, admin_jwt)
            await a3_write(engine, client, admin_jwt, admin_id)
            await a4_rejects(engine, client, admin_jwt)
            await a5_cache_invalidated(engine, client, admin_jwt)
            await a6_wordlist(engine, client, admin_jwt, agent_id)
            tokens = await a7_viewer_real_login(engine, client, viewer_id, admin_jwt)
            await a8_disable(engine, client, admin_jwt, tokens)
            await a9_reset_password(engine, client, admin_jwt, tokens)
            await a10_guards(engine, client, admin_jwt, admin_id)
    finally:
        await _cleanup(engine)
        await _cleanup_config(engine)
        await engine.dispose()
    print("\n===== admin_probe 结果 =====")
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} 项失败 → {FAILURES}")
        sys.exit(1)
    print("全绿：§8.6 配置写入/version/审计 + 账号 CRUD 与真 viewer 登录边界（F-20 闭合）")


if __name__ == "__main__":
    asyncio.run(main())
