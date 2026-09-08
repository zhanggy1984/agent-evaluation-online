"""实时指标聚合 API（detail §8.4 + §14.4 护栏，T-2.2）。

- **鉴权**：四端点全部挂 ViewerUser（viewer/admin，§8.1）。
- **错误码**：前缀 = §8.9 `ERR_METRICS_0001`（复数权威，缺口 B）；window 非法 / agg 超时 /
  ES 不可用 → 统一 400。
- **O-1 护栏**：模块级进程内缓存（仿 core/dict_config 无锁 60s）；key =
  endpoint|agent('*' 全站)|window；
  TTL = metric_agg_cache_ttl_s（seed 默认 60，≤0 不缓存）。缓存命中跳过 ES。agg
  request_timeout = metric_agg_timeout_ms（seed 默认 3000）。
- **响应形状**（散文 → 实现钉定，回填 detail v1.12）：
  - source: "rollup" | "realtime" | "mixed"；1h/24h 只走实时 → realtime，fallback_hours=[]。
  - 7d：覆盖小时 = rollup **meta doc 已处理**的小时（含"处理过但零流量"小时，与真实缺口可
    区分；`_rollup_covered_hours`）→ **卡片 p50/95/99 = 覆盖小时 sketch merge 的近似口径**
    （跨源分位不可精确合成，用户拍板）；计数/error/timeout/序列 = 实时整窗（准确超集，rollup
    计数与源一致由 rollup_job meta 探测保证）。fallback_hours = **已闭合**小时中无 rollup
    覆盖的缺口（当前进行中小时设计上不预聚合、实时回补，不计缺口）→ 全闭合小时覆盖时
    source="rollup"、缺桶 → "mixed"；rollup index 未就位（worker 从未跑）/ES 异常 → 整窗
    实时兜底 source="realtime"（fallback_hours=[]，形状不变）。
  - 卡片 p50/95/99 = request 锚 duration_ms（含 error/timeout）；失败率=error/总、
    超时率=timeout/总。
  - series 每桶 qps = count / 桶宽秒；error_rate/timeout_rate 以桶 count 为分母。
- **口径**：anomalies/llm-failures 是列表，永远读原始事件 index（rollup 丢 trace 身份）。
  llm-failures = Q1 collapse(trace_key) 取每 trace 最新 llm_call 失败现场 + Q2 同 trace request
  状态归属（request ok + llm_call error = 降级/兜底吸收现场，v1 不回流、不并入失败率）。
- 结果护栏：两列表端点 size ≤ 100（§14.4）。
"""
import time
from typing import Annotated, Awaitable, Callable

from elasticsearch.exceptions import TransportError
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ViewerUser
from app.core.db import get_session
from app.core.dict_config import get_global_int
from app.core.errors import AppError
from app.store import es as es_store
from app.store import metrics_rollup as rollup_store

router = APIRouter(prefix="/metrics", tags=["metrics"])

_Session = Annotated[AsyncSession, Depends(get_session)]

# dict_config 运行时键（seed 默认：60s 缓存 / 3000ms agg 超时，§10）
_DEFAULT_CACHE_TTL_S = 60
_DEFAULT_AGG_TIMEOUT_MS = 3000
_MS_PER_HOUR = 3_600_000

# window → (时长 ms, 实时兜底序列桶宽)。1h→1m(60 点)、24h→30m(48 点)、7d→1h(≤168 点)。
_WINDOWS = {
    "1h": (_MS_PER_HOUR, "1m"),
    "24h": (24 * _MS_PER_HOUR, "30m"),
    "7d": (7 * 24 * _MS_PER_HOUR, "1h"),
}
_BUCKET_WIDTH_S = {"1m": 60, "30m": 1800, "1h": 3600}

_LIST_LIMIT = 100  # §14.4：列表端点结果上限


def _validate_window(window: str) -> None:
    if window not in _WINDOWS:
        raise AppError("ERR_METRICS_0001", f"window 非法（∈ {{1h,24h,7d}}）: {window}", http=400)


