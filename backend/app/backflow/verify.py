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
    # 批 35-A（online 只读化）：needs_review 不再返回 terminal。原实现让它 break 掉 K 序列
    # 循环并迁到 `needs_review` 态，而该态的唯一出口是**人工** resolve —— 全自动下没人来救，
    # 簇永久卡死。并入 unclean 档：不中断、不累计、继续往后看；判定信号改由 judge_link
    # 循环内按「仅触发记录」记一条 conv（同 unclean_batch 的写法），状态机不动。
    return seq, False, None


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
    # 批 35-A：`needs_review` 条目已删 —— 它不再是终态（decide_k 已并入 unclean 档），
    # 留着会让 TERMINAL_OUTCOMES 声称一个永不产生的终态，links_advanced 判据随之失真。
}

# 终态迁移 outcome 全集 = **_OUTCOME_MAP 的值域**（judge_link 返回的是映射后的字面量：
# fixed_auto/reopened/needs_review），不是键（键是内部 outcome passed/reopened/needs_review
# ——若取键会把 "passed" 当终态、真判出的 "fixed_auto" 反而不算，links_advanced 恒空）。
# 只有这三种使 link 离开 pending；写回方据此判 links_advanced，避免另抄一份字符串表抄错。
TERMINAL_OUTCOMES = frozenset(_OUTCOME_MAP.values())


async def _replay_k(session: AsyncSession, *, cluster, link) -> dict:
    """K 序列**全链重放**（判定内核）。**本函数不做任何写操作。**

    存在的理由 = **判据只留一份**：写路径 `judge_link` 与详情读路径 `link_k_progress`
    都从这里取数。在读面另抄一份判定（在 TS 里数 pass 行 / 在 API 层重写循环）就等着
    两处漂移——同 `link_gap_version` 的先例。

    ⚠️ **副作用绝不进本函数**：详情接口每次翻页都会调它，一旦在此写 unclean 批，
    就会把人工已 resolve 的同 key 批重开（代价见 `judge_link` 内 unclean 闸的注释）。
    调用方按返回的 `unclean_hit` / `needs_review` 自行施加副作用。

    前置：`link` 非 None 且 `link.case_id` 非空（调用方判，本函数不重复守）。

    返回：
    - `empty`: 本 link 尚无任何已收结果（此时 seq=0，其余字段全空）
    - `seq`: 相邻版本连续纯净 pass 计数（R-17）
    - `outcome` / `terminal_ver`: decide_k 判出的终态及其版本（None = 本 cycle 无终态）
    - `gap_version` / `unjudgeable_ver`: 两种中断现场（互斥）
    - `unclean_hit`: {version, run_id, error_type}，**仅当触发记录**（最后一条推送）命中
    - `needs_review`: [{version, reason}] 逐条列出（不改状态、不计 K，调用方只打日志）
    """
    claim_k = int(cluster.claim_k or 2)
    truncated = bool(cluster.input_truncated)
    link_id = link.id
    case_id = link.case_id

    rec_rows = list((await session.scalars(
        select(VerifyRunRecord)
        .where(VerifyRunRecord.link_id == link_id)
        .order_by(VerifyRunRecord.id)
    )).all())
    if not rec_rows:
        return {"empty": True, "seq": 0, "outcome": None, "terminal_ver": None,
                "gap_version": None, "unjudgeable_ver": None,
                "unclean_hit": None, "needs_review": []}
    # 批 35-A：原「发版水位」闸整条删除。它的语义是「fix_version 还没被 offline 跑到 → 不判」，
    # 即**等一个人声明的版本**；online 只读化后无人声明版本，等它就等于永不推进。
    # 代价：不再有「排除修复前历史」的能力（见下方循环下界的同名说明）。

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
    unclean_hit: dict | None = None
    needs_review: list[dict] = []
    # agent 级版本全集惰性缓存：仅当真的出现「≥ fv 的前序」时才查一次（常见路径零查询）
    seen_versions: set[str] | None = None

    # 批 35-A：原下界 `_ver_key(v) >= _ver_key(fv)` 已去掉 —— fv 是「本轮 K 序列从哪个版本起算」，
    # 全自动下无人声明该起点，改由**全历史重放**：连续 pass 才累计、任何 fail/unclean 都会把 seq
    # 打回 1（见 decide_k），故无需下界自洽。代价：簇创建前的历史 pass 也会被计入。
    for V in sorted(by_version, key=_ver_key):
        rec = by_version[V]
        raw = _raw_of(rec)
        prev_v = raw.get(_RAW_PREV_TERMINAL)
        if prev_v:
            # 缺行中断（v1.23 第 3 刀新判据，替代原「枚举 versions 读面缺版」）：本 run 的前
            # 一个终态版本 online 侧**无记录** → 该版结果推送丢失（fire-and-forget 三次全败）。
            # 为什么必须堵：推送源只有单值最大版本，无法枚举中间版本——v2 的推送全丢时 online
            # 只见 v1(pass)、v3(pass) 会误算「连续 2 次纯净 pass」→ 簇被静默误判 fixed。
            # 批 35-A：原「只看 ≥ fix_version 的前序」界已随下界一并去掉（无人声明起点）。
            # 现改为对**全部前序版本**查记录 —— 比原来更严：原先 fv 之前的前序不查，是因为
            # 那些 run 不属本轮 K 序列；现在全历史都算，任何缺失都该中断。
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
            # ⇒ 本函数**只记录现场**，写批由 judge_link 执行（读面不得触发，见本函数 docstring）。
            unclean_hit = {"version": V, "run_id": rec.run_id,
                           "error_type": _primary_env_na(run_env)}

        if decision["action"] == "needs_review":
            # 批 35-A：needs_review 不再是状态（唯一出口是人工，全自动下会永久卡死），也不再
            # 打 conv —— conv 是业务流水且判定每次都是**全链幂等重放**，打 conv 会被 rejudge
            # 每 60s 重放刷爆。改记日志：三类 reason（na / input_truncated）信息不丢，且日志
            # 天然容忍重复。状态机不动，本版不累计也不清零（decide_k 已并入 unclean 档）。
            needs_review.append({"version": V, "reason": decision.get("reason") or "na"})

        seq, prev_pure, outcome = decide_k(seq, prev_pure, decision, claim_k)
        if outcome is not None:
            terminal_ver = V
            break

    return {"empty": False, "seq": seq, "outcome": outcome, "terminal_ver": terminal_ver,
            "gap_version": gap_version, "unjudgeable_ver": unjudgeable_ver,
            "unclean_hit": unclean_hit, "needs_review": needs_review}


