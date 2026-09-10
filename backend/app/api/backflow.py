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
- 结果推送接收面（v1.23 第 2 刀，**只增不删**）：POST /backflow/regression-results（evaluator
  静态 secret，不新造 JWT/scope）——offline run 终态 commit 后主动推结果，online 落
  verify_run_record 留档（uk_verify_run 幂等）。**本刀只落数据位**：判定内核切推送源（K 折叠
  / 终态收敛）归下一刀，recheck_job/verify.py 原样保留，两路并存。
- 详情读面新增 result_overdue（§8.7 保活标记「回查结果未达（疑似 offline 停摆），人工核查」）：
  MySQL 现算、零 DDL、不落列不设时钟。claim 分支锚定 conv(action='claim_ttl_expire')
  （v1.23 第 3 刀换判据）——原「超 claim_due_ts」判据被 claim_ttl_job 的 60s 回退清场
  冲掉、实际恒假，详见 _result_overdue docstring。
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, EvaluatorUser, ViewerUser
from app.backflow import batches as batch_flow
from app.backflow import claim as claim_flow
from app.backflow import recurrence as recurrence_flow
from app.backflow import requeue as requeue_flow
from app.backflow.ack import CASE_TYPES, SCHEMA_VERSION, _iso_to_naive
from app.backflow.claim import (
    CLAIM_TTL_DAYS_KEY,
    CLAIM_TTL_DEFAULT_DAYS,
    CONV_DETAIL_MAX,
)
from app.backflow.requeue import MANUAL_INVALIDATE_REASON
from app.core.config import get_settings
from app.core.db import get_session
from app.core.dict_config import get_global_int
from app.core.errors import AppError
from app.core.log import get_logger
from app.core.offline_client import OfflineClient, OfflineReadError
from app.models.error_flow import (
    ConversionRecord,
    ErrorCaseLink,
    ErrorCluster,
    NeedsReviewBatch,
    VerifyRunRecord,
)

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


# ---------- 请求/响应模型（v1.23 第 2 刀：结果推送接收面） ----------


class RegressionCaseItem(BaseModel):
    """逐 case 原始行（§8.7 载荷字段表）。case_type 白名单在端点层「丢行不拒单」。"""

    case_id: str = Field(max_length=64)
    case_type: str
    pass_fail: Literal["pass", "fail", "na"]
    error_type: str | None = Field(default=None, max_length=48)
    error_detail: str | None = None


class RegressionResultsRequest(BaseModel):
    """offline 推送的 run 级结果载荷（§8.7；字段必填性 = 该表「必填」列）。"""

    schema_version: str  # 必须 "1.0"，否则 ERR_PULL_0004 拒单
    agent: str = Field(max_length=64)
    agent_version: str = Field(max_length=64)  # = run 绑定版本（原 bound_version）
    run_id: str = Field(max_length=64)
    # 只推终态（原 B-1(c) 值集不变，改由 offline 保证而非 online 过滤）
    run_status: Literal["completed", "partial_failed", "timeout", "cancelled"]
    # 该 (agent, version) 在 offline 侧是否首次出现终态 run（重建 no_progress 守卫，§7.6）
    bound_version_first_seen: bool
    # offline 侧该 agent 已有终态 run 的最大版本（恢复防假连续守卫，§8.7 v1.23）
    agent_latest_version: str = Field(max_length=64)
    trigger_signal_id: int | None = None  # = 信封 source.cluster_id，回关联 cluster_id
    finished_ts: str  # run 终态时刻（ISO8601 UTC）
    cases: list[RegressionCaseItem]  # 必填，**空数组合法**（落 run 级行、case_pass=null）


class RegressionResultsResponse(BaseModel):
    accepted: bool
    duplicated: bool
    run_record_id: int | None
    links_advanced: list[int]
    cases_dropped: int


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
        "input_hash": cluster.input_hash, "first_trace_id": cluster.first_trace_id,
        "input_truncated": int(cluster.input_truncated),
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


