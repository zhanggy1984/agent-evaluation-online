"""批 C2 真机验收 · online 侧种子与取证（在 obs-backend 容器内跑）。

    python tests/integration/c2_push_seed.py seed   --version V --cases 1,2,3 --claim-ks 1,1,2
    python tests/integration/c2_push_seed.py verify --run-id 3049

**为什么需要它**：C2 的验收要断言「link 真的离开 pending」，而 `links_advanced` 非空需要
三个条件同时成立——`cluster.status=='claim'` ∧ `fix_version` 已被水位覆盖 ∧ K 序列满。
真库里没有这样的簇（批 B 遗留的 2223-2226 全是 `offline_status='invalidated'`，不参与判定）。

构造口径：
- 3 个簇，`claim_k` 分别 1/1/2。前两个首推即判出 `fixed_auto`（**分片方案的判别性断言**：
  一次 run 两簇 ⇒ 两条 link 都离开 pending）；第三个 claim_k=2 ⇒ 首推 seq=1 不满、link
  **仍停 pending**，故它是**幂等重推的取证位**（link 若已离开 pending，重推会走 orphan ⇒
  拿到 duplicated=false 的假红，这正是不能用前两簇测幂等的原因）。
- 复用 `claim_probe._seed_cluster` + `_activate`（后者 = 「assemble 出 link + 置 active +
  写 case_id」，即 offline 真 ack 的等价物），不另造一套。
- **不走 claim API**：claim 会把簇从 open 推进 claim，但本脚本要直接控 `fix_version`/`claim_k`
  （claim API 不接受 claim_k），故建完 link 后按 ORM 直写三个字段。

⚠️ 本脚本**不清理**（与 backflow_e2e_seed 同例）：留下的簇/link 是取证对象。
"""
import argparse
import asyncio
import sys
from datetime import datetime

import claim_probe as cp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings
from app.models.error_flow import ErrorCaseLink, ErrorCluster, VerifyRunRecord

AGENT = "probe-c2-push"
cp.IFACE = "POST /api/chat/{session_id}"  # push 链不校验 interface，取值只为落库完整


async def _seed(engine, version: str, cases: list[str], claim_ks: list[int]) -> None:
    made = []
    for case_id, claim_k in zip(cases, claim_ks):
        snapshot = f"批C2真机推送 #{int(datetime.now().timestamp() * 1000)}-{case_id}"
        cid = await cp._seed_cluster(engine, AGENT, snapshot)
        link_id = await cp._activate(engine, cid, case_id)
        async with AsyncSession(engine) as s:
            c = await s.get(ErrorCluster, cid)
            c.status = "claim"
            c.fix_version = version
            c.claim_k = claim_k
            await s.commit()
        made.append((cid, link_id, claim_k))
        print(f"  cluster={cid} link={link_id} claim_k={claim_k} case_id={case_id} "
              f"fix_version={version}")
    print("SEED_OK " + " ".join(f"{c}:{lid}" for c, lid, _ in made))


async def _verify(engine, run_id: str) -> None:
    """取证：run 行落了几条、link 是否离开 pending、簇状态、conversion_record 是否有 orphan。"""
    async with AsyncSession(engine) as s:
        ids = [x for x in run_id.split(",") if x]
        rows = (await s.scalars(select(VerifyRunRecord).where(
            VerifyRunRecord.run_id.in_(ids)).order_by(VerifyRunRecord.id))).all()
        print(f"[verify] run_id={run_id} verify_run_record 行数={len(rows)}")
        for r in rows:
            print(f"  rec={r.id} link_id={r.link_id} bound_version={r.bound_version} "
                  f"case_pass={r.case_pass} run_status={r.run_status}")
        link_ids = {r.link_id for r in rows}
        for lid in sorted(link_ids):
            ln = await s.get(ErrorCaseLink, lid) if lid else None
            if ln is None:
                print(f"  link={lid}（哨兵/orphan，无 link 行）")
                continue
            cl = await s.get(ErrorCluster, ln.cluster_id)
            print(f"  link={lid} cluster={ln.cluster_id} verify_status={ln.verify_status} "
                  f"| cluster.status={cl.status} claim_k={cl.claim_k} "
                  f"fix_version={cl.fix_version}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["seed", "verify"])
    ap.add_argument("--version")
    ap.add_argument("--cases")
    ap.add_argument("--claim-ks")
    ap.add_argument("--run-id")
    a = ap.parse_args()
    db = Settings()  # 容器真 env
    engine = create_async_engine(db.sqlalchemy_url)  # URL 含口令，不打印
    try:
        if a.mode == "seed":
            cases = a.cases.split(",")
            ks = [int(x) for x in a.claim_ks.split(",")]
            assert len(cases) == len(ks), "cases 与 claim-ks 必须一一对应"
            await _seed(engine, a.version, cases, ks)
        else:
            await _verify(engine, a.run_id)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:  # noqa: BLE001 — 探针：失败要一眼看见原因
        print(f"SEED_FAIL {type(exc).__name__}: {exc}")
        sys.exit(1)
