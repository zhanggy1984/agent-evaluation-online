"""T-1.4 store/es 查询层单测（detail §8.2/§14.4 护栏）。

纯函数 query body 直测 + fake client 录调用验执行层（不连真 ES——真 ES 检索留 S-5 dev
集成）。覆盖：折叠去重 + search_after 语义的 body 形状、7d 默认窗由调用方传、body_search
字段面收窄、event/log 分流与截断、request_timeout 透传。
"""
from app.core.config import Settings
from app.store.es import (
    _KEYWORD_FIELDS,
    _KEYWORD_FIELDS_BODY,
    MAX_DETAIL_EVENTS,
    build_trace_events_body,
    build_trace_list_body,
    build_trace_logs_body,
    fetch_trace_events,
    fetch_trace_logs,
    index_patterns,
    search_traces,
)


def settings() -> Settings:
    return Settings(app_env="test", resource_env="dev")


def test_index_patterns_event_log_prefixes():
    # 检索面 = event + log 两前缀（§5.2 周滚动），heartbeat/DB 事件才能一并命中
    assert index_patterns(settings()) == ["dev.obs-event-*", "dev.obs-log-*"]


def test_list_body_trace_id_uses_term_and_no_default_window():
    body = build_trace_list_body(
        trace_id="tr-abc", keyword=None, agent=None, interface=None,
        start_ts=None, end_ts=None, body_search=False, from_=0, size=20,
    )
    must = body["query"]["bool"]["must"]
    # trace_id 走 term；heartbeat 显式排除（无 trace_id 的 form A 心跳不得入检索面）
    assert {"term": {"trace_id": "tr-abc"}} in must
    assert {"term": {"node": "heartbeat"}} in body["query"]["bool"]["must_not"]
    # 折叠 + ts desc：每 trace 回最近命中行（search_after/折叠语义）
    assert body["collapse"] == {"field": "trace_key"}
    assert body["sort"] == [{"ts": {"order": "desc", "format": "epoch_millis"}}]
    assert body["from"] == 0 and body["size"] == 20
    # 去重总数走 cardinality agg（S-5 实测：collapse 不改 hits.total，见 build_trace_list_body）
    assert body["aggs"]["trace_total"] == {"cardinality": {"field": "trace_key"}}
    # 无时间范围参数 → 不产生 filter range（7d 窗由调用方算好传入，§8.2 缺省语义）
    assert body["query"]["bool"]["filter"] == []


def test_list_body_default_7d_window_from_caller():
    body = build_trace_list_body(
        trace_id=None, keyword="熔断", agent="cc", interface=None,
        start_ts=1_700_000_000_000, end_ts=None, body_search=False, from_=0, size=20,
    )
    filt = body["query"]["bool"]["filter"]
    assert {"term": {"agent": "cc"}} in filt
    assert {"range": {"ts": {"gte": 1_700_000_000_000}}} in filt


def test_keyword_body_search_false_excludes_body_fields():
    # §8.2 注 v1.1 / §13.4：body_search=false 检索面不含 input/output/log_message
    off = build_trace_list_body(
        trace_id=None, keyword="检索词", agent=None, interface=None,
        start_ts=None, end_ts=None, body_search=False, from_=0, size=20,
    )
    fields = off["query"]["bool"]["must"][0]["multi_match"]["fields"]
    assert fields == list(_KEYWORD_FIELDS)
    assert not set(_KEYWORD_FIELDS_BODY) & set(fields)

    on = build_trace_list_body(
        trace_id=None, keyword="检索词", agent=None, interface=None,
        start_ts=None, end_ts=None, body_search=True, from_=0, size=20,
    )
    fields_on = on["query"]["bool"]["must"][0]["multi_match"]["fields"]
    assert set(_KEYWORD_FIELDS_BODY) <= set(fields_on)