async def _open_batches(session: AsyncSession, cluster_id: int) -> list[dict]:
    """未决 unclean_run 批：status=open 且 link_refs JSON 含该 cluster_id（P2-6 挂起徽标源）。

    link_refs = [{link_id, cluster_id, case_id}]（batches.py 写），cluster_id 为 numeric → 构造
    字面量 JSON 安全。批量处置端点 POST /needs-review-batches/{id}/resolve 由前端直调。"""
    batches = list((await session.scalars(
        select(NeedsReviewBatch).where(
            NeedsReviewBatch.status == "open",
            func.json_contains(
                NeedsReviewBatch.link_refs, json.dumps({"cluster_id": cluster_id})
            ),
        )
    )).all())
    out: list[dict] = []
    for b in batches:
        refs = b.link_refs if isinstance(b.link_refs, list) else []
        out.append({
            "batch_id": b.id, "run_id": b.run_id, "agent": b.agent,
            "bound_version": b.bound_version, "error_type": b.error_type,
            "ref_count": len(refs),
        })
    return out


# ---------- 「结果未达」标记（§8.7 保活语义 / §9.3 文案，v1.23 #7+#9 合并） ----------

# 逐字契约文案（§9.3）：前端命中即原样渲染，后端不做二次措辞
OVERDUE_CAPTION = "回查结果未达（疑似 offline 停摆），人工核查"


