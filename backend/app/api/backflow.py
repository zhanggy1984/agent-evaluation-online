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
- 结果推送接收面（v1.23 第 2 刀建面 / **第 3 刀接判定**）：POST /backflow/regression-results
  （evaluator 静态 secret，不新造 JWT/scope）——offline run 终态 commit 后主动推结果，online
  落 verify_run_record 留档（uk_verify_run 幂等）**并同事务内推进该 link 判定**
  （verify.judge_link，数据源 = 本 link 已收结果行集），`links_advanced` 随之升级为「真正
  发生终态迁移的 link」。轮询链（core/offline_client + worker/recheck_job）已整删。
- 详情读面新增 result_overdue（§8.7 保活标记「回查结果未达（疑似 offline 停摆），人工核查」）：
  MySQL 现算、零 DDL、不落列不设时钟。claim 分支锚定 conv(action='claim_ttl_expire')
  （v1.23 第 2 刀换判据）——原「超 claim_due_ts」判据被 claim_ttl_job 的 60s 回退清场
  冲掉、实际恒假，详见 _result_overdue docstring。
- 详情读面第二个派生标记 result_gap_suspected（本批补）：本簇现行 pending link 命中
  `verify.link_gap_version`（缺行中断现场）→ true，语义 = 「疑似丢失一笔结果推送」。
  判定异常降级与一次性推送的安全网 = `worker/rejudge_job.py`（本批补）。
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import EvaluatorUser, ViewerUser
from app.backflow import recurrence as recurrence_flow
from app.backflow import requeue as requeue_flow
from app.backflow.ack import CASE_TYPES, SCHEMA_VERSION, _iso_to_naive
from app.backflow.claim import (
    CLAIM_TTL_DAYS_KEY,
    CLAIM_TTL_DEFAULT_DAYS,
    CONV_DETAIL_MAX,
)
from app.backflow.verify import (
    TERMINAL_OUTCOMES,
    judge_link,
    link_gap_version,
    link_k_progress,
)
from app.core.db import get_session
from app.core.dict_config import get_global_int
from app.core.errors import AppError
from app.core.log import get_logger
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

# ---------- 请求/响应模型（v1.23 第 2 刀：结果推送接收面） ----------


class RegressionCaseItem(BaseModel):
    """逐 case 原始行（§8.7 载荷字段表）。case_type 白名单在端点层「丢行不拒单」。"""

    case_id: str = Field(max_length=64)
    case_type: str
    pass_fail: Literal["pass", "fail", "na"]
    error_type: str | None = Field(default=None, max_length=48)
    error_detail: str | None = None
    # 批 54：本次回放用的**不是现场输入**（离线侧换了平台样例文件，见 offline
    # `pull_loop` 的 `_substituted_from` / `error_push._cases_of_cluster`）。
    # 默认 False 承载两种情形——旧 offline（不发该键）与「确实没替换」——两者在本字段上
    # 语义相同（当时没发生替换），故不需要区分，也不需要 None 三态。
    # ⚠️ 它与 `pass_fail` 组合出的才是判据：「替换过 **且** pass」= 这条 pass 证明的是
    # 样例文件跑得通，不是原场景修好了。单看 pass 会被读成后者。
    input_substituted: bool = False


