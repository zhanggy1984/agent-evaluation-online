"""seed.py — 平台引导种子（T-0.6 交付物；执行门 = T-1.1 迁移落表后）。

阶段 0 只交付本脚本 + dict_config v1 基线常量；表结构（detail §5.1 全表）归 T-1.1
`alembic upgrade head`。脚本**不依赖任何 model 类**（core SQL 直写、列级对齐 §5.1），
T-1.1 落表后即可执行：

    cd backend
    python -m app.core.seed            # 读 backend/.env；用运行时账号（DML）

三件事（全部幂等：可重复执行不产生重复行，且不覆盖已有人工配置）：
1) init_admin：`user` 表建首 admin（username 缺省 admin，口令取 settings.admin_password，
   bcrypt 存储，§13.1）。已存在则跳过（不改口令）。
2) 4 个 agent 行 + 空 interface 字典（agent.name 唯一；backflow_allow：cc=0 其余 1，D18）。
3) dict_config v1 生效键（§10.1）按默认落初值：全局键 + per-agent 键；fallback_utterance
   置空表 = fail-closed（§11.4 盘点产出由 agent 侧后续配入）；已存在键不覆盖（seed 只补缺省）。

约束：只用运行时账号能力（SELECT/INSERT/UPDATE，无 DDL）；建表必须先跑迁移账号的
`alembic upgrade head`。表缺失时本脚本明确报错退出，不静默。
"""
import asyncio
import json
import sys

import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings, get_settings
from app.core.log import get_logger

logger = get_logger("app.core.seed")

# 脚本硬依赖的表（§5.1）：缺任何一张 = 迁移未跑，明确报错
REQUIRED_TABLES = ("user", "agent", "interface", "dict_config")

# ---- agent 字典基线（name 唯一；backflow_allow = 维度3 回流白名单，cc=0 见 D18） ----
AGENTS = [
    {"name": "good-question", "display_name": "good-question", "backflow_allow": 1},
    {"name": "customer-service", "display_name": "customer-service", "backflow_allow": 1},
    {"name": "contract-check", "display_name": "contract-check", "backflow_allow": 0},
    {"name": "smart-procurement", "display_name": "smart-procurement", "backflow_allow": 1},
]

# ---- dict_config v1 生效键（§10.1）。默认仅补缺省，不覆盖已存在行 ----
GLOBAL_DEFAULTS: dict[str, object] = {
    "cluster_window_days": 7,
    "claim_ttl_days": 14,
    "auto_fixed_k_default": 2,
    "llm_call_observe_window_min": 1440,  # 24h，§8.5.1 观察窗（key 以分钟计）
    "llm_call_observe_threshold": 10,
    "trace_judge_window_s": 60,
    "trace_judge_grace_s": 300,
    "rollup_late_k_h": 6,
    "keyword_search_days": 7,
    "metric_agg_cache_ttl_s": 60,  # O-1 全站实时 agg 缓存护栏（§8.3）
    "metric_agg_timeout_ms": 3000,
    "trace_query_timeout_ms": 3000,
    "trace_judge_purge_days": 7,
}
# per-agent 键（§10.1；fallback_utterance 空表 = fail-closed，词表盘点见 §11.4）
PER_AGENT_DEFAULTS: dict[str, object] = {
    "fallback_utterance": [],
    "timeout_ms": 30_000,
}
# backflow_enabled 回流总开关（cc 恒 false，D18；§10.1）
AGENT_BACKFLOW_ENABLED = {
    "good-question": True,
    "customer-service": True,
    "contract-check": False,
    "smart-procurement": True,
}


async def _ensure_tables(conn, db: str) -> None:
    """迁移未跑（缺 §5.1 表）时给出明确指引，而不是带裸错。"""
    rows = await conn.execute(
        text(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = :db AND TABLE_NAME IN :names"
        ),
        {"db": db, "names": tuple(REQUIRED_TABLES)},
    )
    exist = {r[0] for r in rows.fetchall()}
    missing = [t for t in REQUIRED_TABLES if t not in exist]
    if missing:
        raise RuntimeError(
            f"缺表 {missing}：seed 需先跑迁移账号 `alembic upgrade head`（T-1.1 落 §5.1 全表），"
            f"库 {db} 当前未就绪"
        )