async def _result_overdue(
    session: AsyncSession, cluster: ErrorCluster,
    links: list[ErrorCaseLink], runs: list[VerifyRunRecord],
    convs: list[ConversionRecord],
) -> dict:
    """结果未达标记（MySQL 现算，零 DDL、不落列、不设 online 时钟）。

    背景：online 改「等 offline 推」后**无法感知 offline 存活**，两类现场需同一标记兜底
    （§8.7 保活语义，§16 风险行「可控停轮 → 不可观测死锁」）：
    ① claim：**出现 TTL 超窗回退现场**（conv action='claim_ttl_expire'）且 fix_version 非空
       且现行 pending link **无任何 verify_run_record**——见下方判据明细；
    ② assembled：现行 pending link 仍 assembled（offline 没来拉/没建 case）且
       `now - assembled_ts` 超 N 天。
    阈值 N 复用 dict_config `claim_ttl_days`（默认 14）——§8.7 明示两标记「共用同一阈值」，
    【实现约定】契约未给数，故以 claim TTL 同源而非新编魔法数。**代价（须明说）**：assembled
    分支要 link 一直停在 assembled 等满 N 天（= 14 天）才命中，短期停摆探测不到；requeue
    刷新 assembled_ts 即归零（§7.2「已待」本义，故按 link.assembled_ts 而非 cluster.first_ts
    现算）。

    claim 分支判据（v1.23 第 3 刀换判据，替换原「超 claim_due_ts ∧ 无 run」）：
    ① 存在 conv(action='claim_ttl_expire')（取最新一条，其 `ts` 作 since_ts）——
       `claim_ttl_job._expire_batch` CAS 回退 open 时必写这条，是「回退现场」唯一**持久**证据；
    ② `cluster.fix_version` 非空（回退时保留 = 有人声明修过该版本，非空才有「在等结果」语义）；
    ③ anchor 存在、**anchor 仍停在 `pending`**、且 anchor_runs 为空（「有个待回的结果」）；
    ④ **抑制**：当前不处于有效 claim 期内（`status='claim' ∧ due 非空 ∧ now ≤ due`）；
    ⑤ **本轮性**：`anchor.assembled_ts` 非空，且回退记录 `ts > anchor.assembled_ts`
       （回退必须发生在本轮等待开始**之后**，见下方「为什么必须有 ⑤」）。
    为什么 ③ 必带 `pending`（**不能用 `links[0]` 兜底**）：本函数的 anchor 兜底取最新一条 link，
    而 cluster 离开「等结果」态时 link 必被终结——`claim_flow.fixed_review(approve=True)` 把现行
    link 打 `passed`、`ignore` 打 `superseded`（claim.py:246 / backflow.py:602），此后
    conv(`claim_ttl_expire`) 在、`fix_version` 在、`anchor_runs` 空，**四个条件全成立** →
    在已 fixed / 已 inactive 的簇上误报「offline 停摆」。加 `pending` 后二者自然落空。
    不用「`cluster.status ∈ {open,claim}` 白名单」的理由：白名单在将来新增非终态时**静默漏报**
    （正是本标记要修的失效模式），而 link 谓词若被新状态漏动只会**误报**——响亮地错优于安静地错。
    为什么不用 `cluster.claim_due_ts`/`claimed_at`（原判据）：claim_ttl_job 每 60s 扫全表把
    **所有**超窗 claim 回退 open 并清 claimed_at/claim_due_ts（worker/claim_ttl_job.py），
    故「超窗 claim」这个现场最长只存在 60s——按它判定等于长期恒假（探测落空），claimed_at
    被清后作 since_ts 也恒 None。
    为什么必须有 ④：回退 open 后 cluster 可**再次 claim**（人工正常处置），而旧的
    claim_ttl_expire 记录仍留在库里 → 不抑制就会在人工等结果期间误报「offline 停摆」。
    为什么必须有 ⑤（`pending` 拦不住「link 被换了一条新的」）：cluster 回退 open 后若走
    `reopen`/`invalidate→requeue`，assemble_job 会给它装配一条**全新的 pending link**
    （旧 link 终结不影响 uk_link_current 放宽），此时 ①②③④ 全成立——fix_version 与旧 conv
    都还在（`reopen_cluster` 只置 status，不清 fix_version/conv），新 link 零 run——而
    since_ts 会是**几十天前**那个陈旧回退时刻，簇却刚刚重新组装。⑤ 用本轮起点（assembled_ts
    由 requeue 刷新）一比即排除。这也说明 ③ 的 `pending` 谓词与 ⑤ **不重叠、都要**：③ 挡
    「link 已被终结」，⑤ 挡「link 已被替换」。

    convs 由调用方传入（详情端点已按 ts desc 取全量）；本函数自行取最新一条，不依赖入参顺序。
    """
    now = _utc_now()
    # 现行 pending link（uk_link_current 保证同 case_type 至多一条）；无则退最新一条
    anchor = next((lk for lk in links if lk.verify_status == "pending"), None)
    if anchor is None:
        anchor = links[0] if links else None
    anchor_id = getattr(anchor, "id", None)
    anchor_runs = [r for r in runs if getattr(r, "link_id", None) == anchor_id]

    # ④ 有效 claim 期：未超窗（超窗者 60s 内必被 claim_ttl_job 回退，故此处只判「还没到期」）
    in_claim_window = (
        cluster.status == "claim" and cluster.claim_due_ts is not None
        and now <= cluster.claim_due_ts
    )
    # ① 最新一条 TTL 回退记录（ts 主序、id 次序，兼容 ts 同秒）
    expiries = [c for c in convs if c.action == "claim_ttl_expire"]
    latest_expire = max(expiries, key=lambda c: (c.ts, c.id)) if expiries else None
    # ⑤ 本轮等待起点 = `anchor.assembled_ts`（requeue 刷新即归零，§7.2「已待」本义）：
    #   回退必须落在**本轮**等待期间（`latest_expire.ts > anchor.assembled_ts`），否则是
    #   陈旧回退记录 + 新 link 的错配现场。
    #   为什么用 assembled_ts 而不是扫 `ts > latest_expire.ts` 的 assemble/claim/reopen/
    #   requeue conv：一次字段比较 vs 一趟扫描（少一次查询、少一组动作白名单，动作集将来
    #   增删不会静默失效），而 assembled_ts 本就是「本轮等到什么时候」的权威起点。
    #   为什么 `assembled_ts is None` 也抑制：link 未组装 = offline 还没有可跑的东西，此时
    #   报「offline 停摆」是误诊（没东西可跑 ≠ 停摆），该现场归 assembled 分支管。
    this_round = (
        anchor is not None and anchor.assembled_ts is not None
        and latest_expire is not None and latest_expire.ts > anchor.assembled_ts
    )
    if (latest_expire is not None and cluster.fix_version and not in_claim_window
            and anchor is not None and anchor.verify_status == "pending"
            and this_round and not anchor_runs):
        return {"hit": True, "kind": "claim",
                "since_ts": _iso(latest_expire.ts), "caption": OVERDUE_CAPTION}

    if (anchor is not None and anchor.verify_status == "pending"
            and anchor.offline_status == "assembled"):
        n_days = await get_global_int(
            session, CLAIM_TTL_DAYS_KEY, CLAIM_TTL_DEFAULT_DAYS)
        over_window = timedelta(days=max(n_days, 1))
        if (anchor.assembled_ts is not None
                and now - anchor.assembled_ts >= over_window):
            return {"hit": True, "kind": "assembled",
                    "since_ts": _iso(anchor.assembled_ts), "caption": OVERDUE_CAPTION}

    return {"hit": False, "kind": None, "since_ts": None, "caption": None}


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
    """cluster 详情：元数据 + links + verify 时间线 + conversion 审计 + 已待天数 + 复发观察/挂起批。

    响应 {…cluster 元数据, links[], verify_runs[], conversions[], waiting_days,
    result_overdue（«结果未达»标记，§8.7/§9.3）, reentry_observe（claim/fixed 现算复发观察，
    其余态 None）, open_batches[]}。"""
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
    observe = await recurrence_flow.cluster_reentry_observe(session, cluster)
    open_batches = await _open_batches(session, cluster_id)
    overdue = await _result_overdue(session, cluster, links, runs, convs)
    item = _cluster_item(cluster, _link_item(links[0]) if links else None)
    item.update({
        "links": [_link_item(lk) for lk in links],
        "verify_runs": verify_items,
        "conversions": conv_items,
        "waiting_days": waiting_days,
        "result_overdue": overdue,
        "reentry_observe": None if observe is None
        else {**observe, "since_ts": _iso(observe["since_ts"])},
        "open_batches": open_batches,
    })
    logger.debug(
        "backflow cluster 详情 出参: cluster_id=%s links=%s runs=%s overdue=%s",
        cluster_id, len(links), len(runs), overdue["kind"] or "-",
    )
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
    agent = cluster.agent
    generation = int(cluster.generation)
    result = await claim_flow.claim_cluster(
        session, cluster, fix_version=body.fix_version, note=body.note,
        k=body.k, actor_id=user.id,
    )
    await session.commit()  # claim 先落库：软提示查询不拖慢/不随读面异常回滚认领
    warning = await _claim_warning(agent, generation, result["fix_version"])  # R-5/R-7
    out = ClaimResponse(**result, warning=warning)
    logger.debug("claim 出参: cluster_id=%s claim_k=%s due=%s", cluster_id,
                 out.claim_k, out.claim_due_ts)
    return out


