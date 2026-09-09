"""backflow 人工处置 API（detail §7.4/§8.4，P2-3 T-3.3 + P2-4 T-3.4）。

P2-3（admin，已落地）：link invalidate / requeue / requeue-batch（复用 payload_id + 防抖）。
P2-4（新增，viewer 为主 / admin 单独 fixed-review）：
- 状态机写面：cluster claim / ignore / reopen / needs-review-resolve（viewer）、
  fixed-review（admin）、needs-review-batches/{id}/resolve（viewer；unclean_run 批载体）。
- 读面 3 GET（viewer，P2-6 前端回流页消费；响应形状在本层钉死为 metrics 风格字段级，
  detail v1.18 修订记录注记）：overview 计数、clusters 列表（分页 + 筛选）、clusters/{id}
  详情（link 摘要 + verify_run_record 时间线 + conversion 审计时间线 + 已待天数）。
- 全写端点：cluster/link 不存在 → ERR_CLUSTER_0001(404)；非法迁移 → ERR_CLUSTER_0003(400)；
  CAS 竞态落空 → ERR_CLUSTER_0002(409，带当前状态)——detail §8.9 语义，P2-4 激活。
"""
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, ViewerUser
from app.backflow import batches as batch_flow
from app.backflow import claim as claim_flow
from app.backflow import requeue as requeue_flow
from app.backflow.requeue import MANUAL_INVALIDATE_REASON
from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.log import get_logger
from app.core.offline_client import OfflineClient, OfflineReadError
from app.models.error_flow import ConversionRecord, ErrorCaseLink, ErrorCluster, VerifyRunRecord

router = APIRouter(prefix="/backflow", tags=["backflow"])
logger = get_logger("app.api.backflow")

_Session = Annotated[AsyncSession, Depends(get_session)]

_STATUSES = ("open", "claim", "fixed", "inactive", "needs_review")
_OFFLINE_STATES = ("assembled", "draft", "active", "invalidated")


# ---------- 请求/响应模型（P2-3） ----------


class LinkInvalidateRequest(BaseModel):
    reason: str | None = None  # 缺省 = manual_invalidate（结构化码）


class LinkInvalidateResponse(BaseModel):
    link_id: int
    payload_id: str
    offline_status: str


class RequeueLinkResponse(BaseModel):
    link_id: int
    payload_id: str
    offline_status: str
    assembled_ts: str  # ISO8601 UTC（刷新后的增量锚）


class RequeueBatchFilter(BaseModel):
    agent: str | None = None
    invalidate_reason: Literal["online_content_gap"] = "online_content_gap"  # v1 仅内容缺愈


class RequeueBatchRequest(BaseModel):
    filter: RequeueBatchFilter


class RequeueBatchResponse(BaseModel):
    requeued: list[dict]  # {link_id, payload_id, offline_status, assembled_ts}
    skipped: list[dict]  # {link_id, payload_id, reason}


# ---------- 请求/响应模型（P2-4 人工处置状态机） ----------


class ClaimRequest(BaseModel):
    fix_version: str  # 必填；trim 归一（比较 lower、存储保原串）
    k: int | None = None  # 值域 {1,2}；缺省 dict_config auto_fixed_k_default
    note: str | None = None


class ClaimResponse(BaseModel):
    cluster_id: int
    fix_version: str
    claim_k: int
    claim_due_ts: str  # ISO8601 UTC（复核窗截止）
    # R-7 软提示：generation>1 reentry 命中；offline 未配/读面不可达 = None（best-effort）
    warning: str | None = None


class NoteRequest(BaseModel):
    note: str | None = None


class StatusResponse(BaseModel):
    cluster_id: int
    status: str


class NeedsReviewResolveRequest(BaseModel):
    action: Literal["reopen_cluster", "escalated"]
    note: str | None = None


class NeedsReviewResolveResponse(BaseModel):
    cluster_id: int
    status: str
    action: str


class BatchResolveRequest(BaseModel):
    # §8.4 batch resolve 动作集：reopen_cluster / escalated（缺省 reopen_cluster 保 v1 兼容）
    action: Literal["reopen_cluster", "escalated"] = "reopen_cluster"
    note: str | None = None


class BatchResolveResponse(BaseModel):
    batch_id: int
    action: str
    results: list[dict]  # [{cluster_id, status, detail?}]（escalated 时 status=cluster 现行态）


class FixedReviewRequest(BaseModel):
    approve: bool


class FixedReviewResponse(BaseModel):
    cluster_id: int
    status: str


# ---------- 工具 ----------


