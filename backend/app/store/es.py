"""链路检索查询侧 ES 层（detail §8.2 + §14.4 护栏）。与 consumer/es.py（写侧）对称但独立：

- **只做查询、不声明 mapping**（不复制映射防漂移；mapping 权威源 = consumer/es.py::_MAPPING，
  见 es-template/README）。
- client 生命周期归 API lifespan（app.state.es_query，main.py 建/关）——与 consumer 私有
  `self._es` 独立，防 D6 已绿测试回归。本层函数收 client 入参，单测注入 fake client 断言
  query body。
- 检索 index pattern = event/log 两前缀 + `-*` 都查（周滚动 §5.2，keyword 命中 log_message
  也可能落在 log index）。
- **护栏（§8.2/§14.4）**：所有查询 request_timeout 由调用方传秒数（trace_query_timeout_ms
  dict 键 / 3000ms，seed 默认）；trace 列表结果 ≤200（分页深度上限）；详情单 trace ≤500
  截断 + truncated；日志懒加载分页。
- **响应字段裁剪**在 api/trace.py 做（正文置空/白名单取 key）；本层只把 ES hit 原样上抛，
  不做字段级处理——正文保护（body_search=false 置空 input/output/log_message）属接口层
  义务（detail §8.2 注 v1.1）。
"""
from typing import Any

from app.core.config import Settings

# 结果上限护栏（detail §8.2：单 trace ≤500 截断；trace 列表 ≤200 引导缩小范围）
MAX_LIST_RESULTS = 200
MAX_DETAIL_EVENTS = 500

# heartbeat 是平台自监控 doc（§3.6 form A，无 trace_id/event_kind）；检索面须显式排除，
# 否则按 agent 过滤的列表会混入心跳行。node=log 行的 event_kind=log，随 event_kind 筛分。
_NODE_HEARTBEAT = {"term": {"node": "heartbeat"}}


def index_patterns(settings: Settings) -> list[str]:
    """检索 index 集：事件 + 日志两前缀周滚动全量（template 接管后按需建）。"""
    return [f"{settings.event_index_prefix}-*", f"{settings.log_index_prefix}-*"]


# keyword 命中字段随 body_search 开关（§8.2 注 v1.1 两层不泄露正文）：
# body_search=false（默认）不检索/不返回正文三字段，仅 error_msg/error_type 可命中；
# true 才把 input/output/log_message 纳入检索面。
_KEYWORD_FIELDS = ("error_msg", "error_type")
_KEYWORD_FIELDS_BODY = ("input", "output", "log_message")


def build_trace_list_body(
    *,
    trace_id: str | None,
    keyword: str | None,
    agent: str | None,
    interface: str | None,
    start_ts: int | None,
    end_ts: int | None,
    body_search: bool,
    from_: int,
    size: int,
) -> dict:
    """GET /traces query body：按 (agent, trace_id) 折叠去重，每 trace 取 ts desc 最新命中行。

    - 折叠键 = concrete `trace_key`（agent#trace_id，keyword/doc_values，consumer 分派时写入
      es.py::_MAPPING，勿在 runtime_mappings 里做——collapse 不支持 runtime 字段，实测 400）。
      一个 trace 只回最近命中行；from/size 在折叠结果上翻页（深分页 ≤200）。
    - **总数口径（S-5 实测修正）**：collapse 不改 hits.total（它仍是折叠前命中文档数）——
      去重 trace 总数另用 `aggs.trace_total = cardinality(trace_key)` 求（精确到
      precision_threshold，默认 3000 > 列表上限 200，够用）；详情/日志非折叠，继续走 hits.total。
    - 排序 ts desc 让"最近命中"代表行上浮；命中行携带该 trace 最近状态/节点供列表行展示。
    - 默认时间窗（7d，keyword_search_days）由调用方算好 start_ts 传入，本层不读表。
    """
    must: list[dict] = []
    filter_: list[dict] = []
    if trace_id:
        must.append({"term": {"trace_id": trace_id}})
    if keyword:
        fields = list(_KEYWORD_FIELDS)
        if body_search:
            fields += list(_KEYWORD_FIELDS_BODY)
        must.append({"multi_match": {"query": keyword, "fields": fields, "type": "best_fields"}})
    if agent:
        filter_.append({"term": {"agent": agent}})
    if interface:
        filter_.append({"term": {"interface": interface}})
    ts_range: dict[str, Any] = {}
    if start_ts is not None:
        ts_range["gte"] = start_ts
    if end_ts is not None:
        ts_range["lte"] = end_ts
    if ts_range:
        filter_.append({"range": {"ts": ts_range}})

    return {
        "query": {
            "bool": {
                "must": must,
                "filter": filter_,
                "must_not": [_NODE_HEARTBEAT],
            }
        },
        "collapse": {"field": "trace_key"},
        "sort": [{"ts": {"order": "desc", "format": "epoch_millis"}}],
        "from": from_,
        "size": size,
        "aggs": {"trace_total": {"cardinality": {"field": "trace_key"}}},
    }


