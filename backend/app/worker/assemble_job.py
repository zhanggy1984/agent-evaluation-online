"""worker assemble_job：D19 信封组装补偿扫描（detail §6.3，T-3.2 / P2-2）。

- 触发 = 纯周期扫描（用户拍板）：每 60s 扫 **status='open'** ∧ input_snapshot 非空
  （快照缺 input 实文 = E-13 只计数不组装，跳过等 R-18 补齐快照后下轮扫到）∧
  **无现行 link**（无 verify_status='pending'——pending 即 cur_key 占位；invalidated
  仍 pending 占位 → 不重组装，§6.3 窗口抑制）的 cluster，统一 assemble。
  单一写路径幂等：cluster_job 与 consumer root-late 内联两处产 open 全覆盖。
- 组装 = converter/envelope.assemble_cluster（写 link assembled+pending +
  conversion_record action=assemble 一步事务）；uk_link_current/uk_link_payload
  冲突（并发双 worker 同簇）→ savepoint 吸收跳过（E-12 先例）。
- 每批一个事务 commit（同 judge_scan/cluster）；DB 异常上抛外层 worker loop 退避
  自愈。每候选独立 SAVEPOINT 隔离（双 worker 竞态失败不回退批内其他候选）。
"""
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.converter.envelope import assemble_cluster
from app.core.log import get_logger
from app.models.error_flow import ErrorCaseLink, ErrorCluster

ASSEMBLE_BATCH = 200  # 单批候选 cluster 数（cluster/assemble 同粒度）

logger = get_logger("worker.assemble")  # worker loop 覆写为 worker.main logger（同 judge 规）


async def _scan_candidates(
    session: AsyncSession, *, batch: int
) -> list:
    """扫 open ∧ 快照非空 ∧ 无现行（pending）link 的 cluster（order by id limit batch）。"""
    no_current_link = ~exists().where(
        ErrorCaseLink.cluster_id == ErrorCluster.id,
        ErrorCaseLink.verify_status == "pending",
    )
    return list(
        (
            await session.scalars(
                select(ErrorCluster)
                .where(
                    ErrorCluster.status == "open",
                    ErrorCluster.input_snapshot.is_not(None),
                    ErrorCluster.input_snapshot != "",
                    no_current_link,
                )
                .order_by(ErrorCluster.id)
                .limit(batch)
            )
        ).all()
    )


async def _assemble_batch(
    engine: AsyncEngine, *, batch: int
) -> tuple[int | None, int, int]:
    """扫一批候选并组装。空批返回 (None, 0, 0)（收敛）；否则 (本批组装数, 快照缺, 重复冲突)。"""
    async with AsyncSession(engine) as session:
        clusters = await _scan_candidates(session, batch=batch)
        if not clusters:
            return None, 0, 0
        assembled = 0
        dup = 0
        for cluster in clusters:
            try:
                async with session.begin_nested():  # 每候选原子：link+conv 同进退
                    if await assemble_cluster(session, cluster):
                        assembled += 1
            except IntegrityError:
                # 并发双 worker 同簇已建现行 link（uk_link_current）/ payload_id 撞唯一
                # （uk_link_payload）→ savepoint 已回退，跳过计数
                dup += 1
                logger.debug("assemble 现行 link 冲突吸收（他方已装）",
                             extra={"cluster_id": cluster.id})
        await session.commit()
        return assembled, 0, dup


async def run_assemble(
    engine: AsyncEngine, *, logger=None, batch: int = ASSEMBLE_BATCH
) -> int:
    """open 且无现行 link 的 cluster 批量组装（worker assemble loop 每 60s 调一次）。

    批循环直到空批收敛；返回本次组装 link 数。快照缺 cluster 被扫排除（E-13），
    DB 异常上抛由 worker loop 退避自愈（同 judge_scan/cluster）。组装 ts 走列
    server_default（assembled_ts / conv ts），不需要时钟入参。
    """
    logger = logger or get_logger("worker.assemble")
    assembled_total = 0
    while True:
        done, _, dup = await _assemble_batch(engine, batch=batch)
        if done is None:
            break
        assembled_total += done
        if dup:
            logger.debug("assemble 批内重复冲突", extra={"dup": dup})
    if assembled_total:
        logger.info("assemble 完成", extra={"assembled": assembled_total})
    return assembled_total
