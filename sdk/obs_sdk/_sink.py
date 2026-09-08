"""上报传输层（detail §3.1/§3.2）：有界内存队列 → 后台线程批量 → kafka-python。

可靠性设计（§3.2「SDK 绝不影响业务」+ T-1.5 验证目标）：
- 记录线程只做 `queue.put_nowait`（有界 maxsize=10000），满则**丢弃并计数**，绝不阻塞业务。
- 单后台 Flusher 线程攒批（flush_batch 条或 flush_interval_s 超时）→ kafka-python 逐条 send
  显式等 ack；失败指数退避重试 ≤3，仍败 → 落 spool 文件（可配路径）+ 计数，下轮补传。
  补传整文件逐行重发——消费端 `_id=sha256(agent|trace|seq)` 幂等吸收重复（S-3），故可安全
  整文件重放（乱序由消费端累积态窗口吸收，R-21 root-late）。
- 心跳（§3.6，1/min obs.selfmonitor）：独立 daemon 线程经同一队列投递，topic 由 agent topic
  逆推 env 拼出（`{env}.obs.selfmonitor`）。
- 线程全 daemon + 惰性 producer（Flusher 首轮才建 KafkaProducer——建对象不连 broker，
  首条 send 触发 metadata；broker 不在只影响 send 不卡业务线程）。
"""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from typing import Any, Optional

from kafka import KafkaProducer
from kafka.errors import KafkaError

from obs_sdk._events import build_heartbeat, now_ms

logger = logging.getLogger("obs_sdk")

QUEUE_MAX = 10_000        # 内存队列上限（满丢弃计数，不阻塞业务）
HEARTBEAT_SEC = 60        # §3.6 SDK 心跳周期（消费端健康卡 1min 粒度对齐）
SEND_RETRY = 3            # 发送失败退避重试 ≤3（§3.2 失败退避 ≤3 次）
SEND_TIMEOUT_S = 10       # 单条 send ack 等待上限
SPOOL_PREFIX = "fail"     # spool 文件前缀（fail-<ts>.jsonl）

EVENT_TOPIC = "agent"     # 队列项 topic 域（内部：业务事件 vs 心跳）
HB_TOPIC = "heartbeat"


