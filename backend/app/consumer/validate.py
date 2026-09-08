"""消费校验入口（detail §4.2）：schema/组合语义 + extra 白名单 → 丢弃原因分类。

丢弃原因分型（selfmonitor.dropped.* 计数键，D5 装配时聚合）：
- SCHEMA：结构/类型/枚举外/组合语义/未知顶层字段（X-1 多余未知字段）
- EXTRA_KEY：extra 白名单外扩展键（§2.9）
- AGENT_MISMATCH：topic 与 agent 归属不一致 / 白名单外 agent（D5 编排层判）
- MASK：未掩码敏感键（D2 脱敏复核判）

`ts` 漂移只告警不丢弃（§3.4）→ 本层不校验漂移，水位判断归消费编排。
"""
from enum import Enum

from pydantic import ValidationError

from app.consumer.schema import EXTRA_ALLOWED, EventModel


class DropCode(str, Enum):
    """丢弃原因（计数分型；值即 selfmonitor.dropped 子键后缀）。"""

    SCHEMA = "schema"
    EXTRA_KEY = "extra_key"
    AGENT_MISMATCH = "agent_mismatch"
    MASK = "mask"


def validate_event(raw: dict) -> tuple[EventModel | None, DropCode | None]:
    """校验一条事件：通过 → (EventModel, None)；拒绝 → (None, DropCode)。

    raw 非 dict（null/标量/数组）同样落入 SCHEMA（X-1 整体 null 事件拒绝路径）。
    """
    if not isinstance(raw, dict):
        return None, DropCode.SCHEMA
    try:
        event = EventModel.model_validate(raw)
    except ValidationError:
        return None, DropCode.SCHEMA
    # extra 白名单外键：整条丢弃并计数（§2.9），与结构错分开分型
    if not EXTRA_ALLOWED.issuperset(event.extra.keys()):
        return None, DropCode.EXTRA_KEY
    return event, None
