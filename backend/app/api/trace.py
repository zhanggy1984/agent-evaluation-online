"""链路查询 API（detail §8.2）：GET /traces 检索 + /traces/{agent}/{trace_id} 详情。

- **鉴权**：全部挂 ViewerUser（viewer/admin，§8.1）；正文另按 **admin-only** 门控（见下）。
- **正文门控（2026-09-20，用户拍板改口径）**：正文 = input/output/log_message，放行条件 =
  **`body_search=true` 且调用方 role == admin**。契约 §13.4 原文「需 viewer 及以上 + **该接口**
  body_search=true」的后半**无载体** —— `interface` 表 0 行、无写入端点、`backend/app` 零读取点
  （§8.5 admin Agent 面 2026-09-14 整节撤除时把那个端点一并带走了），故改挂前半（角色）。
  非 admin 传 true **静默按 false 处理**，不 403：403 与 200 的差异本身就是「这条 trace 有正文」
  的信标，为一个不放行的字段开旁路不值得。
- **两层保护**（v1.1 约定，§8.2 注）：① 检索面不命中正文三字段（store 层 multi_match fields
  随开关收窄到 error 字段）；② 响应序列化前把这三字段置 None。两层都不泄露正文。
  ⚠️ 前端**日志请求**（/logs）固定带 true ⇒ 对 admin 而言第 ② 层在 UI 上已放行；默认值未改。
- **运行时键**（§10 dict_config，seed 默认 7/3000）：keyword_search_days 控缺省时间窗，
  trace_query_timeout_ms 控单查询超时。60s 进程缓存（core/dict_config）。
- **结果护栏（§14.4）**：列表深翻页上限 200（offset≥200 拒）；详情单 trace ≤500 截断 +
  truncated 标记；日志懒加载分页。
- **红显口径**：status ∈ {error, timeout}（error_type 是 error 的伴随字段，非红显判据）；
  llm_call 高亮 = node == "llm_call"——前端判，本层只原样出字段。
- 错误：trace 不存在 → ERR_TRACE_0001(404)；检索超时/ES 暂不可用/超限 → ERR_TRACE_0002(400)。
"""
import time
from typing import Annotated

# 同 metrics.py：ES-py 8.x 的 TransportError 与 ApiError 无公共父类，缺后者则
# index 缺失的 404 接不住（详见 metrics.py 顶部注释）。
from elasticsearch.exceptions import ApiError, TransportError
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ViewerUser
from app.api.schemas import Page
from app.core.db import get_session
from app.core.dict_config import get_global_int
from app.core.errors import AppError
from app.store import es as es_store

router = APIRouter(prefix="/traces", tags=["traces"])

_Session = Annotated[AsyncSession, Depends(get_session)]

# dict_config 运行时键（seed 默认：7 天 / 3000ms，§10）
_DEFAULT_SEARCH_DAYS = 7
_DEFAULT_QUERY_TIMEOUT_MS = 3000
_MS_PER_DAY = 86_400_000


# ---------- 响应模型（§8.2；白名单取 key——绝不把 extra/enabled:false 等旁路字段带出） ----------


class TraceListItem(BaseModel):
    """列表行 = 折叠后"最近命中"事件的摘录（命中即代表，未必是 request 根节点）。"""

    agent: str | None = None
    trace_id: str | None = None
    interface: str | None = None
    node: str | None = None
    status: str | None = None
    error_type: str | None = None
    error_msg: str | None = None
    ts: int | None = None


class TraceEventRow(BaseModel):
    """详情事件行（event_kind=event）；input/output 为正文，随 body_search 置空。"""

    seq: int | None = None
    node: str | None = None
    parent: int | None = None
    branch: int | None = None
    interface: str | None = None
    status: str | None = None
    error_type: str | None = None
    error_msg: str | None = None
    ts: int | None = None
    duration_ms: int | None = None
    model: str | None = None
    usage: dict[str, int] | None = None
    input: str | None = None
    output: str | None = None


class TraceDetail(BaseModel):
    agent: str
    trace_id: str
    events: list[TraceEventRow]
    total: int
    truncated: bool


class TraceLogRow(BaseModel):
    """懒加载日志行；log_message 为正文，随 body_search 置空。"""

    seq: int | None = None
    ts: int | None = None
    log_level: str | None = None
    log_message: str | None = None


def _allow_body(body_search: bool, role: str) -> bool:
    """正文放行判定（2026-09-20）：显式请求 **且** admin。理由见模块 docstring「正文门控」。

    收 role 字符串而非 User 对象：本函数是纯判定、不碰 DB，收窄入参也好测。
    """
    return bool(body_search) and role == "admin"


# ---------- 端点 ----------


