"""backflow 人工处置 API（detail §7.4/§8.4，P2-3 / T-3.3）：admin invalidate + requeue。

- POST /backflow/links/{id}/invalidate：人工失效（仅 assembled/draft；置 invalidated +
  invalidate_reason 默认 manual_invalidate + invalidated_by + conv）。active 后不提供。
- POST /backflow/links/{id}/requeue：§7.4 R-24 守卫复位（invalidated→assembled：复用
  payload_id、重填 payload_json、刷新 assembled_ts、防抖 ≥5min）。
- POST /backflow/links/requeue-batch：批量复位 invalidated+online_content_gap 行（R-7）。
- 鉴权：全部挂 AdminUser（平台 admin JWT，§8.5/§8.6 admin-only）；link 不存在 →
  ERR_CLUSTER_0001(404)。
"""
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser
from app.backflow import requeue as requeue_flow
from app.backflow.requeue import MANUAL_INVALIDATE_REASON
from app.core.db import get_session
from app.core.errors import AppError
from app.core.log import get_logger
from app.models.error_flow import ErrorCaseLink, ErrorCluster

router = APIRouter(prefix="/backflow", tags=["backflow"])
logger = get_logger("app.api.backflow")

_Session = Annotated[AsyncSession, Depends(get_session)]


# ---------- 请求/响应模型 ----------


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


def _utc_now() -> datetime:
    """防抖/刷新锚用当前时刻（naive UTC，与 DB 列口径一致）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _load_link(session: AsyncSession, link_id: int) -> ErrorCaseLink:
    """link 定位（§8.4）：不存在 → ERR_CLUSTER_0001(404)。"""
    link = await session.get(ErrorCaseLink, link_id)
    if link is None:
        raise AppError("ERR_CLUSTER_0001", f"link 不存在：{link_id}", http=404)
    return link


# ---------- 端点（静态段 /links/requeue-batch 先于 /links/{id}/… 声明，防路径吞并） ----------


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
