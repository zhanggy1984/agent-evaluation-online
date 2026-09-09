"""回查 verify 判定内核（detail §7.6 v1.5 R-2 纯净判据 / v1.7 R-19 / R-10 / R-15 / R-16 /
R-17，P2-4 T-3.4 E-7）。

三件套：
1. error_type 影响域归类（字面量对齐 executor 真值）——run 内任一「环境级」na 行污染该
   claimed case 的 pass 判据（③ unclean_run 走批）；「case 级」na 不牵连他 case（② 可判）。
   无标注的新 error_type 默认从严 = 环境级（R-19，宁慢勿假 fixed）。
2. 纯函数：`route_verdict` 产单版判定映射 ①~⑤ + R-10/R-15 优先级；`decide_k` 做 K 折叠 =
   相邻纯净 pass 才递增（R-17 防跨缺版假连续；unclean/missing 断链不清零，seq 保留），
   k_seq ≥ claim_k → passed 终值。DB 无关，可直测。
3. `judge_link` 集成（async）：offline 版本读面取 ≥ fix_version 全版本序，要求 fix_version
   在列（缺 fv = 断链起点，判后置版无意义 → 不推进轮询至发版）；逐版取「当前最近可判
   run」；版本有终值 run → 判（缺 case 行 = missing 不牵连）；无终值 run 且无历史行 → gap
   中断（不得 v1(pass)+v3(pass) 假连续）；已有 verify_run_record 行重派生、新 run_id（有
   推进）才拉 results 追加 —— uk_verify_run 幂等、终态只读不覆写。收敛迁移复用 claim 侧
   `_apply_*`（CAS），单事务内完成，由 recheck_job 逐行 commit/rollback。
"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backflow import claim as claim_flow
from app.models.error_flow import VerifyRunRecord

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

# verify_run_record.raw_json 保留键（重派生判定用，终态只读）
_RAW_X_PF = "x_pf"              # pass/fail/na/missing
_RAW_X_ET = "x_error_type"      # case 行 error_type 原值（na 时溯源用）
_RAW_RUN_ENV_NA = "run_env_na"  # run 内环境级 na error_type 列表（纯净判据）
_RAW_EXCLUDED = "excluded_hit"  # R-16 缺行诊断：case ∈ run.excluded_case_ids
_RAW_ROW = "row"                # run_results 该 case 行原样（留档）

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


def env_na_types(na_error_types: Any) -> list[str]:
    """run 内 na error_type 明细 → 环境级子集（升序，纯净判据输入）。"""
    items = na_error_types or []
    if not isinstance(items, (list, tuple, set)):
        items = [items]
    return sorted(e for e in items if classify_error_type(e) == "env")


def route_verdict(*, x_pf: str, run_env_na: Any = (), input_truncated: bool = False) -> dict:
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


# ---- 集成层 judge_link ----


def _version_of(item: Any) -> str:
    """versions 读面 item → 版本串（兼容 {'version': ...} 与裸字符串）。"""
    if isinstance(item, dict):
        return str(item.get("version") or item.get("name") or "")
    return str(item)


def _pick_run(runs: list[dict]) -> dict | None:
    """同 (agent, version) 多 run 取序：优先 completed；无则取列表首个可判终态（§7.6，
    绝不含 running/pending——list_runs 已按终态白名单过滤）。"""
    if not runs:
        return None
    for r in runs:
        if r.get("status") == "completed":
            return r
    return runs[0]


def _find_case_row(rows: list[dict], case_id: str) -> dict | None:
    """run_results rows 定位本 claimed case 行；case_id 缺失时取首行兜底。"""
    for row in rows:
        if str(row.get("case_id", "")) == str(case_id):
            return row
    return rows[0] if rows else None


def _x_pf_of(row: dict | None) -> str:
    """case 行 → x_pf 字面量；未知 pass_fail 从严按 na（→ needs_review，安全向）。"""
    if row is None:
        return "missing"
    pf = row.get("pass_fail")
    if pf in ("pass", "fail"):
        return pf
    return "na"


def _decision_from_row(rec: VerifyRunRecord, truncated: bool) -> dict:
    """重派生已记录版本判定（uk_verify_run 幂等读取路径，不回放 offline）。"""
    raw = rec.raw_json or {}
    x_pf = raw.get(_RAW_X_PF)
    if x_pf is None:  # 兜底：老行只留 case_pass
        cp = rec.case_pass
        x_pf = "pass" if cp == 1 else ("fail" if cp == 0 else "na")
    return route_verdict(x_pf=x_pf, run_env_na=raw.get(_RAW_RUN_ENV_NA) or (),
                         input_truncated=truncated)


def _append_record(session: AsyncSession, *, link_id: int, run_id: str,
                   bound_version: str, run_status: str, row: dict | None,
                   excluded_hit: bool, run_env: list[str]) -> None:
    """追加 verify_run_record（case_pass + raw_json 留档判定所需字段）。"""
    pf = _x_pf_of(row)
    case_pass = 1 if pf == "pass" else (0 if pf == "fail" else None)
    raw = {
        _RAW_X_PF: pf,
        _RAW_X_ET: (row or {}).get("error_type"),
        _RAW_RUN_ENV_NA: run_env,
        _RAW_EXCLUDED: excluded_hit,
    }
    if row is not None:
        raw[_RAW_ROW] = row
    session.add(VerifyRunRecord(
        link_id=link_id, run_id=run_id, bound_version=bound_version,
        case_pass=case_pass, run_status=run_status, raw_json=raw,
    ))


async def judge_link(
    session: AsyncSession, client: Any, *, cluster: Any, link: Any
) -> dict:
    """单 claim 全周期回查（async 集成层）。

    前置：cluster.status == claim ∧ 现行 pending link 承载（case_id 非空）——无 case_id 的
    claim 由 assemble_job 待补 link 后下轮再来，不硬报错。offline 读面异常（OfflineReadError
    / HTTP）向上抛 → recheck_job 逐行 rollback + 记「回查失败待人工」（§16），幂等可重试。

    返回汇总：{outcome, reason?, seq?, gap_version?, appended?}
    - outcome: fixed_auto / reopened / needs_review / unclean_only / pending /
      gap / no_progress
    """
    cid = cluster.id
    fv = claim_flow.normalize_fix_version(cluster.fix_version or "")
    agent = cluster.agent
    case_id = link.case_id if link is not None else None
    if not fv or not case_id:
        return {"outcome": "no_progress", "reason": "缺 fix_version / 现行 pending case_id"}
    claim_k = int(cluster.claim_k or 2)
    truncated = bool(cluster.input_truncated)
    link_id = link.id

    face = await client.agent_versions(agent=agent)
    face_versions = [_version_of(v) for v in face]
    if fv not in face_versions:
        # fix_version 未发版/读面未收录 → 断链起点缺失，判后置版无意义，不推进（R-17）
        reason = f"fix_version {fv} 未在 versions 读面（待发版）"
        return {"outcome": "no_progress", "reason": reason}
    candidates = sorted(
        (v for v in face_versions if _ver_key(v) >= _ver_key(fv)), key=_ver_key
    )

    # 历史行按 bound_version 归组（同版多 run = 迟到失败回写留痕）
    existing: dict[str, list[VerifyRunRecord]] = {}
    rec_rows = (await session.scalars(
        select(VerifyRunRecord).where(VerifyRunRecord.link_id == link_id)
    )).all()
    for r in rec_rows:
        existing.setdefault(r.bound_version, []).append(r)

    seq = 0
    prev_pure = False
    outcome: dict | None = None
    terminal_ver: str | None = None
    gap_version: str | None = None
    appended = 0
    unclean_registered = False

    for V in candidates:
        runs = await client.list_runs(agent=agent, version=V)
        cur = _pick_run(runs)
        if cur is None:
            # 版本无终值 run：无历史行 → 缺行中断（防假连续）；有历史行 → 保留不回归
            if V not in existing:
                gap_version = V
                break
            continue
        run_id = str(cur["run_id"])
        rid_status = cur.get("status") or "completed"
        matched = next((r for r in existing.get(V, []) if r.run_id == run_id), None)

        if matched is not None:
            decision = _decision_from_row(matched, truncated)
        else:
            # 新 run_id（有推进）→ 拉 results 判 + 追加留档
            rows = await client.run_results(run_id, case_id=case_id)
            row = _find_case_row(rows, case_id)
            run_env = env_na_types(cur.get("na_error_types"))
            excluded_hit = case_id in (cur.get("excluded_case_ids") or [])
            _append_record(
                session, link_id=link_id, run_id=run_id, bound_version=V,
                run_status=rid_status, row=row, excluded_hit=excluded_hit,
                run_env=run_env,
            )
            appended += 1
            decision = route_verdict(x_pf=_x_pf_of(row), run_env_na=run_env,
                                     input_truncated=truncated)
            if decision["action"] == "unclean_run":
                # 新 run 判定产物：入 unclean 批（uk_batch_agg 幂等追加本 cluster 引用）
                from app.backflow import batches
                await batches.ensure_unclean_batch(
                    session, run_id=run_id, agent=agent, bound_version=V,
                    error_type=_primary_env_na(cur.get("na_error_types")),
                    cluster_id=cid, link_id=link_id, case_id=case_id,
                )
                unclean_registered = True

        seq, prev_pure, outcome = decide_k(seq, prev_pure, decision, claim_k)
        if outcome is not None:
            terminal_ver = V
            break

    summary: dict = {"seq": seq, "appended": appended}
    if outcome is not None:
        await _apply_terminal(session, cluster, outcome, terminal=terminal_ver,
                              truncated=truncated, fv=fv)
        summary["outcome"] = _OUTCOME_MAP[outcome["outcome"]]
        summary["reason"] = outcome.get("reason")
        return summary
    if gap_version is not None:
        return {**summary, "outcome": "gap",
                "gap_version": gap_version,
                "reason": "版本无终值 run（缺行中断，防跨缺版假连续）"}
    if unclean_registered:
        return {**summary, "outcome": "unclean_batch",
                "reason": "同 run 环境级 na 污染已入批，cluster 保持 claim 待 resolve/TTL"}
    return {**summary, "outcome": "pending",
            "reason": "本 cycle 未达 K 满/终态，cluster 保持 claim 继续轮询"}


_OUTCOME_MAP = {
    "passed": "fixed_auto",
    "reopened": "reopened",
    "needs_review": "needs_review",
}


async def _apply_terminal(session: AsyncSession, cluster: Any, outcome: dict, *,
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


def _primary_env_na(na_error_types: Any) -> str:
    """批聚合 error_type = 环境级明细最小字典序（同 run 同 error_type 一条，uk_batch_agg）。"""
    env = env_na_types(na_error_types)
    return env[0] if env else "unclassified_env_na"