@router.get("", response_model=Page[TraceListItem])
async def list_traces(
    user: ViewerUser,
    request: Request,
    session: _Session,
    trace_id: str | None = Query(default=None, max_length=64, description="精确 trace_id"),
    keyword: str | None = Query(default=None, max_length=200, description="错误信息关键字"),
    agent: str | None = Query(default=None, max_length=64),
    interface: str | None = Query(default=None, max_length=256),
    status: str | None = Query(
        default=None, max_length=16,
        description="按状态过滤（ok / error / timeout）；判的是该 trace 最新命中行的状态",
    ),
    start_ts: int | None = Query(
        default=None, description="epoch ms；缺省 = now - keyword_search_days"
    ),
    end_ts: int | None = Query(default=None, description="epoch ms；可选"),
    body_search: bool = Query(default=False, description="true 才检索/返回正文三字段"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=es_store.MAX_LIST_RESULTS),
) -> Page[TraceListItem]:
    offset = (page - 1) * page_size
    if offset >= es_store.MAX_LIST_RESULTS:  # §14.4 深翻页上限
        raise AppError(
            "ERR_TRACE_0002", f"检索深度上限 {es_store.MAX_LIST_RESULTS}，请缩小范围", http=400
        )

    settings = request.app.state.settings
    days = await get_global_int(session, "keyword_search_days", _DEFAULT_SEARCH_DAYS)
    timeout_ms = await get_global_int(session, "trace_query_timeout_ms", _DEFAULT_QUERY_TIMEOUT_MS)
    now_ms = int(time.time() * 1000)
    if start_ts is None:
        start_ts = now_ms - days * _MS_PER_DAY
    if end_ts is not None and end_ts < start_ts:
        raise AppError("ERR_TRACE_0002", "end_ts 不得早于 start_ts", http=400)

    try:
        result = await es_store.search_traces(
            request.app.state.es_query,
            settings=settings,
            request_timeout_s=max(timeout_ms / 1000, 1.0),
            trace_id=trace_id,
            keyword=keyword,
            agent=agent,
            interface=interface,
            status=status,
            start_ts=start_ts,
            end_ts=end_ts,
            body_search=_allow_body(body_search, user.role),
            from_=offset,
            size=page_size,
        )
    except (TransportError, ApiError) as exc:  # 超时/连接失败/5xx → §8.2 检索护栏
        raise AppError("ERR_TRACE_0002", f"检索暂不可用或超时: {exc}", http=400) from exc

    items = [
        TraceListItem(
            **{k: h.get(k) for k in ("agent", "trace_id", "interface", "node", "status",
                                     "error_type", "error_msg", "ts")}
        )
        for h in result["hits"]
    ]
    return Page(items=items, total=result["total"], page=page, page_size=page_size)


@router.get("/{agent}/{trace_id}", response_model=TraceDetail)
async def trace_detail(
    user: ViewerUser,
    request: Request,
    session: _Session,
    agent: str,
    trace_id: str,
    body_search: bool = Query(default=False, description="true 才返回 input/output"),
) -> TraceDetail:
    timeout_ms = await get_global_int(session, "trace_query_timeout_ms", _DEFAULT_QUERY_TIMEOUT_MS)
    try:
        result = await es_store.fetch_trace_events(
            request.app.state.es_query,
            settings=request.app.state.settings,
            agent=agent,
            trace_id=trace_id,
            request_timeout_s=max(timeout_ms / 1000, 1.0),
        )
    except (TransportError, ApiError) as exc:
        raise AppError("ERR_TRACE_0002", f"检索暂不可用或超时: {exc}", http=400) from exc

    hits = result["hits"]
    if not hits:
        raise AppError("ERR_TRACE_0001", f"trace 不存在或已过保留期: {agent}/{trace_id}", http=404)

    _KEYS = ("seq", "node", "parent", "branch", "interface", "status", "error_type",
             "error_msg", "ts", "duration_ms", "model", "usage")
    allow_body = _allow_body(body_search, user.role)
    events: list[TraceEventRow] = []
    for h in hits:
        row = TraceEventRow(**{k: h.get(k) for k in _KEYS})
        if allow_body:  # admin 显式请求时回填（两层正文保护，§8.2 注）
            row.input = h.get("input")
            row.output = h.get("output")
        events.append(row)
    return TraceDetail(
        agent=agent, trace_id=trace_id, events=events,
        total=result["total"], truncated=result["truncated"],
    )


@router.get("/{agent}/{trace_id}/logs", response_model=Page[TraceLogRow])
async def trace_logs(
    user: ViewerUser,
    request: Request,
    session: _Session,
    agent: str,
    trace_id: str,
    body_search: bool = Query(default=False, description="true 才返回 log_message"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> Page[TraceLogRow]:
    timeout_ms = await get_global_int(session, "trace_query_timeout_ms", _DEFAULT_QUERY_TIMEOUT_MS)
    offset = (page - 1) * page_size
    try:
        result = await es_store.fetch_trace_logs(
            request.app.state.es_query,
            settings=request.app.state.settings,
            agent=agent,
            trace_id=trace_id,
            request_timeout_s=max(timeout_ms / 1000, 1.0),
            from_=offset,
            size=page_size,
        )
    except (TransportError, ApiError) as exc:
        raise AppError("ERR_TRACE_0002", f"检索暂不可用或超时: {exc}", http=400) from exc

    allow_body = _allow_body(body_search, user.role)
    items = [
        TraceLogRow(seq=h.get("seq"), ts=h.get("ts"), log_level=h.get("log_level"),
                    log_message=h.get("log_message") if allow_body else None)
        for h in result["hits"]
    ]
    return Page(items=items, total=result["total"], page=page, page_size=page_size)
