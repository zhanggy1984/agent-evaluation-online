"""API 侧共享 MySQL 连接（auth 查 User/UserSession、dict_config 运行时键读取）。

- engine 生命周期 = FastAPI lifespan（main.py 建/关），挂 `app.state.engine`。
- 与 consumer 私有 engine（consumer/main.py 自建 self._engine）独立——consumer 连接写侧不动，
  防 D6 已绿测试回归（§8 查询侧只读自身账号面）。
- get_session：FastAPI dependency，每请求一个 AsyncSession（auth 显式 commit；无写则不提交）。
"""
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings


def create_engine(settings: Settings):
    """API 查询引擎（mysql+aiomysql）。

    不用 pool_pre_ping：async engine 的 checkout ping 走 aiomysql.ping()，发生在 greenlet
    上下文外 → MissingGreenlet 500（实测 login 第二次起必现）。改 pool_recycle=3600 兜底
    MySQL wait_timeout 断连（8h 内主动回收重建），不再逐次 ping。
    """
    return create_async_engine(settings.sqlalchemy_url, pool_recycle=3600)


async def get_session(request: Request) -> AsyncSession:
    """FastAPI dependency：yield 一个绑定 API engine 的 AsyncSession。

    expire_on_commit=False：commit 后 ORM 实例不置过期——async 下 commit 后读属性（如
    login 返回前组装 UserOut）会触发同步懒刷新 → MissingGreenlet（实测 500）。改由显式
    refresh 或早取值，避免提交后意外回查。
    """
    async with AsyncSession(request.app.state.engine, expire_on_commit=False) as session:
        yield session
