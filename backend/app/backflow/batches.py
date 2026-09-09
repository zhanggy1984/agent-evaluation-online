"""回归 na 聚合批（detail §7.6 unclean_run 载体 + §8.4 needs-review-batches，P2-4 T-3.4）。

- `ensure_unclean_batch`：同 (run_id, agent, bound_version, error_type) 一条（uk_batch_agg
  幂等）；新 run 的环境级 na 污染把该 cluster 引用追加进批，批引 cluster 保持 claim 不入
  needs_review 态（v1.8 R-14）。
- `resolve_batch`：整批同动作单事务，动作集 {reopen_cluster, escalated}。reopen_cluster =
  逐引用 cluster CAS claim→open + 现行 pending link superseded 释放 cur_key（assemble_job
  重建新 link），逐 cluster 结果 R-9 语义化（reopened / skipped_already_open / skipped_fixed
  / manual_review，每结果都落 conversion_record 审计）；escalated = §16：批置 resolved 不迁移
  cluster（引用 cluster 由人工后续处置）。整批 CAS batch open→resolved（冲突 ERR_CLUSTER_0002
  409）同事务；resolved_ts 一律落审计；note 截断（detail VARCHAR(1024) strict 防 DataError）。
"""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.backflow.claim import CONV_DETAIL_MAX, _conflict_err, _mark_pending_links, _now
from app.core.errors import AppError
from app.models.error_flow import ConversionRecord, ErrorCluster, NeedsReviewBatch

# R-9 逐 cluster resolve 结果语义（批 resolve 响应与 conv detail 同源）
RESOLVE_ACTION = "reopen_cluster"     # 缺省动作（保 v1 请求体兼容）
RESOLVE_ACTIONS = ("reopen_cluster", "escalated")  # §8.4 batch resolve 动作集


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


async def _load_batch(session: AsyncSession, batch_id: int) -> NeedsReviewBatch:
    batch = (await session.scalars(
        select(NeedsReviewBatch).where(NeedsReviewBatch.id == batch_id)
    )).first()
    if batch is None:
        raise AppError("ERR_CLUSTER_0001", f"needs_review_batch {batch_id} 不存在", http=404)
    return batch


def _resolve_conv_detail(
    batch: NeedsReviewBatch, *, result: str, note: str | None, extra: str = ""
) -> str:
    """批 resolve 的 conversion_record.detail（纯文本，note 截断后整体 ≤1024）。

    非 JSON 载荷无结构完整性约束，尾部 slice 安全；note 先按预算裁保留尾部描述可读。"""
    head = (f"batch #{batch.id} unclean_run resolve（run={batch.run_id} "
            f"version={batch.bound_version} error_type={batch.error_type}）")
    body = head + f"结果={result}" + extra
    if note:
        note_txt = f"；note={note.strip()}"
        budget = max(CONV_DETAIL_MAX - len(body) - 12, 8)
        body += note_txt[:budget]
    return body[:CONV_DETAIL_MAX]


