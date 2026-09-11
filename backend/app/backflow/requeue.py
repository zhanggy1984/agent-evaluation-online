"""backflow 人工失效与重推（detail §7.4 / §8.4，P2-3 / T-3.3）。

- `requeue_guard_errors` 纯守卫（R-24 状态域精确化）：仅 invalidated ∧ verify=pending ∧
  cluster.status ∈ {open, claim, needs_review} ∧ 防抖 ≥5min（锚 = assembled_ts）可复位；
  fixed/inactive（已 closed）禁 requeue（需 superseded+reopen 重建新 link/新 payload_id）。
- `requeue_link`：复位 = invalidated→assembled，**复用 payload_id + 重填 payload_json
  （以现 cluster + 现词表重组装 → 内容缺愈）+ 刷新 assembled_ts=now()**；清
  invalidate_reason/invalidated_by；verify_status 保持 pending（仍占现行位 §5.1）；
  **不动 cluster 锚点**（fix_version/claim_k/TTL，§7.4 锚点保护）。
  CAS + conversion_record(action=requeue)。
- `requeue_batch`（§7.4 R-7）：筛选 invalidated+online_content_gap（+agent）批量复位，
  逐行复用守卫 + 防抖，单行 savepoint 隔离；汇总 conversion_record(action=requeue)。
- `invalidate_link`：admin 人工失效，仅 offline_status ∈ {assembled, draft}（active 后不
  提供 → superseded+reopen，§7.3 人工 invalidate 行）。
- `requeue_counts`（成批）/ `requeue_count`（单点）：R-7「可愈性标注」换判据后的数据源 =
  行为数据（该 link 历史被重推次数，不含本次），供前端在 ≥SUSPECT_REQUEUE_THRESHOLD 时转强确认。
- reason 码（§7.4）：offline_cap_gap / online_content_gap / manual_invalidate。
"""
import json
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.backflow.ack import iso_utc
from app.converter.envelope import build_envelope
from app.converter.no_fallback_cfg import resolve_fallback_wordlist
from app.core.errors import AppError
from app.models.error_flow import ConversionRecord, ErrorCaseLink, ErrorCluster

REQUEUE_DEBOUNCE_MINUTES = 5          # §7.4：同一 link 人工重推间隔 ≥5min（锚 = assembled_ts）
REQUEUE_ALLOWED_CLUSTER = ("open", "claim", "needs_review")   # R-24：fixed/inactive closed 禁
MANUAL_INVALIDATE_REASON = "manual_invalidate"
# R-7 可愈性标注（换判据 = 行为数据）：已重推过 ≥该次数仍 invalidated 回来 = 疑似不可自愈
# （如版本不识别 / 配置长期未补齐），前端据此转强确认（二次确认）。该值系拍定、无数据支撑，
# 上线后按真实 conversion_record 分布调；前端 BackflowClusterDetailView.vue 有同值常量。
SUSPECT_REQUEUE_THRESHOLD = 2


# ---------- 纯守卫（单测直打） ----------


def requeue_guard_errors(link, cluster, *, now: datetime) -> str | None:
    """§7.4 R-24 守卫链：通过返回 None，否则返回给 ERR_CLUSTER_0003 的可读信息。"""
    if link.offline_status != "invalidated":
        return f"仅 invalidated 可 requeue（当前 offline_status={link.offline_status}）"
    if link.verify_status != "pending":
        return (
            f"verify 兜底：仅 verify_status=pending 的 invalidated link 走此路"
            f"（当前={link.verify_status}，已推进 passed/failed/superseded 需 superseded+reopen）"
        )
    if cluster is None:
        return "cluster 不存在（link.cluster_id 悬空）"
    if cluster.status not in REQUEUE_ALLOWED_CLUSTER:
        return (
            f"cluster 已 closed（status={cluster.status}）禁 requeue——需 superseded+reopen"
            f" 重建新 link/新 payload_id（§7.4，防对已收敛证据翻案）"
        )
    idle = now - link.assembled_ts
    if idle < timedelta(minutes=REQUEUE_DEBOUNCE_MINUTES):
        return (
            f"防抖：距上次组装/重推 <{REQUEUE_DEBOUNCE_MINUTES}min"
            f"（{idle.total_seconds():.0f}s，锚 = assembled_ts，§7.4）"
        )
    return None


# ---------- requeue 计数（R-7 可愈性标注的数据源：行为数据） ----------


