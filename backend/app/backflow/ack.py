"""平台间契约：pull-API 拉取 + ack 状态回写（detail §7.2/§7.3/§8.7，P2-3 / T-3.3）。

- `ack_decide` 纯函数：§7.3 ack 前置矩阵（含契约修订 R2 例外 + 幂等重复）。无 DB 依赖，
  单测直接打全矩阵；DB 编排走 `apply_ack`（CAS，防并发拉取交错 X-11/E-15）。
- `pull_payloads`：扫 `offline_status='assembled'` 按 (assembled_ts, id) 升序 keyset
  分页（join error_cluster 按 agent 过滤、`assembled_ts ≥ since_ts`、limit+1 截断产
  next_token）。online 不 push、不设拉取时钟（§7.2）——纯请求驱动。
- 时间口径：DB assembled_ts 为 naive UTC（列 server_default），游标/ISO 出入均按
  naive UTC 归一（`.replace(tzinfo=None)`）。
"""
import base64
import json
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.error_flow import ErrorCaseLink, ErrorCluster

SCHEMA_VERSION = "1.0"          # 与 converter/envelope.SCHEMA_VERSION 同源语义
CASE_TYPES = ("regression_error",)   # §8.7 白名单：v1 仅此；二期加值须回方案

# invalidate reason 结构化码（§7.4）：驳回与人工统一
REASON_CODES = ("offline_cap_gap", "online_content_gap", "manual_invalidate")

# ack 前置矩阵（§7.3，含契约修订 R2 例外）。各 action → 允许的 (当前 offline_status, 附加条件)：
#  - 附加条件 None = 无额外要求；'case_id' = 必带 case_id；'reason:code' = 本 ack 带 reason
#    且须为该码；'stored_reason:code' = link 现行 invalidate_reason 须为该码（R2 例外，
#    invalidated(offline_cap_gap) 行 offline 重扫自愈回写 active）。
_ACK_MATRIX = {
    "draft": [("assembled", None)],                                  # 拉取建 draft（case_id 可选）
    "active": [                                                       # 收单即激活
        ("assembled", "case_id"),
        ("draft", "case_id"),
        ("invalidated", "stored_reason:offline_cap_gap"),  # R2：offline 自愈回写带 case_id
    ],
    "invalidated": [                                                  # 结构自检失败驳回 / 人工
        ("assembled", "reason"),
        ("draft", "reason"),
    ],
}

# 幂等目标：ack 到「目标 = 当前」视为重复（E-15，已知 payload 重复 ack=200 不报错）
_TARGET_OF_ACTION = {"draft": "draft", "active": "active", "invalidated": "invalidated"}


def _iso_to_naive(value: str) -> datetime:
    """ISO8601 UTC 串 → naive UTC datetime（since_ts/游标入参归一）。"""
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def iso_utc(dt: datetime) -> str:
    """naive UTC datetime → ISO8601 UTC（响应 assembled_ts；契约 R1：增量锚唯一可靠来源）。"""
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


# ---------- ack 矩阵（纯逻辑） ----------


def ack_decide(
    current_status: str,
    action: str,
    *,
    current_reason: str | None,
    has_case_id: bool,
    reason: str | None,
) -> tuple[str, str | None, str | None]:
    """§7.3 ack 前置矩阵判定。返回 (outcome, target_status, detail)。

    outcome ∈ {"apply", "noop", "violation"}：
    - "apply"    → 允许迁移，target_status = 目标状态（调用方 CAS 落库）。
    - "noop"     → 幂等重复（current 已 == 目标，E-15），target_status=current_status，200 无操作。
    - "violation"→ 前置不符，detail = 给 ERR_CLUSTER_0003 的可读 message。
    """
    if action not in _ACK_MATRIX:
        return "violation", None, f"action 非法（{action!r}，值域 draft/active/invalidated）"

    # 幂等：目标状态 == 当前状态 → noop（即使带不同 case_id/reason，重复 ack 不报错，E-15）
    if current_status == _TARGET_OF_ACTION[action]:
        return "noop", current_status, None

    for allowed_from, cond in _ACK_MATRIX[action]:
        if current_status != allowed_from:
            continue
        if cond is None:
            return "apply", _TARGET_OF_ACTION[action], None
        if cond == "case_id":
            if has_case_id:
                return "apply", _TARGET_OF_ACTION[action], None
            return "violation", None, (
                f"{action} 需携带 case_id（offline case id，单错级回查断链防护，§7.3）"
            )
        if cond == "reason":
            if reason and reason in REASON_CODES:
                return "apply", _TARGET_OF_ACTION[action], None
            if not reason:
                return "violation", None, "invalidated ack 必带结构化 reason（码见 §7.4）"
            return "violation", None, f"reason 码不在值域（{reason!r}，值域 {REASON_CODES}）"
        if cond == "stored_reason:offline_cap_gap":  # R2 例外：gate link 现行 invalidate_reason
            if current_reason == "offline_cap_gap" and has_case_id:
                return "apply", _TARGET_OF_ACTION[action], None
            if current_reason != "offline_cap_gap":
                return "violation", None, (
                    f"invalidated→active 仅契约修订 R2 例外放行"
                    f"（link.invalidate_reason=offline_cap_gap，offline 重扫自愈回写）；"
                    f"当前 reason={current_reason!r} → 人工处置走 admin requeue（§7.4）"
                )
            return "violation", None, "active 需携带 case_id（R2 例外同 §7.3 必带）"

    return "violation", None, (
        f"ack 前置不符：{action} 不允许从 offline_status={current_status} 迁移（§7.3 矩阵）"
    )


