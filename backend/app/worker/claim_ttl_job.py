"""worker claim_ttl_job：复核窗 TTL 超窗回退（detail §7.6，P2-4 E-8）。

- 扫 `status='claim' ∧ claim_due_ts < now` → CAS claim→open：claimed_by/claimed_at/
  claim_due_ts 清空、claim_k 复位（dict_config auto_fixed_k_default）、fix_version 保留
  溯源（回退不丢处置人选的修复版本）；conv action=claim_ttl_expire。
- 现行 pending link 不动：回退 open 后若 viewer 再 claim 同 fix_version，回查续用同一
  link/case（verify_run_record 历史 u k 幂等续判）；assemble_job「open ∧ 无现行 link」扫描
  因仍有 pending link 不重复组装（防双 link 竞态）。
- 每批一个事务 commit；每候选 begin_nested() savepoint（双 worker 同簇 CAS 落空不回退
  批内其他候选）。批循环直到空批收敛（同 assemble）。
"""
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.backflow.claim import AUTO_FIXED_K_KEY
from app.core.dict_config import get_global_int
from app.core.log import get_logger
from app.models.error_flow import ConversionRecord, ErrorCluster

CLAIM_TTL_BATCH = 200

logger = get_logger("worker.claim_ttl")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _scan_overdue(session: AsyncSession, *, batch: int, now: datetime) -> list:
    return list(
        (
            await session.scalars(
                select(ErrorCluster)
                .where(ErrorCluster.status == "claim",
                       ErrorCluster.claim_due_ts.is_not(None),
                       ErrorCluster.claim_due_ts < now)
                .order_by(ErrorCluster.id)
                .limit(batch)
            )
        ).all()
    )


async def _expire_batch(
    engine: AsyncEngine, *, batch: int, now: datetime
) -> tuple[int | None, int]:
    """扫一批超窗 claim 并 CAS 回退。空批返回 (None, 0)；否则 (回退数, 竞态冲突数)。"""
    async with AsyncSession(engine) as session:
        clusters = await _scan_overdue(session, batch=batch, now=now)
        if not clusters:
            return None, 0
        expired = 0
        raced = 0
        default_k = await get_global_int(session, AUTO_FIXED_K_KEY, 2)
        for cluster in clusters:
            cid = cluster.id
            fv = cluster.fix_version
            due = cluster.claim_due_ts
            try:
                async with session.begin_nested():  # 每候选原子：CAS+conv 同进退
                    result = await session.execute(
                        update(ErrorCluster)
                        .where(ErrorCluster.id == cid,
                               ErrorCluster.status == "claim",
                               ErrorCluster.claim_due_ts.is_not(None),
                               ErrorCluster.claim_due_ts < now)
                        .values(status="open", claimed_by=None, claimed_at=None,
                                claim_due_ts=None, claim_k=default_k)
                    )
                    if result.rowcount != 1:
                        raced += 1
                        continue  # 他 worker/人工已抢先处置 → savepoint 无写自动释放
                    session.add(ConversionRecord(
                        cluster_id=cid, action="claim_ttl_expire",
                        detail=f"claim TTL 超窗（due={due.isoformat() if due else '?'}）→ open"
                               f"{'；fix_version=' + fv + ' 保留溯源' if fv else ''}",
                        actor_user_id=None))
                    expired += 1
            except Exception:
                raise  # DB 异常上抛外层退避自愈（同 judge/cluster）
        await session.commit()
        return expired, raced


async def run_claim_ttl(
    engine: AsyncEngine, *, logger=None, batch: int = CLAIM_TTL_BATCH
) -> int:
    """超窗 claim 批量回退 open（worker claim_ttl loop 每 60s 调一次）；返回回退数。"""
    logger = logger or get_logger("worker.claim_ttl")
    expired_total = 0
    while True:
        expired, raced = await _expire_batch(engine, batch=batch, now=_now())
        if expired is None:
            break
        expired_total += expired
        if raced:
            logger.debug("claim_ttl 批内竞态冲突", extra={"raced": raced})
    if expired_total:
        logger.info("claim_ttl 超窗回退", extra={"expired": expired_total})
    return expired_total
