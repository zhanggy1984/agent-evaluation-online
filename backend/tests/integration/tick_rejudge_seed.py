"""一次性脚本：rejudge 真机 tick 取证（seed / check / clean 三段）。

**为什么不做成探针**：cluster/claim/pull/assemble/push 五个探针都是**进程内直调 job 函数**
（或进程内 ASGI），证明的是「函数正确」，证不了**正在跑的 obs-worker 进程**是否真的在
调度它。rejudge 的「真在跑」只能由 live 进程自己产生证据：本脚本只**造数据、不判定**，
把判定留给 worker 的 rejudge loop（60s 一轮），再以「DB 变化 + worker 日志」双证据收口。

**为什么分三段**：跨 ≥1 个 60s 墙钟周期，不能在一个进程里 sleep 等。
    docker exec obs-backend python /app/tests/integration/tick_rejudge_seed.py seed
    # 等 ≥ 60s
    docker exec obs-backend python /app/tests/integration/tick_rejudge_seed.py check
    docker exec obs-backend python /app/tests/integration/tick_rejudge_seed.py clean

**判定通过的标准（check 段）**：原 link 的 `verify_status` 由 `pending` 变为**非 pending**
（= live rejudge 真的扫到并判了）。这是「进程活着且在调度」的直接证据 —— 注意 worker
日志只在 `judged_total>0` 时打印（rejudge_job.py 收尾），故**日志为空不等于没跑**，
DB 变化才是主证据。

**入库理由（2026-09-15 订正原表述「一次性脚本不入库……取证完成后应删除本文件」）**：原句自陈
用后即弃，与既成事实冲突——本脚本是 `revision-design-register.md` v1.23 行「rejudge 运行态
liveness 已取证闭合」**唯一点名的取证手段**，不入库则该断言在 `origin/main` 上不可复核。
故随批入库、保留取证手段。**与 CI 常驻探针的区别不变**：重跑需一个 live worker 跨 ≥1 个 60s
墙钟周期，**无法无人值守**，故不入 `ci.yml`（同目录 `c2_push_seed.py`/`backflow_reject_seed.py`
同为一次性 seed 且已入库，本文件随此惯例）。
"""
import asyncio
import datetime as dt
import importlib.util
import pathlib
import sys

sys.path.insert(0, "/app")

from sqlalchemy import delete, select, update  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.models.error_flow import (  # noqa: E402
    ConversionRecord,
    ErrorCaseLink,
    ErrorCluster,
    NeedsReviewBatch,
    VerifyRunRecord,
)

# tests/ 下没有 __init__.py（探针都是直接跑的脚本），故按**文件路径**加载 claim_probe
# 复用它的造数 helper，而不是 `from tests.integration... import`（那会 ImportError）。
_cp_spec = importlib.util.spec_from_file_location(
    "claim_probe", pathlib.Path(__file__).with_name("claim_probe.py"))
_cp = importlib.util.module_from_spec(_cp_spec)
_cp_spec.loader.exec_module(_cp)  # 其 main 有 __main__ guard，import 无副作用

_activate, _case_row = _cp._activate, _cp._case_row
_seed_agent, _seed_cluster, _seed_run = _cp._seed_agent, _cp._seed_cluster, _cp._seed_run

AGENT = "tick-rejudge-agent"
CASE = "tick-rejudge-case"
RUN_ID = "tick-rejudge-run-1"
FV = "9.9.9"  # fix_version：judge_link 不见它就走 no_progress，判不出东西


async def _engine():
    return create_async_engine(Settings().sqlalchemy_url)


