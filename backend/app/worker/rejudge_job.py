"""worker rejudge_job：本地补判安全网（本批补；(a)）。

**为什么需要它（判定的触发模型变了，安全网没跟着搬）**：v1.23 第 3 刀把回查判定从
「每 60s 无限重试的轮询 job」改成「结果推送到达时**一次性**触发」
（`api/backflow.record_regression_result` → `verify.judge_link`，唯一生产调用点）。
轮询链（`core/offline_client` + `worker/recheck_job`）整删时，**它的重试安全网被一并删掉**，
而判定本身仍是**不可靠的一次性操作** —— 事件到达的那一刻只要「现场未就绪」，这一次判定就
白跑，且没有任何重试。本 job 补回「再判一次」的能力，覆盖三类「事件到达时未就绪」：

① **claim 晚于推送**：正常时序是 建簇(open) → ≤60s 自动组装 pending link（`assemble_job`
   扫 `status=='open'`，**不依赖认领**）→ offline 拉走（pull-API 无 cluster.status 闸）→
   推结果。此时 cluster 仍是 `open` → 推送端点被 `cluster.status=='claim'` 守卫挡下
   （**必须挡**，见该处注释）→ link 永挂 pending，直到 viewer 认领。认领之后**不会再有事件**
   来驱动这次判定 —— 没有本 job 就永久停在 pending。
② **判定抛异常**：判定段已按「降级不回滚」处理（数据照落、响应 200，见
   `record_regression_result` 的 try/except），跳过的这一轮判定只能靠本 job 补。
③ **其它状态过渡窗口**：needs_review 的 resolve ↔ reopen、TTL 回退、admin invalidate/requeue
   等过渡态下推送到达 → 同样被守卫跳过，状态回到 claim 后需要一次补判。

**与已删的 recheck 不是一回事，别混为一谈、也别把 job 清单按 6→5 改回**（见
`worker/__init__.py`）：recheck 是「online 主动拉 offline 结果」（每分钟一个 outbound
HTTP 轮询），本 job 是**纯本地**扫描 + 重放本 link 已落库的结果行 —— **零 outbound**
（`core/offline_client.py` 已删，本模块不 import 任何 offline 客户端），不依赖 offline 存活，
也不产生平台间流量。

扫描谓词刻意与旧 recheck 的扫描谓词**逐字相同**（`cluster.status=='claim'` ∧ 存在
`verify_status=='pending'` 的现行 link），因为「可判现场」的定义没有变，变的是**触发方式**：
旧 job 用它决定「去拉什么」，本 job 用它决定「重放什么」。

- 每候选 begin_nested() savepoint（判定链中途抛异常只回退该候选，不留半态）；
- 每批一个事务 commit；批循环以「零终态迁移」为收敛判据（**不是**空批，见 run_rejudge
  docstring：候选谓词不自清，空批不可达）；
- 判定本身是对全链的**幂等重放**（数据源 = 已落库行集、终态只读守卫在 judge_link 内），
  故重复跑到已收敛的簇上是 no-op，不需要额外「判过了吗」的标记位。
"""
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.backflow.verify import TERMINAL_OUTCOMES, judge_link
from app.core.log import get_logger
from app.models.error_flow import ErrorCaseLink, ErrorCluster

REJUDGE_BATCH = 200  # 单批候选 cluster 数（与 assemble/claim_ttl 同粒度）

logger = get_logger("worker.rejudge")


async def _scan_candidates(session: AsyncSession, *, batch: int) -> list:
    """扫 `status=='claim'` ∧ 存在现行（pending）link 的 cluster（order by id limit batch）。

    只看 cluster 不看 `verify_run_record`：无已收结果的 claim 簇调 judge_link 会走「本 link
    尚无已收结果 → pending」快速返回（零判定成本），不值得为它多加一次 join。
    """
    has_pending_link = exists().where(
        ErrorCaseLink.cluster_id == ErrorCluster.id,
        ErrorCaseLink.verify_status == "pending",
    )
    return list(
        (
            await session.scalars(
                select(ErrorCluster)
                .where(ErrorCluster.status == "claim", has_pending_link)
                .order_by(ErrorCluster.id)
                .limit(batch)
            )
        ).all()
    )


async def _pending_links(session: AsyncSession, cluster_id: int) -> list:
    """该 cluster 的现行 pending link 全集（uk_link_current 下按 case_type 至多各一条）。"""
    return list(
        (
            await session.scalars(
                select(ErrorCaseLink)
                .where(ErrorCaseLink.cluster_id == cluster_id,
                       ErrorCaseLink.verify_status == "pending")
                .order_by(ErrorCaseLink.id)
            )
        ).all()
    )


async def _rejudge_batch(engine: AsyncEngine, *, batch: int) -> tuple[int | None, int, int]:
    """扫一批候选并补判。空批返回 (None, 0, 0)；否则 (本批判定数, 终态迁移数, 异常跳过数)。"""
    async with AsyncSession(engine) as session:
        clusters = await _scan_candidates(session, batch=batch)
        if not clusters:
            return None, 0, 0
        judged = 0
        advanced = 0
        failed = 0
        for cluster in clusters:
            for link in await _pending_links(session, cluster.id):
                try:
                    async with session.begin_nested():  # 每候选原子：判定写全进全出
                        summary = await judge_link(session, cluster=cluster, link=link)
                except Exception:
                    # 判定异常不拖垮本批（其余候选继续）；下轮自愈重试本候选
                    failed += 1
                    logger.exception(
                        "rejudge 补判异常（本轮跳过，下轮重试）: cluster=%s link=%s",
                        cluster.id, link.id,
                    )
                    continue
                judged += 1
                if summary.get("outcome") in TERMINAL_OUTCOMES:  # 终态表单一来源（verify）
                    advanced += 1
                    logger.info(
                        "rejudge 补判收敛: cluster=%s link=%s outcome=%s",
                        cluster.id, link.id, summary.get("outcome"),
                    )
        await session.commit()
        return judged, advanced, failed


async def run_rejudge(
    engine: AsyncEngine, *, logger=None, batch: int = REJUDGE_BATCH
) -> int:
    """claim 簇现行 pending link 批量补判（worker rejudge loop 每 60s 调一次）。

    收敛判据是「本批**零终态迁移**」而**不是**「空批」—— 本 job 的候选谓词（claim ∧ 有
    pending link）**不自清**：gap / 未达 K / 不可判的簇判定完仍然留在候选集里，空批永远等
    不到（实测：照抄 assemble/claim_ttl 的「批循环直到空批」会让一轮 run 永不返回，worker
    该 loop 从此不 sleep、整轮空转打库）。有终态迁移时对应 link 已离开 pending 集合、候选窗口
    前移，才值得再取一批；无迁移时重放同批是幂等 no-op，继续循环纯空转。
    返回本次实际调用判定的 link 数（含未收敛的 pending）。DB 异常上抛由 worker loop 退避
    自愈（同 judge_scan/assemble/claim_ttl）。
    """
    logger = logger or get_logger("worker.rejudge")
    judged_total = 0
    while True:
        judged, advanced, failed = await _rejudge_batch(engine, batch=batch)
        if judged is None:  # 空扫描 = 候选集真的空了（唯一真收敛）
            break
        judged_total += judged
        if failed:
            logger.warning("rejudge 批内判定异常", extra={"failed": failed})
        if advanced == 0:  # 零进展 → 同批重放是 no-op，收工（见 docstring）
            break
    if judged_total:
        logger.info("rejudge 完成", extra={"judged": judged_total})
    return judged_total
