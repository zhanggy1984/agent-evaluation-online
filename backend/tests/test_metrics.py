"""metrics 实时指标层测试（detail §8.4 + §14.4 护栏 + O-1 缓存，T-2.2）。

- store 纯 body：overview 单查询 request 锚（顶层 percentiles 合一 + series 只挂 filter 计数）、
  interfaces 单 body 双 filter agg、anomalies/llm-failures 红显 + collapse + Q2 terms≤100。
- 解析：_parse_percentiles 读 values.{50.0,95.0,99.0}、_series_rows 空桶剔除。
- API（TestClient + dependency_overrides + app.state.es_query fake）：四端点形状、window 非法
  → ERR_METRICS_0001、ES 超时 400、**缓存命中跳 ES**（二次请求 fake.calls 不增）。
- FakeAsyncSession 无 dict_config 行 → 回退 seed 默认（ttl 60 / agg timeout 3000ms）。
"""
import time
from contextlib import contextmanager

from _fakes import FakeAsyncSession, FakeES, es_hits, ns
from elasticsearch.exceptions import TransportError

import app.api.metrics as metrics_api
from app.core.config import Settings
from app.core.db import get_session
from app.core.security import create_access_token
from app.main import create_app
from app.store import es as es_store

_AGENT = "good-question"


def _settings():
    return Settings(app_env="test", resource_env="dev", jwt_secret="mock-secret-" * 8)


def _viewer(role="viewer"):
    return ns(id=1, username="alice", display_name="查看者", password_hash="x",
              role=role, status=1)


def _token(role="viewer"):
    return create_access_token(_settings(), 1, role)


def _auth_hdr(role="viewer"):
    return {"Authorization": f"Bearer {_token(role)}"}


@contextmanager
def _enter(app, fake_es):
    """TestClient 上下文 + state.es_query 换 fake；每条用例先清进程内 O-1 缓存。"""
    from fastapi.testclient import TestClient

    metrics_api._cache.clear()
    with TestClient(app) as client:
        app.state.es_query = fake_es
        yield client


def _app(es, role="viewer"):
    app = create_app(_settings())
    app.dependency_overrides[get_session] = lambda: FakeAsyncSession(users=[_viewer(role)])
    return app, es


def _overview_resp():
    # series 桶 key 贴近 now 的**内部桶**：边界覆盖宽折算（v1.14）下 ts 须落在查询窗内，
    # 否则 covered_ms<=0 → qps=None 破坏"满桶 qps=count/宽"断言。取 now 前 2/3 分钟，
    # 对 1h(1m 桶) 是满覆盖；7d 测试不查 series 数值，仅形状。
    now = int(time.time() * 1000)
    return {
        "hits": {"total": {"value": 120, "relation": "eq"}},
        "aggregations": {
            "pct": {"values": {"50.0": 12.3, "95.0": 88.4, "99.0": 154.2}},
            "err": {"doc_count": 4},
            "to": {"doc_count": 2},
            "series": {"buckets": [
                {"key": now - 180_000, "doc_count": 60,
                 "err": {"doc_count": 2}, "to": {"doc_count": 1}},
                {"key": now - 120_000, "doc_count": 60,
                 "err": {"doc_count": 2}, "to": {"doc_count": 1}},
            ]},
        },
    }


def _interfaces_resp():
    return {
        "hits": {"total": {"value": 1, "relation": "eq"}},
        "aggregations": {
            "req": {"doc_count": 120, "by_iface": {"buckets": [
                {"key": "POST /chat", "doc_count": 100,
                 "pct": {"values": {"50.0": 5.0, "95.0": 40.0, "99.0": 90.0}},
                 "err": {"doc_count": 3}, "to": {"doc_count": 1}},
            ]}},
            "llm": {"doc_count": 200, "by_iface": {"buckets": [
                {"key": "POST /chat", "doc_count": 190, "fail": {"doc_count": 5},
                 "by_model": {"buckets": [
                     {"key": "claude-sonnet", "doc_count": 150, "fail": {"doc_count": 2},
                      "pt": {"value": 1000}, "ct": {"value": 200}},
                 ]}},
            ]}},
        },
    }


def _anomaly_source(**kw):
    base = {"agent": _AGENT, "trace_id": "tr-x", "interface": "POST /chat",
            "status": "error", "error_type": "db_error", "error_msg": "连接超时",
            "ts": 1000, "duration_ms": 800}
    base.update(kw)
    return base


