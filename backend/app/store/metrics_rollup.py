"""7d 小时级 rollup 存储层（detail §5.3 + §8.4，T-2.3）。

- 单 index `{env}.obs-metrics-rollup`（前缀拼装复用 config 的 {resource_env} 命名，
  detail §3.3/§5.2 租户隔离；本文件与 consumer/es.py 写侧/query 侧 es.py 对称但独立）。
- doc 维度 agent×interface×node×(model)×hour：request 级（node=request，model=""）存
  total/error/timeout + duration 分位 sketch；llm_call 级（node=llm_call，model 有值）另存
  prompt/completion_tokens 累计。红色语义 = status∈{error,timeout} 各自独立计数（读侧与
  实时口径对拍：llm 失败率=(error+timeout)/total）。
- mapping dynamic:false + 白名单（§5.2 惯例）。sketch = t-digest 序列化 JSON-base64（v1 版式）。
- **确定性 _id** = sha256("rollup|agent|interface|node|model|hour") → 整小时重算同 _id 覆写
  幂等（worker 迟到重算不双计）；meta doc `meta|{hour}` 记源计数供廉价迟到探测。
- dev 用 ensure_rollup_index 自建（幂等）；生产 index 由 infra template 接管（§13.3）。
  读助手（已完成小时列表 / 分位 merge）供 metrics API 7d 接缝用——见模块尾部函数。
"""
import hashlib
from datetime import datetime, timezone

from app.core.config import Settings
from app.store.tdigest import TDigest

SCHEMA_VERSION = "1"
_HOUR_FORMAT = "%Y-%m-%dT%H:00"
_MS_PER_HOUR = 3_600_000

# §5.3 rollup mapping（dynamic:false）。hour/ts 双写：hour 便于 keyword 归并、ts 供 date_histogram。
ROLLUP_MAPPING = {
    "dynamic": False,
    "properties": {
        "schema_version": {"type": "keyword"},
        "doc_type": {"type": "keyword"},  # "group"=组 doc / "meta"=小时 meta（检索判别）
        "agent": {"type": "keyword"},
        "interface": {"type": "keyword"},
        "node": {"type": "keyword"},
        "model": {"type": "keyword"},
        "hour": {"type": "keyword"},
        "ts": {"type": "date", "format": "epoch_millis"},
        "updated_ts": {"type": "date", "format": "epoch_millis"},
        "total": {"type": "long"},
        "error": {"type": "long"},
        "timeout": {"type": "long"},
        "prompt_tokens": {"type": "long"},
        "completion_tokens": {"type": "long"},
        "sketch": {"type": "keyword"},  # t-digest JSON-base64（payload ~几 KB/组）
    },
}

# 需要参与 rollup 计数的 node（其余 node 如 heartbeat/log 与指标口径无关）
ROLLUP_NODES = ("request", "llm_call")


def rollup_index_name(settings: Settings) -> str:
    """`{resource_env}.obs-metrics-rollup`（非周滚动：小时粒度单 index，总量可控）。"""
    return f"{settings.resource_env}.obs-metrics-rollup"


def floor_hour_ms(ts_ms: int) -> int:
    """ts(ms UTC) → 所在 UTC 整点小时起点（epoch ms）。"""
    return ts_ms - (ts_ms % _MS_PER_HOUR)


def hour_key_of(hour_start_ms: int) -> str:
    """小时起点 → `yyyy-MM-ddTHH:00`（UTC，rollup hour keyword）。"""
    return datetime.fromtimestamp(hour_start_ms / 1000, tz=timezone.utc).strftime(_HOUR_FORMAT)


def rollup_doc_id(agent: str, interface: str, node: str, model: str, hour: str) -> str:
    """确定性 _id：同小时同组重算同 _id 覆写幂等（worker 迟到重算不双计，§5.3）。"""
    raw = f"rollup|{agent}|{interface}|{node}|{model}|{hour}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def rollup_meta_id(hour: str) -> str:
    """小时级 meta doc _id：存该小时源事件计数，供下轮廉价迟到探测比对。"""
    return f"rollup-meta|{hour}"


def build_rollup_doc(
    *, agent: str, interface: str, node: str, model: str, hour: str,
    hour_start_ms: int, total: int, error: int, timeout: int,
    prompt_tokens: int, completion_tokens: int, digest: TDigest | None,
    updated_ts: int,
) -> dict:
    """组级 rollup doc（sketch 由 digest 序列化；无 duration 样本 → sketch=None 不落）。"""
    doc = {
        "schema_version": SCHEMA_VERSION,
        "doc_type": "group",
        "agent": agent,
        "interface": interface,
        "node": node,
        "model": model,
        "hour": hour,
        "ts": hour_start_ms,
        "updated_ts": updated_ts,
        "total": int(total),
        "error": int(error),
        "timeout": int(timeout),
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
    }
    if digest is not None and digest.total() > 0:
        doc["sketch"] = digest.serialize()
    return doc


