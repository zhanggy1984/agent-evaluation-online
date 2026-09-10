"""P2-1 聚类归并 DB 壳集成探针（detail §6.2 / T-3.1）。容器内 `docker exec obs-backend` 运行：

    docker exec obs-backend python /app/tests/integration/cluster_probe.py

前置：obs-backend 已 up（同后端 env：DB_HOST=mysql 容器内 alias）；探针自建 async engine。

覆盖 judge/consumer「DB 壳留集成探针」先例下 cluster 的**实库语义**（单测走 fake 无法覆盖的
多行 select / 聚合 max / UPDATE rowcount / 唯一索引）：
  S-1 开新簇：字段逐项（agent/interface/layer/error_type/input_hash/error_msg/first_trace_id/
      trigger_version/first_ts/latest_ts/count/generation/status）+ _merge_row 结尾 processed CAS=1；
  S-2 窗内同键 count+1（不重建不改代）+ R-13 快照缺回填 + input_truncated 刷新；
  S-3 同键 fixed 终态后正常复发 → generation+1 新簇；root-late（reopen=False）同键 closed → skip 不开；
  S-4 Fork A：root_input_hash NULL 行候选不建簇只置 processed；
  S-5 gate 关停（candidate_error_sets 空）行 → 只置 processed；
  S-6 uk_cluster_dedup 唯一约束在库真在（同键同代重复插 → IntegrityError，E-12 防护面）；
  S-7 fixed+fix_version 后同键再现（agent_version 跨日 > fix）→ gen+1 新簇 + 同事务
      conv(action="reentry", actor_user_id=None，P2-5 §7.5 E-9)；原 fixed 簇不动；
  S-8 新现 agent_version 同日不等值（r48 vs fix r47）→ merge_candidate 返 "blocked" 零落
      （不建簇不 conv，防 r100<r47 类字典序乱序）；
  S-9 新现 agent_version 早于 fix 日期 → "blocked" 零落；
  S-10 回归护栏：fixed 无 fix_version（UPDATE 造数，无 claim 语义）与 inactive 终态复发
      → 维持 P2-1 无条件照开 gen+1（无门控基础不咨询、亦不写 reentry conv，S-3 兼容）。
  S-11→ claim_probe C-14（E-10 终态只读显式守卫：本文件无 claim/verify 基建，回查链路在
      claim_probe 侧同构 C-3 基建处验，跨域脚手架不重复落）。
  S-11/S-12/S-13 = T-3.10 兜底吸收门控的**真库端到端三连**（装载侧→判定→落库→归并全链，
  与单测只打纯函数 decide() 互补）。三者构成一组**防假绿对照**：单看 S-11「零建簇」无从
  判断是门控生效还是 gate 关停/装载失败，必须由 S-12/S-13 反证链路确实会建簇。走真实 job
  入口 `run_judge_scan` + `run_cluster_merge`（非手搓 decide）：
  S-11 兜底吸收（request ok + llm_call error）→ judgement_json.layer=none +
      candidate_error_sets=[]，且归并后 processed=1（行被真消费，非跳过）∧ 该 agent 零簇；
  S-12 对照组 root_status=error + root_error_type=llm_timeout → layer=L1 ∧ 建簇 1（证 S-11
      的零簇不是「链路整体不建簇」）；
  S-13 残 trace（root_ok=0/root_status NULL + 子节点 llm_timeout）→ layer=L1 ∧
      evidence=subnode ∧ 建簇 1（证 T-3.10 未把残 trace 分支一并切掉）。
  注：判据 gate 需 agent 存在且放行，故三场景各建一 cp-% 探针 agent 行（enable/backflow_allow
  均 1、无 dict_config 行 → 缺键回退开），否则 gate 关停产 layer=none，S-11 会**假绿**。

隔离：探针 agent 前缀 cp-（≤64 字符），开头按 LIKE cp-% 清理残留（含 agent 行），结尾再清。
退出码全绿 0。
"""
import asyncio
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app")

from sqlalchemy import delete, select, update  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.analyzer.cluster import merge_candidate  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.models.error_flow import (  # noqa: E402
    ConversionRecord,
    ErrorCluster,
    TraceJudgeState,
)
from app.worker.cluster_job import _merge_row, run_cluster_merge  # noqa: E402
from app.worker.judge_scan_job import run_judge_scan  # noqa: E402

