"""D5 主循环纯逻辑单测（detail §4.1 step1~3 决策 + §3.6/form A 心跳）。

只测无 IO 的部分：classify（step2/step3 决策顺序：schema → agent/topic 一致性 → 脱敏）、
topic→agent 逆拼、心跳 _id/body、DroppedCounter 快照。真 Kafka/MySQL/ES 链留 D6 集成
（S-2 三类丢弃计数 / S-3 同 trace 重放幂等）实库验证。
"""
import pytest

from app.consumer.main import (
    ConsumerApp,
    DroppedCounter,
    agent_name_from_topic,
    build_heartbeat_doc,
    classify,
    heartbeat_id,
)
from app.consumer.schema import EventModel
from app.consumer.validate import DropCode
from app.core.config import Settings


def settings(resource_env="dev") -> Settings:
    return Settings(app_env="test", resource_env=resource_env)


def _req(agent="good-question", **over) -> dict:
    """合法 request 事件 dict（§2.2① 同形），可注入敏感键/错 agent。"""
    data = {
        "schema_version": "1.0", "event_kind": "event", "trace_id": "tr-9f2c1a", "agent": agent,
        "agent_version": "2026.08.31-r47", "interface": "POST /api/chat/{id}", "node": "request",
        "seq": 0, "parent": None, "ts": 1785897600000, "duration_ms": 1200, "status": "error",
        "error_type": "llm_timeout", "error_msg": "provider timeout", "input": {"q": "政策?"},
        "output": None, "usage": None, "model": None, "extra": {},
    }
    data.update(over)
    return data


class TestClassify:
    """step2/step3 决策顺序与分型（§4.2/§3.3/§2.6）。"""

    def test_valid_event_passes(self):
        drop, event = classify(_req(), "good-question")
        assert drop is None
        assert isinstance(event, EventModel)

    def test_schema_invalid_drops_schema(self):
        drop, event = classify({"schema_version": "2.0"}, "good-question")
        assert drop is DropCode.SCHEMA and event is None
        # 非 dict / null 同归 schema
        assert classify(None, "good-question")[0] is DropCode.SCHEMA
        assert classify("nope", "good-question")[0] is DropCode.SCHEMA

    def test_extra_key_drops_extra(self):
        drop, _ = classify(_req(extra={"not_whitelisted": 1}), "good-question")
        assert drop is DropCode.EXTRA_KEY

    def test_agent_topic_mismatch_drops(self):
        # 跨 agent 伪报（§3.3 双重校验）：topic 属 gq、事件 agent 属 cs → 丢弃
        drop, _ = classify(_req(agent="customer-service"), "good-question")
        assert drop is DropCode.AGENT_MISMATCH

    def test_mask_leak_drops_mask(self):
        drop, _ = classify(_req(input={"token": "secret-123"}), "good-question")
        assert drop is DropCode.MASK

    def test_mask_checked_after_agent_mismatch(self):
        # 决策顺序：agent 不一致先判（防陌生 agent 的内容进 mask 复核面）
        drop, _ = classify(_req(agent="evil", input={"token": "x"}), "good-question")
        assert drop is DropCode.AGENT_MISMATCH


class TestTopicAgent:
    def test_agent_name_extract(self):
        s = settings()
        topic = s.agent_topic("good-question")
        assert topic == "dev.obs.agent.good-question"
        assert agent_name_from_topic(topic, s) == "good-question"

    def test_non_agent_topic_raises(self):
        try:
            agent_name_from_topic("dev.obs.selfmonitor", settings())
            raise AssertionError("应抛 ValueError")
        except ValueError:
            pass


class TestHeartbeat:
    def test_id_minute_bucket_stable_and_agent_scoped(self):
        a = heartbeat_id("gq", 1785897600000)
        assert a == heartbeat_id("gq", 1785897600000 + 5)  # 同分钟内覆写（同 id）
        assert a != heartbeat_id("gq", 1785897660000 + 60_000)  # 跨分钟新 doc
        assert a != heartbeat_id("cs", 1785897600000)

    def test_build_doc_drops_zero_and_sorts(self):
        doc = build_heartbeat_doc("gq", 1, dropped={"mask": 2, "schema": 0, "extra_key": 1},
                                  source="consumer")
        assert doc["node"] == "heartbeat"  # §3.6 不属业务 node 枚举
        assert doc["agent"] == "gq" and doc["source"] == "consumer"
        assert doc["dropped"] == {"extra_key": 1, "mask": 2}  # schema=0 不出现


