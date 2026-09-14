"""运行时键读取（detail §10 / §8.2 检索护栏）：dict_config 全局标量键 → 查询护栏参数。

- **范围**：只读本批用到的全局键（keyword_search_days / trace_query_timeout_ms）。
  （**2026-09-14 订正**）per-agent 键的读取在 `converter/no_fallback_cfg.py`（组装瞬间读，
  不走本层缓存）；配置**管理面**（§8.6 写侧）已由 T-3.12 落地于 `api/admin.py`——写入后调
  本模块 `invalidate_cache()` 清缓存。
- **60s 进程内缓存**：对齐阶段 2 O-1 护栏先例（metric_agg_cache_ttl_s=60），避免 trace
  列表每次检索都多一次 MySQL 往返（计划自审薄弱点 #2 预埋）；无配置写入时生效延迟 ≤60s，
  **经 §8.6 写入的变更因 `invalidate_cache()` 而即时生效**。
- **缺键回退**：seed 已写全局键默认（7/3000），但查询层仍须防御缺行（库未 seed / 被删），
  缺键时返回调用方默认值并同样缓存 60s，防缺键每请求打库。
- 表口径：config_value 为 JSON 列，seed 以 json.dumps(标量) 落库 → ORM 读出原生 int 等
  （models/config.py）；本层只读不写。
- **无锁设计**：幂等读缓存，miss 并发最多重复查一次 DB，无脏写；不用模块级 asyncio.Lock——
  单测多 TestClient 各起 event loop，模块级锁跨 loop 绑定会 RuntimeError。
"""
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import DictConfig

_DEFAULT_TTL_S = 60
_cache: dict[str, tuple[float, Any]] = {}


def invalidate_cache() -> None:
    """清空进程内缓存（§8.6 配置写入后调用）。

    单实例（uvicorn --workers 1）语义下即「变更即时生效」；多实例部署时本函数只清本进程
    缓存，其余实例仍受 60s TTL 约束——届时应改为跨进程失效机制。
    """
    _cache.clear()


async def get_global_config(
    session: AsyncSession, key: str, default: Any, *, ttl_s: int = _DEFAULT_TTL_S
) -> Any:
    """读全局键（agent_id IS NULL），带 ttl 缓存；缺行回退 default。"""
    now = time.monotonic()
    hit = _cache.get(key)
    if hit is not None and now - hit[0] < ttl_s:
        return hit[1]

    value = default
    result = await session.execute(
        select(DictConfig.config_value).where(
            DictConfig.config_key == key,
            DictConfig.agent_id.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is not None:
        value = row
    _cache[key] = (time.monotonic(), value)
    return value


async def get_global_int(session: AsyncSession, key: str, default: int) -> int:
    """整型全局键读取（keyword_search_days 等）；非 int 形态回退默认。"""
    value = await get_global_config(session, key, default)
    # bool 是 int 子类，须显式排除，否则 True/False 会被当成 1/0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return default