def build_trace_events_body(*, agent: str, trace_id: str, limit: int) -> dict:
    """详情 query body：单 trace 事件行（event_kind=event 全节点）。

    - **排序 = seq asc（S-1 实测修正）**：SDK 语义下 seq 是 trace 内节点创建序的单调计数
      （§11.1 request 锚点 seq=0 固定、节点/日志共用一把计数器），父 seq 恒小于子 seq →
      seq asc 即结构拓扑序，根锚点恒在首位，树形渲染稳定。不能用 ts asc：request 事件在
      中间件 finally（子都完成后）才发出，ts 恒为全 trace 最大 → ts-asc 会让根沉底、子树
      散乱。
    - 日志行不进详情（走 /logs 懒加载，§8.2 注）；heartbeat 无 event_kind/trace_id 天然被
      term 排除。size=limit 截断，truncated 由调用方按 total>limit 判定。
    """
    return {
        "query": {
            "bool": {
                "must": [
                    {"term": {"agent": agent}},
                    {"term": {"trace_id": trace_id}},
                    {"term": {"event_kind": "event"}},
                ]
            }
        },
        "sort": [{"seq": {"order": "asc"}}],
        "size": limit,
        "track_total_hits": True,
    }


def build_trace_logs_body(
    *, agent: str, trace_id: str, from_: int, size: int
) -> dict:
    """/logs query body：单 trace 日志行（event_kind=log），按 seq 正序分页拉取。"""
    return {
        "query": {
            "bool": {
                "must": [
                    {"term": {"agent": agent}},
                    {"term": {"trace_id": trace_id}},
                    {"term": {"event_kind": "log"}},
                ]
            }
        },
        "sort": [{"seq": {"order": "asc"}}],
        "from": from_,
        "size": size,
        "track_total_hits": True,
    }


async def search_traces(client, *, settings: Settings, request_timeout_s: float, **kw) -> dict:
    """折叠去重 trace 列表 → {hits: [命中行 _source...], total: 去重 trace 数}。"""
    body = build_trace_list_body(**kw)
    resp = await client.options(request_timeout=request_timeout_s).search(
        index=index_patterns(settings), body=body
    )
    result = _hits_result(resp)
    # total 以 cardinality agg 为准（collapse 不改 hits.total → 折叠前文档数，非去重口径）。
    # agg 缺失（旧 fake/极端响应）时回退 hits.total，保证不崩。
    aggs = (resp.get("aggregations") or {}).get("trace_total") or {}
    result["total"] = int(aggs.get("value", result["total"]))
    return result


async def fetch_trace_events(
    client, *, settings: Settings, agent: str, trace_id: str,
    request_timeout_s: float, limit: int = MAX_DETAIL_EVENTS,
) -> dict:
    """单 trace 事件行（seq asc 结构序）→ {hits, total, truncated}。"""
    body = build_trace_events_body(agent=agent, trace_id=trace_id, limit=limit)
    resp = await client.options(request_timeout=request_timeout_s).search(
        index=index_patterns(settings), body=body
    )
    result = _hits_result(resp)
    result["truncated"] = result["total"] > limit
    return result


