"""D4 ES 分派单测（detail §4.1 step5 / §5.2 / S-3 幂等）。

纯函数（周 index 拼装 / _id / 文档体）直测；分派与建 index 用 fake client 录调用——
不连真 ES（真 ES 冒烟留 D6 dev 集成）。S-3「同 trace 重放不重复」的 _id 幂等覆写语义
在 fake 上验证 = 重放走同一 (index, _id)（真 ES 行为 = 同 id 覆盖）。
"""
from datetime import datetime, timezone

from app.consumer.es import (
    EsDispatchError,
    build_doc,
    dispatch_event,
    doc_id,
    ensure_weekly_index,
    iso_week,
    weekly_index_name,
)
from app.consumer.schema import EventModel
from app.core.config import Settings

# 周一 09:00 UTC（周归属唯一）：2026-08-31 = ISO 2026-W36
MON_TS = int(datetime(2026, 8, 31, 9, 0, tzinfo=timezone.utc).timestamp() * 1000)
# 周日 23:00：2026-09-06 仍属 ISO W36（周日收周）
SUN_TS = int(datetime(2026, 9, 6, 23, 0, tzinfo=timezone.utc).timestamp() * 1000)

_EVT_PREFIX = "dev.obs-event"
_LOG_PREFIX = "dev.obs-log"


def settings() -> Settings:
    s = Settings(app_env="test", resource_env="dev")
    return s


def evt(agent="good-question", trace_id="tr-9f2c1a", seq=0, ts=MON_TS, **over):
    """合法 request 事件（可覆写为 log 等）。"""
    data = {
        "schema_version": "1.0", "event_kind": "event", "trace_id": trace_id, "agent": agent,
        "agent_version": "2026.08.31-r47", "interface": "POST /api/chat/{id}", "node": "request",
        "seq": seq, "parent": None, "branch": None, "ts": ts, "duration_ms": 3200, "status": "ok",
        "error_type": None, "error_msg": None, "input": None, "output": None, "usage": None,
        "model": None, "log_level": None, "log_message": None, "extra": {},
    }
    data.update(over)
    return EventModel.model_validate(data)


def log_line(agent="good-question", trace_id="tr-9f2c1a", seq=2, ts=MON_TS, **over):
    """合法 log 行（§2.2③）。"""
    data = {
        "schema_version": "1.0", "event_kind": "log", "trace_id": trace_id, "agent": agent,
        "agent_version": "2026.08.31-r47", "interface": "POST /api/chat/{id}", "node": "log",
        "seq": seq, "parent": None, "ts": ts, "status": "ok",
        "log_level": "WARNING", "log_message": "retry attempt=2", "extra": {},
    }
    data.update(over)
    return EventModel.model_validate(data)


class FakeClient:
    """录调用 fake：记 index 写入与 indices 探测/创建，可注错。"""

    def __init__(self):
        self.writes: list[dict] = []
        self.index_exists = False
        self.create_calls: list[str] = []
        self.fail_index_write = False
        self.fail_after_create = False

    async def index(self, index=None, id=None, document=None):
        if self.fail_index_write:
            raise ConnectionError("es refused")
        self.writes.append({"index": index, "id": id, "document": document})

    class _Indices:
        def __init__(self, client):
            self.client = client

        async def exists(self, index=None):
            return self.client.index_exists

        async def create(self, index=None, mappings=None, settings=None):
            if self.client.fail_after_create:
                raise Exception("resource_already_exists_exception: already exists")
            self.client.create_calls.append(
                {"index": index, "mappings": mappings, "settings": settings}
            )
            self.client.index_exists = True

    @property
    def indices(self):
        return self._Indices(self)


