"""metrics 实时指标层测试（detail §8.4 + §14.4 护栏 + O-1 缓存，T-2.2）。

- store 纯 body：overview 单查询 request 锚（顶层 percentiles 合一 + series 只挂 filter 计数）、
  interfaces 单 body 双 filter agg、anomalies/llm-failures 红显 + collapse + Q2 terms≤100。
- 解析：_parse_percentiles 读 values.{50.0,95.0,99.0}、_series_rows 空桶剔除。
- API（TestClient + dependency_overrides + app.state.es_query fake）：四端点形状、window 非法
  → ERR_METRICS_0001、ES 超时 400、**缓存命中跳 ES**（二次请求 fake.calls 不增）。
- FakeAsyncSession 无 dict_config 行 → 回退 seed 默认（ttl 60 / agg timeout 3000ms）。
"""
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
    return {
        "hits": {"total": {"value": 120, "relation": "eq"}},
        "aggregations": {
            "pct": {"values": {"50.0": 12.3, "95.0": 88.4, "99.0": 154.2}},
            "err": {"doc_count": 4},
            "to": {"doc_count": 2},
            "series": {"buckets": [
                {"key": 1000, "doc_count": 60, "err": {"doc_count": 2}, "to": {"doc_count": 1}},
                {"key": 2000, "doc_count": 60, "err": {"doc_count": 2}, "to": {"doc_count": 1}},
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
        lf = es_store.build_llm_failures_body(agent=None, start_ts=1, end_ts=2, size=50)
        assert lf["collapse"] == {"field": "trace_key"}
        assert {"term": {"node": "llm_call"}} in lf["query"]["bool"]["filter"]

    def test_request_statuses_body_caps_terms_at_100(self):
        body = es_store.build_request_statuses_body([f"t{i}" for i in range(150)])
        terms = [f for f in body["query"]["bool"]["filter"] if "terms" in f][0]
        assert len(terms["terms"]["trace_key"]) == 100  # §14.4 terms 护栏

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
        item = body["items"][0]
        assert item["status"] == "error" and item["error_type"] == "db_error"
        assert item["trace_id"] and item["duration_ms"] == 800
        q = es.calls[0][1]["query"]["bool"]["filter"]
        assert {"term": {"node": "request"}} in q
        assert {"term": {"agent": _AGENT}} in q


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
        items = r.json()["items"]
        assert len(items) == 2 and len(es.calls) == 2  # Q1 → Q2
        by_trace = {it["trace_id"]: it for it in items}
        assert by_trace["tr-x"]["request_status"] == "ok"  # request ok + llm error
        assert by_trace["tr-x"]["llm_node_status"] == "error"
        assert by_trace["tr-x"]["llm_error_type"] == "llm_timeout"
        assert by_trace["tr-x"]["model"] == "claude-sonnet"
        assert by_trace["tr-y"]["request_status"] is None  # Q2 未命中 → 不做兜底猜测
        assert es.calls[0][1]["collapse"] == {"field": "trace_key"}

    def test_llm_failures_es_error_400(self):
        app, es = _app(FakeES(exc=TransportError("模拟超时")))
        with _enter(app, es) as c:
            r = c.get("/api/v1/metrics/llm-failures", headers=_auth_hdr())
        assert r.status_code == 400 and r.json()["code"] == "ERR_METRICS_0001"
