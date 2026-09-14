"""批 B 驳回路径真机种子：造 4 份**必然被 offline 驳回**的在线载荷。

与 `backflow_e2e_seed.py` 同法（复用 claim_probe 装置、不清理），但目标是 **offline 的
`_reject` 四条码**——批 B 提交时明确登记为「未覆盖：只验了激活主干」。本脚本把它补上。

四条各自的构造依据（读 `app/core/error_payload.validate_envelope` 判定表得来，非猜）：

- `content_gap`：agent 用 `customer-service`（其 `fallback_utterance` = `[]`）
  → 空词表在**最早的** validate 就被拦。
- `offline_cap_gap`：agent=`good-question`（词表非空）+ cluster.interface 用**离线未登记**的路径
  → `resolve_interface` → None。
- `offline_cap_gap`：agent 用**离线未登记**的 online agent（需先建该 agent + 其非空词表）
  → `resolve_agent` → None。
- `version_drift`：组装后**直接 UPDATE `payload_json`** 把 schema_version 改成 `9.9`
  → 模拟「online 升级了 schema、offline 未跟上」。

⚠️ 第 3 行是**有争议的一条**：若不建那个 online agent，`resolve_fallback_wordlist` 对未知
agent 必返 `([], 0)` ⇒ 空词表 ⇒ 更早的 validate 判 `content_gap`，于是 `resolve_agent` 那段
**永远轮不到**。即「agent 未登记」分支是否可达，取决于**存在一个 online 有词表、offline 没
登记的 agent** 这种状态——本脚本把它造出来实测，而不是靠读码下结论。

第 4 行是**绕过 online API 的写**：直接改 `error_case_link.payload_json`。这是数据注入不是
代码路径绕过——真机里 schema 漂移就是这样出现的（online 升级、offline 未跟上），且 online
`/pull/payloads` 读库时不复校 payload 内的 schema_version，故注入后能原样送达 offline。
"""
import asyncio
import json
import sys
from datetime import datetime, timezone

import claim_probe as cp
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings
from app.core.db import get_session
from app.main import create_app
from app.models.agent import Agent
from app.models.error_flow import ErrorCaseLink
from app.models.user import User

# ---- 四个场景 ----
AGENT_EMPTY_WORDS = "customer-service"          # online 侧 fallback_utterance = []
AGENT_OK = "good-question"                       # 词表非空 + 离线已登记
AGENT_UNKNOWN = "probe-unknown-agent"            # 只在 online 登记
IFACE_UNREGISTERED = "POST /api/probe/not-registered/{id}"
IFACE_OK = "POST /api/chat/{session_id}"
WORDS = ["抱歉，我暂时无法回答这个问题", "系统繁忙，请稍后再试"]
DRIFT_SCHEMA = "9.9"

SCENARIOS = [
    ("content_gap", AGENT_EMPTY_WORDS, IFACE_OK),
    ("cap_gap_interface", AGENT_OK, IFACE_UNREGISTERED),
    ("cap_gap_agent", AGENT_UNKNOWN, IFACE_OK),
    ("version_drift", AGENT_OK, IFACE_OK),
]


async def _ensure_agent(engine, name: str) -> int:
    async with AsyncSession(engine) as s:
        aid = await s.scalar(select(Agent.id).where(Agent.name == name))
        if aid is not None:
            return aid
        a = Agent(name=name, display_name=name, base_url=None, enable=1,
                  route_source="auto_register", backflow_allow=1)
        s.add(a)
        await s.flush()
        aid = a.id
        await s.commit()
        return aid


async def _put_words(client, admin_token, agent_id: int) -> None:
    r = await client.put(
        "/api/v1/admin/configs",
        json={"agent_id": agent_id, "key": "fallback_utterance", "value": WORDS},
        headers=cp._hdr(admin_token),
    )
    assert r.status_code == 200, f"词表写入失败：{r.status_code} {r.text}"


