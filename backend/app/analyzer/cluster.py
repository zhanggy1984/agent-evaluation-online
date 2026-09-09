"""error 聚类归并（detail §6.2，共享归并内核——cluster_job 与 consumer root-late 同用）。

- 去重键 = agent + interface + error_type 原值 + input_hash（§6.2；error_type 不跨类合并，
  与 §7.5 reentry 观察键同源）。input_hash = sha256(normalize(input))，消费 step4 同源落库。
- 生命周期（§6.2 表格，v1.15 修订记录口径 + P2-5 §7.5 reentry 门控）：
  · 同键 ∃ 非终态簇（open/claim/needs_review）→ 只 count+1 / 刷新 latest_ts /
    input_truncated 单 trace 即刷（R-13）/ 快照缺回填（R-18）——不重生成不改代。
  · 同键无非终态簇且允许复发（reopen_after_terminal=True，正常候选）→ 新开簇
    generation = 历史最大代数 + 1（uk_cluster_dedup 含 generation；IntegrityError =
    同代并发双写被唯一索引吸收，E-12，回退 count）。最高代终态簇 = fixed 且带
    fix_version（claim 产物）→ **§7.5 reentry 版本门控（P2-5，B-5 等值+日期前缀序）**：
    新现 agent_version 过门控 → 开簇 gen+1 + 同事务 conv(action=reentry)；门控不过 → 返
    "blocked"（不开簇零落，judged 行仍由调用方置 processed=1，复发可见性 P2-6 前端 ES
    派生）。最高代终态簇为 inactive / fixed 无 fix_version（造数无 claim 语义）→ 无门控
    基础维持无条件开（§6.2 inactive 复发 / S-3 兼容）。
  · 同键无非终态簇但**不**允许复发（reopen_after_terminal=False，root-late 补候选，
    §4.3④/E-28：closed 跳过不翻案）→ skip。root-late 只在从未出现过该键时开簇。
- 残 trace 无 root input → input_hash NULL → 不归并（Fork A 用户拍板：只置 processed）。
- 本模块不含 link 组装（P2-2）；一般**不写 conversion_record**（P2 各动作批次归属）——
  **P2-5 例外**：fixed 后同键复发过门控的开簇随簇同事务写 action=reentry 审计（§7.5
  L951 提示、actor_user_id=None；随 savepoint 回退防孤儿）。
"""
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.error_flow import ConversionRecord, ErrorCluster

NON_TERMINAL_STATUSES: frozenset[str] = frozenset({"open", "claim", "needs_review"})
ERROR_MSG_MAX = 512  # error_cluster.error_msg ≤512（与 err_summary 脱敏口径一致）


def error_msg_for(entries: list, error_type: str) -> str:
    """err_summary entries 匹配 error_type → 代表 msg（最新非空，≤512）；缺省空串。

    entries 源 = trace_judge_state.err_summary_json.entries（consumer._merge_err_entries 聚合，
    同 error_type 保留最新非空 msg）。空串由 build_cluster_row 兜底成 error_type 可读。
    """
    for e in entries:
        if isinstance(e, dict) and e.get("error_type") == error_type:
            msg = e.get("error_msg")
            if isinstance(msg, str) and msg.strip():
                return msg[:ERROR_MSG_MAX]
    return ""


def pick_merge_target(
    clusters: list, *, reopen_after_terminal: bool
) -> tuple[str, object | None, int | None]:
    """同键现存簇序列 → 归并动作（纯函数，单测面）。

    clusters：该键现存 error_cluster 行（ORM 或 SimpleNamespace，须有 status/generation）。
    返回 (动作, 目标簇或 None, 新代数或 None)：
    - ("count", 现行非终态簇, None)    —— 只计数（窗内同键新现 / root-late 同键 open）
    - ("skip", None, None)             —— closed 不翻案（root-late 同键已 fixed/inactive）
    - ("open", None, next_generation)  —— 开新簇（正常复发 / 该键从未出现）
    """
    nt = sorted(
        (c for c in clusters if c.status in NON_TERMINAL_STATUSES),
        key=lambda c: c.generation if c.generation is not None else 1,
    )
    if nt:
        return "count", nt[-1], None  # 同键非终态至多一个（开 gen+1 前提 = 更早全终态）
    if clusters and not reopen_after_terminal:
        return "skip", None, None
    max_gen = max((c.generation or 1) for c in clusters) if clusters else 0
    return "open", None, max_gen + 1


