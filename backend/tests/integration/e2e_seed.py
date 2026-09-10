"""浏览器 e2e 种子脚本（B4-D0）：往 dev 库写一批**多状态**样本，供回流看板/详情页逐项验收。

为什么需要它：dev 库五张业务表全为 0 行，不造数据只能验空态，而回流页的核心
（状态 pill / link 表 / verify 时间线 / conversions 审计 / admin 动作 / claim 倒计时 /
reentry caption / 批挂起徽标）一个都验不到。

隔离约定（沿用探针）：agent 一律 `e2e-%` 前缀，按外键序幂等清理。
**已知副作用（已与用户确认接受）**：种下的 `open` 且有 input_snapshot 的 cluster 会被
live assemble_job（60s）自动组装、`claim` 过期态会被 claim_ttl_job 回退——这正是 D2 要观察的
真实行为。故清理必须**按 cluster_id 反查**（而非按建时记录的 id），才能收掉 worker 中途新建的
link/conversion。注意 error_case_link 的 uk_link_current 生成列：每 cluster 至多一条 pending。

用法：
    docker exec obs-backend python /app/tests/integration/e2e_seed.py          # 清 + 种 + 打印清单
    docker exec obs-backend python /app/tests/integration/e2e_seed.py clean     # 只清
"""
import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings
from app.models.agent import Agent
from app.models.error_flow import (
    ConversionRecord,
    ErrorCaseLink,
    ErrorCluster,
    NeedsReviewBatch,
    TraceJudgeState,
    VerifyRunRecord,
)

AGENT = "e2e-agent"
IFACE = "POST /api/chat"
NOW = datetime.now(timezone.utc).replace(tzinfo=None)
D = lambda days: NOW - timedelta(days=days)          # noqa: E731
FUTURE = NOW + timedelta(days=13)                    # claim 未到期（复核窗 14 天量级）
PAST = NOW - timedelta(hours=2)                      # claim 已过期（触发前端口径的「等待回退」）

H = lambda n: (n * 64)[:64]                          # noqa: E731  合法 sha256 形状占位


def _cluster(**kw) -> ErrorCluster:
    """按 §6.1 最小必填构造 cluster；status 决定详情页走哪条门控分支。"""
    base = dict(
        agent=AGENT, interface=IFACE, layer="L1", error_type="llm_timeout",
        input_hash=H("a"), input_snapshot='{"messages":[{"role":"user","content":"e2e"}]}',
        error_msg="e2e 样本错误摘要", first_trace_id="e2e-trace-1",
        first_ts=D(9), latest_ts=D(1), count=3, generation=1,
    )
    base.update(kw)
    return ErrorCluster(**base)


async def clean(engine) -> None:
    """按外键序清掉全部 e2e-% 痕迹；按 cluster_id 反查以覆盖 worker 中途新建的行。"""
    async with AsyncSession(engine) as c:
        ids = (await c.execute(
            select(ErrorCluster.id).where(ErrorCluster.agent.like(f"{AGENT}%"))
        )).scalars().all()
        lids = (await c.execute(
            select(ErrorCaseLink.id).where(ErrorCaseLink.cluster_id.in_(ids or [-1]))
        )).scalars().all()
        # conversion 可能只挂 link 不挂 cluster（assemble 审计），两条路径都要覆盖
        await c.execute(delete(ConversionRecord).where(
            ConversionRecord.cluster_id.in_(ids or [-1])
            | ConversionRecord.link_id.in_(lids or [-1])
        ))
        await c.execute(delete(VerifyRunRecord).where(VerifyRunRecord.link_id.in_(lids or [-1])))
        # trace_judge_state.agent 是字符串列、无外键，故只能按前缀直接删——补上这一条
        # 之前漏了它：D2 的真机 tick 样本（judged=0 判定行）会残留，清理不幂等。
        await c.execute(delete(TraceJudgeState).where(TraceJudgeState.agent.like(f"{AGENT}%")))
        await c.execute(delete(NeedsReviewBatch).where(NeedsReviewBatch.agent.like(f"{AGENT}%")))
        await c.execute(delete(ErrorCaseLink).where(ErrorCaseLink.cluster_id.in_(ids or [-1])))
        await c.execute(delete(ErrorCluster).where(ErrorCluster.id.in_(ids or [-1])))
        await c.execute(delete(Agent).where(Agent.name.like(f"{AGENT}%")))
        await c.commit()
    print(f"[clean] cluster={len(ids)} link={len(lids)}")