def _llm_fail_source(trace_key="good-question#tr-x", **kw):
    base = {"agent": _AGENT, "trace_id": "tr-x", "trace_key": trace_key,
            "interface": "POST /chat", "status": "error", "error_type": "llm_timeout",
            "error_msg": "上游超时", "model": "claude-sonnet", "ts": 1000}
    base.update(kw)
    return base


def _agents_resp(agents, distinct=None):
    """terms(agent) agg canned：桶按频次降序（key=agent, doc_count=频次）。

    distinct 缺省 = len(agents)（真实 resp 总带 cardinality agg；v1.14 起 total 读它）。
    """
    return {
        "hits": {"total": {"value": 1, "relation": "eq"}},
        "aggregations": {
            "by_agent": {"buckets": [
                {"key": a, "doc_count": n} for a, n in agents
            ]},
            "distinct": {"value": len(agents) if distinct is None else distinct},
        },
    }


# ---------- store 纯 body（查询形状） ----------


class TestStoreBodies:
    def test_overview_body_request_anchor_no_percentiles_in_series(self):
        body = es_store.build_metrics_overview_body(
            agent=None, start_ts=100, end_ts=200, interval="1m")
        # request 锚在 bool.filter；时间窗 + 排心跳都在
        q = body["query"]["bool"]["filter"]
        assert {"term": {"node": "request"}} in q
        assert {"range": {"ts": {"gte": 100, "lte": 200}}} in q
        assert body["query"]["bool"]["must_not"] == [{"term": {"node": "heartbeat"}}]
        # 顶层单一 percentiles agg；series 子聚合不背 percentiles（成本护栏）
        assert "pct" in body["aggs"] and "percentiles" in body["aggs"]["pct"]
        assert body["aggs"]["series"]["date_histogram"]["fixed_interval"] == "1m"
        assert set(body["aggs"]["series"]["aggs"]) == {"err", "to"}
        assert body["size"] == 0

    def test_overview_body_agent_filter_and_no_percentiles_in_series_aggs(self):
        body = es_store.build_metrics_overview_body(
            agent=_AGENT, start_ts=100, end_ts=200, interval="30m")
        assert {"term": {"agent": _AGENT}} in body["query"]["bool"]["filter"]
        assert body["aggs"]["series"]["date_histogram"]["fixed_interval"] == "30m"

    def test_interfaces_body_single_query_dual_filter_agg(self):
        body = es_store.build_metrics_interfaces_body(agent=_AGENT, start_ts=1, end_ts=2)
        aggs = body["aggs"]
        assert aggs["req"]["filter"] == {"term": {"node": "request"}}
        assert aggs["llm"]["filter"] == {"term": {"node": "llm_call"}}
        # agent 放外层 query（双 tab 共用），不进 filter agg
        assert {"term": {"agent": _AGENT}} in body["query"]["bool"]["filter"]
        pct = aggs["req"]["aggs"]["by_iface"]["aggs"]["pct"]["percentiles"]["percents"]
        assert pct == [50, 95, 99]
        model_aggs = aggs["llm"]["aggs"]["by_iface"]["aggs"]["by_model"]["aggs"]
        assert {"pt", "ct", "fail"} <= set(model_aggs)

    def test_anomalies_and_llm_bodies_red_status(self):
        a = es_store.build_anomalies_body(agent=None, start_ts=1, end_ts=2, size=50)
        assert {"term": {"node": "request"}} in a["query"]["bool"]["filter"]
        assert a["size"] == 50
        # v1.14：列表截断提示需真实 total → 关闭 hits.total 近似（截断语义 §8.4）
        assert a["track_total_hits"] is True
        lf = es_store.build_llm_failures_body(agent=None, start_ts=1, end_ts=2, size=50)
        assert lf["collapse"] == {"field": "trace_key"}
        assert {"term": {"node": "llm_call"}} in lf["query"]["bool"]["filter"]
        # collapse 不改 hits.total → trace_total 单独 cardinality(trace_key)（去重失败 trace 总数）
        assert lf["aggs"]["trace_total"] == {"cardinality": {"field": "trace_key"}}

    def test_request_statuses_body_caps_terms_at_100(self):
        body = es_store.build_request_statuses_body([f"t{i}" for i in range(150)])
        terms = [f for f in body["query"]["bool"]["filter"] if "terms" in f][0]
        assert len(terms["terms"]["trace_key"]) == 100  # §14.4 terms 护栏

    def test_agents_body_request_anchor_terms_no_agent_filter(self):
        body = es_store.build_agents_body(start_ts=1, end_ts=2)
        q = body["query"]["bool"]["filter"]
        assert {"term": {"node": "request"}} in q
        assert {"range": {"ts": {"gte": 1, "lte": 2}}} in q
        # terms(agent) 聚合；纯实测 —— 不并白名单，故无 agent 过滤（全量 request 去重）
        assert body["aggs"]["by_agent"] == {"terms": {"field": "agent", "size": 100}}
        # v1.14：distinct cardinality(agent) = 真实去重总数（terms top100 截断后支撑 truncated）
        assert body["aggs"]["distinct"] == {"cardinality": {"field": "agent"}}
        assert body["size"] == 0

    def test_parse_percentiles_and_series_rows(self):
        p = es_store._parse_percentiles({"pct": {"values": {"50.0": 5, "95.0": 40, "99.0": 90}}})
        assert p == {"50": 5.0, "95": 40.0, "99": 90.0}
        assert es_store._parse_percentiles({}) == {"50": None, "95": None, "99": None}
        rows = es_store._series_rows([
            {"key": 1000, "doc_count": 10, "err": {"doc_count": 1}, "to": {"doc_count": 0}},
            {"key": 0, "doc_count": 0},
        ])
        assert len(rows) == 1 and rows[0]["count"] == 10  # 空桶(key=0)剔除