_DATE_PREFIX_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")


def _date_prefix(version: str) -> str | None:
    """截前 10 位日期前缀（YYYY.MM.DD）；非该形态返 None（整体不透明字面量比较）。"""
    prefix = version[:10]
    return prefix if _DATE_PREFIX_RE.fullmatch(prefix) else None


def reentry_gate_allows(agent_version: str | None, fix_version: str | None) -> bool:
    """§7.5 版本门控（B-5 等值+日期前缀序，solution_detail §7.5 blockquote）纯函数。

    比较「新现事件 agent_version vs fixed 簇 fix_version」是否满足放行 reentry 的序：
    - 两侧各截前 10 位日期前缀（YYYY.MM.DD）且均命中 → 日期前缀相等：仅**完全等值**
      放行（同日不等值按"修复上线中/未上线"不过——防 r100<r47 类字典序乱序把同日
      已上线误判为未上线）；前缀不等 → 按日期前缀字符串序（新现日期晚于 fix → 放行，
      构建标签不参与）。
    - 任一侧非该形态（含 None/空）→ 整体按不透明字面量仅做等值比较。
    - agent_version None（无版本证据）→ False（不开 reentry，人工 reopen 兜底）。
    """
    if agent_version is None or fix_version is None:
        return False
    agent = agent_version.strip()
    fix = fix_version.strip()
    if not agent or not fix:
        return False
    agent_p, fix_p = _date_prefix(agent), _date_prefix(fix)
    if agent_p is not None and fix_p is not None:
        if agent_p == fix_p:
            return agent == fix
        return agent_p > fix_p
    return agent == fix


def build_cluster_row(
    *, agent: str, interface: str, layer: str, error_type: str, input_hash: str,
    input_snapshot: str | None, input_truncated: int, error_msg: str,
    trace_id: str, trigger_version: str | None, generation: int, now,
) -> ErrorCluster:
    """新簇 ORM 行装载（代表字段 = 该 trace 判定态；快照缺 input 实文 → NULL → 组装侧只计数）。"""
    return ErrorCluster(
        agent=agent,
        interface=interface,
        layer=layer,
        error_type=error_type,
        input_hash=input_hash,
        input_snapshot=input_snapshot,
        input_truncated=input_truncated,
        error_msg=error_msg[:ERROR_MSG_MAX] or error_type,  # 无 msg 时以 error_type 兜底可读
        first_trace_id=trace_id,
        trigger_version=trigger_version,
        first_ts=now,
        latest_ts=now,
        count=1,
        generation=generation,
        status="open",
    )


async def merge_candidate(
    session: AsyncSession,
    *,
    agent: str,
    interface: str,
    layer: str,
    error_type: str,
    input_hash: str | None,
    input_snapshot: str | None,
    input_truncated: int,
    error_msg: str,
    trace_id: str,
    trigger_version: str | None,
    reopen_after_terminal: bool,
    now,
) -> str:
    """单候选归并（调用方负责事务；input_hash=None → 不归并返回 "skipped"）。

    返回动作：created / counted / skipped / blocked。blocked = §7.5 reentry 门控不过
    （最高代终态簇 fixed 带 fix_version，新现版本未达"等值+日期前缀"序）——不开簇不落库，
    judged 行仍由调用方置 processed=1（P2-5，复发可见性前端 P2-6 ES 派生）。
    同代并发双开被 uk_cluster_dedup 吸收（E-12）：_merge_once 内 savepoint 回退后
    重查转 count；twin 未提交不可见 → 上抛，由外层 loop 整行退避重试（CAS processed=0 可重入）。
    """
    if not input_hash:
        return "skipped"  # Fork A：残 trace 无 root input → 无法去重，只置 processed
    return await _merge_once(
        session,
        agent=agent, interface=interface, layer=layer, error_type=error_type,
        input_hash=input_hash, input_snapshot=input_snapshot,
        input_truncated=input_truncated, error_msg=error_msg, trace_id=trace_id,
        trigger_version=trigger_version, reopen_after_terminal=reopen_after_terminal,
        now=now,
    )