async def seed() -> None:
    engine = await _engine()
    try:
        async with AsyncSession(engine) as s:
            await s.execute(delete(ErrorCluster).where(ErrorCluster.agent == AGENT))
            await s.execute(delete(Agent).where(Agent.name == AGENT))
            await s.commit()

        await _seed_agent(engine, AGENT)
        cid = await _seed_cluster(engine, AGENT, "tick-snapshot-1")
        lid = await _activate(engine, cid, CASE)  # 组 pending link + 置 active

        # 落一条**失败**结果行（主推形态 raw_json）。prev=None = 该 agent 首个终态 run，
        # 故不触发缺行中断（gap）判据，judge_link 能一路判到终态。
        rid = await _seed_run(
            engine, agent=AGENT, link_id=lid, case_id=CASE, run_id=RUN_ID,
            version=FV, cases=[_case_row(CASE, x_pf="fail")], latest=FV, prev=None,
        )

        # 置 claim 态（judge_link 与 rejudge 的扫描谓词都要求 cluster.status=='claim'）。
        # claim_due_ts 给足 1h：超窗会被 claim_ttl_job 回退成 open，rejudge 就扫不到了。
        now = dt.datetime.now()
        async with AsyncSession(engine) as s:
            await s.execute(
                update(ErrorCluster).where(ErrorCluster.id == cid).values(
                    status="claim", claimed_at=now,
                    claim_due_ts=now + dt.timedelta(hours=1), fix_version=FV,
                )
            )
            await s.commit()

        print(f"[seed] agent={AGENT} cluster={cid} link={lid} run_record={rid} fv={FV}")
        print("[seed] 已置 claim 态；未做任何判定 —— 等 ≥60s 让 live rejudge 去判")
    finally:
        await engine.dispose()


async def check() -> None:
    engine = await _engine()
    try:
        async with AsyncSession(engine) as s:
            cid = (await s.scalars(
                select(ErrorCluster.id).where(ErrorCluster.agent == AGENT))).first()
            if cid is None:
                print("[check] 查无 tick 簇 —— 先跑 seed")
                return
            cluster = (await s.scalars(
                select(ErrorCluster).where(ErrorCluster.id == cid))).one()
            links = list((await s.scalars(
                select(ErrorCaseLink).where(ErrorCaseLink.cluster_id == cid)
                .order_by(ErrorCaseLink.id))).all())
            convs = list((await s.scalars(
                select(ConversionRecord).where(ConversionRecord.cluster_id == cid)
                .order_by(ConversionRecord.id))).all())

        print(f"[check] cluster={cid} status={cluster.status} fv={cluster.fix_version}")
        for lk in links:
            print(f"[check]   link={lk.id} verify_status={lk.verify_status} "
                  f"offline_status={lk.offline_status}")
        print(f"[check]   convs={[c.action for c in convs]}")

        moved = [lk for lk in links if lk.verify_status != "pending"]
        if moved:
            print(f"[check] 结论：**rejudge 生效** —— link "
                  f"{[lk.id for lk in moved]} 已由 pending 迁移为终态")
        else:
            print("[check] 结论：link 仍 pending —— rejudge 未生效或尚未到周期"
                  "（确认 obs-worker 存活且已重启拾取新码）")
    finally:
        await engine.dispose()


async def clean() -> None:
    engine = await _engine()
    try:
        async with AsyncSession(engine) as s:
            csub = select(ErrorCluster.id).where(ErrorCluster.agent == AGENT)
            lsub = select(ErrorCaseLink.id).where(ErrorCaseLink.cluster_id.in_(csub))
            await s.execute(delete(VerifyRunRecord).where(VerifyRunRecord.link_id.in_(lsub)))
            await s.execute(delete(VerifyRunRecord).where(VerifyRunRecord.run_id == RUN_ID))
            await s.execute(delete(ErrorCaseLink).where(ErrorCaseLink.cluster_id.in_(csub)))
            await s.execute(delete(ConversionRecord).where(
                ConversionRecord.cluster_id.in_(csub)))
            await s.execute(delete(ErrorCluster).where(ErrorCluster.agent == AGENT))
            await s.execute(delete(NeedsReviewBatch).where(NeedsReviewBatch.agent == AGENT))
            await s.execute(delete(Agent).where(Agent.name == AGENT))
            await s.commit()
        print("[clean] %s 相关行已清（agent/cluster/link/run/conv）" % AGENT)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    actions = {"seed": seed, "check": check, "clean": clean}
    action = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if action not in actions:
        print(f"用法: {sys.argv[0]} [{'|'.join(actions)}]")
        sys.exit(2)
    asyncio.run(actions[action]())
