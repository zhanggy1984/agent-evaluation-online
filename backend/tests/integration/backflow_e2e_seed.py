"""批 B（#232）端到端种子：给 offline 造一份**真实可拉取**的在线载荷。

一次性脚本，**刻意不清理**（与其它探针相反）——留下的 cluster/link 就是 offline
`pull_once()` 的输入。跑完打印 cluster_id / payload_id / link 初始态。

为什么需要它（不是可省的一步）：
1. 真库 `error_cluster`/`error_case_link`/`verify_run_record` **均为 0 行**，没有现成载荷；
2. agent 2/3/4 的 `fallback_utterance` **是空数组** ⇒ `resolve_fallback_wordlist` 返回
   `([], 0)` ⇒ 信封带空词表 ⇒ offline 侧必然 `REJECT_EMPTY_WORDS`。故本脚本先用**真实 admin
   写入端点**（§8.6 `PUT /admin/configs`）落 per-agent `fallback_utterance`，再建 cluster、
   走**真实 claim API**。
   ⚠️ agent 1（good-question）**原本已有非空词表**（写入前 version=1），本脚本的 `put` 把它
   **覆盖**为 `WORDS`（version→2）。上一版本此处写「`dict_config` 为 0 行」是**错的**——那是
   一次失败查询（`key` 列不存在）留下的无证据推断，且第二次查询只打了列名未打行。旧值见
   `conversion_record` 的 `config_change` 审计（detail 内有 old→new 摘要）。
3. **时序**：`assemble_job` 只扫 `status=='open'` 的簇。建簇后**必须等自动组装**出 pending
   link **再** claim；同一瞬间 claim ⇒ 簇进 `claim` 态 ⇒ 组装永不被拾取 ⇒ pull 恒空。

复用而非自造：直接 import `claim_probe` 的 engine/app 装置与 `_seed_cluster`/`_post`/
`_ensure_user`。仅覆写 `claim_probe.IFACE`（其模块全局，`_seed_cluster` 调用时读取）——
必须选一个 **offline 侧已登记**的 interface，即 `good-question` 的
`POST /api/chat/{session_id}`（resolve_interface 对 `{...}` 段当通配）。
"""
import asyncio
import sys
from datetime import datetime, timezone

import claim_probe as cp
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.core.db import get_session
from app.main import create_app
from app.models.error_flow import ErrorCaseLink, ErrorCluster

AGENT = "good-question"
# offline 侧已登记：agent_interface(id=2188, POST, /api/chat/{session_id})
IFACE = "POST /api/chat/{session_id}"
SNAPSHOT = "帮我看看这份合同的付款条款有没有风险？"
FIX_VERSION = "2026.09.14-r99"
# 兜底话术：自然语言（与真实回流形态一致）。**故意含短 ASCII token「AI」**——
# #235 遗留的「折叠放大短 ASCII 误命中面」只有在这种词表上才量得出来。
WORDS = [
    "抱歉，我暂时无法回答这个问题",
    "当前没有相关信息",
    "系统繁忙，请稍后再试",
    "我无法处理该请求",
    "AI 暂时不可用",
]


async def _seed_wordlist(client, admin_token, agent_id: int) -> None:
    """真实 admin 端点写 per-agent fallback_utterance（version 由端点自增 + 审计）。"""
    # 不走 cp._post：它硬拼 `/api/backflow/` 前缀，admin 路径不在其下
    r = await client.put(
        "/api/v1/admin/configs",
        json={"agent_id": agent_id, "key": "fallback_utterance", "value": WORDS},
        headers=cp._hdr(admin_token),
    )
    status, resp = r.status_code, r.json()
    assert status == 200, f"词表写入失败：{status} {resp}"
    print(f"[seed] fallback_utterance 已写：agent_id={agent_id} version={resp.get('version')} "
          f"词条={len(WORDS)}")