async def _merge_once(
    session: AsyncSession, *, agent, interface, layer, error_type, input_hash,
    input_snapshot, input_truncated, error_msg, trace_id, trigger_version,
    reopen_after_terminal: bool, now,
) -> str:
    """一次归并尝试（无 IntegrityError 吸收，重试由 merge_candidate 控制）。"""
    clusters = list(
        (
            await session.scalars(
                select(ErrorCluster).where(
                    ErrorCluster.agent == agent,
                    ErrorCluster.interface == interface,
                    ErrorCluster.error_type == error_type,
                    ErrorCluster.input_hash == input_hash,
                )
            )
        ).all()
    )
    mode, target, next_gen = pick_merge_target(
        clusters, reopen_after_terminal=reopen_after_terminal
    )
    if mode == "count":
        await _apply_count(session, target, input_snapshot=input_snapshot,
                           input_truncated=input_truncated, now=now)
        return "counted"
    if mode == "skip":
        return "skipped"
    # §7.5 reentry 版本门控（P2-5）：仅当**最高代终态簇 = fixed 且带 fix_version**（claim
    # 产物）才咨询门控——inactive 终态 / fixed 无 fix_version（造数无 claim 语义）无门控
    # 基础 → 维持 P2-1 无条件开（S-3 兼容）。过门控 → 开簇 + 同事务 conv(action=reentry)；
    # 不过 → 返 "blocked" 零落（judged 行仍由调用方置 processed=1，复发可见性 P2-6）。
    latest_terminal = max(clusters, key=lambda c: c.generation or 1) if clusters else None
    gate_fix = (getattr(latest_terminal, "status", None) == "fixed"
                and getattr(latest_terminal, "fix_version", None)) if latest_terminal else None
    is_reentry = False
    if gate_fix:
        if not reentry_gate_allows(trigger_version, gate_fix):
            return "blocked"
        is_reentry = True
    row = build_cluster_row(
        agent=agent, interface=interface, layer=layer, error_type=error_type,
        input_hash=input_hash, input_snapshot=input_snapshot,
        input_truncated=input_truncated, error_msg=error_msg, trace_id=trace_id,
        trigger_version=trigger_version, generation=next_gen, now=now,
    )
    try:
        async with session.begin_nested():  # SAVEPOINT：唯一索引冲突只回退本簇插入
            session.add(row)
            await session.flush()
            if is_reentry:
                # conv 与簇同 savepoint 同进退：E-12 twin 冲突回退时 conv 一并回退不孤儿
                session.add(ConversionRecord(
                    cluster_id=row.id,
                    action="reentry",
                    detail=(f"同键线上再现（agent_version={trigger_version} vs "
                            f"fix_version={gate_fix}）：线上仍复发，claim 或回归失守，"
                            "请核对 fix_version 是否覆盖线上路径"),
                    actor_user_id=None,
                ))
        return "created"
    except IntegrityError:
        # 同代并发双开被 uk_cluster_dedup 吸收（E-12）：savepoint 已回退，重查转 count。
        # twin 事务已提交则此键现行簇立即可见；未提交（不可见）→ 仍无现行 → 再插再冲突 → 上抛。
        clusters = list(
            (
                await session.scalars(
                    select(ErrorCluster).where(
                        ErrorCluster.agent == row.agent,
                        ErrorCluster.interface == row.interface,
                        ErrorCluster.error_type == row.error_type,
                        ErrorCluster.input_hash == row.input_hash,
                    )
                )
            ).all()
        )
        mode, target, _ = pick_merge_target(clusters, reopen_after_terminal=reopen_after_terminal)
        if mode == "count":
            await _apply_count(session, target, input_snapshot=input_snapshot,
                               input_truncated=input_truncated, now=now)
            return "counted"
        raise  # 本 trace 的计数记在 twin 簇上（twin 自会 count 自己那份）；本行外层 CAS 失败自愈


async def _apply_count(session: AsyncSession, cluster, *, input_snapshot: str | None,
                       input_truncated: int, now) -> None:
    """窗内同键新现：count+1 / 刷新 latest_ts / input_truncated 即刷（R-13）/ 快照缺回填。"""
    cluster.count = (cluster.count or 1) + 1
    cluster.latest_ts = now
    cluster.input_truncated = input_truncated
    if not cluster.input_snapshot and input_snapshot:
        cluster.input_snapshot = input_snapshot  # 代表快照缺 input 实文 → 新现补齐（R-18）
