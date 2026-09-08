"""worker judge_scan_job：到期 trace 整批判定（detail §4.3/§6.1，T-2.1）。

- 扫描位点 = ttl_until（idx_judge_scan(judged, ttl_until)）：`judged=0 ∧ ttl_until<=now`
  order by id limit batch；批内一次字典查询组装 AgentContext（context.loader 批读
  agent / dict_config / interface）。
- 判定 = analyzer.classify.decide（纯函数，judged 与 judgement_json 只由本 job 写）。
- **CAS 单行更新**：`UPDATE … SET judged=1, judgement_json=:j WHERE agent/trace_id
  AND judged=0`——rowcount==0 = 双 worker 竞态他方已判，跳过不覆写（单副本亦够）。
  judged=1 后不再进扫描 = 天然「重复到期不重判」（§4.3）。
- 白名单门关停（cc）的行同样置 judged=1（§4.3：判 false 不再重复判），gate 快照
  进 judgement_json，T-3.6 归因可查。
- 顺带 purge：`processed=1 ∧ updated_ts < now − trace_judge_purge_days`（idx_purge），
  阈值读全局 dict_config 键（seed 落 7，缺行回退 7）。
- DB 异常直接上抛：外层 worker loop 退避下轮自愈；单批次一个事务 commit 原子。
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.analyzer.classify import AgentContext, TraceFacts, build_judgement_json, decide
from app.analyzer.context import (
    fetch_agent_rows,
    fetch_backflow_flags,
    fetch_interface_llm_pairs,
)
from app.core.dict_config import get_global_int
from app.core.log import get_logger
from app.models.error_flow import TraceJudgeState

JUDGE_SCAN_BATCH = 200  # 单批行数（批内一次字典查询摊销）
_PURGE_DAYS_DEFAULT = 7  # trace_judge_purge_days 缺键回退


def _facts_from_row(row: TraceJudgeState) -> TraceFacts:
    """判定输入侧事实（analyzer.classify.TraceFacts）：行字段 + err_summary entries。"""
    entries: list[dict] = []
    summary = row.err_summary_json if isinstance(row.err_summary_json, dict) else {}
    for e in summary.get("entries") or []:
        if isinstance(e, dict):
            entries.append(e)
    return TraceFacts(
        root_ok=bool(row.root_ok),
        root_status=row.root_status,
        root_error_type=row.root_error_type,
        interface=row.interface,
        llm_fact_ok=bool(row.llm_fact_ok),
        err_entries=tuple(entries),
    )


def _ctx_for(
    row: TraceJudgeState,
    agents: dict[str, object],
    flags: dict[int, bool],
    llm_pairs: set[tuple[int, str]],
) -> AgentContext:
    """字典侧事实组装。agent 行缺失 → agent_exists=False（gate 关停仍 judged=1）。"""
    agent = agents.get(row.agent)
    if agent is None:
        return AgentContext(
            agent_exists=False, backflow_allow=False, agent_enabled=False,
            backflow_enabled=False, interface_llm=None,
        )
    iface = row.interface
    return AgentContext(
        agent_exists=True,
        backflow_allow=bool(agent.backflow_allow),
        agent_enabled=bool(agent.enable),
        backflow_enabled=flags.get(agent.id, True),  # 缺键回退开启（context.loader 同规）
        # interface 缺失 → None（只靠 llm_fact 兜底）；在册行 → llm=1 命中集内才为 True
        interface_llm=((agent.id, iface) in llm_pairs) if iface else None,
    )


async def _scan_and_judge_batch(
    engine: AsyncEngine, *, batch: int, now: datetime
) -> int | None:
    """扫一批并 CAS 判定。空批返回 None（收敛）；返回本批 CAS 命中数（rowcount 合计）。"""
    async with AsyncSession(engine) as session:
        rows = (
            await session.scalars(
                select(TraceJudgeState)
                .where(TraceJudgeState.judged == 0, TraceJudgeState.ttl_until <= now)
                .order_by(TraceJudgeState.id)
                .limit(batch)
            )
        ).all()
        if not rows:
            return None
        agents = await fetch_agent_rows(session, sorted({r.agent for r in rows}))
        flags = await fetch_backflow_flags(session, [a.id for a in agents.values()])
        pairs = await fetch_interface_llm_pairs(
            session,
            [(agents[r.agent].id, r.interface) for r in rows
             if r.agent in agents and r.interface],
        )
        judged_in_batch = 0
        for row in rows:
            facts = _facts_from_row(row)
            ctx = _ctx_for(row, agents, flags, pairs)
            judgement = build_judgement_json(facts, decide(facts, ctx))
            result = await session.execute(
                update(TraceJudgeState)
                .where(
                    TraceJudgeState.agent == row.agent,
                    TraceJudgeState.trace_id == row.trace_id,
                    TraceJudgeState.judged == 0,
                )
                .values(judged=1, judgement_json=judgement)
            )
            judged_in_batch += int(result.rowcount == 1)  # 双 worker CAS：他方已判则跳过
        await session.commit()
        return judged_in_batch


async def _purge_processed(engine: AsyncEngine, purge_days: int) -> int:
    """清理已聚类消费（processed=1）且长期未动的行（idx_purge；T-3.6 消费后行不再需要）。"""
    if purge_days <= 0:
        return 0
    cutoff = _utc_now() - timedelta(days=purge_days)
    async with AsyncSession(engine) as session:
        result = await session.execute(
            delete(TraceJudgeState).where(
                TraceJudgeState.processed == 1, TraceJudgeState.updated_ts < cutoff
            )
        )
        await session.commit()
        return int(result.rowcount)


def _utc_now() -> datetime:
    """当前 naive UTC datetime（表存 naive UTC，§5 口径；与 state._ms_to_utc 同源）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def run_judge_scan(
    engine: AsyncEngine, *, logger=None, batch: int = JUDGE_SCAN_BATCH
) -> int:
    """到期行批量判定（worker judge loop 每 60s 调一次）。

    批循环直到空批收敛（judged=0 ∧ ttl_until<=now 无行即全部判完）；返回本次置
    judged=1 的行数。purge 顺带执行。DB 异常上抛由 worker loop 退避自愈。
    """
    logger = logger or get_logger("worker.judge_scan")
    async with AsyncSession(engine) as session:
        purge_days = await get_global_int(
            session, "trace_judge_purge_days", _PURGE_DAYS_DEFAULT
        )
    now = _utc_now()
    judged_total = 0
    while True:
        done = await _scan_and_judge_batch(engine, batch=batch, now=now)
        if done is None:
            break
        judged_total += done
    purged = await _purge_processed(engine, purge_days)
    logger.info("judge_scan 完成", extra={"judged": judged_total, "purged": purged})
    return judged_total