def _utc_now() -> datetime:
    """防抖/刷新锚用当前时刻（naive UTC，与 DB 列口径一致）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value) -> str | None:
    """datetime → ISO8601（naive UTC 不加时区后缀）；None 透传。"""
    return value.isoformat() if isinstance(value, datetime) else None


async def _load_link(session: AsyncSession, link_id: int) -> ErrorCaseLink:
    """link 定位（§8.4）：不存在 → ERR_CLUSTER_0001(404)。"""
    link = await session.get(ErrorCaseLink, link_id)
    if link is None:
        raise AppError("ERR_CLUSTER_0001", f"link 不存在：{link_id}", http=404)
    return link


async def _load_cluster(session: AsyncSession, cluster_id: int) -> ErrorCluster:
    """cluster 定位（§8.4）：不存在 → ERR_CLUSTER_0001(404)。"""
    cluster = await session.get(ErrorCluster, cluster_id)
    if cluster is None:
        raise AppError("ERR_CLUSTER_0001", f"cluster 不存在：{cluster_id}", http=404)
    return cluster


def _cluster_item(cluster: ErrorCluster, link: dict | None) -> dict:
    """cluster 列表项序列化（字段级钉死，P2-6 前端逐字段消费）。"""
    return {
        "cluster_id": cluster.id, "agent": cluster.agent,
        "interface": cluster.interface, "layer": cluster.layer,
        "error_type": cluster.error_type, "error_msg": cluster.error_msg,
        "input_hash": cluster.input_hash, "input_truncated": int(cluster.input_truncated),
        "generation": int(cluster.generation), "count": int(cluster.count),
        "status": cluster.status, "first_ts": _iso(cluster.first_ts),
        "latest_ts": _iso(cluster.latest_ts), "fix_version": cluster.fix_version,
        "claimed_by": cluster.claimed_by, "claimed_at": _iso(cluster.claimed_at),
        "claim_due_ts": _iso(cluster.claim_due_ts), "claim_k": int(cluster.claim_k),
        "needs_review_reason": cluster.needs_review_reason, "link": link,
    }


def _link_item(link: ErrorCaseLink) -> dict:
    return {
        "link_id": link.id, "payload_id": link.payload_id, "case_id": link.case_id,
        "case_type": link.case_type, "offline_status": link.offline_status,
        "verify_status": link.verify_status,
        "assembled_ts": _iso(link.assembled_ts),
        "invalidate_reason": link.invalidate_reason,
    }


async def _cluster_links(session: AsyncSession, cluster_ids: list[int]) -> dict[int, dict]:
    """批量取 cluster 现行 link 摘要：pending 优先，无则最新（id 最大）。"""
    if not cluster_ids:
        return {}
    rows = (await session.scalars(
        select(ErrorCaseLink)
        .where(ErrorCaseLink.cluster_id.in_(cluster_ids))
        .order_by(ErrorCaseLink.cluster_id, ErrorCaseLink.id)
    )).all()
    out: dict[int, list[ErrorCaseLink]] = {}
    for link in rows:
        out.setdefault(link.cluster_id, []).append(link)
    picked: dict[int, dict] = {}
    for cid, links in out.items():
        current = next((lk for lk in links if lk.verify_status == "pending"), None)
        rep = current if current is not None else links[-1]
        picked[cid] = _link_item(rep)
    return picked


# ---------- 读面（§8.4 L1084-1086，viewer；P2-6 前端回流页消费） ----------


@router.get("/overview")
async def overview(user: ViewerUser, session: _Session) -> dict:
    """回流总览计数：cluster 状态分布 / link verify 分布 / 待修复集规模（本地镜像近似）。

    响应形状（字段级钉死）：{clusters, links, to_fix, by_agent[]}。"""
    logger.debug("backflow overview 入参: viewer=%s", user.username)
    cluster_rows = (await session.execute(
        select(ErrorCluster.status, func.count()).group_by(ErrorCluster.status)
    )).all()
    clusters = {s: 0 for s in _STATUSES}
    clusters.update({s: int(c) for s, c in cluster_rows})
    link_rows = (await session.execute(
        select(ErrorCaseLink.verify_status, func.count())
        .group_by(ErrorCaseLink.verify_status)
    )).all()
    links = {s: 0 for s in ("pending", "passed", "failed", "invalidated", "superseded")}
    links.update({s: int(c) for s, c in link_rows})
    to_fix = int((await session.scalar(
        select(func.count()).select_from(ErrorCaseLink).where(
            ErrorCaseLink.offline_status == "active",
            ErrorCaseLink.verify_status.in_(("pending", "failed")),
        )
    )) or 0)
    agent_rows = (await session.execute(
        select(ErrorCluster.agent, ErrorCluster.status, func.count())
        .where(ErrorCluster.status.in_(("open", "claim")))
        .group_by(ErrorCluster.agent, ErrorCluster.status)
        .order_by(ErrorCluster.agent)
    )).all()
    by_agent: dict[str, dict] = {}
    for agent, status, cnt in agent_rows:
        by_agent.setdefault(agent, {"open": 0, "claim": 0})[status] = int(cnt)
    out = {
        "clusters": clusters, "links": links, "to_fix": to_fix,
        "by_agent": [{"agent": a, **v} for a, v in by_agent.items()],
    }
    logger.debug("backflow overview 出参: %s", out)
    return out


@router.get("/clusters")
async def list_clusters(
    user: ViewerUser,
    session: _Session,
    agent: str | None = None,
    interface: str | None = None,
    layer: Literal["L1", "L2"] | None = None,
    status: Literal["open", "claim", "fixed", "inactive", "needs_review"] | None = None,
    watch: Literal["assembled", "draft", "active", "invalidated"] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """cluster 列表（分页 + 筛选）。watch = 仅现行（verify pending）link 的 offline 拉取态。

    响应 {items[], total, page, page_size}；items 字段见 _cluster_item（字段级钉死）。"""
    logger.debug(
        "backflow clusters 入参: viewer=%s agent=%s status=%s watch=%s page=%s",
        user.username, agent, status, watch, page,
    )
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    conds = []
    if agent:
        conds.append(ErrorCluster.agent == agent)
    if interface:
        conds.append(ErrorCluster.interface == interface)
    if layer:
        conds.append(ErrorCluster.layer == layer)
    if status:
        conds.append(ErrorCluster.status == status)
    if watch:  # 现行 pending link 的 offline 拉取/确认态
        has_watch = exists().where(
            ErrorCaseLink.cluster_id == ErrorCluster.id,
            ErrorCaseLink.verify_status == "pending",
            ErrorCaseLink.offline_status == watch,
        )
        conds.append(has_watch)
    base = select(ErrorCluster).where(*conds)
    total = int((await session.scalar(
        select(func.count()).select_from(base.subquery())
    )) or 0)
    clusters = list((await session.scalars(
        base.order_by(ErrorCluster.first_ts.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).all())
    link_map = await _cluster_links(session, [c.id for c in clusters])
    items = [_cluster_item(c, link_map.get(c.id)) for c in clusters]
    out = {"items": items, "total": total, "page": page, "page_size": page_size}
    logger.debug("backflow clusters 出参: total=%s", total)
    return out


@router.get("/clusters/{cluster_id}")
async def get_cluster_detail(
    user: ViewerUser, session: _Session, cluster_id: int
) -> dict:
    """cluster 详情：元数据 + links + verify_run_record 版本时间线 + conversion 审计 + 已待天数。

    响应 {…cluster 元数据, links[], verify_runs[], conversions[], waiting_days}。"""
    logger.debug("backflow cluster 详情 入参: viewer=%s cluster_id=%s", user.username, cluster_id)
    cluster = await _load_cluster(session, cluster_id)
    links = list((await session.scalars(
        select(ErrorCaseLink).where(ErrorCaseLink.cluster_id == cluster_id)
        .order_by(ErrorCaseLink.id.desc())
    )).all())
    runs = list((await session.scalars(
        select(VerifyRunRecord)
        .where(VerifyRunRecord.link_id.in_([lk.id for lk in links] or [0]))
        .order_by(VerifyRunRecord.verified_ts.desc(), VerifyRunRecord.id.desc())
    )).all())
    convs = list((await session.scalars(
        select(ConversionRecord).where(ConversionRecord.cluster_id == cluster_id)
        .order_by(ConversionRecord.ts.desc(), ConversionRecord.id.desc())
    )).all())
    anchor = cluster.claimed_at if cluster.status == "claim" else cluster.first_ts
    waiting_days = max(0, (int((_utc_now() - anchor).total_seconds() // 86400))
                       if anchor else 0)
    verify_items = [
        {
            "record_id": r.id, "run_id": r.run_id, "bound_version": r.bound_version,
            "case_pass": r.case_pass,
            "run_status": r.run_status, "verified_ts": _iso(r.verified_ts),
            "excluded_hit": bool((r.raw_json or {}).get("excluded_hit")),
        }
        for r in runs
    ]
    conv_items = [
        {
            "record_id": c.id, "action": c.action, "detail": c.detail,
            "closed_by": c.closed_by, "actor_user_id": c.actor_user_id, "ts": _iso(c.ts),
        }
        for c in convs
    ]
    item = _cluster_item(cluster, _link_item(links[0]) if links else None)
    item.update({
        "links": [_link_item(lk) for lk in links],
        "verify_runs": verify_items,
        "conversions": conv_items,
        "waiting_days": waiting_days,
    })
    return item


# ---------- 写面（P2-4 状态机；cluster/link 不存在 404、非法迁移 400、CAS 竞态 409） ----------


@router.post("/clusters/{cluster_id}/claim", response_model=ClaimResponse)
async def claim_cluster_endpoint(
    user: ViewerUser,
    session: _Session,
    cluster_id: int,
    body: ClaimRequest,
) -> ClaimResponse:
    """viewer 认领：open→claim（fix_version 必填、k 固化、TTL 起算）+ conv；R-7 软提示。"""
    logger.debug(
        "claim 入参: viewer=%s cluster_id=%s fix_version=%s k=%s",
        user.username, cluster_id, body.fix_version, body.k,
    )
    cluster = await _load_cluster(session, cluster_id)
    result = await claim_flow.claim_cluster(
        session, cluster, fix_version=body.fix_version, note=body.note,
        k=body.k, actor_id=user.id,
    )
    warning = None
    if int(cluster.generation) > 1:  # R-7 软提示：同版本已完成 run 命中（best-effort）
        warning = await _reentry_warning(session, cluster.agent, result["fix_version"])
    await session.commit()
    out = ClaimResponse(**result, warning=warning)
    logger.debug("claim 出参: cluster_id=%s claim_k=%s due=%s", cluster_id,
                 out.claim_k, out.claim_due_ts)
    return out


async def _reentry_warning(session: AsyncSession, agent: str, fix_version: str) -> str | None:
    """generation>1 且 fix_version 命中已 completed run → 软提示。

    不强判（硬闸属 P2-5 reentry job）；offline 未配置/读面不可达 → 退 None（best-effort）。
    """
    settings = get_settings()
    if not settings.offline_base_url:
        return None
    client = OfflineClient(settings.offline_base_url,
                           secret=settings.evaluator_service_secret, timeout_s=3)
    try:
        runs = await client.list_runs(agent=agent, version=fix_version)
        if any(r.get("status") == "completed" for r in runs):
            return (f"注意：{agent}@{fix_version} 已存在 completed run（generation>1 同版本"
                    f"重试命中 reentry）——是否确为新修复？verify 回查按实际判定；硬闸属 P2-5")
        return None
    except OfflineReadError as exc:
        logger.warning("claim reentry 软提示查询失败（忽略）", extra={"err": str(exc)})
        return None
    finally:
        await client.aclose()


@router.post("/clusters/{cluster_id}/ignore", response_model=StatusResponse)
async def ignore_cluster_endpoint(
    user: ViewerUser, session: _Session, cluster_id: int
) -> StatusResponse:
    """viewer ignore：open→inactive（现行 pending link superseded 停回查）+ conv。"""
    logger.debug("ignore 入参: viewer=%s cluster_id=%s", user.username, cluster_id)
    cluster = await _load_cluster(session, cluster_id)
    result = await claim_flow.ignore_cluster(session, cluster, actor_id=user.id)
    await session.commit()
    return StatusResponse(**result)


@router.post("/clusters/{cluster_id}/reopen", response_model=StatusResponse)
async def reopen_cluster_endpoint(
    user: ViewerUser, session: _Session, cluster_id: int,
    body: NoteRequest | None = None,
) -> StatusResponse:
    """viewer reopen：fixed/inactive/needs_review→open（复发/误判反悔，note 留痕）。"""
    body = body or NoteRequest()
    logger.debug("reopen 入参: viewer=%s cluster_id=%s", user.username, cluster_id)
    cluster = await _load_cluster(session, cluster_id)
    result = await claim_flow.reopen_cluster(
        session, cluster, note=body.note, actor_id=user.id)
    await session.commit()
    return StatusResponse(**result)


@router.post("/clusters/{cluster_id}/needs-review-resolve",
             response_model=NeedsReviewResolveResponse)
async def needs_review_resolve_endpoint(
    user: ViewerUser,
    session: _Session,
    cluster_id: int,
    body: NeedsReviewResolveRequest,
) -> NeedsReviewResolveResponse:
    """viewer 单条 needs_review 处置：reopen_cluster → open；escalated → §16 只记录保留。"""
    logger.debug("needs-review-resolve 入参: viewer=%s cluster_id=%s action=%s",
                 user.username, cluster_id, body.action)
    cluster = await _load_cluster(session, cluster_id)
    result = await claim_flow.needs_review_resolve_single(
        session, cluster, action=body.action, note=body.note, actor_id=user.id)
    await session.commit()
    return NeedsReviewResolveResponse(**result)


@router.post("/needs-review-batches/{batch_id}/resolve", response_model=BatchResolveResponse)
async def needs_review_batch_resolve_endpoint(
    user: ViewerUser,
    session: _Session,
    batch_id: int,
    body: BatchResolveRequest,
) -> BatchResolveResponse:
    """viewer 处置 unclean_run 聚合批：整批同动作单事务 CAS，逐 cluster R-9 语义化。"""
    logger.debug("batch resolve 入参: viewer=%s batch_id=%s action=%s",
                 user.username, batch_id, body.action)
    result = await batch_flow.resolve_batch(
        session, batch_id=batch_id, action=body.action,
        actor_id=user.id, note=body.note)
    await session.commit()
    return BatchResolveResponse(**result)


@router.post("/clusters/{cluster_id}/fixed-review", response_model=FixedReviewResponse)
async def fixed_review_endpoint(
    user: AdminUser,
    session: _Session,
    cluster_id: int,
    body: FixedReviewRequest,
) -> FixedReviewResponse:
    """admin 复核（closed_by=admin_review）：approve → claim→fixed；驳回 → claim→open。"""
    logger.debug("fixed-review 入参: admin=%s cluster_id=%s approve=%s",
                 user.username, cluster_id, body.approve)
    cluster = await _load_cluster(session, cluster_id)
    result = await claim_flow.fixed_review(
        session, cluster, approve=body.approve, actor_id=user.id)
    await session.commit()
    return FixedReviewResponse(**result)


# ---------- P2-3 admin link 处置（保持原有语义） ----------


@router.post("/links/requeue-batch", response_model=RequeueBatchResponse)
async def requeue_batch_endpoint(
    user: AdminUser,
    session: _Session,
    body: RequeueBatchRequest,
) -> RequeueBatchResponse:
    """批量复位（§8.4/§7.4 R-7）：筛选 invalidated+online_content_gap 逐行守卫+防抖复位。"""
    logger.debug(
        "requeue-batch 入参: admin=%s filter=%s",
        user.username, body.filter.model_dump(),
    )
    result = await requeue_flow.requeue_batch(
        session,
        agent=body.filter.agent,
        actor_id=user.id,
        now=_utc_now(),
    )
    logger.debug(
        "requeue-batch 出参: requeued=%s skipped=%s",
        len(result["requeued"]), len(result["skipped"]),
    )
    return RequeueBatchResponse(**result)


@router.post("/links/{link_id}/invalidate", response_model=LinkInvalidateResponse)
async def invalidate_link_endpoint(
    user: AdminUser,
    session: _Session,
    link_id: int,
    body: LinkInvalidateRequest | None = None,
) -> LinkInvalidateResponse:
    """admin 人工失效（§8.4）：仅 assembled/draft；reason 缺省 manual_invalidate。"""
    body = body or LinkInvalidateRequest()
    reason = body.reason or MANUAL_INVALIDATE_REASON
    logger.debug(
        "link invalidate 入参: admin=%s link_id=%s reason=%s",
        user.username, link_id, reason,
    )
    link = await _load_link(session, link_id)
    result = await requeue_flow.invalidate_link(
        session, link, reason=reason, actor_id=user.id
    )
    await session.commit()
    logger.debug(
        "link invalidate 出参: link_id=%s offline_status=%s",
        link_id, result["offline_status"],
    )
    return LinkInvalidateResponse(**result)


@router.post("/links/{link_id}/requeue", response_model=RequeueLinkResponse)
async def requeue_link_endpoint(
    user: AdminUser,
    session: _Session,
    link_id: int,
) -> RequeueLinkResponse:
    """单 link 复位重推（§7.4 R-24 守卫）：invalidated→assembled，复用 payload_id。"""
    logger.debug("link requeue 入参: admin=%s link_id=%s", user.username, link_id)
    link = await _load_link(session, link_id)
    cluster = await session.get(ErrorCluster, link.cluster_id)
    result = await requeue_flow.requeue_link(
        session, link, cluster, actor_id=user.id, now=_utc_now()
    )
    await session.commit()
    logger.debug(
        "link requeue 出参: link_id=%s offline_status=%s",
        link_id, result["offline_status"],
    )
    return RequeueLinkResponse(**result)