async def _seed_admin(conn, settings: Settings) -> None:
    if not settings.admin_password:
        raise RuntimeError(
            "admin_password 为空：seed init_admin 不落弱口令，请在 backend/.env 配置 ADMIN_PASSWORD"
        )
    pw_hash = bcrypt.hashpw(settings.admin_password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )
    # 已存在 username 则跳过（不改口令；改密走用户管理，token version+1 吊销）
    await conn.execute(
        text(
            "INSERT INTO `user` (username, password_hash, display_name, role, status) "
            "VALUES (:username, :pw_hash, :display, 'admin', 1) "
            "ON DUPLICATE KEY UPDATE updated_at = updated_at"
        ),
        {
            "username": settings.admin_username,
            "pw_hash": pw_hash,
            "display": "平台管理员",
        },
    )
    logger.info("init_admin: username=%s 已就绪（存在则保持原样）", settings.admin_username)


async def _seed_agents(conn) -> None:
    # interface 字典 = 空（自发现注册）；agent 行幂等（uk_agent_name）
    for a in AGENTS:
        await conn.execute(
            text(
                "INSERT INTO `agent` "
                "(name, display_name, base_url, enable, route_source, backflow_allow) "
                "VALUES (:name, :display, NULL, 1, 'auto_register', :backflow_allow) "
                "ON DUPLICATE KEY UPDATE updated_at = updated_at"
            ),
            {
                "name": a["name"],
                "display": a["display_name"],
                "backflow_allow": a["backflow_allow"],
            },
        )
    logger.info("agent 行 4 条已就绪（存在则保持原样）")


async def _seed_configs(conn) -> None:
    """dict_config v1 键落默认。ON DUPLICATE 仅刷新 updated_ts：不覆盖人工配置。"""
    # 全局键（agent_id=NULL）：uk_dc 唯一索引对 NULL 行不约束（MySQL NULL 语义），
    # ON DUPLICATE 不触发 → 必须先查存在再插，保证幂等（只补缺省，不覆盖人工配置）
    for key, val in GLOBAL_DEFAULTS.items():
        hit = await conn.execute(
            text("SELECT 1 FROM `dict_config` WHERE agent_id IS NULL AND config_key = :key"),
            {"key": key},
        )
        if hit.fetchone():
            continue
        await conn.execute(
            text(
                "INSERT INTO `dict_config` "
                "(agent_id, config_key, config_value, version, updated_by) "
                "VALUES (NULL, :key, :val, 1, 'seed')"
            ),
            {"key": key, "val": json.dumps(val, ensure_ascii=False)},
        )
    # per-agent 键：backflow_enabled 按 D18；fallback_utterance/timeout_ms 全 agent 同默认
    for a in AGENTS:
        per = dict(PER_AGENT_DEFAULTS)
        per["backflow_enabled"] = AGENT_BACKFLOW_ENABLED[a["name"]]
        agent_id = await conn.execute(
            text("SELECT id FROM `agent` WHERE name = :name"), {"name": a["name"]}
        )
        row = agent_id.fetchone()
        if row is None:
            raise RuntimeError(f"agent 行 {a['name']} 缺失，先执行 agent 种子")
        for key, val in per.items():
            await conn.execute(
                text(
                    "INSERT INTO `dict_config` "
                    "(agent_id, config_key, config_value, version, updated_by) "
                    "VALUES (:agent_id, :key, :val, 1, 'seed') "
                    "ON DUPLICATE KEY UPDATE updated_ts = updated_ts"
                ),
                {
                    "agent_id": row[0],
                    "key": key,
                    "val": json.dumps(val, ensure_ascii=False),
                },
            )
    logger.info("dict_config v1 键基线已就绪（fallback_utterance 空表 = fail-closed）")


async def seed(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    engine = create_async_engine(settings.sqlalchemy_url)
    try:
        async with engine.begin() as conn:
            await _ensure_tables(conn, settings.database)
            await _seed_admin(conn, settings)
            await _seed_agents(conn)
            await _seed_configs(conn)
    finally:
        await engine.dispose()
    logger.info("seed 完成：库 %s", settings.database)


def main() -> None:
    try:
        asyncio.run(seed())
    except RuntimeError as e:
        logger.error("seed 中止：%s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