async def _claim_warning(agent: str, generation: int, fix_version: str) -> str | None:
    """claim 软提示（best-effort，非硬拦；offline 未配/读面不可达 → 退 None）。

    - R-5 版本预检（P2-6 做全，detail §9.3）：fix_version 未见于 offline 已见版本
      （agents/{agent}/versions 读面）→ 「未观测到…可能未发版或字面量不匹配，已见版本：…」
      ——防字面量 typo；与 verify.judge_link 的 versions 面门控同口径（trim 后精确成员）。
    - R-7 reentry（沿用）：generation>1 且 fix_version 命中已 completed run → 提示同版本
      重试命中 reentry。
    """
    settings = get_settings()
    if not settings.offline_base_url:
        return None
    client = OfflineClient(settings.offline_base_url,
                           secret=settings.evaluator_service_secret, timeout_s=3)
    try:
        face = await client.agent_versions(agent=agent)
        seen = [str(it.get("version") or it.get("name") or "") for it in face]
        seen = list(dict.fromkeys(s for s in seen if s))
        fv = claim_flow.normalize_fix_version(fix_version)
        if seen and fv not in seen:
            shown = "、".join(sorted(seen)[:12])
            if len(seen) > 12:
                shown += f" 等 {len(seen)} 个"
            return (f"注意：未观测到 {agent}@{fv} 评测 run——可能未发版或字面量"
                    f"不匹配，已见版本：{shown}")
        if generation > 1:
            runs = await client.list_runs(agent=agent, version=fv)
            if any(r.get("status") == "completed" for r in runs):
                return (f"注意：{agent}@{fv} 已存在 completed run（generation>1 同版本"
                        f"重试命中 reentry）——是否确为新修复？verify 回查按实际判定；硬闸属 P2-5")
        return None
    except OfflineReadError as exc:
        logger.warning("claim 软提示查询失败（忽略）", extra={"err": str(exc)})
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