# ---------- API 四端点（鉴权/形状/错误/缓存） ----------


class TestOverviewEndpoint:
    def test_overview_ok_shape_and_body(self):
        app, es = _app(FakeES(response=_overview_resp()))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/overview", headers=_auth_hdr(),
                      params={"window": "1h"})
        assert r.status_code == 200
        body = r.json()
        assert body["window"] == "1h" and body["agent"] is None
        assert body["source"] == "realtime" and body["fallback_hours"] == []
        assert body["covered_hours"] == 0  # 分位标注仅 7d rollup 语义；1h 恒 0
        cards = body["cards"]
        assert cards["total"] == 120 and cards["error"] == 4 and cards["timeout"] == 2
        assert cards["p50"] == 12.3 and cards["p99"] == 154.2
        assert abs(cards["error_rate"] - 4 / 120) < 1e-9
        assert abs(cards["qps"] - 120 / 3600) < 1e-9
        assert len(body["series"]) == 2
        point = body["series"][0]
        assert point["count"] == 60 and abs(point["qps"] - 1.0) < 1e-9
        # body 断言：window=1h → series 桶宽 1m，store 只发一次 search
        assert len(es.calls) == 1
        assert es.calls[0][1]["aggs"]["series"]["date_histogram"]["fixed_interval"] == "1m"

    def test_overview_7d_realtime_fallback_shape(self):
        # rollup index 未就位/无覆盖：meta 探测空 + request 组 doc 空 → 整窗实时兜底
        # source=realtime、fallback_hours=[]（无覆盖时缺口列表无意义）
        app, es = _app(FakeES(responses=[
            es_hits(0, []),      # ① meta 覆盖探测
            es_hits(0, []),      # ② request 组 doc（merge 源，空）
            _overview_resp(),    # ③ 实时整窗 agg（series 桶宽 1h）
        ]))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/overview", headers=_auth_hdr(),
                      params={"agent": _AGENT, "window": "7d"})
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "realtime" and body["agent"] == _AGENT
        assert body["fallback_hours"] == []
        assert body["covered_hours"] == 0  # 无覆盖 → 无已 rollup 小时可标
        # 7d 读 rollup index 两次（meta 覆盖探测 + request 组 doc）→ 实时兜底 agg（桶宽 1h）
        assert len(es.calls) == 3
        assert es.calls[0][0] == "dev.obs-metrics-rollup"
        assert es.calls[1][0] == "dev.obs-metrics-rollup"
        assert es.calls[2][1]["aggs"]["series"]["date_histogram"]["fixed_interval"] == "1h"
        # 无覆盖 → 卡片分位仍来自实时整窗 agg（不 merge）
        assert body["cards"]["p50"] == 12.3

    def test_overview_7d_mixed_rollup_covered_percentiles(self):
        # rollup 覆盖部分小时（mixed）：卡片 p50/95/99 = 覆盖小时 sketch merge 近似口径；
        # total/error/timeout 仍实时整窗；fallback = 边界 - 覆盖小时
        import time

        from app.store.metrics_rollup import hour_key_of
        from app.store.tdigest import TDigest

        dig = TDigest()
        for _ in range(40):  # 主体 600ms
            dig.update(600, 1)
        for _ in range(20):  # 尾部 3000ms → p95/p99 落在高值段
            dig.update(3000, 1)
        dig.compress()
        # window 内某个已完成 UTC 整点小时（取 now 前 2h 对齐整点，保证在 7d 窗内）
        hour_ms = int(time.time() * 1000)
        hour_ms -= hour_ms % 3_600_000
        hour_ms -= 3_600_000 * 2
        rollup_docs = [
            # request 粒度 group doc：ts=小时起点、sketch 携带该小时 duration 分布
            {"doc_type": "group", "agent": _AGENT, "interface": "POST /chat",
             "node": "request", "model": "", "hour": "2026-09-06T00:00",
             "ts": hour_ms, "total": 63, "error": 1, "timeout": 1,
             "prompt_tokens": 0, "completion_tokens": 0, "sketch": dig.serialize()},
            # llm 粒度不计入 covered/merge（overview 是 request 锚）
            {"doc_type": "group", "agent": _AGENT, "interface": "POST /chat",
             "node": "llm_call", "model": "m", "hour": "2026-09-06T00:00",
             "ts": hour_ms, "total": 50, "error": 1, "timeout": 1,
             "prompt_tokens": 0, "completion_tokens": 0, "sketch": dig.serialize()},
        ]
        meta_doc = {"doc_type": "meta", "hour": hour_key_of(hour_ms),
                    "source_count": 63}  # 该小时已 rollup（含覆盖判别基准）
        app, es = _app(FakeES(responses=[
            es_hits(1, [meta_doc]),   # ① meta 覆盖探测 → hour_ms 已覆盖
            es_hits(2, rollup_docs),  # ② request 组 doc（merge 源）
            _overview_resp(),         # ③ 实时整窗 agg
        ]))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/overview", headers=_auth_hdr(),
                      params={"agent": _AGENT, "window": "7d"})
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "mixed"  # 有覆盖 + 有缺桶（其余已闭合小时未 rollup）
        assert body["covered_hours"] == 1  # 单个已 rollup 小时（meta 判别）
        cards = body["cards"]
        # total/error/timeout 仍实时整窗（120/4/2，非 merge 出的 63/1/1）
        assert cards["total"] == 120 and cards["error"] == 4 and cards["timeout"] == 2
        # p50/p95/p99 已被覆盖小时 merge 覆盖（≈600 / ≈3000），与实时 canned 值(12.3/88.4/154.2)不同
        assert cards["p50"] < 900 and cards["p95"] > 2000 and cards["p99"] > 2000
        # fallback_hours = 已闭合小时边界 - 覆盖小时（当前进行中小时不计缺口）
        assert hour_ms not in body["fallback_hours"]
        # rollup 读两次（meta 覆盖探测 + request 组 doc）+ 实时 agg 一次
        assert len(es.calls) == 3
        assert es.calls[0][0] == "dev.obs-metrics-rollup"
        assert es.calls[0][1]["query"]["bool"]["filter"][0] == {"term": {"doc_type": "meta"}}
        assert es.calls[1][0] == "dev.obs-metrics-rollup"

    def test_overview_7d_meta_only_empty_hour_is_not_fallback(self):
        # 空小时（rollup 已处理、零 request 流量 → 有 meta 无组 doc）不得当缺口：
        # covered 以 meta 判别 → E 不在 fallback_hours；F（有数据小时）同样不在
        import time

        from app.store.metrics_rollup import hour_key_of
        from app.store.tdigest import TDigest

        now_hour = time.time() * 1000
        now_hour -= now_hour % 3_600_000
        hour_e = int(now_hour) - 3_600_000 * 3  # 早一小时：meta-only（空）
        hour_f = int(now_hour) - 3_600_000 * 2  # 近一小时：meta + 组 doc（有数据）
        dig = TDigest()
        for _ in range(40):
            dig.update(600, 1)
        for _ in range(20):
            dig.update(3000, 1)
        dig.compress()
        rollup_docs = [
            {"doc_type": "group", "agent": _AGENT, "interface": "POST /chat",
             "node": "request", "model": "", "hour": hour_key_of(hour_f),
             "ts": hour_f, "total": 60, "error": 0, "timeout": 0,
             "prompt_tokens": 0, "completion_tokens": 0, "sketch": dig.serialize()},
        ]
        meta_docs = [
            {"doc_type": "meta", "hour": hour_key_of(hour_e), "source_count": 0},
            {"doc_type": "meta", "hour": hour_key_of(hour_f), "source_count": 60},
        ]
        app, es = _app(FakeES(responses=[
            es_hits(2, meta_docs),    # ① meta 覆盖探测 → E/F 均已处理（E 零流量）
            es_hits(1, rollup_docs),  # ② request 组 doc：仅 F 有数据（E 无组 doc）
            _overview_resp(),         # ③ 实时整窗 agg
        ]))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/overview", headers=_auth_hdr(),
                      params={"agent": _AGENT, "window": "7d"})
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "mixed"  # E/F 覆盖，其余已闭合小时缺桶
        assert body["covered_hours"] == 2  # E/F 两个已 rollup 小时（含空小时 E，meta 判别）
        assert hour_e not in body["fallback_hours"]  # 空但已处理 → 非缺口
        assert hour_f not in body["fallback_hours"]
        assert len(body["fallback_hours"]) > 0
        assert body["cards"]["p95"] > 2000  # merge 只来自 F 的 sketch

    def test_invalid_window_400_before_es(self):
        app, es = _app(FakeES(response=_overview_resp()))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/overview", headers=_auth_hdr(), params={"window": "2h"})
        assert r.status_code == 400 and r.json()["code"] == "ERR_METRICS_0001"
        assert es.calls == []  # 纯参数护栏，未触 ES

    def test_es_timeout_maps_400(self):
        app, es = _app(FakeES(exc=TransportError("模拟聚合超时")))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/overview", headers=_auth_hdr())
        assert r.status_code == 400 and r.json()["code"] == "ERR_METRICS_0001"

    def test_cache_hit_skips_es(self):
        # O-1：二次请求（同 endpoint|agent|window）缓存命中 → fake.calls 不增
        app, es = _app(FakeES(response=_overview_resp()))
        with _enter(app, es) as c:
            first = c.get("/api/v1/metrics/overview", headers=_auth_hdr())
            second = c.get("/api/v1/metrics/overview", headers=_auth_hdr())
        assert first.status_code == 200 and second.status_code == 200
        assert len(es.calls) == 1  # 第二次跳过 ES

    def test_requires_viewer(self):
        app, es = _app(FakeES(response=_overview_resp()), role="ops")
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/overview", headers=_auth_hdr("ops"))
        assert r.status_code == 403 and r.json()["code"] == "ERR_AUTH_0002"


