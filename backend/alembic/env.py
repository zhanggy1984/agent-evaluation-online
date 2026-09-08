"""Alembic 运行环境：async 引擎连 MySQL（URL 从 settings.sqlalchemy_migrate_url 覆盖 ini）。

对齐 offline 同款：容器启动命令 `alembic upgrade head` 先建表再起服务（主 compose command）。
全表 DDL 在 T-1.1 落 models 后 autogenerate；骨架仅保证 env 可加载、空迁移幂等。
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import get_settings
from app.models import Base

# 迁移运行方（非库模块）在此落单例：URL 覆盖用 settings.sqlalchemy_migrate_url。
# 容器/CI 经 env 提供 APP_ENV+DB_*；本地 alembic 命令需先 export 同套 env。
settings = get_settings()
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 迁移用专用账号 URL（DB_MIGRATE_* 成对时用迁移账号，缺省回退主账号）
config.set_main_option("sqlalchemy.url", settings.sqlalchemy_migrate_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL，不连库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
