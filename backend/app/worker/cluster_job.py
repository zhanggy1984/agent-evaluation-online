"""worker cluster_job：judged=1 ∧ processed=0 行的聚类归并消费（detail §6.2，T-3.1 / P2-1）。

- 消费源 = `judgement_json.candidate_error_sets`（classify.build_judgement_json 落键，勿用
  candidates）；**不消费 `judgement_json.root_late`**——root-late 由 consumer 在补判事务内
  内联归并（§6.2 R-21 Fork B 用户拍板），本 job 重扫会双计。
- 归并内核 = app/analyzer/cluster.merge_candidate（同键现簇 count+1 / 终态后复发新开代数 /
  uk_cluster_dedup IntegrityError 吸收），本 job 只做扫描 + 每行候选拆解 + processed 置位。
- **Fork A**（用户拍板）：`root_input_hash` NULL 的 judged 行（残 trace 无 input 现场）候选
  不建簇不计数，只置 processed=1——该 trace 错误由 R-21 迟到 root 补判走正规聚类兜底。
- 每行处理包在一个 SAVEPOINT（begin_nested）内 = 「归并 + processed CAS」原子同进退；
  行尾 `UPDATE … SET processed=1 WHERE … AND processed=0`（rowcount==1 CAS）：双 worker
  竞态他方已消费 → rowcount==0 → 抛 _RowRaced 回退本行归并改动（不双计）。
- IntegrityError（并发同代开簇 twin 未提交不可见）→ 本行保 processed=0，下轮重试转 count。
- 每批一个事务 commit（同 judge_scan）；DB 异常上抛外层 worker loop 退避自愈。
"""
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.analyzer.cluster import error_msg_for, merge_candidate
from app.core.log import get_logger
from app.models.error_flow import TraceJudgeState

CLUSTER_BATCH = 200  # 单批行数（judged 但未聚类消费的行；judge_scan 同粒度）
_VALID_LAYERS = frozenset({"L1", "L2"})

logger = get_logger("worker.cluster")  # worker loop 覆写为 worker.main logger（同 judge 规）


class _RowRaced(Exception):
    """processed CAS 失败（他方已置 processed=1）——本行归并整体回退。"""


def _judgement(row: TraceJudgeState) -> dict:
    return row.judgement_json if isinstance(row.judgement_json, dict) else {}


def _candidate_error_sets(row: TraceJudgeState) -> list[dict]:
    """judgement_json.candidate_error_sets（classify 实际落键）→ 可归并候选（防脏跳过）。"""
    out: list[dict] = []
    for c in _judgement(row).get("candidate_error_sets") or []:
        if isinstance(c, dict) and isinstance(c.get("error_type"), str) \
                and c.get("layer") in _VALID_LAYERS:
            out.append(c)
    return out


async def _merge_row(session: AsyncSession, row: TraceJudgeState, *, now: datetime) -> None:
    """单行归并：无 hash（Fork A）跳过；有 hash 逐候选 merge_candidate；结尾 processed CAS。

    不消费 judgement_json.root_late（consumer 内联，Fork B）；gate 关停已由 classify 产空
    候选集，本函数自然只置 processed。层异常仅 IntegrityError/_RowRaced 上抛由调用方处置。
    """
    # Fork A：残 trace 无 root input（root_input_hash NULL）→ 候选不建簇不计数；interface
    # 缺行同样无法成键（error_cluster.interface NOT NULL，理论上 judged 行恒有，防脏数据）
    if row.root_input_hash and row.interface:
        # trigger_version 源 = err_summary_json.agent_version（判定期冻结，nullable）
        summary = row.err_summary_json if isinstance(row.err_summary_json, dict) else {}
        trigger_version = summary.get("agent_version")
        entries = [e for e in (summary.get("entries") or []) if isinstance(e, dict)]
        for cand in _candidate_error_sets(row):
            await merge_candidate(
                session,
                agent=row.agent,
                interface=row.interface,
                layer=cand["layer"],
                error_type=cand["error_type"],
                input_hash=row.root_input_hash,
                input_snapshot=row.input_snapshot_clean,
                input_truncated=row.input_truncated,
                error_msg=error_msg_for(entries, cand["error_type"]),
                trace_id=row.trace_id,
                trigger_version=trigger_version,
                reopen_after_terminal=True,  # 正常候选：同键 closed 后复发 → 新开代数
                now=now,
            )
    result = await session.execute(
        update(TraceJudgeState)
        .where(
            TraceJudgeState.agent == row.agent,
            TraceJudgeState.trace_id == row.trace_id,
            TraceJudgeState.processed == 0,
        )
        .values(processed=1)
    )
    if result.rowcount != 1:
        raise _RowRaced()  # 他方已消费：本行归并改动由调用方回退（不双计）


async def _scan_and_merge_batch(
    engine: AsyncEngine, *, batch: int, now: datetime
) -> int | None:
    """扫一批 judged=1 ∧ processed=0 并消费。空批返回 None（收敛）；返回本批消费行数。"""
    async with AsyncSession(engine) as session:
        rows = (
            await session.scalars(
                select(TraceJudgeState)
                .where(
                    TraceJudgeState.processed == 0,
                    TraceJudgeState.judged == 1,
                )
                .order_by(TraceJudgeState.id)
                .limit(batch)
            )
        ).all()
        if not rows:
            return None
        merged = 0
        for row in rows:
            try:
                async with session.begin_nested():  # 行级原子：归并 + 置位同进退
                    await _merge_row(session, row, now=now)
                merged += 1
            except _RowRaced:
                pass  # 他方已消费：本行改动已在 savepoint 回退，不双计
            except IntegrityError:
                # 并发同代开簇（twin 未提交不可见）：保 processed=0，下轮重试转 count
                logger.debug("cluster 同代并发吸收（行保留下轮）",
                             extra={"agent": row.agent, "trace_id": row.trace_id})
        await session.commit()
        return merged


def _utc_now() -> datetime:
    """当前 naive UTC datetime（表存 naive UTC，§5 口径；与 judge_scan/state 同源）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def run_cluster_merge(
    engine: AsyncEngine, *, logger=None, batch: int = CLUSTER_BATCH
) -> int:
    """judged=1 ∧ processed=0 行批量聚类消费（worker cluster loop 每 15s 调一次）。

    批循环直到空批收敛；返回本次置 processed=1 的行数。DB 异常上抛由 worker loop
    退避自愈（同 judge_scan）。root_late 不在此消费（consumer 内联，Fork B）。
    """
    logger = logger or get_logger("worker.cluster")
    now = _utc_now()
    merged_total = 0
    while True:
        done = await _scan_and_merge_batch(engine, batch=batch, now=now)
        if done is None:
            break
        merged_total += done
    logger.info("cluster_merge 完成", extra={"merged": merged_total})
    return merged_total