# ---------- 结果推送接收面（v1.23 第 2 刀，§8.7；evaluator 凭证，不接平台 JWT） ----------

# 孤儿 run 的 link_id 哨兵（trigger_signal_id 缺失或查不到现行 link）
#
# 取值 0 的理由：error_case_link.id 为 BIGINT UNSIGNED AUTO_INCREMENT（models/base.py
# BIGINT_UX），InnoDB 自增从 1 起分配、无符号列不能存负数（strict 模式写 -1 即 DataError），
# 故 0 是唯一「DB 允许写入且永不会被真实 link 占用」的表示；NULL 不可用（列 NOT NULL）。
# 幂等：orphan 行同样落在 uk_verify_run(link_id, run_id) 上——同一 orphan run 重复推命中
# (0, run_id) 唯一键 → 走重复分支 200 duplicated=true，不重建行、不重复计数。
ORPHAN_LINK_ID = 0


def _split_cases(cases: list[RegressionCaseItem]) -> tuple[list[RegressionCaseItem], int]:
    """case_type 白名单分流（§8.7）：非白名单**丢该行 + 计数，不整体拒单**。

    白名单单一来源 = ack.CASE_TYPES（与 pull 侧「非白名单返空集」同为「不因单行断整批」）。
    """
    kept = [c for c in cases if c.case_type in CASE_TYPES]
    return kept, len(cases) - len(kept)


def _case_pass_of(link: ErrorCaseLink | None, kept: list[RegressionCaseItem]) -> int | None:
    """run 级行的 case_pass：由 link.case_id 命中载荷行派生（无 link/无 case_id/缺行 → NULL）。

    本刀判定内核不切（K 折叠/终态收敛归下一刀），此列只保证与旧轮询路径的兜底读法兼容
    （verify._decision_from_row 在 raw_json 无 x_pf 时回退 case_pass）；na 与缺行同为 NULL，
    两者区分留给下一刀从 raw_json.cases[] 重派生（载荷已原样留档）。
    """
    if link is None or not link.case_id:
        return None
    row = next((c for c in kept if c.case_id == link.case_id), None)
    if row is None or row.pass_fail == "na":
        return None
    return 1 if row.pass_fail == "pass" else 0


async def _find_current_link(
    session: AsyncSession, trigger_signal_id: int | None,
) -> ErrorCaseLink | None:
    """按 trigger_signal_id（= 信封 source.cluster_id）反查现行 link（§8.7 回关联）。

    现行 link = `verify_status='pending'`（cur_key 生成列占位；uk_link_current(case_type,
    cur_key) 保证同 cluster 同 case_type 至多一条，v1 只此一种 case_type）。查不到（含字段
    缺失）→ 返回 None = orphan：调用方仍落库留档，只是不推进任何 link 判定。
    """
    if trigger_signal_id is None:
        return None
    return await session.scalar(
        select(ErrorCaseLink)
        .where(
            ErrorCaseLink.cluster_id == trigger_signal_id,
            ErrorCaseLink.verify_status == "pending",
        )
        .limit(1)
    )


def _conv_detail(
    body: RegressionResultsRequest, link: ErrorCaseLink | None, *,
    kept: int, dropped: int,
) -> str:
    """conversion_record.detail：定位本次推送现场（orphan 显式标注，便于对账关联断裂）。"""
    if link is None:
        head = (f"orphan：trigger_signal_id="
                f"{body.trigger_signal_id if body.trigger_signal_id is not None else '缺'}"
                f" 无现行 pending link（仅留档，不推进判定）")
    else:
        head = f"cluster={link.cluster_id} link={link.id} case_id={link.case_id or '-'}"
    return (
        f"{head}；run_id={body.run_id} agent={body.agent}@{body.agent_version} "
        f"run_status={body.run_status} cases={kept} dropped={dropped}"
    )[:CONV_DETAIL_MAX]


