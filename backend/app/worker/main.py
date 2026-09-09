"""worker 进程主装配（T-2.1 judge_scan 1min + T-3.1 cluster 15s + T-3.2 assemble 1min
+ T-2.3 rollup 整点，独立进程）。

- 入口：`python -m app.worker`（__main__.py）→ asyncio.run(main())。compose 独立
  service（同 backend 镜像同 env），backend 容器不启动 worker。
- **周期调度 = asyncio 自管**（用户裁定，§5.3 注记改「APScheduler 同族」表述）：不引
  APScheduler——judge_scan 每 60s 一轮、cluster 每 15s 一轮、rollup 对齐下一 UTC 整点
  + 5s 抖动后跑；各 job 各自线性 `run → sleep`，await 串行天然不重叠（慢跑只延迟
  下一轮，rollup 的确定性 _id 整小时覆写保证补算幂等，不需跳过本轮）。
- 启动守卫：先有界轮询 `SELECT 1 FROM agent LIMIT 1`（60s 超时报错退出）——等 backend
  的 alembic 建表；worker 自身**不跑 alembic**（防与 upgrade head 抢跑，detail §14）。
- 单 job 异常 logger.exception + 下周期自愈（不拖垮进程）；MySQL/ES 惰性建连：
  start() 构造、stop() 释放。ES 仅 rollup 用（judge_scan 不依赖 ES）。
"""
import asyncio
import signal
import time
from datetime import datetime, timedelta, timezone

from elasticsearch import AsyncElasticsearch
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import create_engine
from app.core.log import get_logger
from app.worker.assemble_job import ASSEMBLE_BATCH, run_assemble
from app.worker.claim_ttl_job import CLAIM_TTL_BATCH, run_claim_ttl
from app.worker.cluster_job import CLUSTER_BATCH, run_cluster_merge
from app.worker.judge_scan_job import JUDGE_SCAN_BATCH, run_judge_scan
from app.worker.recheck_job import RECHECK_BATCH, run_recheck

logger = get_logger("worker.main")

JUDGE_INTERVAL_S = 60   # judge_scan 周期（完成窗口 60s 同级粒度，§4.3）
CLUSTER_INTERVAL_S = 15  # cluster 聚类消费周期（判定到期即应尽快归并进 error_cluster，T-3.1）
ASSEMBLE_INTERVAL_S = 60  # assemble 组装补偿扫描周期（detail §6.3「每分钟扫」，P2-2）
CLAIM_TTL_INTERVAL_S = 60  # claim 复核窗 TTL 回退扫描周期（P2-4 E-8；§7.2 无在线拉取时钟，
                          # TTL/回查全周期 job 驱动）
RECHECK_INTERVAL_S = 60  # claim 回查判定周期（P2-4 E-7；与 assemble 同级；offline_base_url
                         # 空 = 停轮，offline 配套轨启动后填 .env）
ROLLUP_ALIGN_S = 5      # rollup 整点后 5s 抖动（躲开消费侧/其他定时任务整点高峰）
DB_READY_TIMEOUT_S = 60  # 启动守卫等 backend 迁移建表的上限
DB_READY_RETRY_S = 2    # 守卫轮询间隔


