"""R-27 正例对照探针：把 evidence.input 造成**形状自洽**的 JSON 对象。

与 `backflow_e2e_seed` 的唯一差异 = 快照由裸串改为 `{"content": ...}` 对象文本：
`parse_snapshot_input`（online `converter/envelope.py:29`）`json.loads` 成功 ⇒ `evidence.input`
是 dict ⇒ good-question 模板的 `{case.input.content}` 可达 ⇒ 装载闸放行、正常激活建单。

**为什么必须跑**（不是可省的一步）：只跑反例无法排除「闸门把一切都拒了」——那样
「驳回」这项验收就没有判别力。本探针是它的反向对照。

复用 `backflow_e2e_seed` 的装置与 helper（`_wait_link`/`_find_cluster`/`_ensure_user_id`
及常量），仅自建 main。**不重写词表**（已有非空值，避免无谓副作用）。一次性，不入库。
容器内运行：
`docker exec obs-backend python /app/tests/integration/r27_positive_seed.py`
"""
import asyncio
import json
import sys
from datetime import datetime

import backflow_e2e_seed as seed
import claim_probe as cp
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings
from app.core.db import get_session
from app.main import create_app
from app.models.agent import Agent


async def main() -> None:
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
            agent_id = await s.scalar(select(Agent.id).where(Agent.name == seed.AGENT))
        assert agent_id, f"online 无 agent={seed.AGENT}"

        viewer_id = await seed._ensure_user_id(engine, cp.VIEWER, "viewer")
        viewer_token = cp.create_access_token(cp._app_settings(), viewer_id, "viewer")

        cp.IFACE = seed.IFACE  # 覆写模块全局：_seed_cluster 调用时读取
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://seed") as client:
            # 与反例的唯一差异：快照是**合法 JSON 对象文本**，键名对齐模板域 {case.input.content}
            snapshot = json.dumps(
                {"content": f"{seed.SNAPSHOT} #{int(datetime.now().timestamp())}",
                 "stream": True},
                ensure_ascii=False)
            cid = await cp._seed_cluster(engine, seed.AGENT, snapshot)
            print(f"[pos] cluster_id={cid} snapshot={snapshot!r}")

            # 同反例：先等 assemble_job 出 pending link，再 claim（时序铁律）
            link = await seed._wait_link(engine, cid, timeout=180)
            if link is None:
                print(f"POS_FAIL cluster_id={cid}：180s 内 assemble_job 未生成 link")
                sys.exit(1)
            print(f"[pos] assemble_job 已组装 link={link.id} payload_id={link.payload_id}")

            status, resp = await cp._post(
                client, f"clusters/{cid}/claim", viewer_token, {"fix_version": seed.FIX_VERSION}
            )
            assert status == 200, f"claim 失败：{status} {resp}"

        c, link = await seed._find_cluster(engine, cid)
        assert link is not None, "claim 后无 link，载荷不可拉取"
        print(f"POS_SEED_OK cluster_id={cid} payload_id={link.payload_id} "
              f"agent={seed.AGENT} input_shape=dict(content)")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