class TestOverviewSeriesPartials:
    """_overview_series 边界桶 QPS 覆盖宽折算（v1.14 缺陷修，纯函数）。

    ES date_histogram 对齐整边界 → 首桶左越 window_start、尾桶（进行中小时）右越
    window_end；按满桶宽除会虚低（右端爬坡假象）。逐桶 covered_ms 折算；覆盖=0 守卫 None。
    """

    def test_leading_trailing_full_buckets_width_semantics(self):
        start, end, width_s = 100_000, 200_000, 60
        rows = [
            {"ts": 50_000, "count": 60, "error": 0, "timeout": 0},    # 首桶左越窗，覆盖 10s
            {"ts": 110_000, "count": 600, "error": 0, "timeout": 0},  # 内部满桶 60s
            {"ts": 190_000, "count": 60, "error": 0, "timeout": 0},   # 尾桶右越窗，覆盖 10s
        ]
        pts = metrics_api._overview_series(rows, width_s, start, end)
        assert pts[0].qps == 60 / 10
        assert pts[1].qps == 600 / 60
        assert pts[2].qps == 60 / 10
        # error/timeout_rate 分母仍是桶内 count（与覆盖宽无关）
        assert pts[1].count == 600

    def test_out_of_window_bucket_guard_returns_none(self):
        # 理论越界（桶完全在窗外，生产不会出现，纯守卫）：covered_ms<=0 → qps None
        pts = metrics_api._overview_series(
            [{"ts": 9_000_000, "count": 5, "error": 0, "timeout": 0}], 60, 100_000, 200_000)
        assert pts[0].qps is None


