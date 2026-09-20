"""回归 na 聚合批（detail §7.6 unclean_run 载体 + §8.4 needs-review-batches，P2-4 T-3.4）。

- `ensure_unclean_batch`：同 (run_id, agent, bound_version, error_type) 一条（uk_batch_agg
  幂等）；新 run 的环境级 na 污染把该 cluster 引用追加进批，批引 cluster 保持 claim 不入
  needs_review 态（v1.8 R-14）。
"""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.error_flow import NeedsReviewBatch


async def ensure_unclean_batch(
    session: AsyncSession,
    *,
    run_id: str,
    agent: str,
    bound_version: str,
    error_type: str,
    cluster_id: int,
    link_id: int,
    case_id: str | None,
) -> int:
    """把 unclean 判定 cluster 追加进聚合批（uk_batch_agg 幂等：批在即引用、批无则建）。

    同 (run_id, agent, bound_version, error_type) **至多一条批（全状态唯一，uk 跨 status）**：
    open 批 → cluster 按 id 去重追加；**resolved 批后同 key 复发（unclean 未愈，re-claim 同 fv +
    assemble 新 link 后再遇同 run）→ 复用同一批重开**（status=open、清 resolve 审计、挂新 cluster
    ref）——不插第二条（否则 uk IntegrityError，recheck 每轮回滚把 claim 卡死至 TTL）。返回批 id。"""
    ref = {"link_id": link_id, "cluster_id": cluster_id,
           **({"case_id": case_id} if case_id else {})}
    batch = (await session.scalars(
        select(NeedsReviewBatch).where(
            NeedsReviewBatch.run_id == run_id,
            NeedsReviewBatch.agent == agent,
            NeedsReviewBatch.bound_version == bound_version,
            NeedsReviewBatch.error_type == error_type,
        )
    )).first()
    if batch is not None:
        refs = list(batch.link_refs or [])
        appended = not any(int(r.get("cluster_id", -1)) == cluster_id for r in refs)
        if appended:
            refs.append(ref)
        if batch.status != "open":
            await session.execute(
                update(NeedsReviewBatch)
                .where(NeedsReviewBatch.id == batch.id)
                .values(status="open", link_refs=refs,
                        resolve_action=None, resolved_by=None, resolved_ts=None)
            )
        elif appended:
            await session.execute(
                update(NeedsReviewBatch)
                .where(NeedsReviewBatch.id == batch.id)
                .values(link_refs=refs)
            )
        return int(batch.id)
    created = NeedsReviewBatch(
        run_id=run_id, agent=agent, bound_version=bound_version, error_type=error_type,
        link_refs=[ref], status="open",
        reason=f"unclean_run run={run_id} version={bound_version} 环境级 na 污染，等人工处置",
    )
    session.add(created)
    await session.flush()
    return int(created.id)

