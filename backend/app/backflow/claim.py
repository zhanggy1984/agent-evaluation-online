"""人工处置状态机（detail §7.6 状态机矩阵 / §8.4，P2-4 T-3.4）。

cluster.status 迁移（CAS `WHERE status=期望旧值`，防双 viewer/admin 并发）：
- open → claim（viewer，必填 fix_version；claim_k 固化（值域 {1,2}，缺省 dict_config
  auto_fixed_k_default=2 写死固化）；TTL = dict_config claim_ttl_days 默认 14d 起算）
- claim → fixed：auto_regression（verify.py K 满）/ admin_review（fixed-review approve:true）
- claim → open：回归 failed（verify.py）/ TTL 超窗（claim_ttl_job）/ fixed-review approve:false
- claim → needs_review：error run 判定产物 reason ∈ {na, reentry_same_version,
  input_truncated}（unclean_run 不入态——只经 batch 载体、批引 cluster 保持 claim，v1.8 R-14）
- open → inactive（ignore，现行 pending link 先 superseded 停回查）
- needs_review/fixed/inactive → open（reopen / needs-review-resolve reopen_cluster）

每次人工迁移同批落 conversion_record 审计。fix_version trim 归一（Task #4-② 防人手版本
≠ agent 自报；比较用 lower 归一、存储保 trim 原串）。R-1 零推进可降 K = 新端点需 §8.4
登记，本批不建（claim 表单 k 选择已覆盖）。
"""
import json
from datetime import datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.backflow.ack import iso_utc
from app.core.dict_config import get_global_int
from app.core.errors import AppError
from app.models.error_flow import ConversionRecord, ErrorCaseLink, ErrorCluster

AUTO_FIXED_K_KEY = "auto_fixed_k_default"   # dict_config 全局键（seed 默认 2）
CLAIM_TTL_DAYS_KEY = "claim_ttl_days"       # dict_config 全局键（seed 默认 14）
CLAIM_TTL_DEFAULT_DAYS = 14
K_RANGE = (1, 2)
REVIEW_REASONS = ("na", "reentry_same_version", "input_truncated")

CONV_DETAIL_MAX = 1024  # conversion_record.detail VARCHAR(1024)（strict 超长会 DataError）


def _json_detail(fields: dict) -> str:
    """conversion_record.detail 的 JSON 载荷，整体 ≤1024 且 JSON 完整不破库。

    note 是唯一可超长用户输入：先按「除 note 外结构体长 + 转义最坏 ×2 余量」裁 note，
    末尾整体 slice 兜底。"""
    if not fields.get("note"):
        return json.dumps(fields, ensure_ascii=False)[:CONV_DETAIL_MAX]
    rest = {k: v for k, v in fields.items() if k != "note"}
    base = json.dumps(rest, ensure_ascii=False)
    budget = max((CONV_DETAIL_MAX - len(base) - 16) // 2, 1)  # 预留 `,"note":"…"` 结构占用
    note = str(fields["note"]).strip()
    if len(note) > budget:
        note = note[:budget]
    return json.dumps({**rest, "note": note}, ensure_ascii=False)[:CONV_DETAIL_MAX]


def normalize_fix_version(value: str) -> str:
    """fix_version trim 归一（比较用 lower；Task #4-②）。"""
    return value.strip()


def _now() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc).replace(tzinfo=None)


def _state_err(cluster_id: int, state: str) -> AppError:
    """非法迁移/当前状态不符 → 400 带现行状态（§8.9）。"""
    return AppError("ERR_CLUSTER_0003", f"cluster 当前状态 {state}，不允许该迁移", http=400)


def _conflict_err(cluster_id: int) -> AppError:
    """CAS 竞态落空 → 409 带当前状态（后到者；ERR_CLUSTER_0002 本批激活）。"""
    return AppError("ERR_CLUSTER_0002", f"cluster {cluster_id} 已被并发处置，请刷新", http=409)


async def _mark_pending_links(
    session: AsyncSession, cluster_id: int, verify_status: str
) -> int:
    """现行 pending link → 终态（superseded 停回查 / passed / failed），释放 cur_key。"""
    result = await session.execute(
        update(ErrorCaseLink)
        .where(
            ErrorCaseLink.cluster_id == cluster_id,
            ErrorCaseLink.verify_status == "pending",
        )
        .values(verify_status=verify_status)
    )
    return result.rowcount or 0