async def record_regression_result(
    session: AsyncSession, body: RegressionResultsRequest,
) -> dict:
    """结果推送落库（§8.7；幂等键 = uk_verify_run(link_id, run_id)）；返回响应字段字典。

    本刀语义边界（**只落数据位，不重算判定**——内核切推送源归下一刀，两路并存）：
    - 落 verify_run_record 一行（run 级；case_pass 由 link.case_id 命中行派生）+ 一条
      conversion_record（action=regression_result，actor_user_id=NULL = 系统动作）。
    - orphan：仍落库留档（link_id=哨兵 0，防关联断裂丢数据），links_advanced 空、不推进判定；
      conv 照写（cluster_id=NULL、link_id=0）——审计链要求「收到即留痕」，orphan 正是最需要
      人工对账的现场，不写就变成静默丢数据。
    - 重复推送（同 link_id + run_id 已有行）：duplicated=true，不重复落库、不重复写 conv。
    - links_advanced 语义 = **本次真正新落 run 行的 link**（载荷 trigger_signal_id 反查到现行
      pending link 且未重复）：重复推送为空、orphan 为空。本刀不产生 passed/failed/superseded
      等终态迁移（那属判定内核，下一刀），故该字段只表达「数据位推进」。
    - cases_dropped 口径 = **载荷校验产物，与是否落库正交**：每次都按本次载荷现算并返回，
      重复推送（duplicated=true）同样返回该值。因此重试必须拿到与首次**一致**的答案——否则
      offline 在「响应丢失」场景（fire-and-forget 重推，§8.7）会误判「没丢数据」。
    - 载荷内 **case_id 重复**（同一 case 两条结果）→ 400 `ERR_PULL_0002` 整单拒，零落库；
      与 case_type 非白名单「丢行不拒单」互补（丢行 = 行不认识，拒单 = 行互相打架）。
    - v1 硬约束：**一次回归 run 只对应一个 cluster**（载荷只有单值 trigger_signal_id）；跨
      cluster 的批量回归 run 不在 v1 范围（要支持须改载荷为数组 + 幂等键，回方案）。
    """
    if body.schema_version != SCHEMA_VERSION:  # §8.9 ERR_PULL_0004：版本不识别拒单
        raise AppError(
            "ERR_PULL_0004",
            f"schema_version 不支持（{body.schema_version!r}，当前 {SCHEMA_VERSION}）",
            http=400,
        )
    # finished_ts 必须 ISO8601（与 schema_version/R-22 同层：载荷校验，一律落库前拒单）：
    # 它是 offline 侧 run 终态时刻，后续刀要靠它做「版本恢复防假连续」判定（§8.7），
    # 脏串不能留到那时才炸。字段必填（model 无默认）→ 无 None 放行分支。
    try:
        _iso_to_naive(body.finished_ts)
    except (ValueError, TypeError) as exc:
        raise AppError(
            "ERR_PULL_0002",
            f"finished_ts 非 ISO8601（实测值 {body.finished_ts!r}）: {exc}",
            http=400,
        ) from exc
    # 载荷内 case_id 重复 → 整单拒（同层：载荷校验、落库前拒单）。
    # 为什么拒单而非静默取首条：同一 case 出现两条 = 载荷自相矛盾（可一 pass 一 fail），
    # 而 `_case_pass_of` 按 case_id 取**首条**命中行 → 静默取首条等于按一条任意结果收敛判定，
    # 且 run 行落库、link 终态只读（入库不可回改），offline 侧真正的拼装 bug 会被彻底掩盖；
    # 拒单让它立刻可见（响应体带重复值 + 首次出现下标，可直接定位）。
    # 与 case_type 非白名单「丢该行」策略不冲突：那是「行**不认识**」（丢掉可安全降级到剩余
    # 行），这是「行**互相打架**」（取哪条都错，只能整单拒）。
    # 重复检查针对**原始载荷**（`_split_cases` 分流之前）：重复是 offline 拼装缺陷，与
    # case_type 是否白名单无关，不能因某行被丢就免检。
    # case_id 在 model 层必填（`str` 无默认，缺字段/显式 null 在 pydantic 层即 422）→ 本循环
    # 无 None 跳过分支；若将来放开可空，须显式跳过 None（多条无 case_id 的行是合法的 run 级
    # 行，不能按重复误拒）。
    seen_case_ids: dict[str, int] = {}
    for idx, item in enumerate(body.cases):
        first_idx = seen_case_ids.get(item.case_id)
        if first_idx is not None:  # 用 is not None：首次下标 0 是合法值且为假值
            raise AppError(
                "ERR_PULL_0002",
                f"cases[{idx}].case_id 重复（值 {item.case_id!r} 已出现于 cases[{first_idx}]）"
                f"：同一 case 两条结果自相矛盾，整单拒",
                http=400,
            )
        seen_case_ids[item.case_id] = idx

    # R-22 不变量（§8.7）：pass_fail='na' 必带 error_type（收尾三路径统一 scheduler_unexecuted）
    for idx, item in enumerate(body.cases):
        if item.pass_fail == "na" and not item.error_type:
            raise AppError(
                "ERR_PULL_0002",
                f"cases[{idx}].pass_fail=na 必带 error_type（R-22 不变量）",
                http=400,
            )

    kept, dropped = _split_cases(body.cases)
    link = await _find_current_link(session, body.trigger_signal_id)
    link_id = link.id if link is not None else ORPHAN_LINK_ID  # 见 ORPHAN_LINK_ID 注释

    existing_id = await session.scalar(
        select(VerifyRunRecord.id).where(
            VerifyRunRecord.link_id == link_id,
            VerifyRunRecord.run_id == body.run_id,
        )
    )
    if existing_id is not None:
        # 幂等重放：行已由首次推送落库（orphan 哨兵行同样命中 uk_verify_run）→ 零写
        return {"accepted": True, "duplicated": True, "run_record_id": existing_id,
                "links_advanced": [], "cases_dropped": dropped}

    # 幂等 = 先查后写 + uk_verify_run 兜底：并发同 run 双推的窄窗口里后到者会撞唯一键
    # （IntegrityError → 500，零脏写），offline 侧退避重试即命中上面的 duplicated 分支，
    # 不丢数据（fire-and-forget 3 次重试，§8.7）
    record = VerifyRunRecord(
        link_id=link_id,
        run_id=body.run_id,
        bound_version=body.agent_version,  # = 原 verify_run_record.bound_version
        case_pass=_case_pass_of(link, kept),
        run_status=body.run_status,
        # 载荷**原样**留档：cases[] / agent_latest_version / bound_version_first_seen /
        # finished_ts 全在其中——零 DDL 承载 offline 水位字段（§8.7 v1.23 第 2 刀补）
        raw_json=body.model_dump(mode="json"),
    )
    session.add(record)
    session.add(ConversionRecord(
        cluster_id=link.cluster_id if link is not None else None,
        link_id=link_id,
        action="regression_result",
        detail=_conv_detail(body, link, kept=len(kept), dropped=dropped),
        actor_user_id=None,  # 系统动作（offline 推送），非人工
    ))
    await session.flush()  # 回填自增 id 供响应；commit 由端点层显式做（auth/pull 先例）
    return {"accepted": True, "duplicated": False, "run_record_id": record.id,
            "links_advanced": [link_id] if link is not None else [],
            "cases_dropped": dropped}