def _hour_boundaries(start_ms: int, end_ms: int) -> list[int]:
    """窗口内 UTC 整点小时边界（epoch ms，升序，含尾）——fallback_hours/rollup 小时刻度。"""
    first = start_ms - (start_ms % _MS_PER_HOUR)
    out = []
    cur = first
    while cur <= end_ms:
        out.append(cur)
        cur += _MS_PER_HOUR
    return out


def _now_ms() -> int:
    return int(time.time() * 1000)


def _ratio(num: int, den: int) -> float | None:
    """失败率/超时率：分母为 0 → None（前端显示 '-'），否则 0..1 小数。"""
    if not den:
        return None
    return num / den


# ---------- 响应模型（§8.4 钉定形状；清单式白名单取 key，不带旁路字段） ----------


class MetricsOverviewCards(BaseModel):
    qps: float | None = None
    p50: float | None = None
    p95: float | None = None
    p99: float | None = None
    total: int = 0
    error: int = 0
    timeout: int = 0
    error_rate: float | None = None
    timeout_rate: float | None = None


class OverviewSeriesPoint(BaseModel):
    ts: int
    count: int = 0
    qps: float | None = None
    error_rate: float | None = None
    timeout_rate: float | None = None


class MetricsOverview(BaseModel):
    window: str
    agent: str | None = None
    source: str = "realtime"  # rollup | realtime | mixed
    fallback_hours: list[int] = []
    # 7d 卡片分位 merge 的已 rollup 小时数（含零流量已处理小时）；1h/24h 恒 0。
    # UI 据此标注"分位基于 N 个已完成小时"（分位与计数不同样本，§4.4/§8.4 v1.14）。
    covered_hours: int = 0
    cards: MetricsOverviewCards = MetricsOverviewCards()
    series: list[OverviewSeriesPoint] = []


class ReqIfaceRow(BaseModel):
    interface: str
    total: int = 0
    error: int = 0
    timeout: int = 0
    p50: float | None = None
    p95: float | None = None
    p99: float | None = None


class LlmModelRow(BaseModel):
    model: str
    total: int = 0
    error: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LlmIfaceRow(BaseModel):
    interface: str
    total: int = 0
    error: int = 0
    llm_failure_rate: float | None = None
    models: list[LlmModelRow] = []


class MetricsInterfaces(BaseModel):
    window: str
    agent: str | None = None
    source: str = "realtime"
    fallback_hours: list[int] = []
    request: list[ReqIfaceRow] = []
    llm: list[LlmIfaceRow] = []


class AnomalyItem(BaseModel):
    agent: str | None = None
    trace_id: str | None = None
    interface: str | None = None
    status: str | None = None
    error_type: str | None = None
    error_msg: str | None = None
    ts: int | None = None
    duration_ms: int | None = None


class MetricsAnomalies(BaseModel):
    window: str
    agent: str | None = None
    # 窗口内真实总数与截断指示：列表 size≤100（§14.4），total>len 即 items 只是最新一页。
    total: int = 0
    truncated: bool = False
    items: list[AnomalyItem] = []


class LlmFailureItem(BaseModel):
    agent: str | None = None
    trace_id: str | None = None
    interface: str | None = None
    request_status: str | None = None
    llm_node_status: str | None = None
    llm_error_type: str | None = None
    llm_error_msg: str | None = None
    model: str | None = None
    ts: int | None = None


class MetricsLlmFailures(BaseModel):
    window: str
    agent: str | None = None
    # total = 窗口内**失败 trace 去重数**（collapse 不改 hits.total，须 cardinality 单算）；
    # truncated = 折叠列表被 size≤100 截断（§14.4）。
    total: int = 0
    truncated: bool = False
    items: list[LlmFailureItem] = []


class MetricsAgents(BaseModel):
    """近 7d 有流量的 agent 名（纯实测、按频次降序）——筛选下拉数据源（Q4/Q5 决策）。

    total = 真实去重 agent 总数（distinct agg），可能 > len(agents)（top100 截断，
    §14.4）；truncated = total > len(agents)。
    """

    total: int = 0
    truncated: bool = False
    agents: list[str] = []


# ---------- O-1 进程内缓存（仿 dict_config 无锁；key = endpoint|agent|window） ----------

_cache: dict[str, tuple[float, object]] = {}


