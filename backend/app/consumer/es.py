"""事件/日志 ES 分派（detail §4.1 step5 / §5.2 + S-3 幂等覆写）。

- index：`{prefix}-yyyyWW` 周滚动（§5.2）。prefix = `{env}.obs-event` / `{env}.obs-log`
  （config 只出前缀，WW 拼装在此处）；周按事件 ts 归属（ISO 年周，§3.4 ts 用于归窗）。
- `_id = sha256(agent|trace_id|seq)`：seq trace 内全局唯一 + agent 入键防跨 agent 同
  trace_id 互覆（§5.2）→ at-least-once 重投由同 index 同 _id 幂等覆盖（S-3）。
- mapping `dynamic:false` + 白名单字段（§5.2）：`input/output` 声明 text，若值非 str
  （obj/list/标量）须先序列化为文本再落，否则 mapping 解析拒收——明文形态进正文；
  `quality/retrieve_hit/session_ctx/extra` enabled:false（二期占位，只存 _source 不索引）。
- 中文分词（§5.2 analyzer `zh` = ik_max_word）：四个正文/检索字段（input/output/log_message/
  error_msg）声明 `analyzer: zh`，settings 内 custom wrapper（tokenizer `ik_max_word`）。
  本映射与生产 index template **同构**（template 权威源 infra 侧，§13.3；本文件 body 与
  `es-template/` 提交物同源，防漂移见 es-template/README）。IK 插件随 infra ES 镜像装入；
  「无插件则标准分词回退」由部署侧保证插件就位，映射本体不写 fallback。
- dev 期 create-index-with-mapping 助手（ensure_weekly_index）仅 dev 环境调用；生产 index
  由 infra template 接管（index 不存在时写入自动按 template 建，本文件分派不做显式建）。
- **失败语义（§4.1 step5 边界）**：本模块只做"分派 + 抛 EsDispatchError"；写失败后的
  退避重试 / 超阈值显式丢弃计数 / rollup 缺口标记归属主循环（D5 step6）与 §5.3 rollup
  job（T-3.x 指标阶段，rollup 建成后标缺口才落得下）——本层不静默吞。
"""
import hashlib
import json
from datetime import datetime, timezone

from app.consumer.schema import EventModel
from app.core.config import Settings

# §5.2 白名单字段（dynamic:false）。dev 建 index 用；生产 template 由 infra 维护同构映射。
_MAPPING = {
    "dynamic": False,
    "properties": {
        "schema_version": {"type": "keyword"},
        "event_kind": {"type": "keyword"},
        "trace_id": {"type": "keyword"},
        "agent": {"type": "keyword"},
        # 检索折叠键（§8.2）：concrete keyword（doc_values）供列表 collapse——runtime 字段
        # 不被 collapse 支持（实测 400）；agent#trace_id 由 build_doc 写入，跨 agent 同
        # trace_id 不互并。heartbeat 无 trace_id 不写（列表已 must_not node=heartbeat）。
        "trace_key": {"type": "keyword"},
        "agent_version": {"type": "keyword"},
        "interface": {"type": "keyword"},
        "node": {"type": "keyword"},
        "seq": {"type": "integer"},
        "branch": {"type": "integer"},
        "parent": {"type": "integer"},
        "ts": {"type": "date", "format": "epoch_millis"},
        "@timestamp": {"type": "date"},
        "duration_ms": {"type": "long"},
        "status": {"type": "keyword"},
        "error_type": {"type": "keyword"},
        "error_msg": {"type": "text", "analyzer": "zh"},
        "input": {"type": "text", "analyzer": "zh", "fields": {"kw": {"type": "keyword"}}},
        "output": {"type": "text", "analyzer": "zh"},
        "usage": {
            "properties": {
                "prompt_tokens": {"type": "long"},
                "completion_tokens": {"type": "long"},
                "total_tokens": {"type": "long"},
            }
        },
        "model": {"type": "keyword"},
        "log_level": {"type": "keyword"},
        "log_message": {"type": "text", "analyzer": "zh"},
        "quality": {"enabled": False},  # 二期占位：不索引无倒排成本（§2.8）
        "retrieve_hit": {"enabled": False},
        "session_ctx": {"enabled": False},
        "extra": {"enabled": False},
    },
}