async def fetch_trace_logs(
    client, *, settings: Settings, agent: str, trace_id: str,
    request_timeout_s: float, from_: int, size: int,
) -> dict:
    """单 trace 日志行分页 → {hits, total}。"""
    body = build_trace_logs_body(agent=agent, trace_id=trace_id, from_=from_, size=size)
    resp = await client.options(request_timeout=request_timeout_s).search(
        index=index_patterns(settings), body=body
    )
    return _hits_result(resp)


def _hits_result(resp) -> dict:
    """ES search 响应 → 统一 {hits: [str, _source...], total: int}（折叠后 total 已去重）。"""
    total = resp["hits"]["total"]
    total_value = total["value"] if isinstance(total, dict) else int(total)
    return {"hits": [h["_source"] for h in resp["hits"]["hits"]], "total": int(total_value)}


# ============================================================================
# metrics 实时聚合层（detail §8.4 + §14.4 护栏，T-2.2）
# 只读 request/llm_call 事件（overview 以 node=request 锚点；log index 与指标无关，仅查 event index）。
# 护栏：agg request_timeout 由调用方传秒（metric_agg_timeout_ms dict 键 / 3000ms，seed 默认）；
# anomalies/llm-failures 是列表（非聚合）永远读实时事件 index（rollup 丢 trace 身份）。
# 7d 时段已完成小时走 rollup（T-2.3 metrics_rollup 读助手），本层只管实时聚合面。
# ============================================================================


def event_index_patterns(settings) -> list[str]:
    """指标检索 index 集 = 事件前缀周滚动全量（指标只取事件，不查 log index）。"""
    return [f"{settings.event_index_prefix}-*"]


def _base_metrics_query(
    agent: str | None,
    start_ts: int,
    end_ts: int,
    node: str | None = None,
    statuses: list[str] | None = None,
) -> dict:
    """指标查询公共 bool：时间窗 + 排心跳（filter），可选 node/agent/status∈ 追加。

    各 body 的 node/agent/status 约束一律放 filter——指标只做过滤不做评分，语义与 must 一致。
    """
    filters: list[dict] = [{"range": {"ts": {"gte": start_ts, "lte": end_ts}}}]
    if node:
        filters.append({"term": {"node": node}})
    if agent:
        filters.append({"term": {"agent": agent}})
    if statuses:
        filters.append({"bool": {"should": [{"term": {"status": s}} for s in statuses]}})
    return {"bool": {"filter": filters, "must_not": [_NODE_HEARTBEAT]}}


def build_metrics_overview_body(
    *, agent: str | None, start_ts: int, end_ts: int, interval: str
) -> dict:
    """GET /metrics/overview 实时 body（request 锚）：pct[50/95/99] + err/to 计数 + 时序子聚合。

    顶层 percentiles 在 request 锚全量 duration_ms（含 error/timeout，§8.4 口径钉死）；
    series 每桶只挂 err/to 两个 filter 计数（buckets 内不放 percentiles——成本高）。
    """
    return {
        "query": _base_metrics_query(agent, start_ts, end_ts, node="request"),
        "size": 0,
        "track_total_hits": True,
        "aggs": {
            "pct": {"percentiles": {"field": "duration_ms", "percents": [50, 95, 99]}},
            "err": {"filter": {"term": {"status": "error"}}},
            "to": {"filter": {"term": {"status": "timeout"}}},
            "series": {
                "date_histogram": {"field": "ts", "fixed_interval": interval},
                "aggs": {
                    "err": {"filter": {"term": {"status": "error"}}},
                    "to": {"filter": {"term": {"status": "timeout"}}},
                },
            },
        },
    }


