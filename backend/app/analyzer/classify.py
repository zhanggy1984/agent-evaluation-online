"""analyzer classify：L1/L2 分层判定（detail §2.5 值域 + §4.3/§6.1 判定规则）。

纯函数层——不触碰 DB；字典侧事实经 `AgentContext` 注入、判前态经 `TraceFacts` 传入。
judge_scan_job（worker）与 consumer root-late 补判共用本层。

判定语义（§6.1 step1~5，逐条落点）：
1. **白名单门**：agent 存在 ∧ `backflow_allow=1` ∧ `enable=1` ∧ per-agent dict_config
   `backflow_enabled`（缺键回退开启）。cc 双保险 = agent.backflow_allow=0（seed D18）+
   backflow_enabled=false，任一关即不产候选，judged 仍置 1（§4.3 判 false 不再重复判定）。
2. **llm_fact_ok 重算**：累积列=1，**或** err_summary 含 llm_* error（§6.1 step2 动态事实证据
   是 "llm_call 子节点 或 llm_* error"；consumer state.py 只在 node=llm_call 置位，非 llm_call
   节点的 llm_* error 会漏，故判侧须重算双保险）。
3. **L1**：候选 error_type ∈ LLM_ERR_TYPES（7 类透传）。【实现约定·扩展 root 限定】§6.1 step3
   字面写 "request 根事件"，但 §4.3 残 trace "按已有子节点判定" 要求子节点也能产候选——否则残
   trace（root 未达）的纯 LLM 失败（如 llm_call 直接透传 llm_timeout）无层可归漏回流。故 L1
   值域判定放开到 root ∪ 子节点，evidence 记 root/subnode 来源（修订记录 v1.12 回填）。
   **该扩展的范围界定（T-3.10 落地）**：子节点取候选以 `root_status != "ok"` 为前提——请求
   成功返回答时子节点错误已被业务吸收，v1 不回流（§6.1 "兜底吸收现场（request ok + llm_call
   error）不产 L1/L2 候选（L3 二期）"）。本仓原实现未设此门致兜底吸收误回流，T-3.10 修正。
4. **L2**：候选 error_type ∈ L2_ERR_TYPES（root 或子节点）∧（llm_fact ∨ interface 字典
   `interface.llm==1`）——OR 门控（§6.1 step4）。
5. **timeout 事件不带 error_type**（§2.1 schema：仅 status=error 允许 error_type）→ 不产候选
   （P2 error-only；timeout 红显但不回流）。**已知未决歧义（T-3.10 显式标注、本批不触碰）**：
   本条只说 timeout 事件自身不产候选，对"timeout root 的子节点 error 是否参与"沉默；§6.1 step4
   又写 L2 判定用 "request **或**子节点"。故 timeout root 的子节点候选**维持 T-3.10 前的既有
   行为**（仍参与），待真实流量数据再定，勿凭两条互斥原文硬猜。
6. **layer**：任一 L1 候选 → L1（高层优先）；否则任一 L2 → L2；否则 none。同一 error_type
   root+子节点双现 → 单候选（evidence=root、count=root1+子节点 count）。
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

Layer = Literal["L1", "L2", "none"]
Evidence = Literal["root", "subnode"]

# §2.5 L305-314：L1 = LLM 层错误透传 7 类；L2 = 兜底吸收/近 LLM 错误 4 类（P2 error-only 回流值域）
LLM_ERR_TYPES: frozenset[str] = frozenset(
    {
        "llm_timeout",
        "llm_rate_limit",
        "llm_connection",
        "llm_context_exceeded",
        "llm_empty_response",
        "llm_parse_error",
        "llm_other",
    }
)
L2_ERR_TYPES: frozenset[str] = frozenset(
    {"llm_interface_business", "external_non_llm", "db_error", "redis_error"}
)


@dataclass(frozen=True)
class AgentContext:
    """字典侧事实（loader 从 agent / dict_config / interface 表组装注入）。"""

    agent_exists: bool = True
    backflow_allow: bool = True  # agent.backflow_allow==1（布尔语义，TINYINT 0/1）
    agent_enabled: bool = True  # agent.enable==1
    backflow_enabled: bool = True  # per-agent dict_config 'backflow_enabled'，缺键回退开启
    # interface 字典 (agent,interface).llm==1；interface 缺失/行缺 → None（只靠 llm_fact 兜底）
    interface_llm: bool | None = None


@dataclass(frozen=True)
class TraceFacts:
    """判前态（trace_judge_state 判定输入侧事实；loader 从行构造）。"""

    root_ok: bool
    root_status: str | None
    root_error_type: str | None
    interface: str | None
    llm_fact_ok: bool
    err_entries: tuple[dict, ...] = ()  # err_summary.entries: {error_type, error_msg, count}


@dataclass
class ErrorCandidate:
    """单 error_type 回流候选（对应 judgement_json.candidate_error_sets 一项，
    T-3.6 聚类去重键）。"""

    error_type: str
    layer: Layer
    evidence: Evidence  # root=request 根；subnode=子节点（残 trace 无 root 也归此）
    count: int


@dataclass
class JudgeDecision:
    layer: Layer
    gate: dict  # {backflow_allow, agent_enabled, backflow_enabled} 判定快照（归因/审计）
    llm_fact_ok: bool
    root: dict  # {ok, status, error_type}
    candidates: list[ErrorCandidate] = field(default_factory=list)


def effective_llm_fact(facts: TraceFacts) -> bool:
    """§6.1 step2 动态事实重算：累积列 ∨ root/err_summary 任一 llm_* error。

    consumer state.py 只在 node=llm_call 置位累积列；非 llm_call 节点的 llm_* error
    （含 root 自身 error_type 透传）会漏置——故判侧须覆盖 root + entries 三源重算。
    """
    if facts.llm_fact_ok:
        return True
    if facts.root_error_type in LLM_ERR_TYPES:
        return True
    return any(e.get("error_type") in LLM_ERR_TYPES for e in facts.err_entries)


def _layer_for(error_type: str, llm_fact: bool, interface_llm: bool | None) -> Layer | None:
    """单 error_type 值域判定（§6.1 step3/4）：L1 / L2(OR 门) / 不回流。"""
    if error_type in LLM_ERR_TYPES:
        return "L1"
    if error_type in L2_ERR_TYPES and (llm_fact or interface_llm is True):
        return "L2"
    return None


def _collect_candidates(
    facts: TraceFacts, llm_fact: bool, interface_llm: bool | None
) -> list[ErrorCandidate]:
    """候选全集 = {root_error_type} ∪ {err_summary.error_type} 逐个值域判定后归并。

    同一 error_type root+子节点双现 → 单候选：layer 由值域唯一决定（L1/L2 值域互斥）、
    evidence=root 优先、count = root 1 + 子节点 count。

    **兜底吸收门控（T-3.10，§6.1 L826）**：root 终态 ok 时**不取子节点候选**——请求成功
    返回答 = 子节点错误已被业务吸收（v1 不回流，L3 二期）；该 trace 仍可被维度 1 查询、
    其 llm_call error 仍进指标（§2.4 前提）。仅 root 侧候选保留（root ok 时按 §2.1 自带
    error_type 不可能非空，实际等价于不产候选）。
    """
    aggr: dict[str, dict] = {}

    def _consider(error_type: str | None, is_root: bool, add_count: int) -> None:
        if not error_type:
            return
        layer = _layer_for(error_type, llm_fact, interface_llm)
        if layer is None:
            return
        hit = aggr.setdefault(error_type, {"layer": layer, "root": False, "count": 0})
        if is_root:
            hit["root"] = True
        hit["count"] += max(add_count, 1)

    if facts.root_ok and facts.root_error_type:
        _consider(facts.root_error_type, is_root=True, add_count=1)
    # 兜底吸收（T-3.10，§6.1 L826）：request 终态 ok = 子节点错误已被业务吸收，不产候选。
    # 判据只取 root_status —— 刻意不叠加 root_ok：root_status 全仓唯一写点 = consumer/state.py
    # `state.update(root_ok=1, …, root_status=event.status, …)`（root 到达同一条语句同时置位），
    # 故 root_status == "ok" ⟹ root_ok == 1，合取项恒真、可证冗余；留单条件 = 只押「root 终态」
    # 一个语义，不与派生布尔标志的将来定义漂移耦合。
    # 判据不用"root_error_type 为空"——后者会把 timeout root 一并切掉（§6.1 step5 timeout 事件
    # 不带 error_type），属本批未讨论的第二处行为变更，刻意不碰。
    # 残 trace（root_status 恒 NULL，detail §5.1⑩）/ error / timeout 三类行为保持不变。
    if facts.root_status != "ok":
        for e in facts.err_entries:
            _consider(e.get("error_type"), is_root=False, add_count=int(e.get("count") or 1))
    return [
        ErrorCandidate(
            error_type=et,
            layer=a["layer"],
            evidence="root" if a["root"] else "subnode",
            count=a["count"],
        )
        for et, a in aggr.items()
    ]


def _root_dict(facts: TraceFacts) -> dict:
    return {
        "ok": bool(facts.root_ok),
        "status": facts.root_status,
        "error_type": facts.root_error_type,
    }


def decide(facts: TraceFacts, ctx: AgentContext) -> JudgeDecision:
    """完整判定（judge_scan_job 到期行用）：白名单门 → llm_fact → 候选 → layer。"""
    gate = {
        "agent_exists": ctx.agent_exists,
        "backflow_allow": ctx.backflow_allow,
        "agent_enabled": ctx.agent_enabled,
        "backflow_enabled": ctx.backflow_enabled,
    }
    if not (
        ctx.agent_exists
        and ctx.backflow_allow
        and ctx.agent_enabled
        and ctx.backflow_enabled
    ):
        return JudgeDecision(layer="none", gate=gate, llm_fact_ok=effective_llm_fact(facts),
                             root=_root_dict(facts))
    llm_fact = effective_llm_fact(facts)
    candidates = _collect_candidates(facts, llm_fact, ctx.interface_llm)
    layer: Layer
    if any(c.layer == "L1" for c in candidates):
        layer = "L1"
    elif any(c.layer == "L2" for c in candidates):
        layer = "L2"
    else:
        layer = "none"
    return JudgeDecision(layer=layer, gate=gate, llm_fact_ok=llm_fact,
                         root=_root_dict(facts), candidates=candidates)


@dataclass
class RootLateResult:
    """R-21 root-late 单事件补判结果（写 judgement_json.root_late，T-3.6 聚类取数）。"""

    hit: bool
    layer: Layer
    error_type: str | None


def root_late_decision(facts: TraceFacts, ctx: AgentContext) -> RootLateResult:
    """单事件补判（§6.1 R-21）：只把迟到 root 的 error_type 过一次值域表。

    不重跑整 trace、不动 judged、不推翻已判 candidates。白名单门仍须过（agent 期间被
    cc 关停 → 迟到 root 也不产回流候选）。timeout root 无 error_type（§2.1）→ 不产候选。
    llm_fact 用判定期冻结值（facts.llm_fact_ok，root 迟到不改动态事实）。
    """
    if not (
        ctx.agent_exists
        and ctx.backflow_allow
        and ctx.agent_enabled
        and ctx.backflow_enabled
    ):
        return RootLateResult(hit=False, layer="none", error_type=None)
    et = facts.root_error_type
    if not et:
        return RootLateResult(hit=False, layer="none", error_type=None)
    if et in LLM_ERR_TYPES:
        return RootLateResult(hit=True, layer="L1", error_type=et)
    if et in L2_ERR_TYPES and (effective_llm_fact(facts) or ctx.interface_llm is True):
        return RootLateResult(hit=True, layer="L2", error_type=et)
    return RootLateResult(hit=False, layer="none", error_type=None)


def build_judgement_json(
    facts: TraceFacts,
    decision: JudgeDecision,
    *,
    now_ms: int | None = None,
    root_late: dict | None = None,
) -> dict:
    """判定产出落库形状（judgement_json 列；T-3.6 聚类直接消费，字段勿漂移）。"""
    at = datetime.fromtimestamp(
        (now_ms if now_ms is not None else datetime.now(timezone.utc).timestamp() * 1000) / 1000,
        tz=timezone.utc,
    ).isoformat()
    return {
        "version": 1,
        "decided_at": at,
        "layer": decision.layer,
        "gate": decision.gate,
        "llm_fact_ok": decision.llm_fact_ok,
        "root": decision.root,
        "candidate_error_sets": [vars(c) for c in decision.candidates],
        "root_late": root_late,
    }


def root_late_payload(
    result: RootLateResult, root_status: str | None, *, now_ms: int | None = None
) -> dict:
    """R-21 补判落 judgement_json.root_late 的对象（{hit,layer,error_type,status,at}）。"""
    at = datetime.fromtimestamp(
        (now_ms if now_ms is not None else datetime.now(timezone.utc).timestamp() * 1000) / 1000,
        tz=timezone.utc,
    ).isoformat()
    return {
        "hit": result.hit,
        "layer": result.layer,
        "error_type": result.error_type,
        "status": root_status,
        "at": at,
    }