def build_meta_doc(*, hour: str, source_count: int, updated_ts: int) -> dict:
    """小时 meta：源事件计数（廉价比对基础，§5.3 迟到探测）。"""
    return {"hour": hour, "source_count": int(source_count),
            "updated_ts": int(updated_ts), "schema_version": SCHEMA_VERSION,
            "doc_type": "meta"}


async def ensure_rollup_index(client, settings: Settings) -> None:
    """dev 自建 rollup index（幂等：exists 跳过 / create 已存在视为成功）。"""
    index = rollup_index_name(settings)
    if await client.indices.exists(index=index):
        return
    try:
        # 单节点 dev 显式 replica=0：默认 replica=1 无法分配 → 集群 yellow、healthcheck(须 green)假阴性（2026-09-09 C1）
        await client.indices.create(
            index=index, mappings=ROLLUP_MAPPING, settings={"index": {"number_of_replicas": 0}}
        )
    except Exception as exc:  # 竞态已建视为成功；其余异常上抛给 job 自愈
        if "resource_already_exists_exception" not in str(exc):
            raise


def _rollup_event_filter(hour_start_ms: int) -> dict:
    """源事件检索 filter：整点小时窗 + node∈{request,llm_call}（其余与指标口径无关）。"""
    return {
        "bool": {
            "filter": [
                {"range": {"ts": {
                    "gte": hour_start_ms,
                    "lt": hour_start_ms + _MS_PER_HOUR,
                }}},
                {"terms": {"node": list(ROLLUP_NODES)}},
            ]
        }
    }


# ---------- 读侧（metrics API 7d 接缝消费；#127 后由 metrics.py 接入） ----------


async def fetch_rollup_hits(
    client, *, settings: Settings, request_timeout_s: float,
    start_ms: int, end_ms: int, size: int = 10_000,
) -> list[dict]:
    """rollup doc 批量拉取（date 范围 + 可选 agent/interface/node 过滤由调用方拼）。

    返回 _source 原样列表；用于 7d 已完成小时聚合/分位 merge（metrics API / T-2.4）。
    """
    body = {
        "query": {"bool": {"filter": [
            {"range": {"ts": {"gte": start_ms, "lt": end_ms}}},
        ]}},
        "sort": [{"hour": {"order": "asc"}}],
        "_source": True,
        "size": size,
    }
    resp = await client.options(request_timeout=request_timeout_s).search(
        index=rollup_index_name(settings), body=body
    )
    return [h["_source"] for h in resp["hits"]["hits"]]


async def fetch_rollup_covered_hours(
    client, *, settings: Settings, request_timeout_s: float,
    start_ms: int, end_ms: int, size: int = 2000,
) -> list[int]:
    """范围内**已 rollup**（meta doc 在）的小时起点（epoch ms 升序）——读侧覆盖基准。

    覆盖判定用 meta 而非组 doc：rollup_job 对处理过的小时**恒写 meta**（含零流量小时，见
    rollup_job._process_hour 末段无条件写 meta）→ 「已处理但空」与「真实缺口（未处理）」
    可区分，避免把空小时当缺口永久实时回补。meta doc 小时级全局一张（rollup_meta_id，无
    agent 维度；agent 各行落入同一小时处理，小时处理过即该小时各 agent 切片已折叠）。
    hour keyword 为 UTC `yyyy-MM-ddTHH:00` 定长串，字典序 == 时间序 → 区间检索即窗口过滤。
    """
    body = {
        "query": {"bool": {"filter": [
            {"term": {"doc_type": "meta"}},
            {"range": {"hour": {
                "gte": hour_key_of(floor_hour_ms(start_ms)),
                "lte": hour_key_of(floor_hour_ms(end_ms)),
            }}},
        ]}},
        "sort": [{"hour": {"order": "asc"}}],
        "_source": ["hour"],
        "size": size,
    }
    resp = await client.options(request_timeout=request_timeout_s).search(
        index=rollup_index_name(settings), body=body
    )
    out: list[int] = []
    for h in resp["hits"]["hits"]:
        key = (h.get("_source") or {}).get("hour")
        if key:
            dt = datetime.strptime(key, _HOUR_FORMAT).replace(tzinfo=timezone.utc)
            out.append(int(dt.timestamp() * 1000))
    return out


def merge_digests(sources: list[dict], pcts: tuple[float, ...] = ()) -> dict:
    """一批 rollup source（同 node/同 agent 粒度）→ merge 后 {total, error, timeout, p{50,95,99}?}。

    只 merge 带 sketch 的 doc；无 sketch 小时（该组无 duration 样本）不贡献分位。
    """
    merged = TDigest()
    total = error = timeout = 0
    for s in sources:
        total += int(s.get("total") or 0)
        error += int(s.get("error") or 0)
        timeout += int(s.get("timeout") or 0)
        sketch = s.get("sketch")
        if sketch:
            merged.merge(TDigest.deserialize(sketch))
    merged.compress()
    out = {"total": total, "error": error, "timeout": timeout}
    for q in pcts:
        out[f"p{int(q * 100)}"] = merged.percentile(q)
    return out