@router.post("/regression-results", response_model=RegressionResultsResponse)
async def regression_results_endpoint(
    _auth: EvaluatorUser,
    session: _Session,
    body: RegressionResultsRequest,
) -> RegressionResultsResponse:
    """结果推送接收（§8.7 offline→online；evaluator 静态 secret，与 pull/ack 共用不分置）。

    幂等 200（duplicated）/ 拒单 4xx（401 ERR_PULL_0001 / 400 ERR_PULL_0004 / ERR_PULL_0002）
    ——本刀不存在「200 + accepted=false」路径，该字段保留为契约形状。"""
    logger.debug(
        "regression-results 入参: agent=%s agent_version=%s run_id=%s run_status=%s"
        " trigger_signal_id=%s cases=%s first_seen=%s latest_version=%s finished_ts=%s",
        body.agent, body.agent_version, body.run_id, body.run_status,
        body.trigger_signal_id, len(body.cases), body.bound_version_first_seen,
        body.agent_latest_version, body.finished_ts,
    )  # cases 只打条数（正文不落日志）
    result = await record_regression_result(session, body)
    await session.commit()
    logger.debug(
        "regression-results 出参: accepted=%s duplicated=%s run_record_id=%s"
        " links_advanced=%s cases_dropped=%s",
        result["accepted"], result["duplicated"], result["run_record_id"],
        result["links_advanced"], result["cases_dropped"],
    )
    return RegressionResultsResponse(**result)