async def seed(engine) -> None:
    async with AsyncSession(engine) as c:
        c.add(Agent(name=AGENT, display_name="E2E 样本 agent"))
        await c.flush()

        # ---- 六种 cluster 状态（详情页门控矩阵的真实数据源）----
        c_open = _cluster(status="open", input_hash=H("a"), error_type="llm_timeout")
        # open 且带快照 → 会被 live assemble_job 自动组装（D2 观察项）
        c_claim = _cluster(
            status="claim", input_hash=H("b"), error_type="llm_rate_limit",
            fix_version="e2e-v1", claimed_by=1, claimed_at=D(2), claim_due_ts=FUTURE,
            claim_k=2,
        )
        c_expired = _cluster(
            status="claim", input_hash=H("c"), error_type="llm_auth",
            fix_version="e2e-v1", claimed_by=1, claimed_at=D(15), claim_due_ts=PAST,
            claim_k=1,
        )
        c_fixed = _cluster(
            status="fixed", input_hash=H("d"), error_type="llm_content",
            fix_version="e2e-v2", claimed_by=1, claimed_at=D(20), claim_due_ts=PAST,
            first_ts=D(40), latest_ts=D(20), count=7,
        )
        c_inactive = _cluster(
            status="inactive", input_hash=H("e"), error_type="llm_timeout", layer="L2",
            count=2,
        )
        c_review = _cluster(
            status="needs_review", input_hash=H("f"), error_type="llm_timeout",
            needs_review_reason="unclean_run", input_truncated=1, count=5,
        )
        for cl in (c_open, c_claim, c_expired, c_fixed, c_inactive, c_review):
            c.add(cl)

        # ---- 填充行：收掉「分页边界」与「interface 筛选」两个盲区 ----
        # ① 分页：默认 page_size=20，6 行永远落不满一页 → 分页块整块不渲染。
        #    补到 24 行才能验「1/2 页、下一页可点、末页禁用」。
        # ② interface 筛选：下拉项来自 **ES 指标**（metrics.py `_load_interfaces` →
        #    es_store.run_metrics_interfaces），不是本库——灌 MySQL 造不出下拉项。
        #    故反其道：取一个 ES 里**已存在**的接口名挂在种子行上，就能从 UI 下拉选中它
        #    并验筛选链路。'POST /api/chat/{id}' 取自前端下拉实测枚举。
        # snapshot=None：assemble 判据要求快照非空，置空即不参与 live 组装，避免填充行
        # 造出无关噪音（原生 6 行已足够观察自动组装）。
        ES_IFACE = "POST /api/chat/{id}"
        for i in range(18):
            c.add(_cluster(
                status="open", input_hash=H(f"p{i}"),
                interface=ES_IFACE if i == 0 else IFACE,
                error_type="llm_timeout", count=1 + i % 3,
                input_snapshot=None, first_ts=D(1 + i % 7), latest_ts=D(i % 3),
            ))
        await c.flush()
        cid = {k: v.id for k, v in dict(
            open=c_open, claim=c_claim, expired=c_expired, fixed=c_fixed,
            inactive=c_inactive, review=c_review,
        ).items()}

        def link(cluster_id, *, status, verify, reason=None, case_id=None) -> ErrorCaseLink:
            return ErrorCaseLink(
                cluster_id=cluster_id, payload_id=str(uuid.uuid4()),
                case_id=case_id, case_type="regression_error",
                source_trace_id="e2e-trace-1", fix_version="e2e-v1",
                offline_status=status, verify_status=verify,
                payload_json='{"schema_version":1,"e2e":true}',
                invalidate_reason=reason,
            )

        # ---- links：覆盖 offline_status × verify_status ----
        # 两条硬约束决定了下面的分布：
        #  ① uk_link_current 生成列 → 每 cluster 至多 1 条 pending；
        #  ② assemble 只挑「无 pending」的开放簇（§6.3 窗口抑制）→ open 簇必须**不带** pending，
        #     否则 live 组装永远不会触发，D2 的自动组装观察项就落空。
        l_open_failed = link(cid["open"], status="assembled", verify="failed",
                             case_id="e2e-case-1")   # 终态 → 不占现行位，不抑制组装
        l_assemble_failed = link(cid["fixed"], status="assembled", verify="failed",
                                 case_id="e2e-case-2")
        l_active_pending = link(cid["claim"], status="active", verify="pending",
                                case_id="e2e-case-3")
        l_draft_pending = link(cid["expired"], status="draft", verify="pending",
                               case_id="e2e-case-4")
        # invalidated ∧ verify pending ∧ cluster=needs_review → 「重推」按钮可达
        # （挂 review 簇而非 claim 簇：claim 簇已被 l_active_pending 占了现行位）
        l_invalid_pending = link(cid["review"], status="invalidated", verify="pending",
                                 case_id="e2e-case-5", reason="offline_cap_gap")
        l_superseded = link(cid["fixed"], status="assembled", verify="superseded",
                            case_id="e2e-case-6")
        # verify_status='invalidated' 那一格：DB 枚举 5 值、前端 VERIFY_STATUS_TEXT 只配 4，
        # 且该值全仓零写点——只能靠种子覆盖（否则这一格在 UI 上永远测不到）。
        # invalidated ≠ pending → 不占 uk_link_current 现行位，可挂在已有 pending 的簇上。
        l_verify_invalidated = link(cid["inactive"], status="assembled", verify="invalidated",
                                    case_id="e2e-case-7")
        for lk in (l_open_failed, l_assemble_failed, l_active_pending,
                   l_draft_pending, l_invalid_pending, l_superseded, l_verify_invalidated):
            c.add(lk)
        await c.flush()

        # ---- verify 时间线（版本×pass/fail，含 excluded）----
        for rid, ver, passed in (("e2e-run-1", "e2e-v1", 0), ("e2e-run-2", "e2e-v2", 1)):
            c.add(VerifyRunRecord(
                link_id=l_assemble_failed.id, run_id=rid, bound_version=ver,
                case_pass=passed, run_status="passed" if passed else "failed",
                raw_json={"e2e": True}, verified_ts=D(3),
            ))

        # ---- conversions：覆盖多种 action（中文映射核验）----
        for act, det, by in (
            ("assemble", "D19 信封组装", None),
            ("claim", "认领 e2e-v1 K=2", "admin_review"),
            ("needs_review", "run 存在 na 污染", "auto_regression"),
            ("fixed_review", "复核通过", "admin_review"),
            ("reopen", "误判反悔", "admin_review"),
        ):
            c.add(ConversionRecord(
                cluster_id=cid["fixed"] if act != "needs_review" else cid["review"],
                link_id=l_assemble_failed.id, action=act, detail=det,
                closed_by=by, actor_user_id=1 if by else None, ts=D(2),
            ))

        # ---- unclean_run 批（详情页「处置整批」徽标的数据源）----
        c.add(NeedsReviewBatch(
            run_id="e2e-run-batch", agent=AGENT, bound_version="e2e-v1",
            error_type="llm_timeout", status="open",
            link_refs=[{"link_id": l_assemble_failed.id, "cluster_id": cid["review"],
                        "case_id": "e2e-case-2"}],
            reason="环境级 na 污染", created_ts=D(1),
        ))

        # ---- reentry 观察样本（详情页 caption 的数据源）----
        # cluster_reentry_observe（recurrence.py:68-100 / 114-146）口径：
        #   claim 簇 anchor = claimed_at；命中 = 同键(agent+root_input_hash+interface)
        #   ∧ judgement 候选含该 error_type ∧ judged=1 ∧ ts ≥ anchor；
        #   _row_dict 取 ts = root_ts or updated_ts、version = err_summary.agent_version。
        # 挂 claim 簇（不写死 id：重跑 id 必变）：其键 = agent / interface=POST /api/chat /
        # hash=H("b") / error_type=llm_rate_limit，claimed_at = D(2)；
        # 本行 root_ts = D(1) 晚于锚，故应计 1 次、latest_version=e2e-v9。
        # judged=1 且 processed=1：不落 judge_scan 扫描位，live worker 不会改写它（干净样本）。
        c.add(TraceJudgeState(
            agent=AGENT, trace_id="e2e-reentry-1", root_ok=1, interface=IFACE,
            root_status="error", root_error_type="llm_rate_limit",
            root_input_hash=H("b"), root_ts=D(1),
            input_truncated=0,
            err_summary_json={"agent_version": "e2e-v9",
                              "entries": [{"error_type": "llm_rate_limit",
                                           "error_msg": "429 rate limited", "count": 1}]},
            judged=1, processed=1, root_late_complement=0,
            judgement_json={"version": 1, "layer": "L1",
                            "candidate_error_sets": [{"layer": "L1", "error_type": "llm_rate_limit",
                                                      "evidence": "root", "count": 1}]},
            ttl_until=PAST,
        ))
        await c.commit()

    print("[seed] 完成，明细：")
    for k, v in cid.items():
        print(f"  {k:9s} cluster#{v}")
    print(f"  claim 未到期={FUTURE.isoformat()} 已过期={PAST.isoformat()}")


async def main() -> None:
    engine = create_async_engine(Settings().sqlalchemy_url)
    try:
        await clean(engine)
        if "clean" not in sys.argv:
            await seed(engine)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