# 本地/独立集群默认（§5.2）。analysis.analyzer.zh = ik_max_word custom wrapper：analysis-ik
# 插件把 ik_max_word 注册为 tokenizer（非 analyzer type），须包一层 custom analyzer 供字段引用。
_SETTINGS = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
        "analyzer": {
            "zh": {"type": "custom", "tokenizer": "ik_max_word"},
        }
    },
}

_TEXT_SOURCE_FIELDS = ("input", "output")  # 声明 text：非 str 值须序列化后再落


class EsDispatchError(Exception):
    """ES 写失败（含 index 缺失拒收等 400/503）。调用方据此决定重试/丢弃路径。"""


def iso_week(ts_ms: int) -> tuple[int, int]:
    """事件 ts(ms UTC) → (ISO 年, ISO 周)（§5.2 yyyyWW 周滚动归属）。"""
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isocalendar()[:2]


def weekly_index_name(prefix: str, ts_ms: int) -> str:
    """周滚动 index 名：`{prefix}-yyyyWW`（WW 补零两位）。"""
    year, week = iso_week(ts_ms)
    return f"{prefix}-{year}{week:02d}"


def doc_id(agent: str, trace_id: str, seq: int) -> str:
    """`_id = sha256(agent|trace_id|seq)`（§5.2；agent 入键防跨 agent 互覆）。"""
    raw = f"{agent}|{trace_id}|{seq}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_doc(event: EventModel) -> dict:
    """事件 → ES 文档体。input/output 非 str 序列化为文本（mapping text 拒收对象）；None 不入。"""
    doc = event.model_dump(exclude_none=True)
    for field in _TEXT_SOURCE_FIELDS:
        value = doc.get(field)
        if value is not None and not isinstance(value, str):
            # 明文落正文（§5.2 input/output 检索面）；sort_keys 保证同语义文本稳定
            doc[field] = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if doc.get("agent") and doc.get("trace_id"):  # 折叠键：heartbeat 等无 trace_id 的不写
        doc["trace_key"] = f"{doc['agent']}#{doc['trace_id']}"
    return doc


async def dispatch_event(client, event: EventModel, settings: Settings) -> dict:
    """单事件分派：event/log 分流 → 周 index + _id 幂等覆写。

    返回 {index, _id}（供 D5 自监控/日志透出）；写失败抛 EsDispatchError 不静默。
    """
    prefix = settings.log_index_prefix if event.event_kind == "log" else settings.event_index_prefix
    index = weekly_index_name(prefix, event.ts)
    _id = doc_id(event.agent, event.trace_id, event.seq)
    try:
        await client.index(index=index, id=_id, document=build_doc(event))
    except Exception as exc:  # 客户端异常形态多样，统一收口给主循环分类
        raise EsDispatchError(f"index={index} id={_id} 写入失败: {exc}") from exc
    return {"index": index, "_id": _id}


async def ensure_weekly_index(client, prefix: str, ts_ms: int) -> str:
    """dev 自建 index（缺则建，带 §5.2 mapping；建过即跳过幂等）。

    仅 dev 环境调用（D6 集成 / lifespan 启动守卫）；生产 index template 归 infra（§13.3）。
    竞态：exists→create 两跳间另一实例已建 → create 抛 resource_already_exists 视为成功。
    """
    index = weekly_index_name(prefix, ts_ms)
    if await client.indices.exists(index=index):
        return index
    try:
        await client.indices.create(index=index, mappings=_MAPPING, settings=_SETTINGS)
    except Exception as exc:  # 竞态已建视为成功；其余异常抛给调用方
        if "resource_already_exists_exception" not in str(exc):
            raise EsDispatchError(f"index={index} 创建失败: {exc}") from exc
    return index
