"""step4 trace 累积判定态（detail §4.1 step4 / §4.3 / §4.4，表 trace_judge_state §5.1⑩）。

- 落行触发 = 两类态迁移（§4.1 step4）：root 到达 / 子节点 error 汇入 + llm_call 到达
  （§6.1 step2 llm_fact_ok 动态事实需要 llm_call 证据，即使 status=ok）。log/普通 ok
  子节点不落行。
- **判定不在本步执行**（judge_scan_job 到期判，§6.1）；judged/processed 分离防重放
  （judged=1 后重复到期不重判，聚类消费后置 processed）。D3 只做累积 + 幂等位。
- 多实例安全：同 trace 单 partition 串行（§3.3 partition=1），无并发写同行；
  offset 重放由 uk_trace 唯一行吸收（不重复建行）+ judged 位吸收（不重复判定）。
- R-21 root-late（v1.12 判定就位）：judged=1 后迟到的 root（root_ok 0→1）且 root_status
  ∈{error,timeout} → CAS `root_late_complement` 0→1 置位 + 返回触发信号；主循环在**同一
  事务**调 root_late_complement 做单事件补判（analyzer.classify，写 judgement_json.root_late；
  不改 judged、不重跑整 trace、不推翻已判 candidates）。聚类归并 = T-3.6 消费该字段。
- ttl_until = 最后触发行事件的 ts + 完成窗口 + 宽限（【实现约定】60s + 300s，§4.3/§6.1，
  参数由 dict_config 运行时键注入，D5 启动加载）。
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.classify import (
    AgentContext,
    TraceFacts,
    root_late_decision,
    root_late_payload,
)
from app.consumer.schema import EventModel
from app.core.input_hash import compute_input_hash, snapshot_input
from app.models.agent import Agent, Interface
from app.models.config import DictConfig
from app.models.error_flow import TraceJudgeState

_BACKFLOW_KEY = "backflow_enabled"  # per-agent dict_config 回流总开关键（§10.1）


@dataclass
class StateEffects:
    """本次事件对累积态的作用（供主循环决定是否写行 / 转 T-3.6 补判信号）。"""

    affected: bool = False  # 是否触发累积态落库（root/llm_call/error 到达）
    root_late: bool = False  # root-late 补判触发（judged=1 + root 迟到 + CAS 置位成功）
    created: bool = False  # 本次新建行（残 trace / 首 root）


def _ms_to_utc(ms: int) -> datetime:
    """事件 ts(int ms UTC) → naive UTC datetime（DATETIME(3) 存 UTC，detail §5）。"""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(tzinfo=None)


def _empty_state(agent: str, trace_id: str) -> dict:
    """新建行初始状态（全零 + 空累积）。"""
    return {
        "agent": agent,
        "trace_id": trace_id,
        "root_ok": 0,
        "root_ts": None,
        "interface": None,
        "root_status": None,
        "root_error_type": None,
        "root_input_hash": None,
        "input_snapshot_clean": None,
        "input_truncated": 0,
        "err_summary_json": {"agent_version": None, "entries": []},
        "llm_fact_ok": 0,
        "judged": 0,
        "processed": 0,
        "root_late_complement": 0,
        "ttl_until": None,
    }


def _merge_err_entries(entries: list[dict], error_type: str, error_msg: str | None) -> list[dict]:
    """err_summary 汇入（§4.3）：按 error_type 原值聚合 count（§6.2 去重键同源）。

    error_msg 保留最新非空值。
    """
    for entry in entries:
        if entry["error_type"] == error_type:
            entry["count"] += 1
            if error_msg:
                entry["error_msg"] = error_msg
            return entries
    entries.append({"error_type": error_type, "error_msg": error_msg or "", "count": 1})
    return entries


def merge_trace_state(
    current: dict | None,
    event: EventModel,
    *,
    window_s: int,
    grace_s: int,
) -> tuple[dict, StateEffects]:
    """纯函数：现态 + 事件 → 新态 + 效果。db 无关，可单测。

    current=None 表示该 trace 尚无行；返回 affected=False（log/普通 ok 子节点）时状态不变。
    """
    fx = StateEffects()
    is_root = event.node == "request"
    is_llm = event.node == "llm_call"
    is_err_child = not is_root and event.node != "log" and event.status == "error"
    if not (is_root or is_llm or is_err_child):
        # log / 普通 ok 子节点 / 非 error 子节点：不落行（§4.1 step4 两态迁移）
        return current if current is not None else _empty_state(event.agent, event.trace_id), fx

    fx.affected = True
    state = dict(current) if current else _empty_state(event.agent, event.trace_id)
    ttl = _ms_to_utc(event.ts) + timedelta(seconds=window_s + grace_s)

    if is_root:
        fx.created = current is None
        # root 到达：置 root 全字段 + 落明文快照/截断标（R-18）+ 补判 CAS（R-21）。
        # 已判定（judged=1）且 root 缺席 = root-late 前提；root 在场则为重放不入。
        was_judged_without_root = (
            current is not None and bool(current["judged"]) and not current["root_ok"]
        )
        state.update(
            root_ok=1,
            root_ts=_ms_to_utc(event.ts),
            interface=event.interface,
            root_status=event.status,
            root_error_type=event.error_type,
        )
        # 快照与 hash 只在 root 首次带 input 时算；input 为空（null）→ 无 input 现场不产 hash
        if event.input is not None:
            clean, truncated = snapshot_input(event.input)
            state.update(input_snapshot_clean=clean, input_truncated=truncated)
            state["root_input_hash"] = compute_input_hash(event.input)
        # root-late：已判过（judged=1）且 root 迟到 → CAS 补判位，不重跑不推翻
        if was_judged_without_root and event.status in ("error", "timeout"):
            if not state["root_late_complement"]:
                state["root_late_complement"] = 1
                fx.root_late = True
    else:
        fx.created = current is None
        if bool(state["judged"]):
            # 已判定（judged=1）后迟到的子节点：累积已冻结（判定期快照已成型，§4.4 judged 位
            # 防重放）→ 不改动不写行不续窗；迟到 root 由 is_root 的 R-21 CAS 单独处理。
            return state, StateEffects()
        # 缺口 A（v1.12）回填：残 trace（root 未达）首个落行子节点把 request interface 补上。
        # 同 trace 顶层 interface 同值（§2.1 interface 为请求级字段）；root 先到则已被 is_root
        # 分支写死。L2「接口字典 llm=true」判定与后续 cluster 键（agent+interface+…）依赖行级
        # interface，缺行则残 trace 无对象可查。
        if state["interface"] is None and event.interface:
            state["interface"] = event.interface
        # 子节点累积：llm_fact_ok（llm_call 动态事实，§6.1 step2）/ error 汇入 err_summary
        if is_llm:
            state["llm_fact_ok"] = 1
        if is_err_child:
            summary = state["err_summary_json"]
            summary["agent_version"] = event.agent_version
            summary["entries"] = _merge_err_entries(
                summary["entries"], event.error_type, event.error_msg
            )
            state["err_summary_json"] = summary
    # 正常（未判定）路径：完成窗口随触发行事件顺延；已判定行冻结（生命周期归 T-3.6 清理）
    if not bool(state["judged"]):
        state["ttl_until"] = ttl
    return state, fx


async def _get_row(session: AsyncSession, event: EventModel) -> TraceJudgeState | None:
    return await session.scalar(
        select(TraceJudgeState).where(
            TraceJudgeState.agent == event.agent, TraceJudgeState.trace_id == event.trace_id
        )
    )


async def _state_to_row(state: dict) -> TraceJudgeState:
    """state dict → ORM 行（JSON/时间列原样由 ORM 转换）。"""
    return TraceJudgeState(
        agent=state["agent"],
        trace_id=state["trace_id"],
        root_ok=state["root_ok"],
        root_ts=state["root_ts"],
        interface=state["interface"],
        root_status=state["root_status"],
        root_error_type=state["root_error_type"],
        root_input_hash=state["root_input_hash"],
        input_snapshot_clean=state["input_snapshot_clean"],
        input_truncated=state["input_truncated"],
        err_summary_json=state["err_summary_json"],
        llm_fact_ok=state["llm_fact_ok"],
        judged=state["judged"],
        processed=state["processed"],
        root_late_complement=state["root_late_complement"],
        ttl_until=state["ttl_until"],
    )


async def apply_event(
    session: AsyncSession,
    event: EventModel,
    *,
    window_s: int,
    grace_s: int,
) -> StateEffects:
    """单事件累积落库（§4.1 step4 执行方）。

    读现态 → merge → 写。写失败（MySQL 不可用）由调用方**不提交 offset** + 退避重试
    （禁止"丢弃并提交"：丢判定态 = 该 trace 永不回流且 offset 已推进，§14.2）。
    """
    row = await _get_row(session, event)
    current = _row_to_dict(row) if row else None
    next_state, fx = merge_trace_state(current, event, window_s=window_s, grace_s=grace_s)
    if not fx.affected:
        return fx
    if row is None:
        session.add(await _state_to_row(next_state))
    else:
        for key, value in next_state.items():
            setattr(row, key, value)
    await session.flush()
    return fx


def _row_to_dict(row: TraceJudgeState) -> dict:
    """ORM 行 → merge 输入 dict（标量字段；err_summary_json 结构已 dict）。"""
    return {
        "agent": row.agent,
        "trace_id": row.trace_id,
        "root_ok": row.root_ok,
        "root_ts": row.root_ts,
        "interface": row.interface,
        "root_status": row.root_status,
        "root_error_type": row.root_error_type,
        "root_input_hash": row.root_input_hash,
        "input_snapshot_clean": row.input_snapshot_clean,
        "input_truncated": row.input_truncated,
        "err_summary_json": row.err_summary_json,
        "llm_fact_ok": row.llm_fact_ok,
        "judged": row.judged,
        "processed": row.processed,
        "root_late_complement": row.root_late_complement,
        "ttl_until": row.ttl_until,
    }


async def root_late_complement(session: AsyncSession, event: EventModel) -> None:
    """R-21 补判执行（apply_event CAS 置位后、同一事务 commit 前由主循环调用）。

    只把迟到 root 的 error_type 过一次值域表（analyzer.classify.root_late_decision）并写
    `judgement_json.root_late`；不改 judged、不重跑整 trace、不推翻已判 candidates。
    root_late 对象 = T-3.6 聚类归并取数源。幂等：`root_late_complement` 位=1 才进
    （重放时 apply_event 的 CAS 返回 False 不触发本函数，不会重复写）。
    """
    row = await _get_row(session, event)
    if row is None or not (bool(row.judged) and bool(row.root_late_complement)):
        return
    agent_row = await session.scalar(select(Agent).where(Agent.name == event.agent))
    backflow_enabled = True  # per-agent dict_config 缺键回退开启
    interface_llm: bool | None = None
    if agent_row is not None:
        flag = await session.scalar(
            select(DictConfig.config_value).where(
                DictConfig.agent_id == agent_row.id,
                DictConfig.config_key == _BACKFLOW_KEY,
            )
        )
        if flag is not None:
            backflow_enabled = bool(flag)
        hit = await session.scalar(
            select(Interface.id).where(
                Interface.agent_id == agent_row.id,
                Interface.interface == event.interface,
                Interface.llm == 1,
            )
        )
        interface_llm = hit is not None
    facts = TraceFacts(
        root_ok=True,
        root_status=row.root_status,
        root_error_type=row.root_error_type,
        interface=row.interface,
        llm_fact_ok=bool(row.llm_fact_ok),
    )
    ctx = AgentContext(
        agent_exists=agent_row is not None,
        backflow_allow=bool(agent_row.backflow_allow) if agent_row else False,
        agent_enabled=bool(agent_row.enable) if agent_row else False,
        backflow_enabled=backflow_enabled,
        interface_llm=interface_llm,
    )
    result = root_late_decision(facts, ctx)
    jj = dict(row.judgement_json) if isinstance(row.judgement_json, dict) else {}
    jj["root_late"] = root_late_payload(result, row.root_status)
    row.judgement_json = jj