class RegressionResultsRequest(BaseModel):
    """offline 推送的 run 级结果载荷（§8.7；字段必填性 = 该表「必填」列）。"""

    schema_version: str  # 必须 "1.0"，否则 ERR_PULL_0004 拒单
    agent: str = Field(max_length=64)
    agent_version: str = Field(max_length=64)  # = run 绑定版本（原 bound_version）
    run_id: str = Field(max_length=64)
    # 只推终态（原 B-1(c) 值集不变，改由 offline 保证而非 online 过滤）
    run_status: Literal["completed", "partial_failed", "timeout", "cancelled"]
    # offline 侧该 agent 已有终态 run 的最大版本（恢复防假连续守卫，§8.7 v1.23）
    agent_latest_version: str = Field(max_length=64)
    # 本次 run 之前、该 agent 最近一个已到终态 run 的版本（与上面两个水位字段同一次查询产出）。
    # **必填但值可为 null**：null = 该 agent 此前没有任何终态 run（首次），此时无前序可查、
    # 不中断；非空而 online 本地（**该 agent 已收版本全集**，v1.23 第 4 批由「本 link 行集」
    # 改全局，见 `verify._agent_versions`）无该版本记录 = 上一笔结果推送丢失 → gap 中断不
    # 累计 K（见 `verify.judge_link` 缺行中断判据）。
    prev_terminal_version: str | None = Field(max_length=64)
    # = 信封 source.cluster_id。**必填**（offline `error_push.assemble_payload` 恒填）：它既是
    # 回关联簇的锚、又是幂等键 `uk_verify_run(cluster_id, run_id)` 的一半——缺了它这笔推送
    # 既关联不到簇、也无法判重（NULL 在唯一索引中不去重 ⇒ 每次重推都落新行、审计面静默积行）。
    # 缺字段/显式 null 在 pydantic 层即 422（与 `case_id` 同层同例）。
    trigger_signal_id: int
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


async def _load_cluster(session: AsyncSession, cluster_id: int) -> ErrorCluster:
    """cluster 定位（§8.4）：不存在 → ERR_CLUSTER_0001(404)。"""
    cluster = await session.get(ErrorCluster, cluster_id)
    if cluster is None:
        raise AppError("ERR_CLUSTER_0001", f"cluster 不存在：{cluster_id}", http=404)
    return cluster


def _cluster_item(cluster: ErrorCluster, link: dict | None) -> dict:
    """cluster 列表项序列化（字段级钉死，P2-6 前端逐字段消费）。

    ⚠️ `seq`（K 进度）**不在这里**：它要 await 查库，本函数是同步纯序列化。两个调用方
    （列表端点、详情端点）各自算好后 `item["seq"] = …` 补上 —— 两处都必须补，前端
    `taskState` 两页共用，缺一处就出现「列表说还等着人修、详情说没事」的矛盾。"""
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


def _link_item(link: ErrorCaseLink, requeue_count: int = 0) -> dict:
    """link 序列化；requeue_count 由调用方成批查好后传入（勿在此单查 → N+1）。"""
    return {
        "link_id": link.id, "payload_id": link.payload_id, "case_id": link.case_id,
        "case_type": link.case_type, "offline_status": link.offline_status,
        "verify_status": link.verify_status,
        "assembled_ts": _iso(link.assembled_ts),
        "invalidate_reason": link.invalidate_reason,
        "requeue_count": requeue_count,
    }


async def _cluster_link_reps(
    session: AsyncSession, cluster_ids: list[int]
) -> dict[int, ErrorCaseLink]:
    """批量取 cluster **现行 link 对象**：pending 优先，无则最新（id 最大）。

    「现行 link」= 页面上说「这一簇现在到哪一步」所指的那一条，**选取规则只有这一份**：
    `_cluster_links`（要序列化摘要）与 clusters 列表端点（要 ORM 喂判定内核）都从这里取，
    各写一份就等着两处漂移（详情端点是另一种取法：按 id 降序取 links[0]）。
    """
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
    reps = {}
    for cid, links in out.items():
        current = next((lk for lk in links if lk.verify_status == "pending"), None)
        reps[cid] = current if current is not None else links[-1]
    return reps


async def _serialize_links(
    session: AsyncSession, reps: dict[int, ErrorCaseLink]
) -> dict[int, dict]:
    """现行 link 对象 → 序列化摘要（requeue_count 成批取，勿逐项单查 → N+1）。"""
    # R-7 可愈性标注：本屏所有 link 的重推次数一次成批取
    counts = await requeue_flow.requeue_counts(session, [r.id for r in reps.values()])
    return {cid: _link_item(r, counts.get(r.id, 0)) for cid, r in reps.items()}