async def _cache_ttl_s(session: AsyncSession) -> int:
    return await get_global_int(session, "metric_agg_cache_ttl_s", _DEFAULT_CACHE_TTL_S)


async def _agg_timeout_ms(session: AsyncSession) -> int:
    return await get_global_int(session, "metric_agg_timeout_ms", _DEFAULT_AGG_TIMEOUT_MS)


def _cache_get(key: str, ttl_s: int) -> object | None:
    if ttl_s <= 0:
        return None
    hit = _cache.get(key)
    if hit is None:
        return None
    cached_at, value = hit
    if time.monotonic() - cached_at >= ttl_s:
        _cache.pop(key, None)
        return None
    return value


def _cache_put(key: str, value: object) -> None:
    _cache[key] = (time.monotonic(), value)


async def _cached(
    session: AsyncSession,
    endpoint: str,
    agent: str | None,
    window: str,
    loader: Callable[[], Awaitable[object]],
) -> object:
    """O-1 缓存读改写：key = endpoint|agent('*' 全站)|window；命中直接回（跳过 ES）。"""
    ttl_s = await _cache_ttl_s(session)
    key = f"{endpoint}|{agent or '*'}|{window}"
    got = _cache_get(key, ttl_s)
    if got is not None:
        return got
    value = await loader()
    _cache_put(key, value)
    return value


# ---------- 7d rollup 读取（#127 已接线）：覆盖小时 = meta 判别（fetch_rollup_covered_hours），
# 本段 `_rollup_request_docs` 只拉 request 组 doc 供卡片分位 merge ----------


async def _rollup_request_docs(
    client, settings, agent: str | None, start_ms: int, end_ms: int, timeout_s: float,
) -> list[dict]:
    """读 rollup group docs（request 粒度 + agent 过滤）；rollup index 缺失/异常降级 []。

    只 7d 窗消费；index 未建（worker 从未跑）或 ES 故障 → [] = 整窗实时兜底。
    返回总量 ~ 覆盖小时 × 组数（dev 规模 < 万级，fetch_rollup_hits size 护栏已够）。
    """
    try:
        docs = await rollup_store.fetch_rollup_hits(
            client, settings=settings, request_timeout_s=timeout_s,
            start_ms=start_ms, end_ms=end_ms)
    except TransportError:
        return []
    return [d for d in docs
            if d.get("node") == "request"
            and (agent is None or d.get("agent") == agent)]


def _completed_hour_starts(start_ms: int, end_ms: int) -> list[int]:
    """窗口内**已闭合** UTC 整点小时起点（排除当前进行中小时）——rollup 缺口判定基准。

    进行中小时由 rollup 设计上不预聚合（尾小时实时回补，见 §5.3），不构成 rollup 缺口；
    缺口只对已闭合小时成立 → 全闭合小时覆盖时 source="rollup" 可达（三态非死码）。
    """
    cur_hour = end_ms - end_ms % _MS_PER_HOUR  # 当前进行中小时起点
    return [b for b in _hour_boundaries(start_ms, end_ms) if b < cur_hour]


async def _rollup_covered_hours(
    client, settings, start_ms: int, end_ms: int, timeout_s: float,
) -> list[int]:
    """已 rollup 小时起点（meta doc 判别，含"处理过但零流量"小时）；index 缺失/ES 异常 → []. """
    try:
        return await rollup_store.fetch_rollup_covered_hours(
            client, settings=settings, request_timeout_s=timeout_s,
            start_ms=start_ms, end_ms=end_ms)
    except TransportError:
        return []


def _source_of(covered: list[int], fallback_hours: list[int]) -> str:
    """source 派生：无覆盖 → realtime；全覆盖 → rollup；缺桶 → mixed。"""
    if not covered:
        return "realtime"
    return "rollup" if not fallback_hours else "mixed"


# ---------- 各端点装载器 ----------