async def link_k_progress(session: AsyncSession, cluster, link) -> int | None:
    """本 link 的 K 进度 seq（**详情读面专用，零副作用**）；不适用时 None。

    用途 = 详情页显示「回归已连续通过 seq/K 次」——未达 K 的簇此前**看不到任何进度**
    （页面只显示 run 级 pass，与「这簇到哪一步了」是两回事）。

    为什么读路径不能直接调 `judge_link`：内核每次重放都会对**触发记录**重新入 unclean 批，
    而 `batches.ensure_unclean_batch` 对非 open 批会**置回 open 并清 resolve 审计**
    ⇒ 每翻一次页就重开一次人工已 resolve 的批。故这里只调无副作用的 `_replay_k`。

    与内核**同源**、不另抄判据（同 `link_gap_version` 的写法）。

    None 的三种情形各由别的可见面承载，**不是「进度为 0」**：
    无现行 link / link 非 pending（终态只读，K 序列已结束）/ 无 case_id（assemble_job 待补 link）。
    """
    if link is None or link.verify_status != "pending" or not link.case_id:
        return None
    return (await _replay_k(session, cluster=cluster, link=link))["seq"]


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
    case_id = link.case_id if link is not None else None
    if not case_id:
        return {"outcome": "no_progress", "reason": "缺现行 pending case_id"}
    if link.verify_status != "pending":
        # E-10 终态只读显式守卫（P2-5）：pending 是唯一可判定态，passed/failed/
        # invalidated/superseded 均不可覆写（迟到 run 不追加不改写，重开另起新 link）。
        # 此守卫把"终态只读"固化为 judge_link 局部不变量，防调用方（推送端点/未来新路径）
        # 直接对终态 link 误触判定链路。
        return {"outcome": "no_progress",
                "reason": "link 非 pending（终态只读，迟到 run 不覆写）"}
    link_id = link.id
    # 判据全在 _replay_k（本调用**零写**）；本函数只负责「按内核结果施加副作用」。
    # ⚠️ 拆分的顺序差异：原实现在循环内「扫到 unclean 就写批」，现改为「重放完再写」。
    # 二者可观测行为等价——ensure_unclean_batch 只写 NeedsReviewBatch（batches.py:30+），
    # 而重放期唯一的额外读 _agent_versions 只查 verify_run_record（不读该表）
    # ⇒ 写批不会影响重放结果，写到早写晚无差别。
    r = await _replay_k(session, cluster=cluster, link=link)

    for nr in r["needs_review"]:
        logger.warning(
            "判定不可信（needs_review，不迁移状态、不计 K）: "
            "cluster=%s link=%s version=%s reason=%s truncated=%s",
            cid, link_id, nr["version"], nr["reason"], bool(cluster.input_truncated),
        )

    if r["unclean_hit"] is not None:
        # 新 run 判定产物：入 unclean 批（uk_batch_agg 幂等追加本 cluster 引用）。
        # 为什么由内核限定**触发记录**：判定每次都是对全链重放，已入过批的历史行再调一次会
        # **重开人工已 resolve 的同 key 批**（ensure_unclean_batch 对非 open 批会置回 open
        # 并清 resolve 审计）——那不是新污染，是重放副作用。**详情读面因此不得走本路径**
        # （见 _replay_k docstring），它只取 seq、从不写批。
        from app.backflow import batches
        await batches.ensure_unclean_batch(
            session, run_id=r["unclean_hit"]["run_id"], agent=cluster.agent,
            bound_version=r["unclean_hit"]["version"],
            error_type=r["unclean_hit"]["error_type"],
            cluster_id=cid, link_id=link_id, case_id=case_id,
        )

    if r["empty"]:
        # 无任何已收结果：不是 gap（没有「缺失」的证据），只是本 link 还没收到推送
        return {"outcome": "pending", "seq": 0,
                "reason": "本 link 尚无已收结果（等 offline 首次结果推送）"}

    summary: dict = {"seq": r["seq"]}
    if r["outcome"] is not None:
        await _apply_terminal(session, cluster, r["outcome"], terminal=r["terminal_ver"])
        summary["outcome"] = _OUTCOME_MAP[r["outcome"]["outcome"]]
        summary["reason"] = r["outcome"].get("reason")
        return summary
    if r["gap_version"] is not None:
        return {**summary, "outcome": "gap", "gap_version": r["gap_version"],
                "reason": "上一笔结果推送缺失（prev_terminal_version 本地无记录，"
                          "防跨缺版假连续）"}
    if r["unjudgeable_ver"] is not None:
        logger.warning(
            "判定不可判：留档载荷无 cases 键（第 2 刀期老格式行），保持 pending —— "
            "cluster=%s link=%s version=%s", cid, link_id, r["unjudgeable_ver"],
        )
        return {**summary, "outcome": "pending",
                "unjudgeable_version": r["unjudgeable_ver"],
                "reason": f"载荷无 cases 键（老格式行 version={r['unjudgeable_ver']}）不可判，"
                          f"保持 pending 待人工/迁移（不判 missing）"}
    if r["unclean_hit"] is not None:
        return {**summary, "outcome": "unclean_batch",
                "reason": "同 run 环境级 na 污染已入批，cluster 保持 claim 待 resolve/TTL"}
    return {**summary, "outcome": "pending",
            "reason": "本 cycle 未达 K 满/终态，cluster 保持 claim 等后续推送"}