async def requeue_counts(session: AsyncSession, link_ids: list[int]) -> dict[int, int]:
    """批量取各 link **历史** requeue 次数 → {link_id: count}（读面用）。

    成批一次 GROUP BY：读面一屏多个 link，逐 link 单查 COUNT 就是 N+1。
    口径 = 不含本次（只数已落库的 conversion_record(action=requeue) 行），故正在
    requeue_link 里 add 而未落库的那条不计入。返回只含命中 link，未命中者由调用方取 0。
    """
    if not link_ids:  # 空入参不发查询
        return {}
    rows = (await session.execute(
        select(ConversionRecord.link_id, func.count())
        .where(
            ConversionRecord.link_id.in_(link_ids),
            ConversionRecord.action == "requeue",
        )
        .group_by(ConversionRecord.link_id)
    )).all()
    return {link_id: int(cnt) for link_id, cnt in rows}


async def requeue_count(session: AsyncSession, link_id: int) -> int:
    """单点便捷（供 requeue_link 用）：复用成批实现，口径同上 = 历史次数（不含本次）。"""
    return (await requeue_counts(session, [link_id])).get(link_id, 0)


# ---------- 单点 requeue（CAS 复位 + 审计） ----------


async def requeue_link(
    session: AsyncSession,
    link: ErrorCaseLink,
    cluster: ErrorCluster,
    *,
    actor_id: int | None,
    now: datetime,
) -> dict:
    """单 link invalidated→assembled 复位重推（§7.4/§8.4 links/{id}/requeue）。

    守卫不符 → ERR_CLUSTER_0003(400)；CAS 落空（并发双 admin/与 offline ack 交错）→ 400
    带现行状态。复用 payload_id，payload_json 以现 cluster+现词表重填（内容缺愈）。
    """
    # CAS 前置值先捕获进局部量：ORM-enabled update 会 expire 命中对象（async 下事后
    # 读属性触发同步懒刷新 → MissingGreenlet），全程不再读 link/cluster 属性
    link_id, payload_id, cluster_id = link.id, link.payload_id, cluster.id
    prev_reason = link.invalidate_reason
    guard_msg = requeue_guard_errors(link, cluster, now=now)
    if guard_msg:
        raise AppError("ERR_CLUSTER_0003", guard_msg, http=400)

    words, wordlist_version = await resolve_fallback_wordlist(
        session, agent_name=cluster.agent
    )
    envelope = build_envelope(
        cluster=cluster,
        words=words,
        wordlist_version=wordlist_version,
        payload_id=payload_id,  # 复用旧 payload_id（offline upsert 幂等，§7.4）
    )
    now_naive = now.replace(tzinfo=None)
    cutoff = now - timedelta(minutes=REQUEUE_DEBOUNCE_MINUTES)
    result = await session.execute(
        update(ErrorCaseLink)
        .where(
            ErrorCaseLink.id == link_id,
            ErrorCaseLink.offline_status == "invalidated",
            ErrorCaseLink.verify_status == "pending",
            ErrorCaseLink.assembled_ts <= cutoff,
        )
        .values(
            offline_status="assembled",
            invalidate_reason=None,
            invalidated_by=None,
            payload_json=json.dumps(envelope, ensure_ascii=False),
            assembled_ts=now_naive,
        )
    )
    if result.rowcount != 1:
        # 竞态：另一次 requeue / ack 已动——重读给现行状态
        cur = await session.get(ErrorCaseLink, link_id)
        if cur is not None and cur.offline_status == "assembled":
            raise AppError(
                "ERR_CLUSTER_0003",
                "该 link 已被并发 requeue 复位为 assembled（幂等语义内重复触发）",
                http=400,
                extra={"offline_status": cur.offline_status,
                       "invalidate_reason": cur.invalidate_reason or ""},
            )
        state = f"offline_status={cur.offline_status}" if cur else "link 已不存在"
        raise AppError("ERR_CLUSTER_0003", f"requeue 状态已变（{state}），请刷新重试", http=400)

    # 历史次数（不含本次）必须在 add 本次记录**之前**查：查完再 add，
    # 口径即「本次之前已重推过几次」（供前端判 ≥SUSPECT_REQUEUE_THRESHOLD 仍被打回）
    hist_requeue_count = await requeue_count(session, link_id)
    session.add(
        ConversionRecord(
            cluster_id=cluster_id,
            link_id=link_id,
            action="requeue",
            detail=(
                f"requeue invalidated→assembled payload_id={payload_id}"
                f"（reason={prev_reason or 'unknown'}，wordlist_v={wordlist_version}"
                f" words={len(words)}）"
            ),
            actor_user_id=actor_id,  # admin 操作记操作人；系统动作记 NULL
        )
    )
    return {
        "link_id": link_id,
        "payload_id": payload_id,
        "offline_status": "assembled",
        "assembled_ts": iso_utc(now_naive),
        # 口径 = 历史次数（不含本次）
        "requeue_count": hist_requeue_count,
    }


