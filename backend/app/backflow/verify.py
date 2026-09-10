"""回查 verify 判定内核（detail §7.6 v1.5 R-2 纯净判据 / v1.7 R-19 / R-10 / R-15 / R-16 /
R-17，P2-4 T-3.4 E-7；v1.23 第 3 刀判定内核切推送源）。

三件套：
1. error_type 影响域归类（字面量对齐 executor 真值）——run 内任一「环境级」na 行污染该
   claimed case 的 pass 判据（③ unclean_run 走批）；「case 级」na 不牵连他 case（② 可判）。
   无标注的新 error_type 默认从严 = 环境级（R-19，宁慢勿假 fixed）。
2. 纯函数：`route_verdict` 产单版判定映射 ①~⑤ + R-10/R-15 优先级；`decide_k` 做 K 折叠 =
   相邻纯净 pass 才递增（R-17 防跨缺版假连续；unclean/missing 断链不清零，seq 保留），
   k_seq ≥ claim_k → passed 终值。DB 无关，可直测。
3. `judge_link` 集成（async）：**数据源 = 本 link 的 `verify_run_record` 行集**（cutt 2 起
   offline 终态后主动推结果，落库即判，见 `api/backflow.record_regression_result`），
   **不再有 offline 读面**（v1.23 第 3 刀删 `core/offline_client` + `worker/recheck_job`）。
   逐版判定信息全部从行内 `raw_json`（载荷原样留档）重派生：`cases[]` 定 x_pf/环境级 na
   明细/缺测诊断、`agent_latest_version` 定发版水位、`prev_terminal_version` 定缺行中断。
   已收结果按 bound_version 升序 walk（同版多 run 取**最后推送**一条），K 折叠到终态即
   收敛迁移（复用 claim 侧 `_apply_*` CAS），调用方单事务 commit（推送与判定同事务）。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backflow import claim as claim_flow
from app.core.log import get_logger
from app.models.error_flow import ErrorCaseLink, ErrorCluster, VerifyRunRecord

logger = get_logger("app.backflow.verify")

# ---- error_type 影响域归类（R-19 字面量表；与 executor 真值对齐，勿擅改） ----
# 环境级：牵连同 run 内其它 case 判定 → run 不纯净
ENV_LEVEL_ERROR_TYPES = frozenset({
    "circuit_open", "interface_disabled", "scheduler_unexecuted",
    "http_client_error", "pool_error",
})
# case 级：仅本 case 行问题，不牵连他 case pass 可判
CASE_LEVEL_ERROR_TYPES = frozenset({
    "timeout", "connect_error", "sse_parse_error", "http_error", "no_done",
    "body_too_large", "no_usage", "contract_error", "missing_assertion",
    "assertion_shape",
})

# 载荷 raw_json 保留键（判定重派生的唯一数据源；推送源零 DDL 承载）
_RAW_CASES = "cases"                    # 逐 case 原始行（pass_fail + error_type 原值）
_RAW_LATEST = "agent_latest_version"    # offline 已有终态 run 的最大版本（发版水位）
_RAW_PREV_TERMINAL = "prev_terminal_version"  # 本 run 之前该 agent 最近一个终态 run 的版本


# 归一化比较：版本语义号点分转数值元组排序（非数字段按 0，仅判序用）
def _ver_key(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for p in str(value).lstrip("vV").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def classify_error_type(error_type: str | None) -> str:
    """error_type 影响域：case 级字面量 → 'case'；其余（含环境级 5 + 未知新增）→ 'env'。
    R-19 无标注默认从严 = 环境级，宁拖一轮人工也别假 fixed。"""
    if error_type in CASE_LEVEL_ERROR_TYPES:
        return "case"
    return "env"


def env_na_types(na_error_types) -> list[str]:
    """run 内 na error_type 明细 → 环境级子集（升序，纯净判据输入）。"""
    items = na_error_types or []
    if not isinstance(items, (list, tuple, set)):
        items = [items]
    return sorted(e for e in items if classify_error_type(e) == "env")


def route_verdict(*, x_pf: str, run_env_na=(), input_truncated: bool = False) -> dict:
    """单版判定（纯函数，DB 无关）。

    x_pf = case 行判定 ∈ {pass, fail, na, missing}；run_env_na = run 内环境级 na error_type
    列表（env_na_types 产物）。映射（§7.6 v1.5 R-2 ①②③④⑤）：
    - fail → reopen（回归失败，K 清零）
    - na → needs_review(reason=na)（cluster 级单点，不牵连批）
    - pass：input_truncated → needs_review(input_truncated)（R-10 降级 + R-15 双通道优先，
      截断证据强于同 run 环境级 na，单条不入批）；run 有环境级 na → unclean_run（走批载体、
      不计 K 不清零）；纯净 → count_k（可判版计 K）
    - missing（run 在但 case 缺行）→ missing（R-16 不自动 reopen/needs_review/计 K）
    """
    if x_pf == "missing":
        return {"action": "missing"}
    if x_pf == "fail":
        return {"action": "reopen"}
    if x_pf == "na":
        return {"action": "needs_review", "reason": "na"}
    # pass 分支
    if input_truncated:
        return {"action": "needs_review", "reason": "input_truncated"}
    if env_na_types(run_env_na):
        return {"action": "unclean_run"}
    return {"action": "count_k"}


def decide_k(seq: int, prev_pure: bool, decision: dict, claim_k: int):
    """K 序列折叠（纯函数）。返回 (seq, prev_pure, terminal|None)。

    - count_k：前一 walked 版本也纯净(pure pass) → seq+1；断链后首个纯净 pass → seq=1
      （R-17 相邻纯净语义，防跨缺版累计）。seq ≥ claim_k → terminal passed。
    - unclean_run / missing：断链不清零（prev_pure=False，seq 保留原值）。
    - reopen / needs_review → terminal（reason 透传），调用方停扫做收敛迁移。
    """
    action = decision["action"]
    if action == "count_k":
        seq = seq + 1 if prev_pure else 1
        if seq >= claim_k:
            return seq, True, {"outcome": "passed", "seq": seq}
        return seq, True, None
    if action in ("unclean_run", "missing"):
        return seq, False, None
    if action == "reopen":
        return seq, False, {"outcome": "reopened"}
    return seq, False, {"outcome": "needs_review",
                        "reason": decision.get("reason") or "na"}


# ---- 载荷 raw_json 重派生（推送源无 offline 读面，判定信息全部从留档载荷现算） ----


def _raw_of(rec: VerifyRunRecord) -> dict:
    raw = rec.raw_json
    return raw if isinstance(raw, dict) else {}


def _cases_of(rec: VerifyRunRecord) -> list[dict]:
    """载荷逐 case 原始行；缺失/类型不符 → 空表（等价「本 run 无任何 case 行」）。"""
    cases = _raw_of(rec).get(_RAW_CASES)
    return [c for c in cases if isinstance(c, dict)] if isinstance(cases, list) else []


def _case_row_of(cases: list[dict], case_id: str) -> dict | None:
    """cases[] 定位本 claimed case 行；**未命中即 None**（缺失判据）。

    为什么不复用旧 `_find_case_row`：它的 `rows[0] if rows else None` 兜底在旧读面下是安全的
    （`run_results(run_id, case_id=)` 已按 case 过滤，兜底行必然就是本 case），但推送载荷的
    `cases[]` 是**全量**行——直接兜底会把**别的 case 的 pass/fail** 当成本 case 判定（静默错判，
    比 missing 危险得多）。故按 case_id 严格匹配。
    """
    for row in cases:
        if str(row.get("case_id") or "") == str(case_id):
            return row
    return None


def _run_env_na(cases: list[dict]) -> list[str]:
    """run 内环境级 na 明细 = cases[] 中 pass_fail='na' 行的 error_type（环境级子集）。

    原口径读 offline `runs` 读面的 run 级聚合 `na_error_types`；推送源只有逐 case 原始行
    （offline 本就不产结论），故由 online 从原始行现算——**语义等价**（同一份 na 行集合）。
    空 error_type 一并滤掉：`env_na_types` 对 None 从严归 env，混入会让排序 None/str 报错。
    """
    return env_na_types(
        [c.get("error_type") for c in cases
         if c.get("pass_fail") == "na" and c.get("error_type")]
    )


def _x_pf_of(row: dict | None) -> str:
    """case 行 → x_pf 字面量；未知 pass_fail 从严按 na（→ needs_review，安全向）。"""
    if row is None:
        return "missing"
    pf = row.get("pass_fail")
    if pf in ("pass", "fail"):
        return pf
    return "na"


def _cases_key_present(rec: VerifyRunRecord) -> bool:
    """留档载荷是否为**可判格式**（`cases` 键存在且为数组）。

    **老格式行（第 2 刀期 writer 落库）无 `cases` 键**——那时只写列 `case_pass`、raw_json
    不含逐 case 行。此类行**不可判**（既判不了本 case 结果，也判不了 run 内环境级 na），
    调用方必须显式识别并按「保持 pending」处理，**不得判 missing**：missing 的语义是
    「run 到了、本 case 缺行」（R-16 不自动 reopen/needs_review/计 K），把「整份载荷不可判」
    塞进该语义会污染判定内核（将来给 missing 加副作用即误伤），也掩盖真实原因。
    **不做数据迁移**：v1 上线前库内无真实流量，迁移无收益；**若届时线上已有真实 claim
    场景（有老格式行参与 K 序列）则必须先清该批行或补一次 raw 迁移**，否则这些簇会永久
    停在 pending（本函数保证不误判，但也没有别的出口）。
    """
    return isinstance(_raw_of(rec).get(_RAW_CASES), list)


async def _agent_versions(session: AsyncSession, agent: str) -> set[str]:
    """该 agent 的 `verify_run_record` **版本全集**（agent 级事实，供缺行中断判据用）。

    为什么必须是 agent 级而不是本 link 行集：`prev_terminal_version` 描述的是
    「**该 agent** 最近一个终态 run 的版本」——推送丢失同样是 agent 级（offline 一次
    push 失败与哪个 cluster 无关）。用本 link 行集查，会在「同一 agent 多簇并行 claim」时
    把**水位之内但不属本 link** 的正常版本当缺行 → 假 gap（方向安全：只延后推进、不误判
    连续，但会静默拖住 K 累计且无 UI 可见面）。
    防假连续**未被削弱**：v2 推送真丢时全局也无 v2 行 → 仍判 gap。

    两跳 join：record.link_id → link.cluster_id → cluster.agent。
    **orphan 行（`link_id` 哨兵 0）不在集内**——无 link 可 join、归因不到 agent；影响方向
    = 宁判 gap 不误判连续（安全向），且 orphan 本身就该由详情读面对账标记人工处置。
    """
    rows = await session.execute(
        select(VerifyRunRecord.bound_version)
        .join(ErrorCaseLink, ErrorCaseLink.id == VerifyRunRecord.link_id)
        .join(ErrorCluster, ErrorCluster.id == ErrorCaseLink.cluster_id)
        .where(ErrorCluster.agent == agent)
        .distinct()
    )
    return {str(bv) for (bv,) in rows.all() if bv}


# ---- 集成层 judge_link ----

_OUTCOME_MAP = {
    "passed": "fixed_auto",
    "reopened": "reopened",
    "needs_review": "needs_review",
}

# 终态迁移 outcome 全集 = **_OUTCOME_MAP 的值域**（judge_link 返回的是映射后的字面量：
# fixed_auto/reopened/needs_review），不是键（键是内部 outcome passed/reopened/needs_review
# ——若取键会把 "passed" 当终态、真判出的 "fixed_auto" 反而不算，links_advanced 恒空）。
# 只有这三种使 link 离开 pending；写回方据此判 links_advanced，避免另抄一份字符串表抄错。
TERMINAL_OUTCOMES = frozenset(_OUTCOME_MAP.values())


async def judge_link(session: AsyncSession, *, cluster, link) -> dict:
    """单 claim 全周期回查（async 集成层；v1.23 第 3 刀起数据源 = 本 link 已收结果行集）。

    前置：cluster.status == claim ∧ 现行 pending link 承载（case_id 非空）——无 case_id 的
    claim 由 assemble_job 待补 link 后由后续推送再来，不硬报错。调用方负责事务边界：本函数只
    用传进来的 session（推送端点单事务 commit，判定与落库原子）。

    返回汇总：{outcome, reason?, seq?, gap_version?}
    - outcome: fixed_auto / reopened / needs_review / unclean_batch / pending / gap /
      no_progress
    """
    cid = cluster.id
    fv = claim_flow.normalize_fix_version(cluster.fix_version or "")
    case_id = link.case_id if link is not None else None
    if not fv or not case_id:
        return {"outcome": "no_progress", "reason": "缺 fix_version / 现行 pending case_id"}
    if link.verify_status != "pending":
        # E-10 终态只读显式守卫（P2-5）：pending 是唯一可判定态，passed/failed/
        # invalidated/superseded 均不可覆写（迟到 run 不追加不改写，重开另起新 link）。
        # 此守卫把"终态只读"固化为 judge_link 局部不变量，防调用方（推送端点/未来新路径）
        # 直接对终态 link 误触判定链路。
        return {"outcome": "no_progress",
                "reason": "link 非 pending（终态只读，迟到 run 不覆写）"}
    claim_k = int(cluster.claim_k or 2)
    truncated = bool(cluster.input_truncated)
    link_id = link.id

    rec_rows = list((await session.scalars(
        select(VerifyRunRecord)
        .where(VerifyRunRecord.link_id == link_id)
        .order_by(VerifyRunRecord.id)
    )).all())
    if not rec_rows:
        # 无任何已收结果：不是 gap（没有「缺失」的证据），只是本 link 还没收到推送
        return {"outcome": "pending", "seq": 0,
                "reason": "本 link 尚无已收结果（等 offline 首次结果推送）"}
    # 发版水位（原 `fv not in face_versions` 守卫的推送源重建）：offline 已产终态 run 的最大
    # 版本，随载荷单调不减；本 link 全部行取最大 = 最近一次推送的水位。
    latest = max((str(_raw_of(r).get(_RAW_LATEST) or r.bound_version) for r in rec_rows),
                 key=_ver_key)
    if _ver_key(fv) > _ver_key(latest):
        # fix_version 还没被 offline 跑到（水位未达）→ 本轮任何判定都无意义，不推进（R-17
        # 断链起点语义）。为什么不引入「该 (agent,version) 是否首次出现终态 run」这类字段：
        # 它只说「首见」，**没有**「已覆盖到哪个版本」的序关系，判不了水位（该字段本批已从
        # 载荷契约删除——必填却零读取点；水位只由 `agent_latest_version` 承载）。
        return {"outcome": "no_progress",
                "reason": f"fix_version {fv} 未发版（已收结果水位 {latest}，待 offline 跑到）"}

    # 同版多 run：取**最后推送**的一条（id 最大 = 迟到回写的最新真相）。推送源只有终态 run
    # （offline 侧保证），故原 `_pick_run` 的「completed 优先」是死代码——已删。
    by_version: dict[str, VerifyRunRecord] = {}
    for r in rec_rows:  # 已按 id 升序 → 后者覆盖前者
        by_version[str(r.bound_version)] = r
    # 触发本次判定的记录 = 最后一条推送（落库即判；判定本身是对全链重放，见下方 unclean 闸）
    trigger_id = rec_rows[-1].id

    seq = 0
    prev_pure = False
    outcome: dict | None = None
    terminal_ver: str | None = None
    gap_version: str | None = None
    unjudgeable_ver: str | None = None
    unclean_registered = False
    # agent 级版本全集惰性缓存：仅当真的出现「≥ fv 的前序」时才查一次（常见路径零查询）
    seen_versions: set[str] | None = None

    for V in sorted((v for v in by_version if _ver_key(v) >= _ver_key(fv)), key=_ver_key):
        rec = by_version[V]
        raw = _raw_of(rec)
        prev_v = raw.get(_RAW_PREV_TERMINAL)
        if prev_v and _ver_key(str(prev_v)) >= _ver_key(fv):
            # 缺行中断（v1.23 第 3 刀新判据，替代原「枚举 versions 读面缺版」）：本 run 的前
            # 一个终态版本 online 侧**无记录** → 该版结果推送丢失（fire-and-forget 三次全败）。
            # 为什么必须堵：推送源只有单值最大版本，无法枚举中间版本——v2 的推送全丢时 online
            # 只见 v1(pass)、v3(pass) 会误算「连续 2 次纯净 pass」→ 簇被静默误判 fixed。
            # 为什么只看 ≥ fix_version 的前序：claim 锚定 fv，fv 之前的终态 run 是促成本次 claim
            # 的那次失败，**不属本轮 K 序列**，其记录天然不在本 link 上（reopen → 改版重 claim
            # 会换新 link，E-17 现场）——不加该界会把该现场永久钉在 gap，claim 永判不出 fixed。
            # 判据第三修（本批）：`"有行吗"` 由**本 link 行集**改 **agent 级版本全集**（见
            # `_agent_versions` docstring）——prev_terminal_version 本身是 agent 级事实，
            # 用 link 级行集查会在同 agent 多簇并行 claim 时产生假 gap。
            if seen_versions is None:
                seen_versions = await _agent_versions(session, cluster.agent)
            if str(prev_v) not in seen_versions:
                gap_version = str(prev_v)
                break
        if not _cases_key_present(rec):
            # 老格式行（无 cases 键）→ 不可判：保持 pending 等人工/迁移，**不判 missing**（见
            # `_cases_key_present`）。停在首个不可判版本而非跳过它：跳过等于让 v1/v3 变成相邻
            # 纯净 pass，反而制造跨不可判版本的**假连续**（危险向），宁可停。
            unjudgeable_ver = V
            break
        cases = _cases_of(rec)
        row = _case_row_of(cases, case_id)
        run_env = _run_env_na(cases)
        decision = route_verdict(x_pf=_x_pf_of(row), run_env_na=run_env,
                                 input_truncated=truncated)
        if decision["action"] == "unclean_run" and rec.id == trigger_id:
            # 新 run 判定产物：入 unclean 批（uk_batch_agg 幂等追加本 cluster 引用）。
            # 为什么限定触发记录：判定每次都是对全链重放，已入过批的历史行再调一次会**重开
            # 人工已 resolve 的同 key 批**（batches.ensure_unclean_batch 对非 open 批会置回
            # open 并清 resolve 审计）——那不是新污染，是重放副作用。
            from app.backflow import batches
            await batches.ensure_unclean_batch(
                session, run_id=rec.run_id, agent=cluster.agent, bound_version=V,
                error_type=_primary_env_na(run_env),
                cluster_id=cid, link_id=link_id, case_id=case_id,
            )
            unclean_registered = True

        seq, prev_pure, outcome = decide_k(seq, prev_pure, decision, claim_k)
        if outcome is not None:
            terminal_ver = V
            break

    summary: dict = {"seq": seq}
    if outcome is not None:
        await _apply_terminal(session, cluster, outcome, terminal=terminal_ver,
                              truncated=truncated, fv=fv)
        summary["outcome"] = _OUTCOME_MAP[outcome["outcome"]]
        summary["reason"] = outcome.get("reason")
        return summary
    if gap_version is not None:
        return {**summary, "outcome": "gap", "gap_version": gap_version,
                "reason": "上一笔结果推送缺失（prev_terminal_version 本地无记录，"
                          "防跨缺版假连续）"}
    if unjudgeable_ver is not None:
        logger.warning(
            "判定不可判：留档载荷无 cases 键（第 2 刀期老格式行），保持 pending —— "
            "cluster=%s link=%s version=%s", cid, link_id, unjudgeable_ver,
        )
        return {**summary, "outcome": "pending", "unjudgeable_version": unjudgeable_ver,
                "reason": f"载荷无 cases 键（老格式行 version={unjudgeable_ver}）不可判，"
                          f"保持 pending 待人工/迁移（不判 missing）"}
    if unclean_registered:
        return {**summary, "outcome": "unclean_batch",
                "reason": "同 run 环境级 na 污染已入批，cluster 保持 claim 待 resolve/TTL"}
    return {**summary, "outcome": "pending",
            "reason": "本 cycle 未达 K 满/终态，cluster 保持 claim 等后续推送"}


async def link_gap_version(session: AsyncSession, cluster, link) -> str | None:
    """本 link 现行是否处于「缺行中断」现场；是则返回缺失的版本，否则 None。

    用途 = 详情读面派生标记 `result_gap_suspected`（§8.4，零 DDL 现算）的**唯一判据来源**，
    与 `judge_link` 内联的 gap 分支**同源**（同一 `_RAW_PREV_TERMINAL` / 同一「只看 ≥ fv」
    边界 / 同一 `_agent_versions` 全集），不在此另抄一份判据（抄一份就等着两处漂移）。

    与内核的唯一结构差异：内核在第一个终态处 `break`，本函数扫完全部版本。二者**不会分歧**——
    link 仍 pending ⇒ 内核从未判出终态 ⇒ 内核遇到的第一个 gap 即本函数扫出的最小 gap。
    无已收结果行 / 无 fix_version / 无 case_id → None（该三态各有别的可见面，不是「疑似丢推送」）。
    """
    fv = claim_flow.normalize_fix_version(cluster.fix_version or "")
    if not fv or link is None or not link.case_id:
        return None
    rec_rows = list((await session.scalars(
        select(VerifyRunRecord)
        .where(VerifyRunRecord.link_id == link.id)
        .order_by(VerifyRunRecord.id)
    )).all())
    if not rec_rows:
        return None
    by_version: dict[str, VerifyRunRecord] = {}
    for r in rec_rows:
        by_version[str(r.bound_version)] = r  # 同版多 run 取最后推送（与内核同规）
    candidates = [
        str(prev_v)
        for V in sorted((v for v in by_version if _ver_key(v) >= _ver_key(fv)), key=_ver_key)
        if (prev_v := _raw_of(by_version[V]).get(_RAW_PREV_TERMINAL))
        and _ver_key(str(prev_v)) >= _ver_key(fv)
    ]
    if not candidates:
        return None
    seen = await _agent_versions(session, cluster.agent)
    return next((pv for pv in candidates if pv not in seen), None)


async def _apply_terminal(session: AsyncSession, cluster, outcome: dict, *,
                          terminal: str | None, truncated: bool, fv: str) -> None:
    """终态收敛迁移（复用 claim 侧 apply，CAS 由其中 status 守卫兜并发）。"""
    cid = cluster.id
    node = f"version={terminal}" if terminal else "version面"
    if outcome["outcome"] == "passed":
        await claim_flow._mark_pending_links(session, cid, "passed")
        await claim_flow._apply_auto_fixed(
            session, cid, seq_desc=f"{fv}→{terminal} 连续{outcome['seq']}版纯净 pass")
    elif outcome["outcome"] == "reopened":
        await claim_flow._mark_pending_links(session, cid, "failed")
        await claim_flow._apply_verify_reopen(
            session, cid, detail=f"回归 run {node} fail → open（K 清零）")
    else:  # needs_review
        reason = outcome.get("reason") or "na"
        degraded = ("，input_truncated 降级单条"
                    if reason == "input_truncated" and truncated else "")
        note = f"reason={reason}（{node} run 判定产物{degraded}）"
        # 现行 pending link superseded 释放 cur_key：needs_review 停回查，
        # 待 resolve reopen 后 assemble_job 生成新 link（uk_link_current 不占位冲突）
        await claim_flow._mark_pending_links(session, cid, "superseded")
        await claim_flow._apply_needs_review(session, cid, reason=reason, note=note)


def _primary_env_na(na_error_types) -> str:
    """批聚合 error_type = 环境级明细最小字典序（同 run 同 error_type 一条，uk_batch_agg）。"""
    env = env_na_types(na_error_types)
    return env[0] if env else "unclassified_env_na"