async def _ensure_user_id(engine, name: str, role: str) -> int:
    """幂等取/建用户——本脚本不清理，二次运行不能撞 uk_user_username。"""
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User
    async with AsyncSession(engine) as s:
        uid = await s.scalar(select(User.id).where(User.username == name))
        if uid is not None:
            return uid
    return await cp._ensure_user(engine, name, role)


async def _wait_link(engine, cid: int, *, timeout: float):
    """轮询等 assemble_job（obs-worker）把该簇组装成 pending link。"""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        _, link = await _find_cluster(engine, cid)
        if link is not None:
            return link
        await asyncio.sleep(3)
    return None


async def _find_cluster(engine, cid: int) -> tuple[ErrorCluster, ErrorCaseLink | None]:
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(engine) as s:
        c = (await s.scalars(select(ErrorCluster).where(ErrorCluster.id == cid))).one()
        ln = (await s.scalars(
            select(ErrorCaseLink).where(ErrorCaseLink.cluster_id == cid))).first()
        return c, ln


async def main() -> None:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.agent import Agent

    db = Settings()  # 容器真 env
    engine = create_async_engine(db.sqlalchemy_url)
    app = create_app(cp._app_settings())
    app.state.settings = cp._app_settings()

    async def _override_session():
        async with AsyncSession(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override_session

    try:
        async with AsyncSession(engine) as s:
            agent_id = await s.scalar(select(Agent.id).where(Agent.name == AGENT))
        assert agent_id, f"online 无 agent={AGENT}"
        print(f"[seed] online agent={AGENT} id={agent_id}")

        admin_id = await _ensure_user_id(engine, cp.ADMIN, "admin")
        admin_token = cp.create_access_token(cp._app_settings(), admin_id, "admin")

        cp.IFACE = IFACE  # 覆写模块全局：_seed_cluster 调用时读取
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://seed") as client:
            await _seed_wordlist(client, admin_token, agent_id)

            # 快照带 run 后缀：input_hash 由 agent|snapshot 派生，同串会撞 uk_cluster_dedup
            snapshot = f"{SNAPSHOT} #{int(datetime.now().timestamp())}"
            cid = await cp._seed_cluster(engine, AGENT, snapshot)
            print(f"[seed] cluster_id={cid} status=open interface={IFACE!r}")

            # **时序铁律**：assemble_job（obs-worker）只扫 `status=='open'` 的簇。同一瞬间就
            # claim ⇒ 簇进 claim 态 ⇒ 组装永不被拾取 ⇒ link 永不生成 ⇒ pull 恒空。必须先等
            # 自动组装出 pending link，**再** claim（这正是 rejudge_job.py:10 描述的正常时序）。
            link = await _wait_link(engine, cid, timeout=180)
            if link is None:
                print(f"SEED_FAIL cluster_id={cid}：180s 内 assemble_job 未生成 link")
                sys.exit(1)
            print(f"[seed] assemble_job 已组装 link={link.id} payload_id={link.payload_id} "
                  f"offline_status={link.offline_status} verify_status={link.verify_status}")

            # 真实 claim API（viewer 角色即可）——不调 cp._activate，激活由 offline 真 ack 完成
            viewer_id = await _ensure_user_id(engine, cp.VIEWER, "viewer")
            viewer_token = cp.create_access_token(cp._app_settings(), viewer_id, "viewer")
            status, resp = await cp._post(
                client, f"clusters/{cid}/claim", viewer_token, {"fix_version": FIX_VERSION}
            )
            assert status == 200, f"claim 失败：{status} {resp}"
            print(f"[seed] claim 200 fix_version={FIX_VERSION}")

        c, link = await _find_cluster(engine, cid)
        assert link is not None, "claim 后无 link，载荷不可拉取"
        print(f"[seed] cluster.status={c.status} link.id={link.id} "
              f"payload_id={link.payload_id} offline_status={link.offline_status} "
              f"verify_status={link.verify_status}")
        print(f"SEED_OK cluster_id={cid} payload_id={link.payload_id} "
              f"agent={AGENT} interface={IFACE} at={datetime.now(timezone.utc).isoformat()}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