def build_metrics_interfaces_body(
    *, agent: str | None, start_ts: int, end_ts: int
) -> dict:
    """GET /metrics/interfaces 实时 body：单查询双 filter agg（请求级 + LLM 级双 tab）。

    外层 query 只做时间窗 + 排心跳（node 各自在 req/llm filter agg 内锚），一次 ES 往返
    出双 tab——req filter agg 的 doc_count 即请求总数，llm 同。agent 过滤走外层（两 tab 共用）。
    """
    return {
        "query": _base_metrics_query(agent, start_ts, end_ts),
        "size": 0,
        "aggs": {
            "req": {
                "filter": {"term": {"node": "request"}},
                "aggs": {
                    "by_iface": {
                        "terms": {"field": "interface", "size": 50},
                        "aggs": {
                            "pct": {"percentiles": {
                                "field": "duration_ms", "percents": [50, 95, 99]}},
                            "err": {"filter": {"term": {"status": "error"}}},
                            "to": {"filter": {"term": {"status": "timeout"}}},
                        },
                    }
                },
            },
            "llm": {
                "filter": {"term": {"node": "llm_call"}},
                "aggs": {
                    "by_iface": {
                        "terms": {"field": "interface", "size": 50},
                        "aggs": {
                            "fail": {"filter": {"bool": {"should": [
                                {"term": {"status": "error"}},
                                {"term": {"status": "timeout"}},
                            ]}}},
                            "by_model": {
                                "terms": {"field": "model", "size": 20},
                                "aggs": {
                                    "fail": {"filter": {"bool": {"should": [
                                        {"term": {"status": "error"}},
                                        {"term": {"status": "timeout"}},
                                    ]}}},
                                    # tokens 在嵌套 usage.* 下（consumer/es.py::_MAPPING，勿用顶层）
                                    "pt": {"sum": {"field": "usage.prompt_tokens"}},
                                    "ct": {"sum": {"field": "usage.completion_tokens"}},
                                },
                            },
                        },
                    }
                },
            },
        },
    }


def build_anomalies_body(
    *, agent: str | None, start_ts: int, end_ts: int, size: int
) -> dict:
    """GET /metrics/anomalies body：request 红显（error/timeout）列表，ts desc。"""
    return {
        "query": _base_metrics_query(
            agent, start_ts, end_ts, node="request", statuses=["error", "timeout"]),
        "size": size,
        "sort": [{"ts": {"order": "desc", "format": "epoch_millis"}}],
    }


def build_llm_failures_body(
    *, agent: str | None, start_ts: int, end_ts: int, size: int
) -> dict:
    """GET /metrics/llm-failures Q1 body：llm_call 红显按 trace 折叠，取每 trace 最新失败。

    折叠键 = trace_key；命中行为 llm_call 失败现场（携带 interface/model/error），
    Q2（同 trace request 状态查）由 API 层另发，本函数只出 Q1。
    """
    return {
        "query": _base_metrics_query(
            agent, start_ts, end_ts, node="llm_call", statuses=["error", "timeout"]),
        "collapse": {"field": "trace_key"},
        "sort": [{"ts": {"order": "desc", "format": "epoch_millis"}}],
        "size": size,
    }


def build_request_statuses_body(trace_ids: list[str]) -> dict:
    """GET llm-failures Q2 body：一批 trace 的 request 节点行（terms≤100 护栏）。"""
    return {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"node": "request"}},
                    {"terms": {"trace_key": trace_ids[:100]}},
                ],
                "must_not": [_NODE_HEARTBEAT],
            }
        },
        "size": 200,
        "_source": ["trace_key", "status"],
    }


def _parse_percentiles(bucket: dict, key: str = "pct") -> dict[str, float | None]:
    """percentiles agg bucket → {50: v, 95: v, 99: v}（ES 响应键带小数 .0，逐键回读）。"""
    out: dict[str, float | None] = {"50": None, "95": None, "99": None}
    vals = (bucket.get(key) or {}).get("values") or {}
    for pct in ("50.0", "95.0", "99.0"):
        v = vals.get(pct)
        if v is not None:
            out[pct[:-2]] = float(v)
    return out


def _series_rows(buckets: list[dict]) -> list[dict]:
    """date_histogram buckets → [{ts(epoch ms), count, error, timeout}]（空桶剔除）。"""
    rows = []
    for b in buckets:
        ts = int(b.get("key") or 0)
        if not ts:
            continue
        rows.append({
            "ts": ts,
            "count": int(b.get("doc_count") or 0),
            "error": int((b.get("err") or {}).get("doc_count") or 0),
            "timeout": int((b.get("to") or {}).get("doc_count") or 0),
        })
    return rows


