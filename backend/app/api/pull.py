"""平台间 pull-API（detail §7.2/§7.3/§8.7，P2-3 / T-3.3）：offline(evaluator) 拉取 + ack 回写。

- POST /pull/payloads：扫 assembled link keyset 分页下发（join cluster 按 agent 过滤、
  assembled_ts ≥ since_ts 增量锚）。schema_version ≠ 1.0 → ERR_PULL_0002(400)（X-5 拒单）；
  case_type ∉ 白名单 → 200 空集（§12 加固/X-5，不触 DB）。
  每元素 = 信封全文 + 顶层 assembled_ts(ISO8601 UTC)。
- POST /pull/ack：§7.3 状态回写（draft/active/invalidated + case_id/invalidate_reason），
  前置不符 ERR_CLUSTER_0003(400 带当前状态 R3)，未知 payload ERR_PULL_0003(404)；
  重复 ack 幂等 200（E-15）。
- 鉴权：全部挂 EvaluatorUser（require_evaluator，预共享静态 secret，fail-closed；§8.8）。
  不接平台 JWT——offline 侧只持 service secret。
"""
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import EvaluatorUser
from app.backflow import ack as ack_flow
from app.backflow.ack import (
    CASE_TYPES,
    SCHEMA_VERSION,
    _iso_to_naive,
    decode_cursor,
    iso_utc,
    pull_payloads,
)
from app.core.db import get_session
from app.core.errors import AppError
from app.core.log import get_logger

router = APIRouter(prefix="/pull", tags=["pull"])
logger = get_logger("app.api.pull")

_Session = Annotated[AsyncSession, Depends(get_session)]


# ---------- 请求/响应模型（§8.7；信封全文 dict 直透，保键序） ----------


class PullPayloadsRequest(BaseModel):
    """增量拉取请求。next_token 与 since_ts 同传时 keyset 分页 + 下界过滤双生效。"""

    schema_version: str
    case_type: str
    agent: str | None = Field(default=None, max_length=64)
    limit: int = Field(default=100, ge=1, le=100)
    since_ts: str | None = None  # ISO8601 UTC；语义 = assembled_ts ≥ since_ts
    next_token: str | None = None


class PullPayloadsResponse(BaseModel):
    payloads: list[dict]  # 信封全文 + 顶层 assembled_ts（ISO8601 UTC）
    next_token: str | None = None


class PullAckRequest(BaseModel):
    payload_id: str
    action: Literal["draft", "active", "invalidated"]
    case_id: str | None = None  # offline case id（active 必带 / invalidated 驳回可选）
    reason: str | None = None  # invalidated ack 必带结构化码；R2 例外场景取 link 现行标注


class PullAckResponse(BaseModel):
    payload_id: str
    offline_status: str
    case_id: str | None = None


# ---------- 端点 ----------


@router.post("/payloads", response_model=PullPayloadsResponse)
async def pull_payloads_endpoint(
    _auth: EvaluatorUser,
    session: _Session,
    body: PullPayloadsRequest,
) -> PullPayloadsResponse:
    """增量拉取（offline evaluator 凭证；§7.2 online 不 push 不设拉取时钟，纯请求驱动）。"""
    logger.debug(
        "pull payloads 入参: agent=%s limit=%s since_ts=%s has_next_token=%s"
        " case_type=%s schema=%s",
        body.agent, body.limit, body.since_ts, body.next_token is not None,
        body.case_type, body.schema_version,
    )
    if body.schema_version != SCHEMA_VERSION:  # X-5：版本不匹配拒单（计数，不空集糊弄）
        raise AppError(
            "ERR_PULL_0002",
            f"schema_version 不支持（{body.schema_version!r}，当前 {SCHEMA_VERSION}）",
            http=400,
        )
    if body.case_type not in CASE_TYPES:  # §12 加固：case_type 非白名单 = 空集而非全量泄漏
        logger.debug("pull payloads 出参: 空集（case_type=%s 不在白名单）", body.case_type)
        return PullPayloadsResponse(payloads=[], next_token=None)

    since_ts = None
    cursor = None
    try:
        if body.since_ts is not None:
            since_ts = _iso_to_naive(body.since_ts)
        if body.next_token is not None:
            cursor = decode_cursor(body.next_token)
    except (ValueError, KeyError, TypeError) as exc:
        raise AppError(
            "ERR_PULL_0002", f"since_ts/next_token 解析失败: {exc}", http=400
        ) from exc

    rows, next_token = await pull_payloads(
        session,
        since_ts=since_ts,
        agent=body.agent,
        limit=body.limit,
        cursor=cursor,
    )
    payloads = []
    for link in rows:
        envelope = json.loads(link.payload_json)
        envelope["assembled_ts"] = iso_utc(link.assembled_ts)  # 顶层增量锚（契约 R1）
        payloads.append(envelope)
    logger.debug(
        "pull payloads 出参: payloads=%s next_token=%s",
        len(payloads), next_token is not None,
    )
    return PullPayloadsResponse(payloads=payloads, next_token=next_token)


@router.post("/ack", response_model=PullAckResponse)
async def pull_ack_endpoint(
    _auth: EvaluatorUser,
    session: _Session,
    body: PullAckRequest,
) -> PullAckResponse:
    """ack 回写（§7.3）：offline 对 payload 的处置上报 → link 状态迁移
    （幂等 200 / R3 带态 400）。"""
    logger.debug(
        "pull ack 入参: payload_id=%s action=%s case_id=%s reason=%s",
        body.payload_id, body.action, body.case_id, body.reason,
    )
    result = await ack_flow.apply_ack(
        session,
        payload_id=body.payload_id,
        action=body.action,
        case_id=body.case_id,
        reason=body.reason,
    )
    await session.commit()  # 写操作显式提交（auth 先例；violation/noop 路径无脏写）
    logger.debug(
        "pull ack 出参: payload_id=%s offline_status=%s",
        body.payload_id, result["offline_status"],
    )
    return PullAckResponse(**result)