class TestNewConsumer:
    """_new_consumer 构造（aiokafka 0.14 topics 为位置参数）。D6 集成抓到的坑回归锁。"""

    def test_topics_positional_not_keyword(self, monkeypatch):
        # aiokafka 0.14：AIOKafkaConsumer(*topics, ...) topics 是 VAR_POSITIONAL，
        # 传 keyword topics= 会 TypeError —— D6 集成验证（真 consumer 启动）暴露，
        # 单测曾只测纯函数未覆盖此构造。monkeypatch 假 consumer 录调用校验。
        import app.consumer.main as consumer_main

        captured = {}

        class FakeConsumer:
            def __init__(self, *topics, **kwargs):
                captured["topics"] = topics
                captured["kwargs"] = kwargs

            async def start(self):  # 契约面：ConsumerApp 生命周期按此调
                pass

            async def stop(self):
                pass

        monkeypatch.setattr(consumer_main, "AIOKafkaConsumer", FakeConsumer)
        app = ConsumerApp(settings())
        app._new_consumer(["dev.obs.agent.good-question"])
        # topics 走位置参数；group/enable_auto_commit 等仍 keyword
        assert captured["topics"] == ("dev.obs.agent.good-question",)
        kw = captured["kwargs"]
        assert kw["group_id"] == "dev.obs.consumer"
        assert kw["enable_auto_commit"] is False
        assert kw["auto_offset_reset"] == "earliest"


class TestConsumerLoopLifecycle:
    """agent/selfmonitor 循环生命周期：先 start 再 async for + 异常退避重连。

    真 aiokafka 漏 start 直接 async for 会崩 `_coordinator is None`（getone → check_errors，
    D6 集成抓到的第 4 坑）。FakeConsumer 复刻该形态：未 start 的 next 抛 AttributeError；
    首 consumer 迭代抛普通异常（走重连），重连后的 consumer 迭代抛 CancelledError（收尾）。
    """

    @pytest.mark.asyncio
    async def test_agent_loop_starts_consumer_and_reconnects(self, monkeypatch):
        import asyncio

        import app.consumer.main as consumer_main

        made: list = []   # 构造次数（= 消费循环轮数）
        started: list = []  # start() 调用次数
        iters: list = []   # 进入 async for 取值次数

        class FakeConsumer:
            def __init__(self, *topics, **kwargs):
                made.append(topics)

            async def start(self):
                started.append(1)

            async def stop(self):
                pass

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not started:   # 未 start 就迭代 = 复刻 aiokafka 崩溃形态
                    raise AttributeError("'_coordinator' is None（未 start 就迭代）")
                iters.append(1)
                if len(made) == 1:  # 首 consumer 故障 → 走退避重连
                    raise RuntimeError("模拟消费故障")
                raise asyncio.CancelledError  # 重连后第二 consumer：取消收尾

        monkeypatch.setattr(consumer_main, "AIOKafkaConsumer", FakeConsumer)
        monkeypatch.setattr(consumer_main, "_backoff", lambda n: 0)  # 退避归零加速
        app = ConsumerApp(settings())

        try:
            await app._agent_loop("good-question")
            raise AssertionError("应以 CancelledError 结束（重连消费被收尾取消）")
        except asyncio.CancelledError:
            pass

        # 首故障 → 退避 → 重连再造：构造 2 轮、每轮 start 后进入迭代
        assert len(made) == 2
        assert len(started) == 2 and len(iters) == 2


class TestHandleMessage:
    """_handle_agent_message offset 提交走 consumer 对象（aiokafka 无 msg.consumer）。

    D6 集成抓到的第 5 坑：曾用 `msg.consumer.commit()` 崩 AttributeError——commit API
    在 AIOKafkaConsumer 上，ConsumerRecord 不携带 consumer。FakeMsg 刻意不提供
    .consumer 属性复刻真实形态。
    """

    @pytest.mark.asyncio
    async def test_commit_uses_consumer_arg(self):
        committed: list = []

        class FakeConsumer:
            async def commit(self):
                committed.append(1)

        class FakeMsg:
            value = b'{"schema_version": "1.0"}'  # 缺必填字段 → schema 丢弃路径

        app = ConsumerApp(settings())
        await app._handle_agent_message(FakeMsg(), FakeConsumer(), "good-question")
        assert committed == [1]  # 丢弃即 commit；若回退 msg.consumer 会在 FakeMsg 上 AttributeError
        assert app.dropped.per_agent() == {"good-question": {"schema": 1}}


class TestDroppedCounter:
    def test_bump_and_snapshot_copies(self):
        c = DroppedCounter()
        c.bump("gq", DropCode.SCHEMA.value)
        c.bump("gq", DropCode.SCHEMA.value)
        c.bump("gq", DropCode.MASK.value)
        snap = c.per_agent()
        assert snap == {"gq": {"schema": 2, "mask": 1}}
        # 快照是拷贝：外部改写不影响计数器
        snap["gq"]["schema"] = 999
        assert c.per_agent()["gq"]["schema"] == 2

    def test_multi_agent_isolated(self):
        c = DroppedCounter()
        c.bump("gq", DropCode.MASK.value)
        c.bump("cs", DropCode.SCHEMA.value)
        assert c.per_agent() == {"gq": {"mask": 1}, "cs": {"schema": 1}}
