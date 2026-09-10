"""链路查询 API（detail §8.2）：GET /traces 检索 + /traces/{agent}/{trace_id} 详情。

- **鉴权**：全部挂 ViewerUser（viewer/admin，§8.1）；正文可见度再按 body_search 参数分层。
- **正文保护（v1.1 约定，§8.2 注 / §13.4 两层）**：body_search=false（默认）时——① 检索面
  不命中 input/output/log_message（store 层 multi_match fields 随开关收窄到 error 字段）；
  ② 响应序列化前把这三字段置 None。两层都不泄露正文；body_search=true 仅显式放行
  （curl/S-5 验收用）。
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

from elasticsearch.exceptions import TransportError
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
            start_ts=start_ts,
            end_ts=end_ts,
            body_search=body_search,
            from_=offset,
            size=page_size,
        )
    except TransportError as exc:  # 超时/连接失败/5xx → §8.2 检索护栏
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
    except TransportError as exc:
        raise AppError("ERR_TRACE_0002", f"检索暂不可用或超时: {exc}", http=400) from exc

    hits = result["hits"]
    if not hits:
        raise AppError("ERR_TRACE_0001", f"trace 不存在或已过保留期: {agent}/{trace_id}", http=404)

    _KEYS = ("seq", "node", "parent", "branch", "interface", "status", "error_type",
             "error_msg", "ts", "duration_ms", "model", "usage")
    events: list[TraceEventRow] = []
    for h in hits:
        row = TraceEventRow(**{k: h.get(k) for k in _KEYS})
        if body_search:  # 正文仅显式放行时回填（两层正文保护，§8.2 注）
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
    except TransportError as exc:
        raise AppError("ERR_TRACE_0002", f"检索暂不可用或超时: {exc}", http=400) from exc

    items = [
        TraceLogRow(seq=h.get("seq"), ts=h.get("ts"), log_level=h.get("log_level"),
                    log_message=h.get("log_message") if body_search else None)
        for h in result["hits"]
    ]
    return Page(items=items, total=result["total"], page=page, page_size=page_size)