async def _cluster_links(session: AsyncSession, cluster_ids: list[int]) -> dict[int, dict]:
    """批量取 cluster 现行 link **摘要**（序列化 dict）。

    ⚠️ 要 ORM 对象（如喂判定内核 `link_k_progress`）用 `_cluster_link_reps` ——
    本函数返回的 `link` 是 dict，取属性会 AttributeError。
    """
    return await _serialize_links(session, await _cluster_link_reps(session, cluster_ids))


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
    而 cluster 离开「等结果」态时 link 必被终结——自动收口时 `_mark_pending_links("passed")`
    把现行 link 打 `passed`（claim.py；原论据另举的 fixed_review / ignore 两条人工路径已随
    批 35-B 删除，判据本身不动），此后
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
    （`_apply_verify_reopen` 记 conv(action=reopen)），assemble_job 会给它装配一条**全新的
    pending link**（旧 link 终结不影响 uk_link_current 放宽），此时 ①②③④ 全成立——
    fix_version 与旧 conv 都还在（回退路径不清 fix_version/conv），新 link 零 run——而
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


# ---------- 「疑似丢了一笔结果推送」标记（本批补，(g)；零 DDL 现算） ----------

# 逐字文案（前端命中即原样渲染，与 OVERDUE_CAPTION 同规）
GAP_CAPTION = "疑似丢失一笔结果推送（回归 K 序列已中断，待 offline 补推或人工核查）"


async def _result_gap_suspected(
    session: AsyncSession, cluster: ErrorCluster, links: list[ErrorCaseLink]
) -> bool:
    """本簇**现行 pending link** 是否存在「缺行中断」现场（派生布尔，不落列、不设时钟）。

    为什么要有这个可见面：判定内核遇到 gap 时（§8.7 `prev_terminal_version` 本地无记录 =
    上一笔结果推送 fire-and-forget 三次全败）结论是「**不迁移、不累计 K**」，簇静默停在
    claim——**除了日志没有任何可见面**：offline 侧以为推过了、viewer 只看得到「一直待回归」，
    这是本刀（判定从轮询改一次性事件推送）新引入的失效模式，必须可观测。

    判据本体在 `verify.link_gap_version`（与 `judge_link` 内联 gap 分支同源），本函数只做
    遍历与短路，**不在此另抄判据**。只扫 pending link：终态 link 的判定已收口，再报 gap 无
    处置意义（且终态 link 的 K 序列不再演进）。
    """
    for lk in links:
        if lk.verify_status != "pending":
            continue
        if await link_gap_version(session, cluster, lk) is not None:
            return True
    return False


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
    # 现行 link 一次取：序列化摘要给页面、ORM 对象喂判定内核（勿分两次查同一批行）
    reps = await _cluster_link_reps(session, [c.id for c in clusters])
    link_map = await _serialize_links(session, reps)
    # K 进度：详情页与列表页共用前端 `taskState`（`mine` 决定「需要你」行与红字 `.need`），
    # 两页必须拿到同一个数 —— 只给详情会让同一簇在列表说「还等着人修」、在详情说「没事」。
    # 开销随「页内**待回归**簇数」走而非恒定 N：link_k_progress 对非 pending / 无 case_id /
    # 无 link 的行**在查库之前**就返回 None。
    items = []
    for c in clusters:
        it = _cluster_item(c, link_map.get(c.id))
        it["seq"] = await link_k_progress(session, c, reps.get(c.id))
        items.append(it)
    out = {"items": items, "total": total, "page": page, "page_size": page_size}
    logger.debug("backflow clusters 出参: total=%s", total)
    return out


