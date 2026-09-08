"""worker rollup_job：7d 小时级指标预聚合（detail §5.3 + §8.4，T-2.3）。

- 入口 `run_rollup(engine, es, settings, *, logger)`（worker/main.py `_rollup_loop` 每整点
  后调用；main.py 已对齐整点，本函数不做睡整点只做**已完成小时的迟到回填**）。
- 每次跑「最近 rollup_late_k_h 个已完成小时」（seed 默认 6，dict_config 键可调），对每个小时：
  1) **廉价探测**：读 meta doc（source_count）↔ `es.count` 源事件数比对——一致 = 该小时已
     rollup 且无迟到 → 跳过（避免每轮重放 6h，§5.3 迟到探测）；
  2) 不一致/缺 meta → **全量重算**：search_after 分页读原始事件（sort ts/trace_key/seq 全序
     确定性）→ 按 (agent, interface, node, model) 分组计数 + duration Counter → digest 折叠
     → 逐组写 rollup doc（确定性 _id 覆写，幂等）→ 写小时 meta doc。
- 超 rollup_late_k_h 的老小时缺口不回填：读取侧对缺桶小时回退实时口径（fallback_hours
  明示缺口，metrics API 已按该语义实现）。
- 写失败/ES 异常：该小时 logger.exception 跳过，下轮自愈（不中断其余小时）；DB 读配置异常
  上抛由 worker loop 退避。
- 分批写入用逐 doc `client.index`（小时组数 ~ 几十~几百，整点低频可接受；超量再上 bulk）。
"""
import time
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings
from app.core.dict_config import get_global_int
from app.core.log import get_logger
from app.store import metrics_rollup as store
from app.store.es import event_index_patterns
from app.store.tdigest import TDigest

_LATE_K_DEFAULT = 6     # rollup_late_k_h 缺键回退（seed 落同值）
_PAGE = 5000            # search_after 分页 size（§5.3 chunk 5000）
_ES_TIMEOUT_S = 60      # rollup 读源超时（低频整点任务，给足余量）
_MS_PER_HOUR = 3_600_000

# 源事件只取参与计数的字段（usage.tokens 嵌套、duration_ms 聚合、model 分组用）
_SOURCE_FIELDS = [
    "agent", "interface", "node", "model", "status",
    "duration_ms", "ts", "trace_key", "seq",
    "usage.prompt_tokens", "usage.completion_tokens",
]


def _utc_now_ms() -> int:
    return int(time.time() * 1000)


def _late_hour_starts(now_ms: int, late_k: int) -> list[int]:
    """本次要处理的已完成小时起点（旧→新）：[now 所在小时起 − k·1h]，k=late_k..1。

    now 所在小时是进行中小时（offset 0）不算已完成；offset≥1 的小时窗口
    [now_h − k·1h, now_h − (k−1)·1h) 已完全闭合。
    """
    now_h = store.floor_hour_ms(now_ms)
    return [now_h - k * _MS_PER_HOUR for k in range(late_k, 0, -1)]


# ---------- 廉价探测（§5.3：count 比对 meta，差异小时才重算） ----------


def _decide_recompute(meta_source_count: int | None, source_count: int) -> bool:
    """meta 缺/过期（计数不一致）才全量重算；一致返回 False（跳过）。"""
    return meta_source_count is None or meta_source_count != source_count


async def _hour_meta(es, settings: Settings, hour_start_ms: int) -> int | None:
    """读小时 meta doc 的 source_count；无 meta（未 rollup/跨过初启窗口）返回 None。"""
    resp = await es.options(request_timeout=_ES_TIMEOUT_S).search(
        index=store.rollup_index_name(settings),
        body={
            "query": {"bool": {"filter": [
                {"term": {"doc_type": "meta"}},
                {"term": {"hour": store.hour_key_of(hour_start_ms)}},
            ]}},
            "size": 1,
            "_source": ["source_count"],
        },
    )
    hits = resp["hits"]["hits"]
    return int(hits[0]["_source"]["source_count"]) if hits else None


async def _source_count(es, settings: Settings, hour_start_ms: int) -> int:
    """源事件廉价 count（request/llm_call 在小时窗内命中数；与全量重算消耗口径一致）。"""
    resp = await es.count(
        index=event_index_patterns(settings),
        query=store._rollup_event_filter(hour_start_ms),
    )
    return int(resp["count"])


# ---------- 全量重算（分组计数 → digest → rollup doc） ----------