async def _find_link(engine, cid: int) -> ErrorCaseLink | None:
    async with AsyncSession(engine) as s:
        return (await s.scalars(
            select(ErrorCaseLink).where(ErrorCaseLink.cluster_id == cid))).first()


async def _wait_links(engine, cids: list[int], *, timeout: float) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        got = {}
        for cid in cids:
            ln = await _find_link(engine, cid)
            if ln is not None:
                got[cid] = ln
        if len(got) == len(cids):
            return got
        await asyncio.sleep(3)
    return got


async def main() -> None:
    db = Settings()
    engine = create_async_engine(db.sqlalchemy_url)
    app = create_app(cp._app_settings())
    app.state.settings = cp._app_settings()

    async def _override_session():
        async with AsyncSession(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override_session

    try:
        admin_id = await _ensure_user_id(engine, cp.ADMIN, "admin")
        admin_token = cp.create_access_token(cp._app_settings(), admin_id, "admin")
        viewer_id = await _ensure_user_id(engine, cp.VIEWER, "viewer")
        viewer_token = cp.create_access_token(cp._app_settings(), viewer_id, "viewer")

        unknown_id = await _ensure_agent(engine, AGENT_UNKNOWN)
        print(f"[seed] online agent {AGENT_UNKNOWN} id={unknown_id}")

        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://seed") as client:
            await _put_words(client, admin_token, unknown_id)

            # --- 1) 先全建簇（都停在 open），让 assemble_job 一轮扫全 ---
            cids = []
            for tag, agent, iface in SCENARIOS:
                cp.IFACE = iface  # _seed_cluster 调用时读模块全局
                snap = f"驳回场景 {tag} #{int(datetime.now().timestamp())}"
                cid = await cp._seed_cluster(engine, agent, snap)
                cids.append(cid)
                print(f"[seed] {tag}: cluster_id={cid} agent={agent} interface={iface!r}")

            links = await _wait_links(engine, cids, timeout=240)
            missing = [c for c in cids if c not in links]
            if missing:
                print(f"SEED_FAIL：cluster {missing} 240s 内未组装")
                sys.exit(1)
            for (tag, _, _), cid in zip(SCENARIOS, cids):
                print(f"[seed] {tag}: link={links[cid].id} payload_id={links[cid].payload_id}")

            # --- 2) version_drift：直接改 payload_json 的 schema_version ---
            drift_cid = cids[-1]
            async with AsyncSession(engine) as s:
                ln = await s.get(ErrorCaseLink, links[drift_cid].id)
                env = json.loads(ln.payload_json)
                before = env["schema_version"]
                print(f"[seed] version_drift: schema_version {before} → {DRIFT_SCHEMA}")
                env["schema_version"] = DRIFT_SCHEMA
                ln.payload_json = json.dumps(env, ensure_ascii=False)
                await s.commit()

            # --- 3) 全部 claim（此时 link 已存在，claim 不会再挡住组装）---
            for (tag, _, _), cid in zip(SCENARIOS, cids):
                status, resp = await cp._post(
                    client, f"clusters/{cid}/claim", viewer_token,
                    {"fix_version": "2026.09.14-r99"},
                )
                assert status == 200, f"claim 失败 {tag}: {status} {resp}"

        for (tag, _, _), cid in zip(SCENARIOS, cids):
            print(f"SCENARIO tag={tag} cluster_id={cid} payload_id={links[cid].payload_id}")
        print(f"SEED_OK cids={cids} at={datetime.now(timezone.utc).isoformat()}")
    finally:
        await engine.dispose()


async def _user_id(engine, name: str) -> int | None:
    async with AsyncSession(engine) as s:
        return await s.scalar(select(User.id).where(User.username == name))


async def _ensure_user_id(engine, name: str, role: str) -> int:
    """幂等取/建用户——上一次 seed 已建过（撞 `uk_user_username`），不能直接 add。"""
    uid = await _user_id(engine, name)
    return uid if uid is not None else await cp._ensure_user(engine, name, role)


if __name__ == "__main__":
    asyncio.run(main())