class Sink:
    """进程级上报出口：record_* 线程 put_nowait，Flusher 线程批量发 kafka。"""

    def __init__(self, kafka_servers: str, *, agent: str, agent_topic: str,
                 sasl_username: Optional[str] = None, sasl_password: Optional[str] = None,
                 flush_batch: int = 500, flush_interval_s: float = 2.0,
                 spool_dir: Optional[str] = None, heartbeat: bool = True) -> None:
        self._servers = kafka_servers
        self._sasl_user = sasl_username
        self._sasl_pass = sasl_password
        self._agent_topic = agent_topic
        self._batch = max(1, flush_batch)
        self._interval = max(0.1, flush_interval_s)
        self._spool_dir = spool_dir
        self._heartbeat_on = heartbeat
        self._queue: "queue.Queue[tuple[str, dict]]" = queue.Queue(maxsize=QUEUE_MAX)
        self.dropped = {"queue_full": 0, "send_fail": 0, "serialize": 0}
        self._producer: Optional[KafkaProducer] = None
        self._producer_lock = threading.Lock()
        self._flusher: Optional[threading.Thread] = None
        self._hb_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        # selfmonitor topic 逆推：agent topic = {env}.obs.agent.{name} → env.obs.selfmonitor
        env = agent_topic.split(".obs.agent.", 1)[0]
        self._selfmonitor_topic = f"{env}.obs.selfmonitor"
        self._agent = agent
        self._failed = 0

    # ---- 生命周期 -----------------------------------------------------

    def start(self) -> None:
        if self._flusher is not None:
            return
        self._flusher = threading.Thread(target=self._run_flusher, name="obs-sdk-flusher",
                                         daemon=True)
        self._flusher.start()
        if self._heartbeat_on:
            self._hb_thread = threading.Thread(target=self._run_heartbeat,
                                               name="obs-sdk-heartbeat", daemon=True)
            self._hb_thread.start()

    def stop(self, flush: bool = True) -> None:
        """收尾：停线程 + 终刷剩余（应用 shutdown 钩子调用）。

        终刷不依赖 flusher 线程是否曾启动（测试免线程场景也要把已入队事件发完）；
        已启动则 _stop.set 后 join，flusher 攒批轮会在 interval 死线内退出（默认 2s）。
        """
        self._stop.set()
        if flush:
            self._flush_once(timeout=10.0)  # 终刷剩余 + spool 补传
        if self._flusher is not None and self._flusher.is_alive():
            self._flusher.join(timeout=5)
        if self._hb_thread is not None and self._hb_thread.is_alive():
            self._hb_thread.join(timeout=2)
        if self._producer is not None:
            try:
                self._producer.flush(timeout=5)
                self._producer.close(timeout=5)
            except Exception:  # 收尾不因关闭失败中断
                logger.exception("obs-sdk producer 关闭异常")
            self._producer = None

    # ---- 业务线程接口（record_* 调用，绝不停留） ------------------------

    def emit(self, topic_domain: str, event: dict[str, Any]) -> None:
        """事件入队（EVENT_TOPIC=agent 业务 topic；HB_TOPIC=心跳）。满则丢弃计数。"""
        try:
            self._queue.put_nowait((topic_domain, event))
        except queue.Full:
            self.dropped["queue_full"] += 1
            logger.warning("obs-sdk 队列满丢弃 1 条（kafka 消费慢）",
                           extra={"dropped_total": self.dropped["queue_full"]})

    def _target_topic(self, domain: str) -> str:
        return self._agent_topic if domain == EVENT_TOPIC else self._selfmonitor_topic

    # ---- Flusher -------------------------------------------------------

    def _run_flusher(self) -> None:
        while not self._stop.is_set():
            try:
                self._flush_once()
            except Exception:  # 单轮异常不自杀线程，下轮自愈
                logger.exception("obs-sdk flusher 轮次异常（下轮自愈）")
                time.sleep(self._interval)

    def _flush_once(self, timeout: Optional[float] = None) -> None:
        """攒一个批次发送；随后补传 spool 遗留。timeout 供 stop 终刷用。"""
        batch: list[tuple[str, dict]] = []
        deadline = time.time() + (timeout if timeout is not None else self._interval)
        while len(batch) < self._batch:
            remain = deadline - time.time()
            if remain <= 0:
                break
            try:
                item = self._queue.get(timeout=min(remain, 0.5))
            except queue.Empty:
                if timeout is not None:
                    break  # 终刷/手动 flush：无新事件即完成（不等攒批窗口，stop 不空卡）
                continue   # 攒批轮：空则继续等到 interval 死线，收集中途到达（interval 内聚批）
            batch.append(item)
        for domain, event in batch:
            self._send_with_retry(self._target_topic(domain), event)
        self._replay_spool()

    # ---- kafka 发送（含重试/spool） ------------------------------------

    def _ensure_producer(self) -> KafkaProducer:
        if self._producer is None:
            with self._producer_lock:
                if self._producer is None:
                    kwargs: dict[str, Any] = {
                        "bootstrap_servers": self._servers,
                        # 无 value_serializer（why）：本层发送前已统一预编码为 UTF-8 bytes
                        # （_send_with_retry / _send_once），再配 serializer 会对 bytes 二次
                        # json.dumps → TypeError 非 KafkaError，逃过重试/spool 且不计数，
                        # 静默丢事件（#89 冒烟实测抓到）。kafka 侧以 bytes 原样发送。
                        "acks": 1, "retries": 0,  # 重试由本层指数控制（§3.2 有界）
                        "max_in_flight_requests_per_connection": 1,  # 单连接保序
                        "linger_ms": 0, "request_timeout_ms": SEND_TIMEOUT_S * 1000,
                    }
                    if self._sasl_user:
                        kwargs.update({
                            "security_protocol": "SASL_PLAINTEXT",
                            "sasl_mechanism": "PLAIN",
                            "sasl_plain_username": self._sasl_user,
                            "sasl_plain_password": self._sasl_pass or "",
                        })
                    self._producer = KafkaProducer(**kwargs)
        return self._producer

    def _send_with_retry(self, topic: str, event: dict) -> None:
        """发送：指数退避重试 ≤3（1/2/4s），仍败落 spool + 计数。重复投递由消费端 _id 幂等吸收。

        序列化兜底（why）：extra 白名单值只做键过滤未做 JSON 类型保证——UUID/datetime 等经
        default=str 归字符串；连 str 化都失败（自定义对象 __str__ 炸）则整条计数丢弃，绝不
        让序列化异常打断 _flush_once 里同批其余事件（防静默丢整批）。
        """
        try:
            payload = json.dumps(event, ensure_ascii=False, default=str).encode("utf-8")
        except Exception:  # noqa: BLE001  序列化异常与 kafka 异常同属"本条发不出"，与 broker 无关
            self.dropped["serialize"] += 1
            logger.error("obs-sdk 事件不可 JSON 序列化，计数丢弃（extra 值需 str 化）",
                         extra={"serialize_total": self.dropped["serialize"]})
            return
        for attempt in range(1, SEND_RETRY + 1):
            try:
                self._ensure_producer().send(topic, payload).get(timeout=SEND_TIMEOUT_S)
                return
            except KafkaError as exc:
                logger.warning("obs-sdk 发送失败退避重试", extra={
                    "topic": topic, "attempt": attempt, "err": str(exc)})
                if attempt < SEND_RETRY:
                    time.sleep(2 ** (attempt - 1))  # 1s/2s
        self.dropped["send_fail"] += 1
        self._spool_write(payload)
        logger.warning("obs-sdk 发送超限落 spool（下轮补传）",
                       extra={"topic": topic, "spool_fail_total": self.dropped["send_fail"]})

    def _spool_write(self, payload: bytes) -> None:
        """发送失败落盘（可配路径；无 spool_dir = 纯丢弃降级）。"""
        if not self._spool_dir:
            return
        try:
            os.makedirs(self._spool_dir, exist_ok=True)
            path = os.path.join(self._spool_dir, f"{SPOOL_PREFIX}-{now_ms()}.jsonl")
            with open(path, "ab") as fh:
                fh.write(payload + b"\n")
        except Exception:  # spool 也失败（磁盘问题）→ 纯丢弃，降级到底
            logger.exception("obs-sdk spool 落盘失败（丢弃）")

    def _replay_spool(self) -> None:
        """补传 spool 遗留：整文件重发成功后删（重复行消费端 _id 幂等吸收）。"""
        if not self._spool_dir or not os.path.isdir(self._spool_dir):
            return
        for name in sorted(os.listdir(self._spool_dir)):
            if not name.startswith(SPOOL_PREFIX) or not name.endswith(".jsonl"):
                continue
            path = os.path.join(self._spool_dir, name)
            try:
                with open(path, "rb") as fh:
                    lines = fh.read().splitlines()
                for raw in lines:
                    self._send_once(raw)  # 失败即中断，保文件下次整补
                os.remove(path)
            except Exception:  # 单文件补传失败留下次
                logger.warning("obs-sdk spool 补传未完成（留待下轮）", extra={"file": name})
                break

    def _send_once(self, payload: bytes) -> None:
        try:
            self._ensure_producer().send(self._agent_topic, payload).get(timeout=SEND_TIMEOUT_S)
        except KafkaError:
            raise

    # ---- 心跳（§3.6） --------------------------------------------------

    def _run_heartbeat(self) -> None:
        while not self._stop.is_set():
            time.sleep(HEARTBEAT_SEC)
            self.emit(HB_TOPIC, build_heartbeat(self._agent, now_ms()))
