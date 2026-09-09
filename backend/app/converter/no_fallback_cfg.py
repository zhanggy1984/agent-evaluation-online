"""no_fallback 词表固化读取（detail §6.3 step3 / §7.1 / §10.1）。

组装瞬间从 dict_config 读 per-agent `fallback_utterance`（JSON 词条数组）：
- `words` = config_value（JSON 列 ORM 读回即 list）；`wordlist_version` = config.version
  （fallback_utterance 的 version 即 D19 wordlist_version，变更 +1，admin-only）。
- `fallback_utterance` 是 **per-agent 键**（seed GLOBAL_DEFAULTS 无此项 → 无全局回退概念）；
  agent 行缺失 / 配置行缺失 → `([], 0)` 防御——空词表信封照建（fail-closed 载体
  words==[]，offline 结构自检 content_gap 判不过，§6.3 step3）。
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.config import DictConfig

BACKFLOW_UTTERANCE_KEY = "fallback_utterance"


def parse_words(value) -> list[str]:
    """config_value → 词条数组（防御非 list 脏列值 → []，不崩组装）。"""
    if isinstance(value, list):
        return value
    return []


async def resolve_fallback_wordlist(
    session: AsyncSession, *, agent_name: str
) -> tuple[list[str], int]:
    """组装瞬间取 per-agent fallback_utterance 词表 → (words, wordlist_version)。

    命中：words=config_value（list）+ version=config.version（≥1）。agent 行或配置行
    缺失 → (words=[], wordlist_version=0)：信封照建、带空词表标记（fail-closed）。
    """
    agent_id = await session.scalar(
        select(Agent.id).where(Agent.name == agent_name)
    )
    if agent_id is None:
        return [], 0
    row = await session.scalar(
        select(DictConfig).where(
            DictConfig.agent_id == agent_id,
            DictConfig.config_key == BACKFLOW_UTTERANCE_KEY,
        )
    )
    if row is None:
        return [], 0
    return parse_words(row.config_value), row.version or 0
