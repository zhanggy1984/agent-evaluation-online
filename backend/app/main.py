"""FastAPI 装配（detail §1.2：CORS、错误 handler、路由注册、lifespan 拉起 API 与消费侧资源）。

T-0.3 骨架：health + CORS + 错误 handler + 日志。
T-1.2 D5：app_env != test 时 lifespan 拉起消费主循环（consumer/main.py，§4.1 step1~6）。
阶段 1 收尾批（auth + traces，§8.1/§8.2）：lifespan 挂 app.state 三件套——settings /
engine（API 侧共享 MySQL，core/db）+ es_query（查询侧 ES client，store/es）——供
api/deps、api/auth、api/trace 的 `request.app.state.*` 解析；include api_router 到 /api/v1。
engine/es_query 惰性建连：app_env=test 亦建对象但不连库（依赖覆盖/fake 注入的单测不受扰）。
消费主循环只在 app_env != test 拉起；API 侧资源与 consumer 私有 _engine/_es 相互独立，
防 D6 已绿测试回归（§8 查询侧只读自身账号面）。
"""
from contextlib import asynccontextmanager

from elasticsearch import AsyncElasticsearch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.db import create_engine
from app.core.errors import register_exception_handlers
from app.core.log import get_logger, setup_logging

logger = get_logger("app.main")


def create_app(settings: Settings | None = None) -> FastAPI:
    """app factory：测试注入 Settings(app_env=test) 起无密钥强校验实例。"""
    settings = settings or get_settings()
    setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 真实依赖（API 侧 MySQL engine + ES 查询 client + 消费链）只在非 test 环境拉起：
        # test 走 app.dependency_overrides / 覆盖 app.state 注入 fake（无 aiohttp/连库前置，
        # 对齐 consumer「test 不起真连接」语义）。app.state.settings 恒挂——deps 解码要用。
        app.state.settings = settings
        engine = es_query = None
        if settings.app_env != "test":
            engine = create_engine(settings)
            es_query = AsyncElasticsearch(settings.es_url)
            app.state.engine = engine
            app.state.es_query = es_query
            from app.consumer.main import ConsumerApp

            consumer = ConsumerApp(settings)
            await consumer.start()
        else:
            consumer = None
        yield
        if consumer is not None:
            await consumer.stop()
        if es_query is not None:
            await es_query.close()
        if engine is not None:
            await engine.dispose()

    app = FastAPI(title="agent-evaluation-online", version="0.1.0", lifespan=lifespan)

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    register_exception_handlers(app)
    # detail §8：/api/v1 挂载面 = auth + traces（组合在 app/api/router.py）
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/api/v1/health", tags=["ops"])
    async def health() -> dict:
        # 只探进程存活；依赖连通性探针（DB/ES/Kafka）阶段 0 连通冒烟时按需补
        logger.debug("health 入参: -")
        return {"status": "ok", "env": settings.app_env}

    @app.get("/healthz", include_in_schema=False, tags=["ops"])
    async def healthz() -> dict:
        # 容器 HEALTHCHECK 探活端点（无鉴权，offline 同款语义）；镜像内 python slim
        # 无 curl，用 urllib 打这里
        return {"status": "ok"}

    return app


app = create_app()