def _overview_series(
    rows: list[dict], bucket_width_s: int, start_ms: int, end_ms: int
) -> list[OverviewSeriesPoint]:
    """date_histogram 行 → 序列点；QPS 按**桶实际覆盖窗宽**折算（v1.14 缺陷修）。

    ES date_histogram 对齐 interval 起于整边界：首桶可能左越 window_start、尾桶右越
    window_end（进行中小时），若按满桶宽除会虚低 → 右端持续爬坡假象。逐桶
    `covered_ms = min(ts+width, end_ms) - max(ts, start_ms)` 得真实样本时长；
    covered_ms<=0（理论边界守卫）→ qps None。error/timeout_rate 分母仍是桶内 count 不变。
    """
    out: list[OverviewSeriesPoint] = []
    for p in rows:
        ts = p["ts"]
        covered_ms = min(ts + bucket_width_s * 1000, end_ms) - max(ts, start_ms)
        qps = p["count"] / (covered_ms / 1000) if covered_ms > 0 else None
        out.append(OverviewSeriesPoint(
            ts=ts,
            count=p["count"],
            qps=qps,
            error_rate=_ratio(p["error"], p["count"]),
            timeout_rate=_ratio(p["timeout"], p["count"]),
        ))
    return out


async def _load_overview(
    request: Request, session: AsyncSession, agent: str | None, window: str
) -> MetricsOverview:
    settings = request.app.state.settings
    client = request.app.state.es_query
    window_ms, interval = _WINDOWS[window]
    end_ms = _now_ms()
    start_ms = end_ms - window_ms
    timeout_s = max(await _agg_timeout_ms(session) / 1000, 1.0)

    rollup_docs: list[dict] = []
    covered: list[int] = []
    if window == "7d":
        # covered = meta doc 已处理小时（含"处理过但零流量"小时，区分真实缺口）；
        # rollup_docs = request 组 doc（卡片分位 merge 源）；index 未就位/ES 异常 → [] 整窗实时
        covered = await _rollup_covered_hours(
            client, settings, start_ms, end_ms, timeout_s)
        rollup_docs = await _rollup_request_docs(
            client, settings, agent, start_ms, end_ms, timeout_s)
    fallback_hours: list[int] = []
    _source = "realtime"
    if window == "7d" and covered:
        # 缺口只对**已闭合**小时成立：当前进行中小时 rollup 不预聚合（尾小时实时回补），
        # 不计缺口 → 全闭合小时覆盖时 source="rollup" 可达（三态落实）；缺桶才 mixed
        fallback_hours = [h for h in _completed_hour_starts(start_ms, end_ms)
                          if h not in set(covered)]
        _source = _source_of(covered, fallback_hours)

    try:
        result = await es_store.run_metrics_overview(
            client, settings=settings, request_timeout_s=timeout_s,
            agent=agent, start_ts=start_ms, end_ts=end_ms,
            interval=interval if window != "7d" else "1h",
        )
    except TransportError as exc:
        raise AppError("ERR_METRICS_0001", f"指标聚合暂不可用或超时: {exc}", http=400) from exc

    p50, p95, p99 = result["p50"], result["p95"], result["p99"]
    if covered:
        # 卡片分位 = rollup 覆盖小时 sketch merge 的近似口径（跨源分位不可精确合成，用户拍板）；
        # 计数/error/timeout/序列仍实时整窗（准确超集；rollup 计数与源一致由
        # rollup_job meta 探测保证）
        merged = rollup_store.merge_digests(rollup_docs, (0.50, 0.95, 0.99))
        p50, p95, p99 = merged["p50"], merged["p95"], merged["p99"]

    bucket_width_s = _BUCKET_WIDTH_S["1h" if window == "7d" else interval]
    return MetricsOverview(
        window=window, agent=agent, source=_source, fallback_hours=fallback_hours,
        covered_hours=len(covered),
        cards=MetricsOverviewCards(
            qps=result["total"] / (window_ms / 1000) if window_ms else None,
            p50=p50, p95=p95, p99=p99,
            total=result["total"], error=result["error"], timeout=result["timeout"],
            error_rate=_ratio(result["error"], result["total"]),
            timeout_rate=_ratio(result["timeout"], result["total"]),
        ),
        series=_overview_series(result["series"], bucket_width_s, start_ms, end_ms),
    )