async def resolve_batch(
    session: AsyncSession,
    *,
    batch_id: int,
    action: str = RESOLVE_ACTION,
    actor_id: int,
    note: str | None = None,
) -> dict:
    """整批同动作单事务处置（§8.4 needs-review-batches/{id}/resolve）。

    动作集 {reopen_cluster, escalated}：reopen_cluster = 逐引用 cluster CAS claim→open +
    现行 pending link superseded（R-14；assemble_job 重建新 link），逐 cluster R-9 语义化
    reopened / skipped_already_open / skipped_fixed / manual_review（每结果都落
    conversion_record 审计）；escalated = §16 通道：批置 resolved 但不迁移 cluster，引用
    cluster 由人工后续处置。整批 CAS batch open→resolved（后到者 ERR_CLUSTER_0002 409）
    同事务原子，resolved_ts 一律落审计。"""
    if action not in RESOLVE_ACTIONS:
        raise AppError("ERR_CLUSTER_0003", "action 值域 {reopen_cluster, escalated}", http=400)
    batch = await _load_batch(session, batch_id)
    if batch.status != "open":
        raise AppError("ERR_CLUSTER_0002",
                       f"needs_review_batch {batch_id} 状态 {batch.status}，已处置过", http=409)
    refs = list(batch.link_refs or [])
    results: list[dict] = []
    for ref in refs:
        cid = int(ref.get("cluster_id"))
        cluster = (await session.scalars(
            select(ErrorCluster).where(ErrorCluster.id == cid)
        )).first()
        if cluster is None:
            results.append({"cluster_id": cid, "status": "manual_review",
                            "detail": "cluster 不存在"})
            if action == "reopen_cluster":
                session.add(ConversionRecord(
                    cluster_id=cid, action="needs_review_resolve",
                    detail=_resolve_conv_detail(batch, result="manual_review", note=note,
                                                extra="；cluster 不存在"),
                    actor_user_id=actor_id))
            continue
        if action == "escalated":
            # §16 通道 v1 只记录：批置 resolved，cluster 状态保留由人工后续处置（不自动迁移）
            results.append({"cluster_id": cid, "status": cluster.status,
                            "detail": "escalated：批置 resolved，cluster 交人工后续处置"})
            continue
        cur = cluster.status
        if cur == "claim":
            # claim → open：现行 pending link superseded 释放 cur_key（assemble 重建新 link）
            await _mark_pending_links(session, cid, "superseded")
            moved = await session.execute(
                update(ErrorCluster)
                .where(ErrorCluster.id == cid, ErrorCluster.status == "claim")
                .values(status="open")
            )
            if moved.rowcount != 1:
                after = (await session.scalars(
                    select(ErrorCluster).where(ErrorCluster.id == cid)
                )).first()
                status = ("skipped_already_open"
                          if after and after.status == "open" else "manual_review")
                results.append({"cluster_id": cid, "status": status,
                                "detail": "CAS 竞态落空，并发已变更"})
                session.add(ConversionRecord(
                    cluster_id=cid, action="needs_review_resolve",
                    detail=_resolve_conv_detail(batch, result=status, note=note,
                                                extra="；CAS 竞态落空"),
                    actor_user_id=actor_id))
                continue
            session.add(ConversionRecord(
                cluster_id=cid, action="needs_review_resolve",
                detail=_resolve_conv_detail(batch, result="reopened", note=note,
                                            extra="；现行 pending link superseded 释放 cur_key"),
                actor_user_id=actor_id))
            results.append({"cluster_id": cid, "status": "reopened"})
        elif cur == "open":
            results.append({"cluster_id": cid, "status": "skipped_already_open"})
            session.add(ConversionRecord(
                cluster_id=cid, action="needs_review_resolve",
                detail=_resolve_conv_detail(batch, result="skipped_already_open", note=note,
                                            extra="；已 open 无需迁移"),
                actor_user_id=actor_id))
        elif cur == "fixed":
            # 极端：resolve 前 K 满先收敛（E-7 auto_regression）→ 跳过
            results.append({"cluster_id": cid, "status": "skipped_fixed"})
            session.add(ConversionRecord(
                cluster_id=cid, action="needs_review_resolve",
                detail=_resolve_conv_detail(batch, result="skipped_fixed", note=note,
                                            extra="；K 满已 auto fixed"),
                actor_user_id=actor_id))
        else:
            results.append({"cluster_id": cid, "status": "manual_review",
                            "detail": f"cluster 状态 {cur} 不可预期，交人工"})
            session.add(ConversionRecord(
                cluster_id=cid, action="needs_review_resolve",
                detail=_resolve_conv_detail(batch, result="manual_review", note=note,
                                            extra=f"；状态 {cur} 不可预期"),
                actor_user_id=actor_id))
    # 整批抢占（后到者在此失败 → 409；前面未 commit 全回滚，保持整批同动作）
    claimed = await session.execute(
        update(NeedsReviewBatch)
        .where(NeedsReviewBatch.id == batch.id, NeedsReviewBatch.status == "open")
        .values(status="resolved", resolve_action=action,
                resolved_by=actor_id, resolved_ts=_now(), link_refs=refs)
    )
    if claimed.rowcount != 1:
        raise _conflict_err(batch.id)
    return {"batch_id": batch.id, "action": action, "results": results}
