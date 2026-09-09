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
  S-6 uk_cluster_dedup 唯一约束在库真在（同键同代重复插 → IntegrityError，E-12 防护面）。

隔离：探针 agent 前缀 cp-（≤64 字符），开头按 LIKE cp-% 清理残留，结尾再清。退出码全绿 0。
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
from app.models.error_flow import ErrorCluster, TraceJudgeState  # noqa: E402
from app.worker.cluster_job import _merge_row  # noqa: E402

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
               truncated=0, jj=None, err_summary=None):
    row = TraceJudgeState(
        agent=agent, trace_id=trace_id, root_ok=1, interface=IFACE,
        root_status="error", root_error_type="llm_timeout",
        root_input_hash=root_hash, input_snapshot_clean=snapshot,
        input_truncated=truncated,
        err_summary_json=err_summary if err_summary is not None else _summary(),
        llm_fact_ok=1, judged=1, processed=0, root_late_complement=0,
        judgement_json=jj if jj is not None else _jj(),
        ttl_until=NOW,
    )
    session.add(row)
    return row


async def _reset(engine) -> None:
    async with AsyncSession(engine) as s:
        await s.execute(delete(TraceJudgeState).where(TraceJudgeState.agent.like("cp-%")))
        await s.execute(delete(ErrorCluster).where(ErrorCluster.agent.like("cp-%")))
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
    finally:
        await _reset(engine)
        await engine.dispose()
    print("\n===== cluster_probe 结果 =====")
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} 项失败 → {FAILURES}")
        sys.exit(1)
    print("全绿：P2-1 聚类归并 DB 壳 6 场景通过")


if __name__ == "__main__":
    asyncio.run(main())
