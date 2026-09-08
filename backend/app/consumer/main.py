"""T-1.2 D5 消费主循环装配（detail §4.1 step1~6 全链 + §3.6 心跳 + §14.1 S-2/S-3）。

- **每 agent 一消费协程组**（§1.2 L101/§4.1 step1）：topic = `{env}.obs.agent.{name}`
  partition=1 → 同 trace 串行，天然满足 §4.3/§4.5 顺序依赖；一个 agent 卡死不拖垮其他。
- 管线编排 = validate(step2) → agent/topic 一致性 → 脱敏复核(step3) → trace 累积态落库
  (step4) → ES 分派(step5) → offset 后提交(step6)。整 trace 批量判定不在消费链
  （worker judge_scan_job：到期行批次判，T-2.1）；消费链只做累积 + R-21 单事件补判。
- **step4 写失败铁律（§14.2）**：不提交 offset + 指数退避重试**直至成功**——丢弃并提交 =
  该 trace 永不回流且 offset 已推进不可找回。ES 失败走显式丢弃（§4.1 step5「不静默丢」；
  spool 归二期，ES 非判定源，分析/回流不依赖 ES）；超阈值只计数不阻塞判定主链。
- **自监控（form A，§14.1 S-2「selfmonitor 可见」）**：进程内按 (agent, reason) 计数 +
  周期 60s 写 `node=heartbeat` 心跳 doc 到事件 index（健康卡 §8.5 聚合源）；同时消费
  `obs.selfmonitor`（SDK 心跳，§3.6）透写入同一 index。已判定 trace 的 judged 冻结防
  重放；R-21 迟到 root：judge 后 root_ok 0→1 且 status∈{error,timeout} → apply_event
  CAS 置位 `root_late_complement`，`_step4_db` **同事务**调 state.root_late_complement
  单事件补判写 judgement_json.root_late（对象钉死 = T-3.6 聚类取数源）。
"""
import asyncio
import hashlib
import json
import time

from aiokafka import AIOKafkaConsumer
from elasticsearch import AsyncElasticsearch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.consumer import es as es_layer
from app.consumer.mask_recheck import find_sensitive_leak
from app.consumer.schema import EventModel
from app.consumer.state import apply_event, root_late_complement
from app.consumer.validate import DropCode, validate_event
from app.core.config import Settings
from app.core.log import get_logger
from app.models.agent import Agent

logger = get_logger("consumer.main")

TRACE_WINDOW_S = 60   # §4.3【实现约定】完成窗口
TRACE_GRACE_S = 300   # §4.3【实现约定】宽限
HEARTBEAT_SEC = 60    # form A 心跳周期（健康卡 1min 粒度）
RETRY_ES_MAX = 3      # ES 写失败重试上限（超限显式丢弃计数）
DRIFT_WARN_MS = 24 * 3600 * 1000  # §3.4 ts 漂移告警窗（>24h 只告警不丢弃）


def classify(raw, topic_agent: str) -> tuple[DropCode | None, EventModel | None]:
    """step2/step3 决策（纯函数）：非法 → (DropCode, None)；合法 → (None, Event)。

    顺序 = schema 校验（§4.2）→ agent 与 topic 归属一致（§3.3 防跨 agent 伪报）→
    脱敏复核（§2.6 平台兜底）。agent≠topic 需 topic 上下文，故独立于 validate_event。
    """
    event, drop = validate_event(raw)
    if drop is not None:
        return drop, None
    if event.agent != topic_agent:
        return DropCode.AGENT_MISMATCH, None
    if find_sensitive_leak(event):
        return DropCode.MASK, None
    return None, event


def agent_name_from_topic(topic: str, settings: Settings) -> str:
    """topic → agent 名（逆拼 `{env}.obs.agent.{name}`）。前缀不符视为内部错误。"""
    prefix = f"{settings.resource_env}.obs.agent."
    if not topic.startswith(prefix):
        raise ValueError(f"非 agent 业务 topic：{topic!r}")
    return topic[len(prefix):]