def _r3_extra(link) -> dict:
    """契约修订 R3：ERR_CLUSTER_0003 响应体带当前 offline_status +
    invalidate_reason（供 offline 对账）。"""
    return {
        "offline_status": link.offline_status,
        "invalidate_reason": link.invalidate_reason or "",
    }


# ---------- ack 落库（CAS，并发交错吸收） ----------


async def apply_ack(
    session: AsyncSession,
    *,
    payload_id: str,
    action: str,
    case_id: str | None = None,
    reason: str | None = None,
) -> dict:
    """按 §7.3 更新单 link（payload_id upsert 幂等）：未知 → ERR_PULL_0003(404)；
    前置不符 → ERR_CLUSTER_0003(400，带当前状态 R3)；重复 ack → 200 no-op。
    CAS = UPDATE ... WHERE offline_status=:前置，rowcount=0 → 重读判幂等/给 R3
    （并发双 offline 交错 X-11/E-15）。调用方负责 commit。
    """
    link = await session.scalar(
        select(ErrorCaseLink).where(ErrorCaseLink.payload_id == payload_id)
    )
    if link is None:
        raise AppError(
            "ERR_PULL_0003", f"payload_id 不存在：{payload_id}", http=404
        )

    outcome, target, detail = ack_decide(
        link.offline_status,
        action,
        current_reason=link.invalidate_reason,
        has_case_id=bool(case_id and case_id.strip()),
        reason=reason,
    )
    if outcome == "noop":
        return {"payload_id": payload_id, "offline_status": link.offline_status}
    if outcome == "violation":
        raise AppError("ERR_CLUSTER_0003", detail, http=400, extra=_r3_extra(link))

    # CAS：仅当前仍 == 判定时读到的前置状态才落（并发 ack 交错时 rowcount=0 → 下重读分支）
    fields: dict = {"offline_status": target}
    if target in ("draft", "active"):
        if case_id:
            fields["case_id"] = case_id
        # 清失效标注：R2 从 invalidated 自愈回写 active 后不留旧 invalidate_reason/invalidated_by
        fields["invalidate_reason"] = None
        fields["invalidated_by"] = None
    if target == "invalidated":
        fields["invalidate_reason"] = reason
    result = await session.execute(
        update(ErrorCaseLink)
        .where(
            ErrorCaseLink.payload_id == payload_id,
            ErrorCaseLink.offline_status == link.offline_status,
        )
        .values(**fields)
    )
    if result.rowcount == 1:
        return {
            "payload_id": payload_id,
            "offline_status": target,
            **({"case_id": case_id} if case_id else {}),
        }

    # 竞态落空：重读当前，== target（他方已置同目标）→ 幂等 200；否则 R3 带现行状态
    cur = await session.scalar(
        select(ErrorCaseLink).where(ErrorCaseLink.payload_id == payload_id)
    )
    if cur is not None and cur.offline_status == target:
        return {"payload_id": payload_id, "offline_status": cur.offline_status}
    if cur is None:  # 理论上不达（payload_id 不删），防御
        raise AppError("ERR_PULL_0003", f"payload_id 不存在：{payload_id}", http=404)
    return _violation_r3(cur, f"{action} 迁移与并发 ack 交错，当前状态为 {cur.offline_status}")


def _violation_r3(link, detail: str) -> dict:
    raise AppError("ERR_CLUSTER_0003", detail, http=400, extra=_r3_extra(link))


# ---------- pull（keyset 分页扫描） ----------


def encode_cursor(assembled_ts: datetime, link_id: int) -> str:
    """(assembled_ts, id) keyset 游标 → 不透明 token（base64url JSON）。"""
    raw = json.dumps({"ts": iso_utc(assembled_ts), "id": link_id}).encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(token: str) -> tuple[datetime, int]:
    """游标 token → (assembled_ts naive UTC, id)。畸形 → ValueError（调用方按坏请求 400）。"""
    raw = base64.urlsafe_b64decode(token.encode())
    obj = json.loads(raw)
    return _iso_to_naive(obj["ts"]), int(obj["id"])


async def pull_payloads(
    session: AsyncSession,
    *,
    since_ts: datetime | None = None,
    agent: str | None = None,
    limit: int = 100,
    cursor: tuple[datetime, int] | None = None,
) -> tuple[list[ErrorCaseLink], str | None]:
    """扫 assembled link（§8.7）：join cluster 按 agent 过滤、assembled_ts ≥ since_ts、
    order (assembled_ts, id) 升序、limit+1 截断产 next_token。返回 (rows, next_token)。
    """
    q = (
        select(ErrorCaseLink)
        .join(ErrorCluster, ErrorCluster.id == ErrorCaseLink.cluster_id)
        .where(ErrorCaseLink.offline_status == "assembled")
    )
    if since_ts is not None:
        q = q.where(ErrorCaseLink.assembled_ts >= since_ts)
    if agent:
        q = q.where(ErrorCluster.agent == agent)
    if cursor is not None:
        c_ts, c_id = cursor
        q = q.where(
            or_(
                ErrorCaseLink.assembled_ts > c_ts,
                and_(ErrorCaseLink.assembled_ts == c_ts, ErrorCaseLink.id > c_id),
            )
        )
    rows = list(
        (
            await session.scalars(
                q.order_by(ErrorCaseLink.assembled_ts, ErrorCaseLink.id).limit(limit + 1)
            )
        ).all()
    )
    if len(rows) <= limit:
        return rows, None
    last = rows[-2]  # 第 limit+1 行仅作「还有下一页」哨兵，不返回
    return rows[:limit], encode_cursor(last.assembled_ts, last.id)