async def claim_cluster(
    session: AsyncSession,
    cluster: ErrorCluster,
    *,
    fix_version: str,
    note: str | None,
    k: int | None,
    actor_id: int,
) -> dict:
    """claim：CAS open→claim（§8.4/§7.6 v1.5 R-1）。fix_version 必填；claim_k 固化。"""
    now = _now()
    cid = cluster.id
    if cluster.status != "open":
        raise _state_err(cid, cluster.status)
    fv = normalize_fix_version(fix_version)
    if not fv:
        raise AppError("ERR_CLUSTER_0003", "fix_version 必填（trim 后非空）", http=400)
    if k is None:
        k = await get_global_int(session, AUTO_FIXED_K_KEY, 2)
    if k not in K_RANGE:
        raise AppError("ERR_CLUSTER_0003", f"k 值域 {{1,2}}（当前 {k}）", http=400)
    ttl_days = await get_global_int(session, CLAIM_TTL_DAYS_KEY, CLAIM_TTL_DEFAULT_DAYS)
    due_ts = now + timedelta(days=max(ttl_days, 1))

    result = await session.execute(
        update(ErrorCluster)
        .where(ErrorCluster.id == cid, ErrorCluster.status == "open")
        .values(
            status="claim",
            fix_version=fv,
            claimed_by=actor_id,
            claimed_at=now,
            claim_due_ts=due_ts,
            claim_k=k,
        )
    )
    if result.rowcount != 1:
        raise _conflict_err(cid)
    session.add(
        ConversionRecord(
            cluster_id=cid,
            action="claim",
            detail=_json_detail(
                {"fix_version": fv, "k": k, "ttl_days": ttl_days,
                 **({"note": note} if note else {})},
            ),
            actor_user_id=actor_id,
        )
    )
    return {"cluster_id": cid, "fix_version": fv, "claim_k": k,
            "claim_due_ts": iso_utc(due_ts)}


async def ignore_cluster(
    session: AsyncSession, cluster: ErrorCluster, *, actor_id: int
) -> dict:
    """ignore：open→inactive（§8.4）；现行 pending link 先 superseded 停回查（§7.5）。"""
    cid = cluster.id
    if cluster.status != "open":
        raise _state_err(cid, cluster.status)
    links = await _mark_pending_links(session, cid, "superseded")
    result = await session.execute(
        update(ErrorCluster)
        .where(ErrorCluster.id == cid, ErrorCluster.status == "open")
        .values(status="inactive")
    )
    if result.rowcount != 1:
        raise _conflict_err(cid)
    session.add(
        ConversionRecord(
            cluster_id=cid,
            action="ignore",
            detail=f"ignore open→inactive（现行 link superseded ×{links}，停回查）",
            actor_user_id=actor_id,
        )
    )
    return {"cluster_id": cid, "status": "inactive"}


async def reopen_cluster(
    session: AsyncSession, cluster: ErrorCluster, *, note: str | None, actor_id: int
) -> dict:
    """reopen：fixed/inactive/needs_review→open（复发/误判反悔，§8.4）。"""
    cid = cluster.id
    if cluster.status not in ("fixed", "inactive", "needs_review"):
        raise _state_err(cid, cluster.status)
    prev = cluster.status
    result = await session.execute(
        update(ErrorCluster)
        .where(ErrorCluster.id == cid, ErrorCluster.status == prev)
        .values(status="open")
    )
    if result.rowcount != 1:
        raise _conflict_err(cid)
    session.add(
        ConversionRecord(
            cluster_id=cid,
            action="reopen",
            detail=_json_detail({"from": prev, **({"note": note} if note else {})}),
            actor_user_id=actor_id,
        )
    )
    return {"cluster_id": cid, "status": "open"}