def heartbeat_id(agent: str, ts_ms: int) -> str:
    """心跳 doc `_id`：按 (agent, 分钟) 覆写——每分钟至多一条现行，健康聚合按 ts 段读。"""
    minute = ts_ms // 60_000
    return hashlib.sha256(f"hb|{agent}|{minute}".encode("utf-8")).hexdigest()


def build_heartbeat_doc(agent: str, ts_ms: int, *, dropped: dict[str, int],
                        source: str) -> dict:
    """form A 心跳 body：`node=heartbeat`（不属业务 node 枚举，§3.6）。"""
    return {
        "node": "heartbeat", "agent": agent, "ts": ts_ms,
        "dropped": {k: v for k, v in sorted(dropped.items()) if v},
        "source": source,
    }


class DroppedCounter:
    """进程内 dropped 计数（form A）：按 (agent, reason) 累加，心跳任务定期快照。"""

    def __init__(self) -> None:
        self._counts: dict[str, dict[str, int]] = {}

    def bump(self, agent: str, reason: str) -> None:
        self._counts.setdefault(agent, {}).setdefault(reason, 0)
        self._counts[agent][reason] += 1

    def per_agent(self) -> dict[str, dict[str, int]]:
        """agent → {reason: count}（拷贝快照，心跳写完不清零 = 累计口径）。"""
        return {a: dict(c) for a, c in self._counts.items()}