# ---------- 批量 requeue（R-7） ----------


async def requeue_batch(
    session: AsyncSession,
    *,
    agent: str | None,
    actor_id: int | None,
    now: datetime,
) -> dict:
    """批量复位（§8.4 requeue-batch / §7.4 R-7）：筛选 invalidated+online_content_gap
    （+agent）→ 逐行守卫 + 防抖，每行 savepoint 隔离；
    【v1.23 反查订正】原写「可愈性 = 补齐现场即愈」——该表述与 register R-7 拍板
    （逐行可愈性标注 + 不愈行禁勾/强确认门控）不符，实现只落了批量端点；
    勿据此认为可愈性已交付。
    返回逐行结果 + 汇总 conversion_record(action=requeue)。
    """
    q = (
        select(ErrorCaseLink, ErrorCluster)
        .join(ErrorCluster, ErrorCluster.id == ErrorCaseLink.cluster_id)
        .where(
            ErrorCaseLink.offline_status == "invalidated",
            ErrorCaseLink.invalidate_reason == "online_content_gap",
            ErrorCluster.status.in_(REQUEUE_ALLOWED_CLUSTER),
        )
    )
    if agent:
        q = q.where(ErrorCluster.agent == agent)
    candidates = list((await session.execute(q)).all())

    requeued: list[dict] = []
    skipped: list[dict] = []
    for link, cluster in candidates:
        guard_msg = requeue_guard_errors(link, cluster, now=now)
        if guard_msg:
            skipped.append(
                {"link_id": link.id, "payload_id": link.payload_id, "reason": guard_msg}
            )
            continue
        try:
            async with session.begin_nested():  # 单行原子：requeue 失败不回退批内其他行
                out = await requeue_link(session, link, cluster, actor_id=actor_id, now=now)
                requeued.append(out)
        except AppError as exc:
            skipped.append(
                {"link_id": link.id, "payload_id": link.payload_id, "reason": exc.detail}
            )
    await session.commit()

    if requeued or skipped:
        session.add(
            ConversionRecord(
                cluster_id=None,  # 批量：聚合审计（不逐行）
                link_id=None,
                action="requeue",
                detail=json.dumps(
                    {
                        "filter": {"invalidate_reason": "online_content_gap",
                                   **({"agent": agent} if agent else {})},
                        "requeued": len(requeued),
                        "skipped": len(skipped),
                        "skipped_reasons": [
                            s["reason"] for s in skipped
                        ][:8],  # detail 1024 上限，截前 8 条
                    },
                    ensure_ascii=False,
                ),
                actor_user_id=actor_id,
            )
        )
        await session.commit()

    return {"requeued": requeued, "skipped": skipped}


# ---------- 人工 invalidate ----------


async def invalidate_link(
    session: AsyncSession,
    link: ErrorCaseLink,
    *,
    reason: str,
    actor_id: int | None,
) -> dict:
    """admin 人工失效（§8.4 links/{id}/invalidate）：仅 offline_status ∈ {assembled, draft}
    （active 后不提供，废弃走 superseded+reopen）；置 invalidated + invalidate_reason +
    invalidated_by + conversion_record(action=invalidate)。
    """
    # CAS 前置值先捕获进局部量（update 会 expire 命中对象，见 requeue_link 注）
    link_id, payload_id, cluster_id = link.id, link.payload_id, link.cluster_id
    if link.offline_status not in ("assembled", "draft"):
        raise AppError(
            "ERR_CLUSTER_0003",
            f"仅 assembled/draft 可人工 invalidate（当前={link.offline_status}；"
            f"active 后走 superseded+reopen，§7.3）",
            http=400,
        )
    result = await session.execute(
        update(ErrorCaseLink)
        .where(
            ErrorCaseLink.id == link_id,
            ErrorCaseLink.offline_status.in_(("assembled", "draft")),
        )
        .values(
            offline_status="invalidated",
            invalidate_reason=reason,
            invalidated_by=actor_id,
        )
    )
    if result.rowcount != 1:
        cur = await session.get(ErrorCaseLink, link_id)
        state = f"offline_status={cur.offline_status}" if cur else "link 已不存在"
        raise AppError("ERR_CLUSTER_0003", f"invalidate 状态已变（{state}），请刷新重试", http=400)

    session.add(
        ConversionRecord(
            cluster_id=cluster_id,
            link_id=link_id,
            action="invalidate",
            detail=f"人工 invalidate（reason={reason}）payload_id={payload_id}",
            actor_user_id=actor_id,
        )
    )
    return {"link_id": link_id, "payload_id": payload_id, "offline_status": "invalidated"}