FAILURES: list[str] = []
IFACE = "POST /api/probe/{id}"
H1 = "a" * 64  # 固定 64-char 伪 hash（探针隔离，仅要求列宽与等值语义，不验密码学哈希）
NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def check(name: str, ok: bool, detail: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        FAILURES.append(name)


def _summary(agent_version="2026.09.09-r1", msg="provider timeout"):
    return {"agent_version": agent_version,
            "entries": [{"error_type": "llm_timeout", "error_msg": msg, "count": 2}]}


def _jj(layer="L1", error_type="llm_timeout"):
    return {"version": 1, "layer": layer,
            "candidate_error_sets": [{"layer": layer, "error_type": error_type,
                                      "evidence": [], "count": 1}]}


def _probe_row(session, *, agent, trace_id, root_hash=H1, snapshot=None,
               truncated=0, jj=None, err_summary=None, root_ok=1,
               root_status="error", root_error_type="llm_timeout",
               judged=1, ttl_until=None):
    """判定态探针行。默认值 = 既有 10 场景口径（root error + 已判）；S-11~S-13 需传
    `judged=0`（未判 → 进 judge_scan 扫描位）与自定义 root 三态。

    `judged=0` 时 judgement_json 落 NULL——真实未判行即无判定产物，塞默认 _jj() 会让
    「判前本无产物」这一前提失真（S-11 要验的恰是**判后**产物为空）。
    """
    row = TraceJudgeState(
        agent=agent, trace_id=trace_id, root_ok=root_ok, interface=IFACE,
        root_status=root_status, root_error_type=root_error_type,
        root_input_hash=root_hash, input_snapshot_clean=snapshot,
        input_truncated=truncated,
        err_summary_json=err_summary if err_summary is not None else _summary(),
        llm_fact_ok=1, judged=judged, processed=0, root_late_complement=0,
        judgement_json=jj if jj is not None else (_jj() if judged else None),
        ttl_until=ttl_until if ttl_until is not None else NOW,
    )
    session.add(row)
    return row


async def _probe_agent(engine, name: str) -> None:
    """建探针 agent 行（门控放行前提）。enable/backflow_allow 取模型 server_default=1、
    不建 dict_config 行（fetch_backflow_flags 缺键回退开）= 白名单门全开。

    必须真建行：agent 缺失时 `_ctx_for` 返 agent_exists=False → decide 短路 layer=none，
    S-11 的「零候选」会与被验门控无关地成立（假绿），S-12/S-13 则直接失败。
    """
    async with AsyncSession(engine) as s:
        s.add(Agent(name=name, display_name=name))
        await s.commit()


async def _reset(engine) -> None:
    async with AsyncSession(engine) as s:
        await s.execute(delete(TraceJudgeState).where(TraceJudgeState.agent.like("cp-%")))
        # conv 引用 cluster（FK）→ 先删 conv 再删 cluster
        csub = select(ErrorCluster.id).where(ErrorCluster.agent.like("cp-%"))
        await s.execute(delete(ConversionRecord).where(ConversionRecord.cluster_id.in_(csub)))
        await s.execute(delete(ErrorCluster).where(ErrorCluster.agent.like("cp-%")))
        await s.execute(delete(Agent).where(Agent.name.like("cp-%")))
        await s.commit()


async def _clusters(engine, agent: str) -> list:
    async with AsyncSession(engine) as s:
        return list(
            (await s.scalars(
                select(ErrorCluster).where(ErrorCluster.agent == agent)
            )).all()
        )


async def s1_open(engine) -> None:
    print("\n===== S-1 开新簇 + processed CAS =====")
    agent, trace = "cp-open", "cp-open-1"
    async with AsyncSession(engine) as s:
        row = _probe_row(s, agent=agent, trace_id=trace, snapshot=None)
        await s.flush()
        await _merge_row(s, row, now=NOW)  # 内含候选归并 + processed CAS
        await s.commit()
    clusters = await _clusters(engine, agent)
    check("S-1 恰一簇 g1 且 status=open",
          len(clusters) == 1 and clusters[0].generation == 1 and clusters[0].status == "open",
          f"n={len(clusters)}")
    if clusters:
        c = clusters[0]
        check("S-1 字段装载",
              c.agent == agent and c.interface == IFACE and c.layer == "L1"
              and c.error_type == "llm_timeout" and c.input_hash == H1
              and c.count == 1 and c.first_trace_id == trace
              and c.trigger_version == "2026.09.09-r1"
              and c.error_msg == "provider timeout",
              f"agent={c.agent} layer={c.layer} err={c.error_type} msg={c.error_msg}")
        check("S-1 快照缺 input 实文 → NULL（组装侧只计数，E-13 前提）",
              c.input_snapshot is None, f"snapshot={c.input_snapshot!r}")
    async with AsyncSession(engine) as s:
        done = (await s.scalars(
            select(TraceJudgeState).where(
                TraceJudgeState.agent == agent, TraceJudgeState.trace_id == trace
            )
        )).one()
        check("S-1 processed CAS=1", bool(done.processed), f"processed={done.processed}")


async def s2_count_backfill(engine) -> None:
    print("\n===== S-2 窗内同键 count+1 + R-13 快照回填 =====")
    agent = "cp-count"
    async with AsyncSession(engine) as s:
        r1 = _probe_row(s, agent=agent, trace_id="cp-count-1", snapshot=None, truncated=1)
        await s.flush()
        await _merge_row(s, r1, now=NOW)  # created（snapshot None）
        # 同 session 内读（autoflush 保证可见，另开会话看不到未提交簇）
        cid_1 = (await s.scalars(
            select(ErrorCluster).where(ErrorCluster.agent == agent)
        )).one().id
        r2 = _probe_row(s, agent=agent, trace_id="cp-count-2", snapshot="clean input",
                        truncated=0)
        await s.flush()
        await _merge_row(s, r2, now=NOW)  # counted（同键）
        await s.commit()
    clusters = sorted(await _clusters(engine, agent), key=lambda c: c.id)
    check("S-2 同键 count+1 不重建不改代（簇 id 不变、count=2、gen=1）",
          len(clusters) == 1 and clusters[0].id == cid_1
          and clusters[0].count == 2 and clusters[0].generation == 1,
          f"n={len(clusters)} id_same={clusters[0].id == cid_1} count={clusters[0].count}")
    check("S-2 R-13：快照缺回填 + input_truncated 按新现刷新",
          clusters[0].input_snapshot == "clean input" and clusters[0].input_truncated == 0,
          f"snap={clusters[0].input_snapshot!r} trunc={clusters[0].input_truncated}")


async def s3_gen_after_fixed(engine) -> None:
    print("\n===== S-3 fixed 后复发 gen+1 + root-late closed skip =====")
    agent = "cp-gen"
    async with AsyncSession(engine) as s:
        r1 = _probe_row(s, agent=agent, trace_id="cp-gen-1")
        await s.flush()
        await _merge_row(s, r1, now=NOW)
        g1_id = (await s.scalars(
            select(ErrorCluster).where(ErrorCluster.agent == agent)
        )).one().id  # 同 session 读（autoflush），另开会话不可见未提交
        await s.execute(update(ErrorCluster)
                        .where(ErrorCluster.id == g1_id).values(status="fixed"))
        r2 = _probe_row(s, agent=agent, trace_id="cp-gen-2")
        await s.flush()
        await _merge_row(s, r2, now=NOW)  # 同键 closed 后正常复发 → 新开 g2
        await s.commit()
    clusters = sorted(await _clusters(engine, agent), key=lambda c: c.generation)
    check("S-3 closed 后复发新开 generation=2（原簇不动）",
          len(clusters) == 2 and clusters[1].generation == 2 and clusters[1].count == 1
          and clusters[0].generation == 1 and clusters[0].status == "fixed",
          f"n={len(clusters)} gens={[c.generation for c in clusters]}")
    # root-late 同键 closed（现 latest = g2 fixed）→ skip 不开
    async with AsyncSession(engine) as s:
        await s.execute(update(ErrorCluster)
                        .where(ErrorCluster.agent == agent, ErrorCluster.generation == 2)
                        .values(status="fixed"))
        await s.commit()
        action = await merge_candidate(
            s, agent=agent, interface=IFACE, layer="L1", error_type="llm_timeout",
            input_hash=H1, input_snapshot=None, input_truncated=0,
            error_msg="late", trace_id="cp-gen-3", trigger_version=None,
            reopen_after_terminal=False, now=NOW,
        )
        await s.commit()
    check("S-3 §4.3④/E-28：root-late 同键 closed → skip 不开（不翻案）",
          action == "skipped" and len(await _clusters(engine, agent)) == 2,
          f"action={action}")


async def s4_forka_no_hash(engine) -> None:
    print("\n===== S-4 Fork A：无 root input 行只置 processed 不建簇 =====")
    agent, trace = "cp-forka", "cp-forka-1"
    async with AsyncSession(engine) as s:
        row = _probe_row(s, agent=agent, trace_id=trace, root_hash=None)
        await s.flush()
        await _merge_row(s, row, now=NOW)
        await s.commit()
    check("S-4 无候选簇 + processed=1",
          len(await _clusters(engine, agent)) == 0, "不应建簇")
    async with AsyncSession(engine) as s:
        done = (await s.scalars(select(TraceJudgeState).where(
            TraceJudgeState.agent == agent, TraceJudgeState.trace_id == trace))).one()
        check("S-4 processed CAS=1", bool(done.processed), f"processed={done.processed}")


async def s5_gate_closed(engine) -> None:
    print("\n===== S-5 gate 关停（空候选）行只置 processed =====")
    agent, trace = "cp-gate", "cp-gate-1"
    async with AsyncSession(engine) as s:
        row = _probe_row(s, agent=agent, trace_id=trace, jj={
            "version": 1, "layer": "none", "candidate_error_sets": [],
        })
        await s.flush()
        await _merge_row(s, row, now=NOW)
        await s.commit()
    check("S-5 空候选不建簇", len(await _clusters(engine, agent)) == 0, "不应建簇")
    async with AsyncSession(engine) as s:
        done = (await s.scalars(select(TraceJudgeState).where(
            TraceJudgeState.agent == agent, TraceJudgeState.trace_id == trace))).one()
        check("S-5 processed CAS=1", bool(done.processed), f"processed={done.processed}")


async def s6_unique(engine) -> None:
    print("\n===== S-6 uk_cluster_dedup 唯一约束在库（E-12 吸收面） =====")
    agent, trace = "cp-uniq", "cp-uniq-1"
    async with AsyncSession(engine) as s:
        _probe_row(s, agent=agent, trace_id=trace)
        await s.flush()
        await _merge_row(s, (await s.scalars(select(TraceJudgeState).where(
            TraceJudgeState.agent == agent))).one(), now=NOW)
        await s.commit()
    dup = ErrorCluster(
        agent=agent, interface=IFACE, layer="L1", error_type="llm_timeout",
        input_hash=H1, input_snapshot=None, input_truncated=0,
        error_msg="dup", first_trace_id=trace, trigger_version=None,
        first_ts=NOW, latest_ts=NOW, count=1, generation=1, status="open",
    )
    got_ie = False
    async with AsyncSession(engine) as s:
        s.add(dup)
        try:
            await s.flush()
            await s.commit()
        except IntegrityError:
            got_ie = True
            await s.rollback()
    check("S-6 同键同代重复插被 uk_cluster_dedup 拒绝（IntegrityError）",
          got_ie, f"got_integrity_error={got_ie}")


async def _conv_for(engine, cluster_id: int) -> list:
    async with AsyncSession(engine) as s:
        return list((await s.scalars(
            select(ConversionRecord).where(ConversionRecord.cluster_id == cluster_id)
        )).all())


async def _fixed_with(engine, agent: str, *, fix_version: str | None) -> int:
    """造 fixed 终态簇（P2-5 §7.5 门控锚点）：首现 merge → UPDATE fixed [+fix_version]。"""
    async with AsyncSession(engine) as s:
        r1 = _probe_row(s, agent=agent, trace_id=f"{agent}-1")
        await s.flush()
        await _merge_row(s, r1, now=NOW)
        cid = (await s.scalars(select(ErrorCluster).where(
            ErrorCluster.agent == agent))).one().id
        vals = {"status": "fixed"}
        if fix_version is not None:
            vals["fix_version"] = fix_version  # claim 产物恒带 fix_version
        await s.execute(update(ErrorCluster).where(ErrorCluster.id == cid).values(**vals))
        await s.commit()
        return cid


async def s7_reentry_e9(engine) -> None:
    print("\n===== S-7 E-9：fixed+fix_version 后跨日再现过门控 → gen+1 + conv(reentry) =====")
    agent = "cp-re7"
    async with AsyncSession(engine) as s:
        await _fixed_with(engine, agent, fix_version="2026.09.08-r47")  # g1 fixed
        # 同键线上再现：agent_version 跨日后于 fix 日期 → 过 §7.5 门控 → reentry 新簇
        r2 = _probe_row(s, agent=agent, trace_id="cp-re7-2",
                        err_summary=_summary(agent_version="2026.09.09-r2"))
        await s.flush()
        await _merge_row(s, r2, now=NOW)
        await s.commit()
    clusters = sorted(await _clusters(engine, agent), key=lambda c: c.generation)
    check("S-7 再现（版本>fix）→ 新簇 gen2 open + trigger_version 冻结",
          len(clusters) == 2 and clusters[1].generation == 2
          and clusters[1].status == "open"
          and clusters[1].trigger_version == "2026.09.09-r2",
          f"n={len(clusters)} gens={[c.generation for c in clusters]}")
    check("S-7 原 fixed 簇不动（gen1 保持 fixed + fix_version + count=1）",
          clusters[0].status == "fixed"
          and clusters[0].fix_version == "2026.09.08-r47"
          and clusters[0].count == 1,
          f"g1 status={clusters[0].status} fix={clusters[0].fix_version} count={clusters[0].count}")
    convs = await _conv_for(engine, clusters[1].id)
    check("S-7 conv(action=reentry) 落新簇 + actor_user_id=None + §7.5 提示原文",
          len(convs) == 1 and convs[0].action == "reentry"
          and convs[0].actor_user_id is None
          and "线上仍复发" in (convs[0].detail or ""),
          f"conv={[(c.action, c.cluster_id) for c in convs]}")


async def s8_sameday_blocked(engine) -> None:
    print("\n===== S-8 同日不等值 → merge_candidate 返 blocked（零落不建簇不 conv） =====")
    agent = "cp-re8"
    await _fixed_with(engine, agent, fix_version="2026.09.08-r47")
    action = None
    async with AsyncSession(engine) as s:
        action = await merge_candidate(
            s, agent=agent, interface=IFACE, layer="L1", error_type="llm_timeout",
            input_hash=H1, input_snapshot=None, input_truncated=0,
            error_msg="sameday", trace_id="cp-re8-2",
            trigger_version="2026.09.08-r48",  # 同日不同构建 → 按 fix 上线中挡
            reopen_after_terminal=True, now=NOW)
        await s.commit()
    clusters = await _clusters(engine, agent)
    check("S-8 blocked + 簇数不变（gen1 孤） + 无 reentry conv",
          action == "blocked" and len(clusters) == 1
          and not await _conv_for(engine, clusters[0].id),
          f"action={action} n={len(clusters)}")


async def s9_early_blocked(engine) -> None:
    print("\n===== S-9 早于 fix 日期 → blocked（零落） =====")
    agent = "cp-re9"
    await _fixed_with(engine, agent, fix_version="2026.09.08-r47")
    action = None
    async with AsyncSession(engine) as s:
        action = await merge_candidate(
            s, agent=agent, interface=IFACE, layer="L1", error_type="llm_timeout",
            input_hash=H1, input_snapshot=None, input_truncated=0,
            error_msg="early", trace_id="cp-re9-2",
            trigger_version="2026.09.07-r1",  # 事件早于 fix → 非复发
            reopen_after_terminal=True, now=NOW)
        await s.commit()
    clusters = await _clusters(engine, agent)
    check("S-9 blocked + 簇数不变 + 无 conv",
          action == "blocked" and len(clusters) == 1
          and not await _conv_for(engine, clusters[0].id),
          f"action={action} n={len(clusters)}")


async def s10_no_gate_regression(engine) -> None:
    print("\n===== S-10 回归护栏：无门控基础维持 P2-1 无条件开（S-3 兼容） =====")
    # (a) fixed 但 fix_version NULL（UPDATE 造数，无 claim 语义）→ 照开 gen2
    agent_a = "cp-re10a"
    await _fixed_with(engine, agent_a, fix_version=None)
    action_a = None
    async with AsyncSession(engine) as s:
        action_a = await merge_candidate(
            s, agent=agent_a, interface=IFACE, layer="L1", error_type="llm_timeout",
            input_hash=H1, input_snapshot=None, input_truncated=0,
            error_msg="recur", trace_id="cp-re10a-2", trigger_version="2026.09.09-r1",
            reopen_after_terminal=True, now=NOW)
        await s.commit()
    ca = sorted(await _clusters(engine, agent_a), key=lambda c: c.generation)
    check("S-10a fixed 无 fix_version → 照开 gen2 + 不写 reentry conv",
          action_a == "created" and len(ca) == 2 and ca[1].generation == 2
          and not await _conv_for(engine, ca[1].id),
          f"action={action_a} n={len(ca)}")
    # (b) inactive 终态复发 → 照开 gen2（最高代非 fixed，不咨询门控）
    agent_b = "cp-re10b"
    async with AsyncSession(engine) as s:
        await _fixed_with(engine, agent_b, fix_version=None)
        # 把上一步 fixed(无 fv) 改为 inactive——测试 inactive 终态分支
        await s.execute(update(ErrorCluster)
                        .where(ErrorCluster.agent == agent_b)
                        .values(status="inactive"))
        await s.commit()
    action_b = None
    async with AsyncSession(engine) as s:
        action_b = await merge_candidate(
            s, agent=agent_b, interface=IFACE, layer="L1", error_type="llm_timeout",
            input_hash=H1, input_snapshot=None, input_truncated=0,
            error_msg="recur", trace_id="cp-re10b-2", trigger_version="2026.09.09-r1",
            reopen_after_terminal=True, now=NOW)
        await s.commit()
    cb = sorted(await _clusters(engine, agent_b), key=lambda c: c.generation)
    check("S-10b inactive 终态复发 → 照开 gen2 + 无 reentry conv",
          action_b == "created" and len(cb) == 2 and cb[1].generation == 2
          and not await _conv_for(engine, cb[1].id),
          f"action={action_b} n={len(cb)}")


async def _row_of(engine, agent: str, trace_id: str) -> TraceJudgeState:
    async with AsyncSession(engine) as s:
        return (await s.scalars(select(TraceJudgeState).where(
            TraceJudgeState.agent == agent, TraceJudgeState.trace_id == trace_id))).one()


async def _seed_and_run(engine, agent: str, trace_id: str, **row_kw) -> TraceJudgeState:
    """建 agent + 未判行 → 跑真实 job 链（judge_scan → cluster_merge）→ 回读行。

    走 job 入口而非手搓 decide/_merge_row：正是要覆盖「装载侧 `_facts_from_row`/`_ctx_for`
    → 判定 → judgement_json 落库 → 归并消费」这条单测打不到的壳链路。
    """
    await _probe_agent(engine, agent)
    async with AsyncSession(engine) as s:
        _probe_row(s, agent=agent, trace_id=trace_id, **row_kw)
        await s.commit()
    await run_judge_scan(engine)
    await run_cluster_merge(engine)
    return await _row_of(engine, agent, trace_id)


async def s11_absorbed_no_candidate(engine) -> None:
    print("\n===== S-11 兜底吸收（request ok + 子节点 llm_call error）→ 零候选零建簇 =====")
    agent, trace = "cp-absorb", "cp-absorb-1"
    row = await _seed_and_run(
        engine, agent, trace,
        judged=0, root_ok=1, root_status="ok", root_error_type=None,
    )
    jj = row.judgement_json or {}
    check("S-11 judge_scan 真判了该行（judged=1 + judgement_json 落库）",
          bool(row.judged) and isinstance(row.judgement_json, dict),
          f"judged={row.judged} has_jj={isinstance(row.judgement_json, dict)}")
    check("S-11 layer=none ∧ candidate_error_sets=[]（§6.1 L826 兜底吸收不产候选）",
          jj.get("layer") == "none" and jj.get("candidate_error_sets") == [],
          f"layer={jj.get('layer')} cands={jj.get('candidate_error_sets')!r}")
    check("S-11 root 快照如实落库（ok=True/status=ok/error_type=None）",
          jj.get("root") == {"ok": True, "status": "ok", "error_type": None},
          f"root={jj.get('root')!r}")
    check("S-11 gate 快照 = 放行（证零候选非 gate 关停所致）",
          jj.get("gate", {}).get("agent_exists") is True
          and jj.get("gate", {}).get("backflow_allow") is True,
          f"gate={jj.get('gate')!r}")
    check("S-11 归并后 processed CAS=1（行被真消费，非静默跳过）",
          bool(row.processed), f"processed={row.processed}")
    check("S-11 该 agent 零 error_cluster（不触发 offline 回归）",
          len(await _clusters(engine, agent)) == 0, "不应建簇")


async def s12_root_error_control(engine) -> None:
    print("\n===== S-12 对照组：root 自身 error → L1 建簇（证链路确实会建簇） =====")
    agent, trace = "cp-rooterr", "cp-rooterr-1"
    row = await _seed_and_run(engine, agent, trace, judged=0)
    jj = row.judgement_json or {}
    check("S-12 layer=L1 ∧ 候选 evidence=root（同 error_type root+子节点双现归并单候选）",
          jj.get("layer") == "L1"
          and [(c.get("error_type"), c.get("evidence"))
               for c in jj.get("candidate_error_sets") or []] == [("llm_timeout", "root")],
          f"layer={jj.get('layer')} cands={jj.get('candidate_error_sets')!r}")
    clusters = await _clusters(engine, agent)
    # 簇 count = **trace 出现次数**（本场景 1 行 =1），非候选级 count（=3，见上行断言）：
    # 两个粒度，`_merge_row` 调 merge_candidate 不传候选 count（S-1 同口径已钉死）。
    check("S-12 归并建簇 1 个（L1/llm_timeout，簇 count=1=trace 出现次数）",
          len(clusters) == 1 and clusters[0].layer == "L1"
          and clusters[0].error_type == "llm_timeout" and clusters[0].count == 1
          and clusters[0].first_trace_id == trace,
          f"n={len(clusters)} "
          f"{[(c.layer, c.error_type, c.count) for c in clusters]}")


async def s13_residual_control(engine) -> None:
    print("\n===== S-13 对照组：残 trace（root 未达）→ 子节点候选 L1 建簇 =====")
    agent, trace = "cp-residual", "cp-residual-1"
    row = await _seed_and_run(
        engine, agent, trace,
        judged=0, root_ok=0, root_status=None, root_error_type=None,
    )
    jj = row.judgement_json or {}
    check("S-13 layer=L1 ∧ evidence=subnode（T-3.10 未误切残 trace 分支）",
          jj.get("layer") == "L1"
          and [(c.get("error_type"), c.get("evidence"))
               for c in jj.get("candidate_error_sets") or []] == [("llm_timeout", "subnode")],
          f"layer={jj.get('layer')} cands={jj.get('candidate_error_sets')!r}")
    clusters = await _clusters(engine, agent)
    check("S-13 归并建簇 1 个（簇 count=1=trace 出现次数，非候选级 2）",
          len(clusters) == 1 and clusters[0].layer == "L1" and clusters[0].count == 1,
          f"n={len(clusters)} {[(c.layer, c.count) for c in clusters]}")


async def main() -> None:
    settings = Settings()
    engine = create_async_engine(settings.sqlalchemy_url)
    try:
        await _reset(engine)  # 幂等：清 cp-% 残留（防重跑累积干扰断言）
        await s1_open(engine)
        await s2_count_backfill(engine)
        await s3_gen_after_fixed(engine)
        await s4_forka_no_hash(engine)
        await s5_gate_closed(engine)
        await s6_unique(engine)
        await s7_reentry_e9(engine)
        await s8_sameday_blocked(engine)
        await s9_early_blocked(engine)
        await s10_no_gate_regression(engine)
        await s11_absorbed_no_candidate(engine)
        await s12_root_error_control(engine)
        await s13_residual_control(engine)
    finally:
        await _reset(engine)
        await engine.dispose()
    print("\n===== cluster_probe 结果 =====")
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} 项失败 → {FAILURES}")
        sys.exit(1)
    print("全绿：P2-1 聚类归并 + P2-5 §7.5 reentry 门控 + T-3.10 兜底吸收门控 "
          "DB 壳 13 场景通过")


if __name__ == "__main__":
    asyncio.run(main())
