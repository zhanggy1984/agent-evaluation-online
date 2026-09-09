"""worker recheck_job：claim 复核窗回查判定（detail §7.6 / §8.7，P2-4 E-7）。

- 目标 = `status='claim'` ∧ 现行 pending link（verify pending ∧ case_id 非空）的 cluster；
  case_id 尚缺（assemble 未补/迟 pull）下轮再来（claim 无现行 link 也允许，轮询至 TTL，
  R-16 缺行兜底）。
- 判据 = offline 读面（app.core.offline_client）：`offline_base_url` **空 = 本轮停轮**
  （debug 注明；offline 配套轨未启动前的安全默认，不误伤 online 侧）——配置后按版本序
  逐版判 → verify_run_record 追加 → verify_status/cluster.status 按映射收口（verify.judge_link）。
- 单错级、逐 cluster 独立事务 commit（offline HTTP 慢不拖长别簇事务；异常 rollback 该簇
  已追加的 verify_run_record，下轮幂等重判）。offline 读面失败（OfflineReadError）只记日志
  不崩 worker——§16 语义：连续失败超上限 = 「回查失败待人工」，online 侧不退避无限。
- 每批一个事务 commit（同 judge_scan/cluster 规）；DB 异常上抛外层退避自愈。
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.backflow.verify import judge_link
from app.core.log import get_logger
from app.core.offline_client import OfflineClient, OfflineReadError
from app.models.error_flow import ErrorCaseLink, ErrorCluster

RECHECK_BATCH = 200

logger = get_logger("worker.recheck")


async def _scan_claim_links(session: AsyncSession, *, batch: int) -> list[ErrorCluster]:
    """扫 claim ∧ 现行 pending link（case_id 非空）的 cluster（distinct by id）。"""
    rows = await session.execute(
        select(ErrorCluster)
        .join(ErrorCaseLink, ErrorCaseLink.cluster_id == ErrorCluster.id)
        .where(ErrorCluster.status == "claim",
               ErrorCaseLink.verify_status == "pending",
               ErrorCaseLink.case_id.is_not(None))
        .order_by(ErrorCluster.id)
        .limit(batch)
    )
    seen: set[int] = set()
    clusters: list[ErrorCluster] = []
    for cluster in rows.scalars().all():
        if cluster.id not in seen:
            seen.add(cluster.id)
            clusters.append(cluster)
    return clusters


async def _judge_cluster(engine: AsyncEngine, client: OfflineClient, cluster_id: int) -> dict:
    """单 cluster 独立事务：重读 cluster + 现行 pending link → judge_link → commit。"""
    async with AsyncSession(engine) as session:
        cluster = (await session.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cluster_id)
        )).first()
        if cluster is None or cluster.status != "claim":
            return {"outcome": "no_progress", "reason": "cluster 已非 claim（并发处置/删除）"}
        link = (await session.scalars(
            select(ErrorCaseLink).where(
                ErrorCaseLink.cluster_id == cluster_id,
                ErrorCaseLink.verify_status == "pending",
                ErrorCaseLink.case_id.is_not(None),
            )
        )).first()
        if link is None:
            return {"outcome": "no_progress",
                    "reason": "cluster claim 但无现行 pending link（待 assemble 补 / TTL 兜底）"}
        summary = await judge_link(session, client, cluster=cluster, link=link)
        await session.commit()
        return summary


async def _run_recheck_cycle(
    engine: AsyncEngine, client: OfflineClient, *, batch: int
) -> tuple[dict, int]:
    """一轮：扫候选 → 逐 cluster 判。返回 (结果计数 map, 处理数)。"""
    counts: dict = {}
    total = 0
    async with AsyncSession(engine) as scan_session:
        clusters = await _scan_claim_links(scan_session, batch=batch)
    for cluster in clusters:
        try:
            summary = await _judge_cluster(engine, client, int(cluster.id))
            total += 1
            key = summary.get("outcome", "unknown")
            counts[key] = counts.get(key, 0) + 1
            if summary.get("reason"):
                logger.debug("recheck cluster 汇总",
                             extra={"cluster_id": cluster.id, "summary": summary})
        except OfflineReadError as exc:
            # §16：offline 读面失败 → 「回查失败待人工」提示，簇保持 claim 不误 closed
            logger.warning("recheck 回查失败待人工", extra={"cluster_id": cluster.id,
                                                           "err": str(exc)})
        except Exception:
            logger.exception("recheck 单簇异常（该簇回滚，下轮重判）",
                             extra={"cluster_id": cluster.id})
    return counts, total


async def run_recheck(
    engine: AsyncEngine, settings, *, logger=None, batch: int = RECHECK_BATCH
) -> int:
    """claim 复核窗回查一轮（worker recheck loop 每 60s 调一次）；返回处理 cluster 数。

    settings.offline_base_url 空 → 停轮（debug；offline 配套轨未启动的安全默认）。
    """
    logger = logger or get_logger("worker.recheck")
    if not settings.offline_base_url:
        logger.debug("recheck 停轮：offline_base_url 未配置（offline 配套轨启动后填 .env）")
        return 0
    client = OfflineClient(settings.offline_base_url,
                           secret=settings.evaluator_service_secret)
    try:
        counts, total = await _run_recheck_cycle(engine, client, batch=batch)
    finally:
        await client.aclose()
    if total:
        logger.info("recheck 回查完成", extra={"processed": total, "outcomes": counts})
    return total
