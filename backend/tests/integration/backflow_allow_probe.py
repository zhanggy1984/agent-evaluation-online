"""批 C2 / 闭环可用：backflow_allow 负对照真机探针（pending-phases §5.8 ②）。容器内运行：

    docker exec obs-backend python /app/tests/integration/backflow_allow_probe.py

**前置（换环境跑之前先看这条）**：库里须有 cc（`contract-check`，seed D18 置
`backflow_allow=0`）与 cs（`customer-service`，`backflow_allow=1`）**两条 agent 行**。
库未 seed 出 agent 时 gate 的 `agent_exists=False` ⇒ 两行**都不会被判**（`judged=0`），
探针必红 —— 那是**环境缺 seed，不是本模块的缺陷**。

本探针**不在** `.github/workflows/ci.yml` 的真库探针 job 内（那批只有
cluster/claim/pull/push/assemble 五个）；是否纳入**未拍板**，前置 = 先核 CI 那个 job 的库
有没有 seed 出这两条 agent 行，没有则加进去只会恒红成噪音。

**为什么单测不够**：`test_analyzer_classify.py:86` 已覆盖 `decide()` 纯函数层
（backflow_allow=False ⇒ layer=none）。但那只证函数，证不了**链路**——本探针走真实
`run_judge_scan` + `run_cluster_merge`，断言该行在真机上确实不产簇。

判据（成对，唯一差异 = agent）：
- cc 行（contract-check，seed D18 置 backflow_allow=0）→ judged=1 ∧ layer='none'
  ∧ gate.backflow_allow=False ∧ 该 input_hash 无 cluster
- cs 行（customer-service，backflow_allow=1）→ judged=1 ∧ layer='L1' ∧ 已建簇
**正对照不可省**：没有它，「cc 不建簇」也能被「这条行本来就无效」解释掉。

⚠️ 归因边界：cc 侧实有**双保险**（`classify.py:8-9`：`agent.backflow_allow=0` + per-agent
`backflow_enabled=false`），两者在 gate 上同时为假 ⇒ 本探针只证明「这一对关闸生效」，
**不能归因到其中单条**。见 §5.8 ② 的归因订正。

隔离：interface='POST /api/probe/c2' 且 trace_id 前缀 c2-，开头清残留、结尾再清。
"""
import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")

from sqlalchemy import delete, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.models.error_flow import ErrorCluster, TraceJudgeState  # noqa: E402
from app.worker.cluster_job import run_cluster_merge  # noqa: E402
from app.worker.judge_scan_job import run_judge_scan  # noqa: E402

FAILURES: list[str] = []
IFACE = "POST /api/probe/c2"
NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def check(name: str, ok: bool, detail: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)
    if not ok:
        FAILURES.append(name)


def _row(agent: str, tag: str) -> TraceJudgeState:
    """未判行（judged=0、ttl 已过）⇒ 落进 judge_scan 扫描位。"""
    return TraceJudgeState(
        agent=agent, trace_id=f"c2-{tag}-{uuid.uuid4().hex[:8]}",
        root_ok=1, interface=IFACE, root_status="error", root_error_type="llm_timeout",
        root_input_hash=uuid.uuid4().hex + uuid.uuid4().hex,  # 64 字符、唯一
        input_snapshot_clean='{"content": "c2 probe"}', input_truncated=0,
        err_summary_json={"agent_version": "c2-probe",
                          "entries": [{"error_type": "llm_timeout",
                                       "error_msg": "provider timeout", "count": 1}]},
        llm_fact_ok=1, judged=0, processed=0, root_late_complement=0,
        judgement_json=None, ttl_until=NOW - timedelta(minutes=1),
    )


async def _cleanup(db) -> None:
    ids = [r[0] for r in (await db.execute(
        text("SELECT id FROM error_cluster WHERE interface = :i"), {"i": IFACE})).fetchall()]
    if ids:
        lst = ",".join(str(i) for i in ids)
        await db.execute(text(f"DELETE FROM error_case_link WHERE cluster_id IN ({lst})"))
        await db.execute(text(f"DELETE FROM conversion_record WHERE cluster_id IN ({lst})"))
        await db.execute(text(f"DELETE FROM error_cluster WHERE id IN ({lst})"))
    await db.execute(delete(TraceJudgeState).where(TraceJudgeState.trace_id.like("c2-%")))


async def main() -> int:
    settings = Settings()
    engine = create_async_engine(settings.sqlalchemy_url)
    try:
        async with AsyncSession(engine) as db:          # 幂等：清上轮残留
            await _cleanup(db)
            await db.commit()

        async with AsyncSession(engine) as db:
            cc, cs = _row("contract-check", "cc"), _row("customer-service", "cs")
            db.add(cc)
            db.add(cs)
            # 先取 id/hash 再 commit：commit 后属性过期，读它会触发同步 lazy refresh
            await db.flush()
            cc_id, cs_id, cc_hash, cs_hash = cc.id, cs.id, cc.root_input_hash, cs.root_input_hash
            await db.commit()
            print(f"种入未判行：cc={cc_id} cs={cs_id}（唯一差异 = agent）", flush=True)

        scanned = await run_judge_scan(engine)
        print(f"judge_scan 判定行数={scanned}", flush=True)
        await run_cluster_merge(engine)

        async with AsyncSession(engine) as db:
            cc_r = await db.get(TraceJudgeState, cc_id)
            cs_r = await db.get(TraceJudgeState, cs_id)
            cc_j = cc_r.judgement_json or {}
            cs_j = cs_r.judgement_json or {}
            cc_gate = cc_j.get("gate") or {}
            print(
                f"cc 判定产物：judged={cc_r.judged} layer={cc_j.get('layer')} gate={cc_gate}",
                flush=True,
            )
            print(f"cs 判定产物：judged={cs_r.judged} layer={cs_j.get('layer')}", flush=True)

            check("cc 行已判定", cc_r.judged == 1, f"judged={cc_r.judged}")
            check("cc 层=none（负对照）", cc_j.get("layer") == "none", f"layer={cc_j.get('layer')}")
            check(
                "cc gate.backflow_allow=False",
                cc_gate.get("backflow_allow") is False,
                str(cc_gate),
            )
            check("cs 行已判定（正对照）", cs_r.judged == 1, f"judged={cs_r.judged}")
            check("cs 层=L1（正对照）", cs_j.get("layer") == "L1", f"layer={cs_j.get('layer')}")

            cc_c = (await db.execute(select(ErrorCluster).where(
                ErrorCluster.input_hash == cc_hash))).scalars().first()
            cs_c = (await db.execute(select(ErrorCluster).where(
                ErrorCluster.input_hash == cs_hash))).scalars().first()
            check("cc 未建簇", cc_c is None, f"cluster={None if cc_c is None else cc_c.id}")
            check(
                "cs 已建簇（正对照）",
                cs_c is not None,
                f"cluster={None if cs_c is None else cs_c.id}",
            )

        async with AsyncSession(engine) as db:
            await _cleanup(db)
            await db.commit()
            print("已清理探针残留（行 + 簇）", flush=True)
    finally:
        await engine.dispose()

    print(f"FAILURES={FAILURES}", flush=True)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