class TestInterfacesEndpoint:
    def test_interfaces_shape_dual_tabs(self):
        app, es = _app(FakeES(response=_interfaces_resp()))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/interfaces", headers=_auth_hdr(),
                      params={"window": "24h"})
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "realtime" and len(body["fallback_hours"]) == 0
        req = body["request"][0]
        assert req["interface"] == "POST /chat" and req["total"] == 100
        assert req["p95"] == 40.0 and req["error"] == 3
        llm = body["llm"][0]
        assert llm["total"] == 190 and abs(llm["llm_failure_rate"] - 5 / 190) < 1e-9
        m = llm["models"][0]
        assert m["model"] == "claude-sonnet" and m["prompt_tokens"] == 1000
        assert es.calls[0][1]["aggs"]["llm"]["filter"] == {"term": {"node": "llm_call"}}

    def test_interfaces_es_error_400(self):
        app, es = _app(FakeES(exc=TransportError("ES down")))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/interfaces", headers=_auth_hdr())
        assert r.status_code == 400 and r.json()["code"] == "ERR_METRICS_0001"


class TestAnomaliesEndpoint:
    def test_anomalies_shape_and_node_filter(self):
        src = [_anomaly_source(), _anomaly_source(status="timeout", trace_id="tr-y")]
        app, es = _app(FakeES(response=es_hits(2, src)))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/anomalies", headers=_auth_hdr(),
                      params={"window": "1h", "agent": _AGENT})
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 2
        assert body["total"] == 2 and body["truncated"] is False
        item = body["items"][0]
        assert item["status"] == "error" and item["error_type"] == "db_error"
        assert item["trace_id"] and item["duration_ms"] == 800
        q = es.calls[0][1]["query"]["bool"]["filter"]
        assert {"term": {"node": "request"}} in q
        assert {"term": {"agent": _AGENT}} in q

    def test_anomalies_total_truncated_hint(self):
        # hits.total(5) > 返回条数(2) → truncated True：UI 渲染"仅显示最新 N 条"
        src = [_anomaly_source(), _anomaly_source(status="timeout", trace_id="tr-y")]
        app, es = _app(FakeES(response=es_hits(5, src)))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/anomalies", headers=_auth_hdr())
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 2
        assert body["total"] == 5 and body["truncated"] is True