async def run_metrics_overview(
    client, *, settings, request_timeout_s: float, **kw
) -> dict:
    """overview 实时查询 → {total, p50, p95, p99, error, timeout, series[]}。"""
    body = build_metrics_overview_body(**kw)
    resp = await client.options(request_timeout=request_timeout_s).search(
        index=event_index_patterns(settings), body=body
    )
    total = resp["hits"]["total"]
    total_value = total["value"] if isinstance(total, dict) else int(total)
    aggs = resp.get("aggregations") or {}
    pcts = _parse_percentiles(aggs)
    return {
        "total": int(total_value),
        "p50": pcts["50"],
        "p95": pcts["95"],
        "p99": pcts["99"],
        "error": int((aggs.get("err") or {}).get("doc_count") or 0),
        "timeout": int((aggs.get("to") or {}).get("doc_count") or 0),
        "series": _series_rows((aggs.get("series") or {}).get("buckets") or []),
    }


async def run_metrics_interfaces(
    client, *, settings, request_timeout_s: float, **kw
) -> dict:
    """interfaces 实时查询 → {request: [ReqIfaceRow], llm: [LlmIfaceRow]}（解析钉定形状）。"""
    body = build_metrics_interfaces_body(**kw)
    resp = await client.options(request_timeout=request_timeout_s).search(
        index=event_index_patterns(settings), body=body
    )
    aggs = resp.get("aggregations") or {}
    request_rows: list[dict] = []
    for b in (aggs.get("req") or {}).get("by_iface", {}).get("buckets") or []:
        pcts = _parse_percentiles(b)
        request_rows.append({
            "interface": b.get("key"),
            "total": int(b.get("doc_count") or 0),
            "error": int((b.get("err") or {}).get("doc_count") or 0),
            "timeout": int((b.get("to") or {}).get("doc_count") or 0),
            "p50": pcts["50"], "p95": pcts["95"], "p99": pcts["99"],
        })
    llm_rows: list[dict] = []
    for b in (aggs.get("llm") or {}).get("by_iface", {}).get("buckets") or []:
        llm_rows.append({
            "interface": b.get("key"),
            "total": int(b.get("doc_count") or 0),
            "error": int((b.get("fail") or {}).get("doc_count") or 0),
            "models": [
                {
                    "model": m.get("key"),
                    "total": int(m.get("doc_count") or 0),
                    "error": int((m.get("fail") or {}).get("doc_count") or 0),
                    "prompt_tokens": int((m.get("pt") or {}).get("value") or 0),
                    "completion_tokens": int((m.get("ct") or {}).get("value") or 0),
                }
                for m in (b.get("by_model") or {}).get("buckets") or []
            ],
        })
    return {"request": request_rows, "llm": llm_rows}


async def fetch_anomalies(
    client, *, settings, request_timeout_s: float, size: int = 100, **kw
) -> dict:
    """anomalies 实时列表（request 红显，ts desc）。"""
    body = build_anomalies_body(size=size, **kw)
    resp = await client.options(request_timeout=request_timeout_s).search(
        index=event_index_patterns(settings), body=body
    )
    return _hits_result(resp)


async def fetch_llm_failures(
    client, *, settings, request_timeout_s: float, size: int = 100, **kw
) -> dict:
    """llm-failures Q1（按 trace 折叠的最新 llm_call 失败现场）。"""
    body = build_llm_failures_body(size=size, **kw)
    resp = await client.options(request_timeout=request_timeout_s).search(
        index=event_index_patterns(settings), body=body
    )
    return _hits_result(resp)


async def fetch_request_statuses(client, *, settings, request_timeout_s: float,
                                 trace_keys: list[str]) -> dict[str, str]:
    """llm-failures Q2：trace_key → request 节点 status（无该 trace request 则缺失）。"""
    if not trace_keys:
        return {}
    body = build_request_statuses_body(trace_keys)
    resp = await client.options(request_timeout=request_timeout_s).search(
        index=event_index_patterns(settings), body=body
    )
    return {h["_source"].get("trace_key"): h["_source"].get("status")
            for h in resp["hits"]["hits"] if h["_source"].get("trace_key")}