async def link_gap_version(session: AsyncSession, cluster, link) -> str | None:
    """本 link 现行是否处于「缺行中断」现场；是则返回缺失的版本，否则 None。

    用途 = 详情读面派生标记 `result_gap_suspected`（§8.4，零 DDL 现算）的**唯一判据来源**，
    与 `judge_link` 内联的 gap 分支**同源**（同一 `_RAW_PREV_TERMINAL` / 同一「全历史重放、
    **无版本下界**」/ 同一 `_agent_versions` 全集），不在此另抄一份判据（抄一份就等着两处漂移）。

    与内核的唯一结构差异：内核在第一个终态处 `break`，本函数扫完全部版本。二者**不会分歧**——
    link 仍 pending ⇒ 内核从未判出终态 ⇒ 内核遇到的第一个 gap 即本函数扫出的最小 gap。
    无已收结果行 / 无 case_id → None（两态各有别的可见面，不是「疑似丢推送」）。
    """
    # 批 35-A：原 `fv` 及其「只看 ≥ fv」边界随内核一并去掉（本函数 docstring 明写与内核
    # **同源**、不得漂移）—— 内核去掉了下界与水位闸，此处必须同步，否则 result_gap_suspected
    # 会按一个内核已不用的口径报「疑似丢推送」。
    if link is None or not link.case_id:
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
        for V in sorted(by_version, key=_ver_key)
        if (prev_v := _raw_of(by_version[V]).get(_RAW_PREV_TERMINAL))
    ]
    if not candidates:
        return None
    seen = await _agent_versions(session, cluster.agent)
    return next((pv for pv in candidates if pv not in seen), None)


async def _apply_terminal(session: AsyncSession, cluster, outcome: dict, *,
                          terminal: str | None) -> None:
    """终态收敛迁移（复用 claim 侧 apply）。

    批 35-A：`outcome` 只剩 passed / reopened 两种 —— needs_review 已不再是终态（见 decide_k），
    故删去原 else 分支，以及只供它使用的 `fv` / `truncated` 两个参数。
    """
    cid = cluster.id
    node = f"version={terminal}" if terminal else "version面"
    if outcome["outcome"] == "passed":
        await claim_flow._mark_pending_links(session, cid, "passed")
        await claim_flow._apply_auto_fixed(
            session, cid, seq_desc=f"{terminal} 连续{outcome['seq']}版纯净 pass")
    else:  # reopened
        await claim_flow._mark_pending_links(session, cid, "failed")
        await claim_flow._apply_verify_reopen(
            session, cid, detail=f"回归 run {node} fail → open（K 清零）")


def _primary_env_na(na_error_types) -> str:
    """批聚合 error_type = 环境级明细最小字典序（同 run 同 error_type 一条，uk_batch_agg）。"""
    env = env_na_types(na_error_types)
    return env[0] if env else "unclassified_env_na"