def test_trace_events_body_filters_log_and_sort_tree_order():
    # 详情只取 event_kind=event（日志行走 /logs 懒加载）；树序 = seq asc（§11.1 创建序单调，
    # 根锚点 seq=0 恒首位；ts asc 会让 finally 才发出的 request 沉底，S-1 实测修正）
    body = build_trace_events_body(agent="cc", trace_id="tr-1", limit=500)
    must = body["query"]["bool"]["must"]
    assert {"term": {"event_kind": "event"}} in must
    assert body["size"] == 500 and body["track_total_hits"] is True
    assert body["sort"] == [{"seq": {"order": "asc"}}]


def test_trace_logs_body_pagination():
    body = build_trace_logs_body(agent="cc", trace_id="tr-1", from_=100, size=50)
    assert {"term": {"event_kind": "log"}} in body["query"]["bool"]["must"]
    assert body["from"] == 100 and body["size"] == 50
    assert body["sort"] == [{"seq": {"order": "asc"}}]


class FakeES:
    """录调用的查询 client：search 返回 canned 响应，options 记录超时。"""

    def __init__(self, resp, exc=None):
        self._resp = resp
        self._exc = exc
        self.calls = []
        self.timeouts = []

    def options(self, **kw):
        self.timeouts.append(kw.get("request_timeout"))
        return self

    async def search(self, index=None, body=None):
        self.calls.append((index, body))
        if self._exc is not None:
            raise self._exc
        return self._resp


def _resp(total, sources):
    return {
        "hits": {
            "total": {"value": total, "relation": "eq"},
            "hits": [{"_source": s} for s in sources],
        }
    }


def _resp_agg(total_hits, sources, trace_total):
    resp = _resp(total_hits, sources)
    resp["aggregations"] = {"trace_total": {"value": trace_total}}
    return resp


def test_search_traces_runs_and_parses():
    src = {"agent": "cc", "trace_id": "tr-1", "ts": 111, "status": "error"}
    # 模拟真实 ES：hits.total=5（折叠前文档数），cardinality agg=1（去重 trace）——total 取 agg
    fake = FakeES(_resp_agg(5, [src], trace_total=1))
    out = _run(search_traces(
        fake, settings=settings(), request_timeout_s=3.0,
        trace_id=None, keyword=None, agent=None, interface=None,
        start_ts=None, end_ts=None, body_search=False, from_=0, size=20,
    ))
    assert out == {"hits": [src], "total": 1}
    # timeout 护栏透传 client.options
    assert fake.timeouts == [3.0]
    idx, body = fake.calls[0]
    assert idx == ["dev.obs-event-*", "dev.obs-log-*"]
    assert body["collapse"]["field"] == "trace_key"


def test_search_traces_fallback_to_hits_total_without_agg():
    # 无 aggregations（异常/旧 client 响应）→ 回退 hits.total，不崩
    fake = FakeES(_resp(3, [{"trace_id": "t"}]))
    out = _run(search_traces(
        fake, settings=settings(), request_timeout_s=3.0,
        trace_id=None, keyword=None, agent=None, interface=None,
        start_ts=None, end_ts=None, body_search=False, from_=0, size=20,
    ))
    assert out["total"] == 3


def test_fetch_trace_events_truncated_flag():
    # §8.2 单 trace ≤500 截断：total > limit → truncated=True
    fake = FakeES(_resp(501, [{"seq": 0}]))
    out = _run(fetch_trace_events(fake, settings=settings(), agent="cc", trace_id="t",
                                  request_timeout_s=3.0))
    assert out["truncated"] is True and out["total"] == 501
    assert fake.calls[0][1]["size"] == MAX_DETAIL_EVENTS

    fake2 = FakeES(_resp(10, []))
    out2 = _run(fetch_trace_events(fake2, settings=settings(), agent="cc", trace_id="t",
                                   request_timeout_s=3.0))
    assert out2["truncated"] is False


def test_fetch_trace_logs_from_size_forwarded():
    fake = FakeES(_resp(2, [{"seq": 1}]))
    out = _run(fetch_trace_logs(fake, settings=settings(), agent="cc", trace_id="t",
                                request_timeout_s=3.0, from_=50, size=50))
    assert out["total"] == 2
    assert fake.calls[0][1]["from"] == 50 and fake.calls[0][1]["size"] == 50


def _run(coro):
    import asyncio
    return asyncio.new_event_loop().run_until_complete(coro)