async def needs_review_resolve_single(
    session: AsyncSession,
    cluster: ErrorCluster,
    *,
    action: str,
    note: str | None,
    actor_id: int,
) -> dict:
    """单条 needs_review 处置（§8.4；源 = 纯 na / reentry_same_version / input_truncated）。
    reopen_cluster → needs_review→open；escalated → §16 通道 v1 只记录（状态保留待人工）。
    """
    cid = cluster.id
    if cluster.status != "needs_review":
        raise _state_err(cid, cluster.status)
    reason = cluster.needs_review_reason or ""
    if action not in ("reopen_cluster", "escalated"):
        raise AppError("ERR_CLUSTER_0003", "action 值域 {reopen_cluster, escalated}", http=400)
    detail = _json_detail(
        {"action": action, "reason": reason, **({"note": note} if note else {})}
    )
    if action == "escalated":  # §16 通道 v1 只记录：状态保留，不迁移
        session.add(ConversionRecord(
            cluster_id=cid, action="needs_review_resolve", detail=detail,
            actor_user_id=actor_id))
        return {"cluster_id": cid, "status": "needs_review", "action": action}
    result = await session.execute(
        update(ErrorCluster)
        .where(ErrorCluster.id == cid, ErrorCluster.status == "needs_review")
        .values(status="open")
    )
    if result.rowcount != 1:
        raise _conflict_err(cid)
    session.add(ConversionRecord(
        cluster_id=cid, action="needs_review_resolve", detail=detail,
        actor_user_id=actor_id))
    return {"cluster_id": cid, "status": "open", "action": action}


async def fixed_review(
    session: AsyncSession,
    cluster: ErrorCluster,
    *,
    approve: bool,
    actor_id: int,
) -> dict:
    """admin 复核（§8.4 fixed-review）：approve:true → claim→fixed(admin_review)，
    现行 link verify passed；approve:false → claim→open（=reopen），link verify failed。"""
    cid = cluster.id
    if cluster.status != "claim":
        raise _state_err(cid, cluster.status)
    target = "fixed" if approve else "open"
    link_v = "passed" if approve else "failed"
    await _mark_pending_links(session, cid, link_v)
    result = await session.execute(
        update(ErrorCluster)
        .where(ErrorCluster.id == cid, ErrorCluster.status == "claim")
        .values(status=target)
    )
    if result.rowcount != 1:
        raise _conflict_err(cid)
    session.add(
        ConversionRecord(
            cluster_id=cid,
            action="fixed_review" if approve else "reopen",
            detail=f"admin 复核 approve={approve}（closed_by=admin_review）",
            closed_by="admin_review",
            actor_user_id=actor_id,
        )
    )
    return {"cluster_id": cid, "status": target}


async def _apply_auto_fixed(session: AsyncSession, cluster_id: int, *, seq_desc: str) -> None:
    """verify K 满收敛：claim→fixed（closed_by=auto_regression）。"""
    result = await session.execute(
        update(ErrorCluster)
        .where(ErrorCluster.id == cluster_id, ErrorCluster.status == "claim")
        .values(status="fixed")
    )
    if result.rowcount != 1:
        raise _conflict_err(cluster_id)
    session.add(ConversionRecord(
        cluster_id=cluster_id, action="auto_fixed", detail=f"K 满纯净序列（{seq_desc}）",
        closed_by="auto_regression", actor_user_id=None))


async def _apply_verify_reopen(session: AsyncSession, cluster_id: int, *, detail: str) -> None:
    """回归 failed：claim→open（K 清零由判据自然重算）。"""
    result = await session.execute(
        update(ErrorCluster)
        .where(ErrorCluster.id == cluster_id, ErrorCluster.status == "claim")
        .values(status="open")
    )
    if result.rowcount != 1:
        raise _conflict_err(cluster_id)
    session.add(ConversionRecord(
        cluster_id=cluster_id, action="reopen", detail=f"回归 failed → open（{detail}）",
        actor_user_id=None))


async def _apply_needs_review(
    session: AsyncSession, cluster_id: int, *, reason: str, note: str
) -> None:
    """error run 判定产物：claim→needs_review（reason ∈ {na, reentry_same_version,
    input_truncated}；unclean_run 不入态）。"""
    result = await session.execute(
        update(ErrorCluster)
        .where(ErrorCluster.id == cluster_id, ErrorCluster.status == "claim")
        .values(status="needs_review", needs_review_reason=reason)
    )
    if result.rowcount != 1:
        raise _conflict_err(cluster_id)
    session.add(ConversionRecord(
        cluster_id=cluster_id, action="needs_review", detail=note[:1024], actor_user_id=None))