class ConsumerApp:
    """消费侧主循环：生命周期 = app lifespan 拉起/收尾（create_app 装配，见 app/main.py）。

    仅 app_env != test 时启用（conftest 骨架单测不起消费链）。依赖（Kafka/MySQL/ES）
    全部惰性建连：start() 内构造，stop() 内释放，杜绝 import 期副作用。
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.dropped = DroppedCounter()
        self._engine: AsyncEngine | None = None
        self._es: AsyncElasticsearch | None = None
        self._consumers: list[AIOKafkaConsumer] = []
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._ensured_indexes: set[str] = set()

    # ---- 生命周期 -----------------------------------------------------

    async def start(self) -> None:
        self._engine = create_async_engine(self.settings.sqlalchemy_url, pool_pre_ping=True)
        self._es = AsyncElasticsearch(self.settings.es_url)
        agents = await self._enabled_agents()
        logger.info("consumer 启动", extra={"agents": agents,
                                            "group": self.settings.kafka_consumer_group})
        for agent in agents:
            self._tasks.append(asyncio.create_task(self._agent_loop(agent)))
        self._tasks.append(asyncio.create_task(self._selfmonitor_loop()))
        self._tasks.append(asyncio.create_task(self._heartbeat_loop(agents)))

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        for consumer in self._consumers:
            try:
                await consumer.stop()
            except Exception:  # stop 幂等，收尾不因单个失败中断
                logger.exception("consumer stop 异常")
        for task in self._tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):  # 收尾吞取消
                pass
        if self._es is not None:
            await self._es.close()
        if self._engine is not None:
            await self._engine.dispose()

    # ---- 装配辅助 -----------------------------------------------------

    async def _enabled_agents(self) -> list[str]:
        """agent 白名单（topic 驱动源，§4.1 step1）：agent 表 enable=1。"""
        if self._engine is None:
            return []
        async with AsyncSession(self._engine) as session:
            rows = await session.scalars(select(Agent.name).where(Agent.enable == 1))
            return [str(name) for name in rows]

    def _new_consumer(self, topics: list[str]) -> AIOKafkaConsumer:
        # aiokafka 0.14：topic 是位置参数（VAR_POSITIONAL），非 topics= keyword——
        # D6 集成抓到的 TypeError 坑。group_id 走 property（显式或缺省 {env}.obs.consumer）
        consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.settings.kafka_bootstrap,
            group_id=self.settings.consumer_group,
            enable_auto_commit=False,          # step6：处理后手动提交
            auto_offset_reset="earliest",       # dev/对账可重放；生产幂等吸收（_id/judged）
        )
        self._consumers.append(consumer)
        return consumer

    async def _ensure_dev_index(self, prefix: str, ts_ms: int) -> str:
        """dev 自建周 index（§5.2 mapping；生产 template 归 infra）。同周只探一次。"""
        index = es_layer.weekly_index_name(prefix, ts_ms)
        if index not in self._ensured_indexes and self.settings.app_env == "dev":
            await es_layer.ensure_weekly_index(self._es, prefix, ts_ms)
            self._ensured_indexes.add(index)
        return index

    # ---- 业务 topic 主循环（每 agent 一协程组） ------------------------

    async def _agent_loop(self, agent: str) -> None:
        """单 agent 消费循环：start 后 async for，异常退避重连（不拖垮进程）。

        必须先 await consumer.start()（coordinator 建立）才能 async for——漏 start 直接
        async for 会崩 `_coordinator None` AttributeError（D6 集成抓到的坑）；单 agent 异常
        不 raise 出 task（task 异常会被 asyncio 吞=该 agent 永死），退避后重连自愈。
        """
        topic = self.settings.agent_topic(agent)
        while not self._stop.is_set():
            consumer = self._new_consumer([topic])
            try:
                await consumer.start()
                async for msg in consumer:
                    await self._handle_agent_message(msg, consumer, agent)
            except asyncio.CancelledError:  # 收尾取消：清 consumer 后上抛
                await consumer.stop()
                raise
            except Exception:  # 单 agent 异常不拖垮进程，退避后重连
                logger.exception("agent 消费循环异常（退避重连）", extra={"agent": agent})
                await consumer.stop()
            await asyncio.sleep(_backoff(3))  # 稳定退避 4s（_backoff(3)=4），重连上限依赖外层 stop

    async def _handle_agent_message(self, msg, consumer, agent: str) -> None:
        """step2~step6：决策 → 落库/分派 → offset 提交（异常路径见函数内注释）。

        注意 commit 走 consumer 对象本身——aiokafka 的 ConsumerRecord 无 .consumer
        属性（D6 集成抓到的坑），offset 提交 API 在 AIOKafkaConsumer 上。
        """
        try:
            raw = json.loads(msg.value)
        except (TypeError, json.JSONDecodeError):
            self.dropped.bump(agent, DropCode.SCHEMA.value)
            await consumer.commit()
            return
        drop, event = classify(raw, agent)
        if drop is not None:
            self.dropped.bump(agent, drop.value)
            await consumer.commit()   # 丢弃即终态：计数后推进（重投会重计数，自监控近似）
            return
        _warn_ts_drift(event.ts)
        # step4：判定态落库（铁律：失败不提交 + 重试直至成功，§14.2 禁止"丢弃并提交"）
        await self._step4_db(event)
        # step5：ES 分派（失败有界重试 → 超限显式丢弃计数，不阻塞判定主链）
        await self._step5_es(event, agent)
        await consumer.commit()   # step6：全链成功才推进 offset

    async def _step4_db(self, event: EventModel) -> None:
        while True:
            try:
                async with AsyncSession(self._engine) as session:
                    fx = await apply_event(
                        session, event, window_s=TRACE_WINDOW_S, grace_s=TRACE_GRACE_S
                    )
                    if fx.root_late:
                        # R-21 补判：apply_event 已 CAS 置位 root_late_complement=1，同一事务
                        # 内读该行做单事件值域补判（写 judgement_json.root_late，不重跑整 trace）
                        await root_late_complement(session, event)
                    await session.commit()
                return
            except Exception as exc:  # DB 故障形态多样
                logger.warning("step4 落库失败退避重试（不提交 offset）",
                               extra={"trace_id": event.trace_id, "err": str(exc)})
                await asyncio.sleep(_backoff(1))

    async def _step5_es(self, event: EventModel, agent: str) -> None:
        prefix = (
            self.settings.log_index_prefix if event.event_kind == "log"
            else self.settings.event_index_prefix
        )
        await self._ensure_dev_index(prefix, event.ts)
        for attempt in range(1, RETRY_ES_MAX + 1):
            try:
                await es_layer.dispatch_event(self._es, event, self.settings)
                return
            except es_layer.EsDispatchError as exc:
                if attempt == RETRY_ES_MAX:
                    # 显式丢弃 + 计数（form A）：ES 非判定源（§4.1 step5 不静默丢）；spool 二期
                    self.dropped.bump(agent, "es_fail")
                    logger.warning("ES 分派超限显式丢弃",
                                   extra={"trace_id": event.trace_id, "err": str(exc)})
                    return
                await asyncio.sleep(_backoff(attempt))

    # ---- selfmonitor（SDK 心跳透传，§3.6）与 form A 心跳 -----------------

    async def _selfmonitor_loop(self) -> None:
        """SDK 心跳透传（§3.6）：obs.selfmonitor → 事件 index `node=heartbeat`。

        同 _agent_loop：先 await consumer.start()（coordinator）再 async for，异常退避重连。
        """

        topic = self.settings.selfmonitor_topic
        while not self._stop.is_set():
            consumer = self._new_consumer([topic])
            try:
                await consumer.start()
                async for msg in consumer:
                    try:
                        hb = json.loads(msg.value)
                    except (TypeError, json.JSONDecodeError):
                        await consumer.commit()
                        continue
                    agent, ts_ms = hb.get("agent"), hb.get("ts")
                    if not agent or not isinstance(ts_ms, int):
                        await consumer.commit()
                        continue
                    prefix = self.settings.event_index_prefix
                    await self._ensure_dev_index(prefix, ts_ms)
                    hb["node"] = "heartbeat"
                    hb["source"] = "sdk"
                    index = es_layer.weekly_index_name(prefix, ts_ms)
                    try:  # 心跳非关键（§3.6：发送失败不重试惩罚）——单条失败不阻塞后续
                        await self._es.index(
                            index=index, id=heartbeat_id(str(agent), ts_ms), document=hb
                        )
                    except Exception:  # 心跳尽力而为，失败跳过不阻塞（§3.6）
                        logger.warning("SDK 心跳落 index 失败（跳过）", extra={"agent": agent})
                    await consumer.commit()
            except asyncio.CancelledError:
                await consumer.stop()
                raise
            except Exception:  # selfmonitor 单点异常不拖垮进程，退避后重连
                logger.exception("selfmonitor 消费循环异常（退避重连）")
                await consumer.stop()
            await asyncio.sleep(_backoff(3))

    async def _heartbeat_loop(self, agents: list[str]) -> None:
        """form A：每 60s 把进程内 dropped 计数写心跳 doc（S-2「count 可见」聚合面）。"""
        while not self._stop.is_set():
            try:
                ts_ms = int(time.time() * 1000)
                prefix = self.settings.event_index_prefix
                await self._ensure_dev_index(prefix, ts_ms)
                index = es_layer.weekly_index_name(prefix, ts_ms)
                counts = self.dropped.per_agent()
                for agent in agents:
                    dropped = counts.get(agent, {})
                    if not dropped:
                        continue
                    await self._es.index(
                        index=index, id=heartbeat_id(agent, ts_ms),
                        document=build_heartbeat_doc(agent, ts_ms, dropped=dropped,
                                                     source="consumer"),
                    )
            except Exception:  # 心跳尽力而为，自愈下次周期
                logger.exception("form A 心跳写失败（下周期重试）")
            await asyncio.sleep(HEARTBEAT_SEC)


def _backoff(attempt: int) -> float:
    """指数退避（cap 30s）：1s/2s/4s/8s…step4 重试与 ES 重试共用。"""
    return min(2 ** (attempt - 1), 30)


def _warn_ts_drift(ts_ms: int) -> None:
    """§3.4：事件 ts 与现时差 > 24h 记漂移告警，只告警不丢弃（恢复补传不丢）。"""
    drift = abs(int(time.time() * 1000) - ts_ms)
    if drift > DRIFT_WARN_MS:
        logger.warning("事件 ts 漂移告警（只告警不丢弃，§3.4）",
                       extra={"ts": ts_ms, "drift_ms": drift})