def _accumulate(src: dict, accs: dict) -> bool:
    """把一条源事件计入分组累加器；非计数事件（node 不匹配）返回 False 不计 source_count。"""
    node = src.get("node")
    agent = src.get("agent")
    if not agent or node not in store.ROLLUP_NODES:
        return False
    key = (agent, src.get("interface") or "", node, src.get("model") or "")
    acc = accs.setdefault(
        key, {"total": 0, "error": 0, "timeout": 0, "pt": 0, "ct": 0, "dur": Counter()})
    acc["total"] += 1
    status = src.get("status")
    if status == "error":
        acc["error"] += 1
    elif status == "timeout":
        acc["timeout"] += 1
    usage = src.get("usage") or {}
    pt, ct = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if isinstance(pt, (int, float)):
        acc["pt"] += int(pt)
    if isinstance(ct, (int, float)):
        acc["ct"] += int(ct)
    d = src.get("duration_ms")
    if isinstance(d, (int, float)) and d >= 0:
        acc["dur"][int(d)] += 1  # ms 整数去重喂 digest（README：distinct × 次数，成本可控）
    return True


def _fold_docs(accs: dict, *, hour_start_ms: int, updated_ts: int) -> list[dict]:
    """分组累加器 → rollup doc 列表（确定性排序；digest 由 dur Counter 折叠压缩后序列化）。"""
    docs = []
    hour = store.hour_key_of(hour_start_ms)
    for key, acc in sorted(accs.items()):
        agent, interface, node, model = key
        digest = None
        if acc["dur"]:
            digest = TDigest()
            for d, c in acc["dur"].items():
                digest.update(d, c)
            digest.compress()
        docs.append(store.build_rollup_doc(
            agent=agent, interface=interface, node=node, model=model,
            hour=hour, hour_start_ms=hour_start_ms,
            total=acc["total"], error=acc["error"], timeout=acc["timeout"],
            prompt_tokens=acc["pt"], completion_tokens=acc["ct"],
            digest=digest, updated_ts=updated_ts,
        ))
    return docs


async def _process_hour(
    es, settings: Settings, hour_start_ms: int, updated_ts: int,
) -> tuple[str, int]:
    """重算/跳过一个小时候；返回 (动作, source_count)。动作 ∈ {"skip", "rebuilt"}。"""
    meta_count = await _hour_meta(es, settings, hour_start_ms)
    count = await _source_count(es, settings, hour_start_ms)
    if not _decide_recompute(meta_count, count):
        return "skip", count

    index = store.rollup_index_name(settings)
    hour = store.hour_key_of(hour_start_ms)
    accs: dict = {}
    consumed = 0
    sort = [
        {"ts": {"order": "asc"}},
        {"trace_key": {"order": "asc"}},  # (ts, trace_key, seq) 全序 → search_after 确定性翻页
        {"seq": {"order": "asc"}},
    ]
    search_after: list | None = None
    while True:
        body = {
            "query": store._rollup_event_filter(hour_start_ms),
            "sort": sort,
            "_source": _SOURCE_FIELDS,
            "size": _PAGE,
        }
        if search_after is not None:
            body["search_after"] = search_after
        resp = await es.options(request_timeout=_ES_TIMEOUT_S).search(
            index=event_index_patterns(settings), body=body)
        hits = resp["hits"]["hits"]
        if not hits:
            break
        for h in hits:
            if _accumulate(h["_source"], accs):
                consumed += 1
        if len(hits) < _PAGE:
            break
        last = hits[-1]["sort"]
        search_after = [last[0], last[1], last[2]]

    # 写组 doc（确定性 _id 覆写幂等）+ 小时 meta doc（下轮廉价探测基准）
    for doc in _fold_docs(accs, hour_start_ms=hour_start_ms, updated_ts=updated_ts):
        await es.index(
            index=index,
            id=store.rollup_doc_id(doc["agent"], doc["interface"], doc["node"],
                                    doc["model"], hour),
            document=doc,
        )
    await es.index(
        index=index,
        id=store.rollup_meta_id(hour),
        document=store.build_meta_doc(hour=hour, source_count=consumed,
                                      updated_ts=updated_ts),
    )
    return "rebuilt", consumed


# ---------- 主入口 ----------


async def run_rollup(
    engine: AsyncEngine, es, settings: Settings, *, logger=None,
) -> dict:
    """跑一轮小时级 rollup（worker 整点调用）：迟到窗口逐小时重算/跳过。返回统计。"""
    logger = logger or get_logger("worker.rollup")
    async with AsyncSession(engine) as session:
        late_k = await get_global_int(session, "rollup_late_k_h", _LATE_K_DEFAULT)
    await store.ensure_rollup_index(es, settings)
    now_ms = _utc_now_ms()
    updated_ts = now_ms
    rebuilt, skipped = 0, 0
    for hour_start_ms in _late_hour_starts(now_ms, max(late_k, 1)):
        action, consumed = await _process_hour(es, settings, hour_start_ms, updated_ts)
        if action == "rebuilt":
            rebuilt += 1
        else:
            skipped += 1
        logger.debug("rollup 小时处理", extra={
            "hour": store.hour_key_of(hour_start_ms), "action": action,
            "source_count": consumed, "late_k": late_k})
    logger.info("rollup 完成", extra={"rebuilt": rebuilt, "skipped": skipped})
    return {"rebuilt_hours": rebuilt, "skipped_hours": skipped}