class TestLlmFailuresEndpoint:
    def test_llm_failures_two_hop_with_request_status(self):
        # Q1（折叠 llm_call 失败现场）+ Q2（同 trace request 归属：ok = 兜底吸收现场）
        q1 = es_hits(2, [
            _llm_fail_source("good-question#tr-x"),
            _llm_fail_source("good-question#tr-y", status="timeout", trace_id="tr-y"),
        ])
        q2 = es_hits(1, [
            {"trace_key": "good-question#tr-x", "status": "ok"},
        ])
        app, es = _app(FakeES(responses=[q1, q2]))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/llm-failures", headers=_auth_hdr())
        assert r.status_code == 200
        body = r.json()
        items = body["items"]
        assert len(items) == 2 and len(es.calls) == 2  # Q1 → Q2
        assert body["total"] == 2 and body["truncated"] is False  # 无 agg → 回退 hits.total
        by_trace = {it["trace_id"]: it for it in items}
        assert by_trace["tr-x"]["request_status"] == "ok"  # request ok + llm error
        assert by_trace["tr-x"]["llm_node_status"] == "error"
        assert by_trace["tr-x"]["llm_error_type"] == "llm_timeout"
        assert by_trace["tr-x"]["model"] == "claude-sonnet"
        assert by_trace["tr-y"]["request_status"] is None  # Q2 未命中 → 不做兜底猜测
        assert es.calls[0][1]["collapse"] == {"field": "trace_key"}

    def test_llm_failures_total_from_cardinality_agg_truncated(self):
        # collapse 不改 hits.total → total 走 trace_total cardinality agg（去重失败 trace 数）
        q1 = {
            "hits": {"total": {"value": 7, "relation": "eq"}, "hits": [
                {"_source": _llm_fail_source("good-question#tr-x")},
                {"_source": _llm_fail_source("good-question#tr-y",
                                             status="timeout", trace_id="tr-y")},
            ]},
            "aggregations": {"trace_total": {"value": 7}},
        }
        app, es = _app(FakeES(responses=[q1, es_hits(0, [])]))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/llm-failures", headers=_auth_hdr())
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 2
        assert body["total"] == 7 and body["truncated"] is True
        # Q1 body 携带 trace_total cardinality agg
        agg = es.calls[0][1]["aggs"]["trace_total"]
        assert agg == {"cardinality": {"field": "trace_key"}}

    def test_llm_failures_es_error_400(self):
        app, es = _app(FakeES(exc=TransportError("模拟超时")))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/llm-failures", headers=_auth_hdr())
        assert r.status_code == 400 and r.json()["code"] == "ERR_METRICS_0001"


