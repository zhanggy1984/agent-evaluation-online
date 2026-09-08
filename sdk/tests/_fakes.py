"""单测替身（绝不真连 broker——dev 环境有真 Kafka，误连会污染 dev.obs.agent topic）。

KafkaProducer 替身：obs_sdk._sink 模块级名字在 conftest autouse 替换。send 记录 (topic,payload)
立即成功（返回值支持 .get），flush/close no-op；实例登记 class 级供断言取回。
Sink 替身：纯内存记录，观测 record_*/log 的 emit 行为（不经队列/线程）。
"""
from __future__ import annotations

from kafka.errors import KafkaError


class FakeProducer:
    """kafka.KafkaProducer 薄替身：send 记录即成功。instances 供断言取回真实发送序列。"""

    instances: list["FakeProducer"] = []

    def __init__(self, **kwargs) -> None:
        self.sent: list[tuple[str, bytes]] = []
        self.flushed = False
        self.closed = False
        type(self).instances.append(self)

    def send(self, topic: str, value: bytes):
        self.sent.append((topic, value))
        return self

    def get(self, timeout=None):  # noqa: ARG001  仿 FutureRecordMetadata.get
        return b"metadata"

    def flush(self, timeout=None) -> None:  # noqa: ARG001
        self.flushed = True

    def close(self, timeout=None) -> None:  # noqa: ARG001
        self.closed = True


class FailingProducer(FakeProducer):
    """send 恒抛 KafkaError（测重试/spool 降级路径）。"""

    def send(self, topic: str, value: bytes):
        raise KafkaError("broker down")


class RecordingSink:
    """Sink 替身：emit 直接记录（topic_domain, event），供 handler/processor 逻辑测试。

    实现 Sink 接口子集（含 stop——conftest teardown 会经 shutdown 调 sink.stop）。
    """

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def emit(self, topic_domain: str, event: dict) -> None:
        self.events.append((topic_domain, event))

    def stop(self, flush: bool = True) -> None:  # noqa: ARG001   teardown 兼容 no-op
        return None
