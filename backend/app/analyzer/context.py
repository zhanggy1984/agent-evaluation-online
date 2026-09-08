"""analyzer 字典事实读取薄层：agent / dict_config / interface → AgentContext 原料。

judge_scan_job（批量）与 consumer root-late 补判（单 trace）共用。只做查询不做判定；
判定在 classify.py 纯函数。语义对齐 detail §5.1②③⑧：
- agent.backflow_allow = 0/1 布尔（cc=0，D18）；enable=1 参与门。
- per-agent dict_config 键 'backflow_enabled'（seed 已落 4 agent；新 agent 缺键回退 True）。
- interface.llm=1 命中 (agent_id, interface) 对 → 字典 OR 门控为真。
"""
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, Interface
from app.models.config import DictConfig

_BACKFLOW_KEY = "backflow_enabled"


async def fetch_agent_rows(session: AsyncSession, names: list[str]) -> dict[str, Agent]:
    """agent 行按 name 索引（name 唯一 uk_agent_name）；缺行自然不在 dict。"""
    if not names:
        return {}
    rows = await session.scalars(select(Agent).where(Agent.name.in_(names)))
    return {r.name: r for r in rows}


async def fetch_backflow_flags(
    session: AsyncSession, agent_ids: list[int]
) -> dict[int, bool]:
    """per-agent dict_config 'backflow_enabled'（缺键回退 True——未配置视作回流开）。"""
    if not agent_ids:
        return {}
    rows = await session.execute(
        select(DictConfig.agent_id, DictConfig.config_value).where(
            DictConfig.agent_id.in_(agent_ids), DictConfig.config_key == _BACKFLOW_KEY
        )
    )
    flags = {agent_id: bool(value) for agent_id, value in rows}
    return {aid: flags.get(aid, True) for aid in agent_ids}


async def fetch_interface_llm_pairs(
    session: AsyncSession, pairs: list[tuple[int, str]]
) -> set[tuple[int, str]]:
    """llm=1 的 (agent_id, interface) 命中集（interface 行未注册/llm=0 → 不在集 = 字典门为假）。"""
    pairs = [(aid, iface) for aid, iface in pairs if aid is not None and iface]
    if not pairs:
        return set()
    conds = [(Interface.agent_id == aid) & (Interface.interface == iface) for aid, iface in pairs]
    rows = await session.execute(
        select(Interface.agent_id, Interface.interface).where(
            Interface.llm == 1, or_(*conds)
        )
    )
    return {(aid, iface) for aid, iface in rows}