class TestWeekIndex:
    def test_iso_week_basic(self):
        # 周一与周日同属一周 → 同 index
        assert iso_week(MON_TS) == (2026, 36)
        assert iso_week(SUN_TS) == (2026, 36)

    def test_week_crossing(self):
        # 周日至次周一翻周；次周周一归属 2026-W37
        next_monday = int(datetime(2026, 9, 7, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
        assert iso_week(next_monday) == (2026, 37)

    def test_year_boundary_iso(self):
        # 2027-01-01 属 2026-W53（ISO 年 ≠ 日历年）——周归属按 ISO 年，检索分桶同源
        jan1 = int(datetime(2027, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp() * 1000)
        assert iso_week(jan1) == (2026, 53)

    def test_index_name_padding(self):
        assert weekly_index_name(_EVT_PREFIX, MON_TS) == "dev.obs-event-202636"
        assert weekly_index_name(_LOG_PREFIX, MON_TS) == "dev.obs-log-202636"

    def test_event_log_split(self):
        # 同 ts 同前缀源：event/log 前缀不同 → index 分列（§5.2）
        ev = weekly_index_name(_EVT_PREFIX, MON_TS)
        lg = weekly_index_name(_LOG_PREFIX, MON_TS)
        assert ev != lg and ev.endswith("202636") and lg.endswith("202636")


class TestDocId:
    def test_deterministic_and_agent_scoped(self):
        a = doc_id("gq", "tr-1", 3)
        assert a == doc_id("gq", "tr-1", 3)  # 幂等重放 → 同 id
        assert a != doc_id("cs", "tr-1", 3)  # agent 入键：防跨 agent 同 trace_id 互覆
        assert a != doc_id("gq", "tr-2", 3)
        assert a != doc_id("gq", "tr-1", 4)
        assert len(a) == 64  # sha256 hex

    def test_seq_shared_with_log(self):
        # log 行占 seq 槽位（单计数器）：event 与 log 不同 index，同 id 无碍（§5.2）
        assert doc_id("gq", "tr-1", 2) == doc_id("gq", "tr-1", 2)


class TestBuildDoc:
    def test_request_doc_fields(self):
        doc = build_doc(evt(status="error", error_type="llm_timeout",
                            error_msg="provider timeout", input={"q": "政策?"}))
        assert doc["schema_version"] == "1.0"
        assert doc["event_kind"] == "event"
        assert doc["trace_id"] == "tr-9f2c1a"
        assert doc["seq"] == 0 and doc["ts"] == MON_TS
        assert doc["status"] == "error"
        assert doc["error_type"] == "llm_timeout"
        # input 为对象 → 序列化为文本落正文（mapping text 拒收对象，§5.2）
        assert doc["input"] == '{"q": "政策?"}'
        # None 字段不入文档体
        assert "output" not in doc and "parent" not in doc and "branch" not in doc
        assert "model" not in doc and "usage" not in doc

    def test_str_and_scalar_input_kept(self):
        assert build_doc(evt(input="帮我查政策"))["input"] == "帮我查政策"
        assert build_doc(evt(input=123))["input"] == "123"  # 标量也序列化（text 拒非 str）
        assert build_doc(evt(input=True))["input"] == "true"

    def test_usage_nested_object_kept(self):
        # llm_call 合法构造：usage 嵌套对象原样入体（§5.2 mapping properties）
        doc = build_doc(evt(node="llm_call", seq=1, parent=0, duration_ms=3000,
                            usage={"prompt_tokens": 10, "completion_tokens": 0,
                                   "total_tokens": 10},
                            model="deepseek-v3"))
        assert doc["usage"] == {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10}
        assert doc["model"] == "deepseek-v3"
        assert doc["parent"] == 0  # 非根子节点 parent 值入体（供 (ts,seq,parent) 树还原）

    def test_log_doc_goes_to_log_shape(self):
        doc = build_doc(log_line())
        assert doc["event_kind"] == "log"
        assert doc["node"] == "log"
        assert doc["log_level"] == "WARNING"
        assert doc["log_message"] == "retry attempt=2"
        assert "error_type" not in doc and "duration_ms" not in doc

    def test_extra_and_quality_carried(self):
        doc = build_doc(evt(extra={"request_id": "x"}, quality={"level": "y"}))
        assert doc["extra"] == {"request_id": "x"}  # enabled:false 只存 _source 不索引
        assert doc["quality"] == {"level": "y"}


class TestDispatch:
    def test_event_writes_event_index_with_id(self):
        import asyncio

        async def run():
            client = FakeClient()
            event = evt(status="error", error_type="llm_timeout", input={"q": "a"})
            out = await dispatch_event(client, event, settings())
            assert out["index"] == "dev.obs-event-202636"
            assert out["_id"] == doc_id(event.agent, event.trace_id, event.seq)
            assert len(client.writes) == 1
            w = client.writes[0]
            assert w["index"] == out["index"] and w["id"] == out["_id"]
            assert w["document"]["input"] == '{"q": "a"}'

        asyncio.run(run())

    def test_log_writes_log_index(self):
        import asyncio

        async def run():
            client = FakeClient()
            ev = log_line()
            out = await dispatch_event(client, ev, settings())
            assert out["index"] == "dev.obs-log-202636"

        asyncio.run(run())

    def test_replay_same_index_and_id_idempotent(self):
        # S-3 语义：同 trace 事件重放 → 同 (index, _id)（真 ES 同 id 覆写，不产生第二行）
        import asyncio

        async def run():
            client = FakeClient()
            event = evt()  # 同 root（seq=0）重放
            e1 = await dispatch_event(client, event, settings())
            e2 = await dispatch_event(client, event, settings())
            assert e1 == e2
            assert client.writes[0]["id"] == client.writes[1]["id"]

        asyncio.run(run())

    def test_write_failure_raises_typed(self):
        import asyncio

        async def run():
            client = FakeClient()
            client.fail_index_write = True
            try:
                await dispatch_event(client, evt(), settings())
                raise AssertionError("应抛 EsDispatchError")
            except EsDispatchError as exc:
                assert "index=" in str(exc)  # 异常带 index/id 上下文，供 D5 计数/重试路由

        asyncio.run(run())


class TestEnsureIndex:
    def test_creates_when_missing_with_mapping(self):
        import asyncio

        async def run():
            client = FakeClient()
            index = await ensure_weekly_index(client, _EVT_PREFIX, MON_TS)
            assert index == "dev.obs-event-202636"
            assert len(client.create_calls) == 1
            call = client.create_calls[0]
            assert call["index"] == index
            assert call["mappings"]["dynamic"] is False  # §5.2 dynamic:false
            assert "input" in call["mappings"]["properties"]
            assert call["settings"]["number_of_shards"] == 1

        asyncio.run(run())

    def test_skips_when_exists(self):
        import asyncio

        async def run():
            client = FakeClient()
            client.index_exists = True
            index = await ensure_weekly_index(client, _EVT_PREFIX, MON_TS)
            assert index == "dev.obs-event-202636"
            assert client.create_calls == []  # 幂等：已建不重建

        asyncio.run(run())

    def test_create_race_already_exists_is_success(self):
        # exists=false 但 create 撞竞态（他实例已建）→ 不视为失败
        import asyncio

        async def run():
            client = FakeClient()
            client.fail_after_create = True
            index = await ensure_weekly_index(client, _EVT_PREFIX, MON_TS)
            assert index == "dev.obs-event-202636"

        asyncio.run(run())