@router.get("/clusters/{cluster_id}")
async def get_cluster_detail(
    user: ViewerUser, session: _Session, cluster_id: int
) -> dict:
    """cluster 详情：元数据 + links + verify 时间线 + conversion 审计 + 已待天数 + 复发观察/挂起批。

    响应 {…cluster 元数据, links[], verify_runs[], conversions[], waiting_days,
    result_overdue（«结果未达»标记，§8.7/§9.3）, result_gap_suspected（缺行中断现场）,
    seq（**现行 link 的 K 进度**，与 claim_k 配对显示「已连续通过 seq/K 次」；不适用时
    null —— 见 link_k_progress docstring 的三种情形）, reentry_observe（claim/fixed 现算
    复发观察，其余态 None）, open_batches[]}。"""
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
    link_case = {lk.id: lk.case_id for lk in links}

    def _excluded_hit(r: VerifyRunRecord) -> bool:
        """本 run 是否**没跑到**本 link 的 case（读面对账标记；v1.23 第 3 刀重派生）。

        原读 offline run 详情的 excluded_case_ids；推送源 raw_json = 载荷原样，不再有该键，
        故按同义重算 = 载荷 cases[] 未含本 link 的 case_id（等价于判定内核判 missing 的现场：
        run 收到了、本 case 缺行）。空 cases[] → True（整个 run 无逐 case 行，本 case 必然未跑）。
        无 cases 键（第 2 刀落的旧行）→ False：旧行语义不可重算，宁缺勿假报。
        """
        cid = link_case.get(r.link_id)
        if not cid:
            return False
        cases = (r.raw_json or {}).get("cases")
        if not isinstance(cases, list):
            return False
        return all(str(c.get("case_id") or "") != str(cid)
                   for c in cases if isinstance(c, dict))

    def _substituted_hit(r: VerifyRunRecord) -> bool:
        """本 run 里本 link 的 case 是否用了**替身输入**（批 54；读面对账标记）。

        与 `_excluded_hit` 同一取材面（本行 `raw_json.cases[]`），但答的是另一个问题：
        前者问「跑到没跑到本 case」，本函数问「跑到的那次用的是不是**现场输入**」。
        两者正交——`excluded_hit=True`（没跑到）与 `input_substituted=True`（跑的是替身）
        可以同时为假而不矛盾，也可以分别单独为真。

        缺行 / 旧格式无 `cases` 键 / 载荷无该字段 → False。这是「没有证据说它替换过」，
        不是「确认用的是现场输入」——与 `_excluded_hit` 的「宁缺勿假报」同一取态：
        未知一律不入标记，绝不让读面把没把握的事说成替换（那会反过来冤枉正常回归）。
        """
        cid = link_case.get(r.link_id)
        if not cid:
            return False
        cases = (r.raw_json or {}).get("cases")
        if not isinstance(cases, list):
            return False
        return any(
            str(c.get("case_id") or "") == str(cid) and bool(c.get("input_substituted"))
            for c in cases if isinstance(c, dict)
        )

    verify_items = [
        {
            "record_id": r.id, "run_id": r.run_id, "bound_version": r.bound_version,
            "case_pass": r.case_pass,
            "run_status": r.run_status, "verified_ts": _iso(r.verified_ts),
            "excluded_hit": _excluded_hit(r),
            "input_substituted": _substituted_hit(r),
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
    gap_suspected = await _result_gap_suspected(session, cluster, links)
    # K 进度（未达 K 的簇此前只显示 run 级 pass，看不到「这簇到哪一步了」）。
    # 只取**最新 link**：页面 taskState 读的就是 item["link"]（= links[0]，按 id 降序），
    # 报别的 link 的进度会让一句话混进两个对象的状态。
    # ⚠️ 必须走 link_k_progress（零副作用），不能走 judge_link —— 本接口每次翻页都调它，
    # 而 judge_link 会对触发记录重入 unclean 批（把人工已 resolve 的批重开）。
    k_seq = await link_k_progress(session, cluster, links[0]) if links else None
    # R-7 可愈性标注：本簇全部 link 的重推次数一次成批取（逐项单查即 N+1）
    counts = await requeue_flow.requeue_counts(session, [lk.id for lk in links])
    link_items = [_link_item(lk, counts.get(lk.id, 0)) for lk in links]
    item = _cluster_item(cluster, link_items[0] if link_items else None)
    item.update({
        "links": link_items,
        "verify_runs": verify_items,
        "conversions": conv_items,
        "waiting_days": waiting_days,
        "result_overdue": overdue,
        "result_gap_suspected": gap_suspected,
        "seq": k_seq,
        "reentry_observe": None if observe is None
        else {**observe, "since_ts": _iso(observe["since_ts"])},
        "open_batches": open_batches,
    })
    logger.debug(
        "backflow cluster 详情 出参: cluster_id=%s links=%s runs=%s overdue=%s gap=%s",
        cluster_id, len(links), len(runs), overdue["kind"] or "-", gap_suspected,
    )
    return item


# ---------- 结果推送接收面（v1.23 第 2 刀，§8.7；evaluator 凭证，不接平台 JWT） ----------

# 孤儿 run 的 link_id 哨兵（trigger_signal_id 缺失或查不到现行 link）
#
# 取值 0 的理由：error_case_link.id 为 BIGINT UNSIGNED AUTO_INCREMENT（models/base.py
# BIGINT_UX），InnoDB 自增从 1 起分配、无符号列不能存负数（strict 模式写 -1 即 DataError），
# 故 0 是唯一「DB 允许写入且永不会被真实 link 占用」的表示；NULL 不可用（列 NOT NULL）。
# ⚠️ **哨兵只用于 `link_id` 一列，不参与幂等**（v1.23 C2-补订正）：本常量曾写「orphan 行落在
# uk_verify_run(link_id, run_id) 上」，据此同一 orphan run 重推会命中 (0, run_id) —— 实测证明
# 该说法**只对「全表第一条 orphan」成立**：0 被所有簇共用，第二条起会命中**别的簇**的行（真机
# 拿到过别人的 run_record_id）。幂等键已改为 uk_verify_run(cluster_id, run_id)，orphan 行照记
# 真实簇 id ⇒ 重推才稳定命中自己那一行。
ORPHAN_LINK_ID = 0


def _split_cases(cases: list[RegressionCaseItem]) -> tuple[list[RegressionCaseItem], int]:
    """case_type 白名单分流（§8.7）：非白名单**丢该行 + 计数，不整体拒单**。

    白名单单一来源 = ack.CASE_TYPES（与 pull 侧「非白名单返空集」同为「不因单行断整批」）。
    """
    kept = [c for c in cases if c.case_type in CASE_TYPES]
    return kept, len(cases) - len(kept)


def _case_pass_of(link: ErrorCaseLink | None, kept: list[RegressionCaseItem]) -> int | None:
    """run 级行的 case_pass：由 link.case_id 命中载荷行派生（无 link/无 case_id/缺行 → NULL）。

    **本列已非判定输入**（v1.23 第 3 刀判定内核切源后，判据从 raw_json.cases[] 现算，见
    verify.judge_link/_x_pf_of，na 与缺行在那里被区分开）——保留写入只为读面对账/人工排查时
    仍有一眼可读的 pass 位，勿再据此判 K。
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
    cur_key) 保证同 cluster 同 case_type 至多一条，v1 只此一种 case_type）。查不到 → 返回
    None = orphan：调用方仍落库留档（记真实 cluster_id），只是不推进任何 link 判定。
    **link 已判出终态的簇重推也走这条**（终态只读 ⇒ 无现行 pending link）——这是正常的
    「重放」而非异常，幂等由 uk_verify_run(cluster_id, run_id) 兜住。
    """
    if trigger_signal_id is None:  # 防御：model 层已必填，正常到不了这里
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
    """结果推送落库 + **同事务判定**（§8.7；幂等键 = uk_verify_run(cluster_id, run_id)）。

    v1.23 第 3 刀：判定内核已切推送源（offline 出站读面与轮询链整删），落库即判——**`flush`
    后、`commit` 前**调用 `judge_link`，判定写入与数据位同一事务。**判定异常 → 降级不回滚**
    （本批补，见下方 try/except 与 rejudge_job）：savepoint 只回退判定写，结果行照常落库、
    响应仍 200 —— 旧架构（轮询 recheck）判失败不影响行已落库，本刀不得低于它。语义边界：
    - 落 verify_run_record 一行（run 级；case_pass 由 link.case_id 命中行派生）+ 一条
      conversion_record（action=regression_result，actor_user_id=NULL = 系统动作）。
    - orphan：仍落库留档（link_id=哨兵 0，防关联断裂丢数据），links_advanced 空、**不调判定**
      （无 link 可判）；conv 照写、**cluster_id 记载荷的 trigger_signal_id**（v1.23 C2-补：
      原先写 NULL，导致「最需要人工对账的现场」在审计面上反而关联不到簇）——审计链要求
      「收到即留痕」，不写就变成静默丢数据。
    - 重复推送（同 cluster_id + run_id 已有行）：duplicated=true，不重复落库、不重复写 conv、
      **不重跑判定**（该 run 的首推已判过；重判只是对全链重放，副作用见 verify.judge_link
      unclean 闸）。**这条在 link 已判出终态的簇上同样成立**（旧键做不到：那时 link_id 已变
      哨兵 0，重推被判成新推送）。
    - links_advanced 语义 = **本次真正发生终态迁移的 link**（passed/failed/superseded 三类，
      判据单一来源 = verify.TERMINAL_OUTCOMES）。**这是相对第 2 刀的收窄**：第 2 刀该字段只表达
      「数据位推进」（落了 run 行即列），现在只有 link 真正离开 pending 才列——offline 的对账读法
      随之升级（收到非空 = 已收敛终态）。
    - cluster 非 `claim` 态不判（数据照落）：`_find_current_link` 的谓词是「pending link」，
      **不等价于**原 recheck 扫描谓词（`cluster.status=='claim'` ∧ pending link）——见下方守卫。
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

    # 幂等查按 **(簇, run)**，与 `uk_verify_run` 同键——**不能按 link_id 查**：link 生命
    # 周期会让同一笔推送落到两个不同的 link_id 上（pending 时=簇 id、终态后=哨兵 0），按
    # link_id 查会把「已判出簇的重推」误判成新推送（本批修，见 models 的 cluster_id 列注释）。
    existing_id = await session.scalar(
        select(VerifyRunRecord.id).where(
            VerifyRunRecord.cluster_id == body.trigger_signal_id,
            VerifyRunRecord.run_id == body.run_id,
        )
    )
    if existing_id is not None:
        # 幂等重放：行已由首次推送落库（orphan 行同样命中）→ 零写
        return {"accepted": True, "duplicated": True, "run_record_id": existing_id,
                "links_advanced": [], "cases_dropped": dropped}

    # 幂等 = 先查后写 + uk_verify_run 兜底：并发同 (簇, run) 双推的窄窗口里后到者会撞唯一键
    # （IntegrityError → 500，零脏写），offline 侧退避重试即命中上面的 duplicated 分支，
    # 不丢数据（fire-and-forget 3 次重试，§8.7）
    record = VerifyRunRecord(
        link_id=link_id,
        cluster_id=body.trigger_signal_id,
        run_id=body.run_id,
        bound_version=body.agent_version,  # = 原 verify_run_record.bound_version
        case_pass=_case_pass_of(link, kept),
        run_status=body.run_status,
        # 载荷**原样**留档：cases[] / agent_latest_version / prev_terminal_version /
        # finished_ts 全在其中——零 DDL 承载 offline 水位字段（§8.7 v1.23 第 2 刀补）
        raw_json=body.model_dump(mode="json"),
    )
    session.add(record)
    session.add(ConversionRecord(
        # orphan 也记载荷声明的簇（不写 NULL）：审计面要能按簇 join 到这笔推送
        cluster_id=body.trigger_signal_id,
        link_id=link_id,
        action="regression_result",
        detail=_conv_detail(body, link, kept=len(kept), dropped=dropped),
        actor_user_id=None,  # 系统动作（offline 推送），非人工
    ))
    await session.flush()  # 回填自增 id 供响应；commit 由端点层显式做（auth/pull 先例）

    # ---- 落库即判（v1.23 第 3 刀；与上面落库同一事务）----
    # **必须补 cluster.status == 'claim' 守卫**：`_find_current_link` 只按「link.verify_status
    # = pending」查——那是**读面**的现行定义，不等于判定的**可判谓词**。cluster 可以非 claim
    # 却仍有 pending link：needs_review 的 resolve → reopen 之间、TTL 认领失效、admin 手工
    # invalidate 的过渡窗口都会留下 pending link（且 uk_link_current 下至多一条）。旧 recheck
    # 是靠扫描谓词（cluster.status=='claim' ∧ pending link）挡住的，切源后没有那层扫描，**不补
    # 这个判断就会对非 claim 簇调用判定链 → 对已 fixed/needs_review 簇写终态迁移**（越权改状态，
    # CAS 守卫只能兜住并发、兜不住语义错）。不满足即静默跳过：数据仍落库留档，等簇回到 claim
    # 后由后续推送重新驱动判定（判定本身是对全链重放，不依赖触发时机）。
    advanced: list[int] = []
    if link is not None:
        cluster = await session.get(ErrorCluster, link.cluster_id)
        if cluster is not None and cluster.status == "open":
            try:
                # savepoint 隔离判定副作用（本批偏离规格的**加严**，非放宽）：判定链是**边判
                # 边写**（link/cluster CAS + conv），可能在链的后半段才抛异常 —— 裸调用时那些
                # 半笔写会随本次 commit 一起落库（半态：link 已迁移却无终态判定/无 auto_fixed
                # conv），且 link 一旦离开 pending 就再也补判不到。savepoint 让判定的写**全进
                # 全出**，半笔自动回退、link 保持 pending 交 rejudge 重放（同 claim_ttl_job
                # savepoint 先例）。
                # 注意别把理由写成「异常会污染事务致 commit 失败」——**实测不成立**（MySQL 的
                # 语句级报错不作废整个事务，裸调用时这里照样 200 且行照落，探针 S-18 第一版
                # 正是这么假绿的）：savepoint 挡的是**半态落库**，不是提交失败。
                async with session.begin_nested():
                    summary = await judge_link(session, cluster=cluster, link=link)
            except Exception:
                # 为什么**降级**而非回滚/500：本刀把判定搬进落库同事务后，判定抛异常会让
                # **一笔已到达的真实结果**整单 500 —— offline fire-and-forget 三次重试全败
                # 即永久丢数据。第 2 刀架构下 recheck 判失败不影响行已落库，本刀不得低于它。
                # 降级不产生半态：判定是对全链的**幂等重放**（数据源 = 已落库行集），跳过只是
                # 「这一轮没判」，行已落库、link 仍 pending，由 rejudge_job 兜底补判。
                # 回滚则相反：它把「数据先保住」与「状态立刻迁移」捆绑，牺牲的还是数据 ——
                # 状态可补判，丢掉的推送不可补（online 无法向 offline 索要）。
                logger.exception(
                    "回归结果落库后判定异常（降级跳过，待 rejudge 兜底）: "
                    "link_id=%s cluster_id=%s run_id=%s",
                    link_id, link.cluster_id, body.run_id,
                )
            else:
                if summary.get("outcome") in TERMINAL_OUTCOMES:
                    advanced.append(link_id)
                if summary.get("outcome") == "gap":
                    # 推送丢失是对账事件（offline fire-and-forget 三次全败），留痕不静默
                    logger.warning(
                        "结果推送缺行中断: cluster=%s link=%s gap_version=%s",
                        link.cluster_id, link_id, summary.get("gap_version"),
                    )
    return {"accepted": True, "duplicated": False, "run_record_id": record.id,
            "links_advanced": advanced,
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
        " trigger_signal_id=%s cases=%s latest_version=%s prev_terminal=%s finished_ts=%s",
        body.agent, body.agent_version, body.run_id, body.run_status,
        body.trigger_signal_id, len(body.cases),
        body.agent_latest_version, body.prev_terminal_version, body.finished_ts,
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
