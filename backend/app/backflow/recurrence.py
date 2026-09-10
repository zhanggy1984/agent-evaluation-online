"""blocked/claim 同键复发读面（detail §7.5 / register P2-5「阻断可见性归 P2-6」）。

P2-5 reentry 门控不过的事件在 error_cluster 侧 DB 零落（不建簇不 count 不 conv，
judged 行仍被 cluster_job processed=1 消费、保留至 purge 窗）——fixed/claim cluster
详情的「同键新版本复发 N 次」只能从 trace_judge_state 的现行 judged 事件**现算**
（近 trace_judge_purge_days 保留窗），不新增存储列（P2-5 拍板 + detail v1.3「查 ES」
措辞经核实不可行后改写为 MySQL 现算，见 P2-6 修订记录）。

- 行命中键 = agent + root_input_hash(=cluster.input_hash 同源) + interface 等值 +
  judgement_json.candidate_error_sets[] 任一 error_type == cluster.error_type
  （沿用 cluster_job._candidate_error_sets 提取口径；cluster 归并键不含 layer）。
- mode="fixed"：ts ≥ fixed 锚 且 reentry_gate_allows(version, fix_version) **不过**的
  judged 行（= 被门控零落的 blocked 事件）；fix_version 空 → 无门控基础不展示（None）。
- mode="claim"：ts ≥ claimed_at 全计（claim 非终态，同键事件本就走 count+1 可见，
  此处只补「最新版本」观察视图）。
- 计数/最新版本为**展示语义**，非精确重放：purge 窗内现算、超窗自然回退（caption 标注
  近 N 天保留窗）。查询收窄 (agent, root_input_hash, judged=1) 后 Python 侧过滤——不加
  JSON 谓词，纯函数核可单测注入。表无 (agent, root_input_hash) 复合索引，但保留窗
  (idx_purge) 限表小、本读面 on-demand 单簇详情，零 DDL 前提下可接受。
"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.cluster import reentry_gate_allows
from app.models.error_flow import ConversionRecord, TraceJudgeState

# cluster → fixed 的迁移动作（claim.py auto_fixed / fixed_review）：fixed 锚 = max ts
_FIXED_ACTIONS = ("auto_fixed", "fixed_review")


def _candidate_error_types(judgement: dict | None) -> set[str]:
    """judgement_json.candidate_error_sets → error_type 集合（防脏跳过，层不限：
    cluster 归并键 (agent, interface, error_type, input_hash) 不含 layer，layer 只需合法）。"""
    out: set[str] = set()
    for c in (judgement or {}).get("candidate_error_sets") or []:
        if isinstance(c, dict) and isinstance(c.get("error_type"), str):
            out.add(c["error_type"])
    return out


def _row_dict(row: TraceJudgeState) -> dict:
    """judged 行 → 纯函数核输入（时间锚 = root_ts 优先，缺则 updated_ts 兜底）。"""
    summary = row.err_summary_json if isinstance(row.err_summary_json, dict) else {}
    return {
        "ts": row.root_ts or row.updated_ts,
        "agent": row.agent,
        "interface": row.interface,
        "root_input_hash": row.root_input_hash,
        "judged": int(row.judged or 0),
        "judgement_json": row.judgement_json if isinstance(row.judgement_json, dict) else {},
        "version": summary.get("agent_version"),
    }


def recurrence_rows_py(
    rows: list[dict],
    *,
    cluster_agent: str,
    cluster_interface: str | None,
    cluster_error_type: str,
    cluster_input_hash: str,
    anchor_ts,
    mode: str,
    fix_version: str | None = None,
) -> dict:
    """纯函数过滤核：同键 judged 行中命中复发观察的行数 + 最新 agent_version。

    命中 = agent/root_input_hash/interface/error_type 同键 ∧ ts ≥ anchor_ts。
    - mode="fixed"：额外要求 reentry_gate_allows 不过（= 门控零落的 blocked 行）；
      fix_version 空 → 一律跳过（无门控基础不展示）。
    - mode="claim"：全计（含版本为 None 的行——无法判门控即视为在观察）。
    返回 {count, latest_version}（latest_version = 命中行版本字典序最大，全 None → None）。
    """
    count = 0
    latest_version: str | None = None
    for r in rows:
        if int(r.get("judged") or 0) != 1:
            continue
        if r.get("agent") != cluster_agent or r.get("root_input_hash") != cluster_input_hash:
            continue
        if cluster_interface and r.get("interface") != cluster_interface:
            continue
        if cluster_error_type not in _candidate_error_types(r.get("judgement_json")):
            continue
        ts = r.get("ts")
        if ts is None or anchor_ts is None or ts < anchor_ts:
            continue
        version = r.get("version")
        if mode == "fixed":
            if fix_version is None:
                continue
            # 过门控 = 真 reentry 已另开新簇（gen+1 独立可见），不属本簇 blocked 计数
            if reentry_gate_allows(version, fix_version):
                continue
        count += 1
        if version and (latest_version is None or version > latest_version):
            latest_version = version
    return {"count": count, "latest_version": latest_version}


async def _fixed_anchor(session: AsyncSession, cluster_id: int):
    """fixed 锚 = cluster→fixed 迁移（auto_fixed/fixed_review）的 max ts；无则 None。"""
    ts_list = list((await session.scalars(
        select(ConversionRecord.ts).where(
            ConversionRecord.cluster_id == cluster_id,
            ConversionRecord.action.in_(_FIXED_ACTIONS),
        )
    )).all())
    return max(ts_list) if ts_list else None


async def cluster_reentry_observe(
    session: AsyncSession, cluster: Any
) -> dict | None:
    """detail 读面：cluster ∈ {claim, fixed} 才计算，否则 None。

    返回 {count, latest_version, since_ts, mode}（since_ts = naive UTC datetime，
    响应序列化由 api 层 _iso 统一口径；claim/fixed 无锚（正常不会）→ None）。"""
    mode = "fixed" if cluster.status == "fixed" else "claim"
    if cluster.status not in ("claim", "fixed"):
        return None
    if mode == "fixed" and not cluster.fix_version:
        return None  # 无门控基础（S-3 式 UPDATE fixed 夹具）不展示
    anchor_ts = await _fixed_anchor(session, cluster.id) if mode == "fixed" else cluster.claimed_at
    if anchor_ts is None:
        return None
    rows = list((await session.scalars(
        select(TraceJudgeState).where(
            TraceJudgeState.agent == cluster.agent,
            TraceJudgeState.root_input_hash == cluster.input_hash,
            TraceJudgeState.judged == 1,
        )
    )).all())
    result = recurrence_rows_py(
        [_row_dict(r) for r in rows],
        cluster_agent=cluster.agent,
        cluster_interface=cluster.interface,
        cluster_error_type=cluster.error_type,
        cluster_input_hash=cluster.input_hash,
        anchor_ts=anchor_ts,
        mode=mode,
        fix_version=cluster.fix_version,
    )
    return {**result, "since_ts": anchor_ts, "mode": mode}
