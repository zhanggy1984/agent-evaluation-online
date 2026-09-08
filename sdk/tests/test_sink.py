"""_sink 白盒单测：入队丢弃计数 / 发送失败降级 spool / spool 补传 / topic 域路由。

直接构造 Sink 实例注入 producer（不经 init 后台线程），手动调 _flush_once 触发发送。
退避重试有真实 sleep（1s/2s），失败路径测试用 monkeypatch SEND_RETRY=1 取消重试等待。
"""
from __future__ import annotations

import json
import queue

from _fakes import FailingProducer, FakeProducer

import obs_sdk._sink as sink_mod
from obs_sdk._sink import EVENT_TOPIC, HB_TOPIC, Sink

AGENT = "good-question"
AGENT_TOPIC = "dev.obs.agent.good-question"


def _make_sink(tmp_path=None, **kwargs) -> Sink:
    return Sink("nohost:1", agent=AGENT, agent_topic=AGENT_TOPIC,
                spool_dir=str(tmp_path) if tmp_path else None, **kwargs)


def test_topic_domain_routing(tmp_path):
    sink = _make_sink(tmp_path)
    assert sink._target_topic(EVENT_TOPIC) == AGENT_TOPIC
    # §3.6：agent topic = {env}.obs.agent.{name} → env.obs.selfmonitor
    assert sink._target_topic(HB_TOPIC) == "dev.obs.selfmonitor"


def test_producer_no_value_serializer():
    """#89 冒烟实测回归：producer 装配禁 value_serializer。

    本层两个发送点（_send_with_retry/_send_once）均预编码为 UTF-8 bytes 再交给 producer；
    若再加 value_serializer，kafka-python 会对 bytes 二次 json.dumps → TypeError（非 KafkaError）
    逃过重试/spool/计数，静默丢事件。故装配参数必须不含 value_serializer。
    """
    sink = _make_sink()
    producer = sink._ensure_producer()
    assert "value_serializer" not in producer.kwargs, "禁止二次序列化（#89 冒烟根因）"
    # 发送路径产物是预编码 bytes（不经 serializer 直接可达 broker）
    sink._producer = producer
    sink.emit(EVENT_TOPIC, {"node": "request"})
    sink._flush_once(timeout=1)
    assert len(producer.sent) == 1
    assert isinstance(producer.sent[0][1], bytes)
    assert json.loads(producer.sent[0][1]) == {"node": "request"}


def test_send_success_no_spool(tmp_path):
    sink = _make_sink(tmp_path)
    producer = FakeProducer()
    sink._producer = producer
    sink.emit(EVENT_TOPIC, {"node": "request"})
    sink.emit(EVENT_TOPIC, {"node": "llm_call"})
    sink._flush_once(timeout=1)
    assert [t for t, _ in producer.sent] == [AGENT_TOPIC, AGENT_TOPIC]
    assert json.loads(producer.sent[0][1]) == {"node": "request"}
    assert not list(tmp_path.iterdir()), "成功路径不得落 spool"


def test_send_fail_writes_spool(monkeypatch, tmp_path):
    monkeypatch.setattr(sink_mod, "SEND_RETRY", 1)  # 免退避 sleep
    sink = _make_sink(tmp_path)
    sink._producer = FailingProducer()
    sink.emit(EVENT_TOPIC, {"node": "llm_call", "seq": 1})
    sink._flush_once(timeout=1)
    assert sink.dropped["send_fail"] == 1
    files = [p for p in tmp_path.iterdir() if p.name.endswith(".jsonl")]
    assert len(files) == 1, "发送失败应落 spool 供补传"
    payload = files[0].read_text().strip()
    assert json.loads(payload)["node"] == "llm_call"


def test_spool_replay_success(tmp_path):
    sink = _make_sink(tmp_path)
    producer = FakeProducer()
    sink._producer = producer
    spool = tmp_path / "fail-1.jsonl"
    spool.write_text(json.dumps({"a": 1}) + "\n" + json.dumps({"a": 2}) + "\n", encoding="utf-8")
    sink._replay_spool()
    assert [json.loads(payload) for _, payload in producer.sent] == [{"a": 1}, {"a": 2}]
    assert not spool.exists(), "补传成功后删除 spool 文件"


def test_spool_replay_keeps_file_on_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(sink_mod, "SEND_RETRY", 1)
    sink = _make_sink(tmp_path)
    sink._producer = FailingProducer()
    spool = tmp_path / "fail-1.jsonl"
    spool.write_text(json.dumps({"a": 1}) + "\n", encoding="utf-8")
    sink._replay_spool()
    assert spool.exists(), "补传失败保留文件下次整补"


def test_queue_full_drop_counts():
    sink = _make_sink()
    sink._queue = queue.Queue(maxsize=1)  # 缩容模拟背压
    sink.emit(EVENT_TOPIC, {"n": 1})
    sink.emit(EVENT_TOPIC, {"n": 2})  # 满 → 丢弃计数，绝不阻塞业务线程
    sink.emit(EVENT_TOPIC, {"n": 3})
    assert sink._queue.qsize() == 1
    assert sink.dropped["queue_full"] == 2


def test_no_spool_dir_drops_quietly(monkeypatch):
    monkeypatch.setattr(sink_mod, "SEND_RETRY", 1)
    sink = _make_sink()  # spool_dir=None → 纯丢弃降级（§3.2）
    sink._producer = FailingProducer()
    sink.emit(EVENT_TOPIC, {"n": 1})
    sink._flush_once(timeout=1)
    assert sink.dropped["send_fail"] == 1
    assert sink._spool_dir is None


def test_serialize_datetime_via_default_str(tmp_path):
    from datetime import datetime

    sink = _make_sink(tmp_path)
    producer = FakeProducer()
    sink._producer = producer
    sink.emit(EVENT_TOPIC, {"ts": datetime(2026, 9, 8, 12, 0, 0)})
    sink._flush_once(timeout=1)
    assert len(producer.sent) == 1, "datetime 经 default=str 转字符串发出，不炸整批"
    assert '"ts": "2026-09-08 12:00:00"' in producer.sent[0][1].decode("utf-8")


def test_unserializable_event_dropped_and_counted(tmp_path):
    class _Unstr:
        def __str__(self):
            raise RuntimeError("不可 str 化")

    sink = _make_sink(tmp_path)
    producer = FakeProducer()
    sink._producer = producer
    sink.emit(EVENT_TOPIC, {"ts": _Unstr()})
    sink._flush_once(timeout=1)
    assert sink.dropped["serialize"] == 1
    assert producer.sent == [], "序列化失败整条计数丢弃，绝不打断同批后续事件"
    assert not list(tmp_path.iterdir()), "序列化失败无法落 spool（计数降级）"