class WorkerApp:
    """后台 job 主循环：judge_scan + cluster + assemble + rollup 协程组；stop() 取消 + dispose。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._engine: AsyncEngine | None = None
        self._es: AsyncElasticsearch | None = None
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()

    # ---- 生命周期 -----------------------------------------------------

    async def start(self) -> None:
        self._engine = create_engine(self.settings)  # pool_recycle=3600（core/db，同 API 侧）
        await self._wait_db_ready()
        self._es = AsyncElasticsearch(self.settings.es_url)
        self._tasks.append(asyncio.create_task(self._judge_loop()))
        self._tasks.append(asyncio.create_task(self._cluster_loop()))
        self._tasks.append(asyncio.create_task(self._assemble_loop()))
        self._tasks.append(asyncio.create_task(self._claim_ttl_loop()))
        self._tasks.append(asyncio.create_task(self._recheck_loop()))
        self._tasks.append(asyncio.create_task(self._rollup_loop()))
        logger.info("worker 启动", extra={"env": self.settings.app_env,
                                         "judge_interval_s": JUDGE_INTERVAL_S,
                                         "cluster_interval_s": CLUSTER_INTERVAL_S,
                                         "assemble_interval_s": ASSEMBLE_INTERVAL_S,
                                         "claim_ttl_interval_s": CLAIM_TTL_INTERVAL_S,
                                         "recheck_interval_s": RECHECK_INTERVAL_S})

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):  # 收尾吞取消/异常
                pass
        if self._es is not None:
            await self._es.close()
        if self._engine is not None:
            await self._engine.dispose()

    # ---- 启动守卫 -----------------------------------------------------

    async def _wait_db_ready(self) -> None:
        """有界轮询 agent 表存在（等 backend alembic 建表）；超时抛错退出。"""
        deadline = _monotonic() + DB_READY_TIMEOUT_S
        while True:
            try:
                async with AsyncSession(self._engine) as session:
                    await session.execute(text("SELECT 1 FROM agent LIMIT 1"))
                return
            except Exception as exc:
                if _monotonic() >= deadline:
                    raise RuntimeError(
                        f"worker 启动：agent 表 {DB_READY_TIMEOUT_S}s 内不可达"
                        f"（backend 未迁移/MySQL 未起?）：{exc}"
                    ) from exc
                logger.warning("等待 agent 表就绪…", extra={"err": str(exc)})
                await asyncio.sleep(DB_READY_RETRY_S)

    # ---- job 循环 -----------------------------------------------------

    async def _judge_loop(self) -> None:
        """judge_scan：每 60s 一轮。run → sleep 串行，慢跑只延迟下轮不重叠。"""
        while not self._stop.is_set():
            try:
                judged = await run_judge_scan(
                    self._engine, logger=logger, batch=JUDGE_SCAN_BATCH
                )
                if judged:
                    logger.debug("judge_scan 本轮新判", extra={"judged": judged})
            except Exception:
                logger.exception("judge_scan 异常（下轮自愈）")
            await asyncio.sleep(JUDGE_INTERVAL_S)

    async def _cluster_loop(self) -> None:
        """cluster 聚类消费：每 15s 一轮。run → sleep 串行，慢跑只延迟下轮不重叠。"""
        while not self._stop.is_set():
            try:
                merged = await run_cluster_merge(
                    self._engine, logger=logger, batch=CLUSTER_BATCH
                )
                if merged:
                    logger.debug("cluster_merge 本轮消费", extra={"merged": merged})
            except Exception:
                logger.exception("cluster_merge 异常（下轮自愈）")
            await asyncio.sleep(CLUSTER_INTERVAL_S)

    async def _assemble_loop(self) -> None:
        """D19 组装补偿扫描：每 60s 一轮。run → sleep 串行，慢跑只延迟下轮不重叠。"""
        while not self._stop.is_set():
            try:
                assembled = await run_assemble(
                    self._engine, logger=logger, batch=ASSEMBLE_BATCH
                )
                if assembled:
                    logger.debug("assemble 本轮组装", extra={"assembled": assembled})
            except Exception:
                logger.exception("assemble 异常（下轮自愈）")
            await asyncio.sleep(ASSEMBLE_INTERVAL_S)

    async def _claim_ttl_loop(self) -> None:
        """claim 复核窗 TTL 回退：每 60s 一轮。run → sleep 串行，慢跑只延迟下轮不重叠。"""
        while not self._stop.is_set():
            try:
                expired = await run_claim_ttl(
                    self._engine, logger=logger, batch=CLAIM_TTL_BATCH
                )
                if expired:
                    logger.debug("claim_ttl 本轮回退", extra={"expired": expired})
            except Exception:
                logger.exception("claim_ttl 异常（下轮自愈）")
            await asyncio.sleep(CLAIM_TTL_INTERVAL_S)

    async def _recheck_loop(self) -> None:
        """claim 回查判定：每 60s 一轮。offline_base_url 空 → run_recheck 停轮（安全默认）。"""
        while not self._stop.is_set():
            try:
                processed = await run_recheck(
                    self._engine, self.settings, logger=logger, batch=RECHECK_BATCH
                )
                if processed:
                    logger.debug("recheck 本轮回查", extra={"processed": processed})
            except Exception:
                logger.exception("recheck 异常（下轮自愈）")
            await asyncio.sleep(RECHECK_INTERVAL_S)

    async def _rollup_loop(self) -> None:
        """rollup：对齐下一 UTC 整点 + 5s 抖动后跑一轮（run_rollup 内做整小时回填）。

        rollup_job 延迟 import：本模块与 judge_scan 解耦（T-2.3 挂入前 judge 不受扰）。
        """
        while not self._stop.is_set():
            await _sleep_until_next_hour(ROLLUP_ALIGN_S)
            try:
                from app.worker import rollup_job  # T-2.3：模块在本 worker 进程内

                await rollup_job.run_rollup(self._engine, self._es, self.settings, logger=logger)
            except Exception:
                logger.exception("rollup 异常（下轮自愈）")


async def _sleep_until_next_hour(extra_s: float) -> None:
    """睡到下一个 UTC 整点 + extra_s（小时对齐以 UTC 计：事件 ts 与 rollup hour 均 UTC）。"""
    now = datetime.now(timezone.utc)
    nxt = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    await asyncio.sleep((nxt - now).total_seconds() + extra_s)


def _monotonic() -> float:
    return time.monotonic()


async def main() -> None:
    """worker 进程入口（__main__.py 调用）：start → 等信号 → stop。"""
    worker = WorkerApp(get_settings())
    await worker.start()
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows：无 POSIX 信号，KeyboardInterrupt 兜底
            pass
    try:
        await stop.wait()
    except asyncio.CancelledError:  # 异常中断路径也走 stop 释放
        pass
    await worker.stop()