class TestAgentsEndpoint:
    def test_agents_ok_shape_and_order(self):
        # 桶按频次降序由 ES terms 保证；API 层只透传 key 列表（纯实测，不含配置白名单）
        app, es = _app(FakeES(response=_agents_resp([
            ("good-question", 300), ("smart-procurement", 80), ("customer-service", 20),
        ])))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/agents", headers=_auth_hdr())
        assert r.status_code == 200
        body = r.json()
        assert body["agents"] == ["good-question", "smart-procurement", "customer-service"]
        assert body["total"] == 3 and body["truncated"] is False  # distinct=len 未截断
        # 固定 7d 窗：range 下界 ≈ now-7d（上界 now）；只发一次 search
        assert len(es.calls) == 1
        index, qbody = es.calls[0]
        assert "metrics-rollup" not in index  # agents 走实时事件 index，非 rollup
        assert qbody["aggs"]["distinct"] == {"cardinality": {"field": "agent"}}
        rng = [f for f in qbody["query"]["bool"]["filter"]
               if "range" in f][0]["range"]["ts"]
        assert rng["lte"] - rng["gte"] == 7 * 24 * 3_600_000

    def test_agents_distinct_total_truncated_hint(self):
        # top3 桶 + 真实去重 7 个 → total=7、truncated=True（下拉只列最活跃 3 个）
        app, es = _app(FakeES(response=_agents_resp([
            ("good-question", 300), ("smart-procurement", 80), ("customer-service", 20),
        ], distinct=7)))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/agents", headers=_auth_hdr())
        assert r.status_code == 200
        body = r.json()
        assert len(body["agents"]) == 3
        assert body["total"] == 7 and body["truncated"] is True

    def test_agents_no_distinct_agg_falls_back_to_len(self):
        # 无 distinct agg（低版本 ES / 测试替身）→ total 回退 len(agents)，truncated=False
        resp = {
            "hits": {"total": {"value": 1, "relation": "eq"}},
            "aggregations": {"by_agent": {"buckets": [
                {"key": "good-question", "doc_count": 300},
                {"key": "smart-procurement", "doc_count": 80},
            ]}},
        }
        app, es = _app(FakeES(response=resp))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/agents", headers=_auth_hdr())
        assert r.status_code == 200
        body = r.json()
        assert body["agents"] == ["good-question", "smart-procurement"]
        assert body["total"] == 2 and body["truncated"] is False

    def test_agents_es_error_400(self):
        app, es = _app(FakeES(exc=TransportError("模拟超时")))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/agents", headers=_auth_hdr())
        assert r.status_code == 400 and r.json()["code"] == "ERR_METRICS_0001"

    def test_agents_cache_hit_skips_es(self):
        app, es = _app(FakeES(response=_agents_resp([("good-question", 300)])))
        with _enter(app, es) as c:
            first = c.get("/api/v1/metrics/agents", headers=_auth_hdr())
            second = c.get("/api/v1/metrics/agents", headers=_auth_hdr())
        assert first.status_code == 200 and second.status_code == 200
        assert len(es.calls) == 1  # O-1：二次命中缓存跳 ES

    def test_agents_requires_viewer(self):
        app, es = _app(FakeES(response=_agents_resp([])), role="ops")
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/agents", headers=_auth_hdr("ops"))
        assert r.status_code == 403 and r.json()["code"] == "ERR_AUTH_0002"