async def _load_interfaces(
    request: Request, session: AsyncSession, agent: str | None, window: str
) -> MetricsInterfaces:
    settings = request.app.state.settings
    client = request.app.state.es_query
    window_ms, _interval = _WINDOWS[window]
    end_ms = _now_ms()
    start_ms = end_ms - window_ms
    timeout_s = max(await _agg_timeout_ms(session) / 1000, 1.0)

    covered: list[int] = []
    if window == "7d":
        # 行级分位/计数走实时，rollup 只读覆盖（meta 判别）供 source/fallback 标记
        covered = await _rollup_covered_hours(
            client, settings, start_ms, end_ms, timeout_s)
    fallback_hours: list[int] = []
    _source = "realtime"
    if window == "7d" and covered:
        fallback_hours = [h for h in _completed_hour_starts(start_ms, end_ms)
                          if h not in set(covered)]
        _source = _source_of(covered, fallback_hours)

    try:
        result = await es_store.run_metrics_interfaces(
            client, settings=settings, request_timeout_s=timeout_s,
            agent=agent, start_ts=start_ms, end_ts=end_ms,
        )
    except TransportError as exc:
        raise AppError("ERR_METRICS_0001", f"指标聚合暂不可用或超时: {exc}", http=400) from exc

    # 行级分位/计数仍实时整窗：覆盖小时不足支撑行级 covered-only 近似（每接口样本更稀疏），
    # 实时全窗反而更稳；rollup 读取只用于 source/fallback 真实标记（缺桶页面标"回退实时口径"）。
    llm_rows = [
        LlmIfaceRow(
            interface=r["interface"], total=r["total"], error=r["error"],
            llm_failure_rate=_ratio(r["error"], r["total"]),
            models=[LlmModelRow(**m) for m in r["models"]],
        )
        for r in result["llm"]
    ]
    return MetricsInterfaces(
        window=window, agent=agent, source=_source, fallback_hours=fallback_hours,
        request=[ReqIfaceRow(**r) for r in result["request"]],
        llm=llm_rows,
    )


async def _load_anomalies(
    request: Request, session: AsyncSession, agent: str | None, window: str
) -> MetricsAnomalies:
    client = request.app.state.es_query
    window_ms, _interval = _WINDOWS[window]
    end_ms = _now_ms()
    start_ms = end_ms - window_ms
    timeout_s = max(await _agg_timeout_ms(session) / 1000, 1.0)
    try:
        result = await es_store.fetch_anomalies(
            client, settings=request.app.state.settings, request_timeout_s=timeout_s,
            agent=agent, start_ts=start_ms, end_ts=end_ms, size=_LIST_LIMIT,
        )
    except TransportError as exc:
        raise AppError("ERR_METRICS_0001", f"指标检索暂不可用或超时: {exc}", http=400) from exc
    items = [AnomalyItem(**{k: h.get(k) for k in (
        "agent", "trace_id", "interface", "status", "error_type", "error_msg",
        "ts", "duration_ms")}) for h in result["hits"]]
    total = int(result["total"])
    return MetricsAnomalies(
        window=window, agent=agent, total=total, truncated=total > len(items),
        items=items,
    )


async def _load_llm_failures(
    request: Request, session: AsyncSession, agent: str | None, window: str
) -> MetricsLlmFailures:
    client = request.app.state.es_query
    window_ms, _interval = _WINDOWS[window]
    end_ms = _now_ms()
    start_ms = end_ms - window_ms
    timeout_s = max(await _agg_timeout_ms(session) / 1000, 1.0)
    try:
        q1 = await es_store.fetch_llm_failures(
            client, settings=request.app.state.settings, request_timeout_s=timeout_s,
            agent=agent, start_ts=start_ms, end_ts=end_ms, size=_LIST_LIMIT,
        )
        trace_keys = [
            h.get("trace_key") or f"{h.get('agent')}#{h.get('trace_id')}"
            for h in q1["hits"]
        ]
        q2 = await es_store.fetch_request_statuses(
            client, settings=request.app.state.settings, request_timeout_s=timeout_s,
            trace_keys=[k for k in trace_keys if k],
        )
    except TransportError as exc:
        raise AppError("ERR_METRICS_0001", f"指标检索暂不可用或超时: {exc}", http=400) from exc

    items = []
    for h in q1["hits"]:
        tkey = h.get("trace_key") or f"{h.get('agent')}#{h.get('trace_id')}"
        items.append(LlmFailureItem(
            agent=h.get("agent"),
            trace_id=h.get("trace_id"),
            interface=h.get("interface"),
            request_status=q2.get(tkey),  # None = 该 trace request 不在窗内/缺失（不做兜底猜测）
            llm_node_status=h.get("status"),
            llm_error_type=h.get("error_type"),
            llm_error_msg=h.get("error_msg"),
            model=h.get("model"),
            ts=h.get("ts"),
        ))
    total = int(q1["total"])  # 失败 trace 去重总数（cardinality agg；缺 agg 回退 hits.total）
    return MetricsLlmFailures(
        window=window, agent=agent, total=total, truncated=total > len(items),
        items=items,
    )


async def _load_agents(request: Request, session: AsyncSession) -> MetricsAgents:
    """近 7d request 事件里真实出现的 agent 名（terms 去重、按频次降序）。"""
    client = request.app.state.es_query
    window_ms = _WINDOWS["7d"][0]
    end_ms = _now_ms()
    start_ms = end_ms - window_ms
    timeout_s = max(await _agg_timeout_ms(session) / 1000, 1.0)
    try:
        res = await es_store.run_agents(
            client, settings=request.app.state.settings, request_timeout_s=timeout_s,
            start_ts=start_ms, end_ts=end_ms, size=_LIST_LIMIT,
        )
    except TransportError as exc:
        raise AppError("ERR_METRICS_0001", f"指标检索暂不可用或超时: {exc}", http=400) from exc
    total = int(res["total"])
    return MetricsAgents(
        total=total, truncated=total > len(res["agents"]), agents=res["agents"],
    )


# ---------- 端点 ----------


@router.get("/overview", response_model=MetricsOverview)
async def metrics_overview(
    user: ViewerUser,
    request: Request,
    session: _Session,
    agent: str | None = Query(default=None, max_length=64),
    window: str = Query(default="1h"),
) -> MetricsOverview:
    _validate_window(window)
    value = await _cached(session, "overview", agent, window,
                          lambda: _load_overview(request, session, agent, window))
    return value  # type: ignore[return-value]


@router.get("/interfaces", response_model=MetricsInterfaces)
async def metrics_interfaces(
    user: ViewerUser,
    request: Request,
    session: _Session,
    agent: str | None = Query(default=None, max_length=64),
    window: str = Query(default="1h"),
) -> MetricsInterfaces:
    _validate_window(window)
    value = await _cached(session, "interfaces", agent, window,
                          lambda: _load_interfaces(request, session, agent, window))
    return value  # type: ignore[return-value]


@router.get("/anomalies", response_model=MetricsAnomalies)
async def metrics_anomalies(
    user: ViewerUser,
    request: Request,
    session: _Session,
    agent: str | None = Query(default=None, max_length=64),
    window: str = Query(default="24h"),
) -> MetricsAnomalies:
    _validate_window(window)
    value = await _cached(session, "anomalies", agent, window,
                          lambda: _load_anomalies(request, session, agent, window))
    return value  # type: ignore[return-value]


@router.get("/llm-failures", response_model=MetricsLlmFailures)
async def metrics_llm_failures(
    user: ViewerUser,
    request: Request,
    session: _Session,
    agent: str | None = Query(default=None, max_length=64),
    window: str = Query(default="24h"),
) -> MetricsLlmFailures:
    _validate_window(window)
    value = await _cached(session, "llm-failures", agent, window,
                          lambda: _load_llm_failures(request, session, agent, window))
    return value  # type: ignore[return-value]


@router.get("/agents", response_model=MetricsAgents)
async def metrics_agents(
    user: ViewerUser,
    request: Request,
    session: _Session,
) -> MetricsAgents:
    """近 7d 有流量的 agent 名列表（筛选下拉数据源；固定 7d 窗，agent/window 无参）。"""
    value = await _cached(session, "agents", None, "7d",
                          lambda: _load_agents(request, session))
    return value  # type: ignore[return-value]
