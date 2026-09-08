"""FastAPI 装配（detail §1.2：CORS、JWT 中间件、路由注册、startup 拉起 worker）。

T-0.3 骨架：health + CORS + 错误 handler + 日志。路由（api/）、JWT 鉴权（core/auth，
§13.1）、worker 拉起（consumer/worker，§4/§1.3）随阶段 1+ 逐步挂入，不一次堆完。
T-1.2 D5：app_env != test 时 lifespan 拉起消费主循环（consumer/main.py，§4.1 step1~6）。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.log import get_logger, setup_logging

logger = get_logger("app.main")


def create_app(settings: Settings | None = None) -> FastAPI:
    """app factory：测试注入 Settings(app_env=test) 起无密钥强校验实例。"""
    settings = settings or get_settings()
    setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 消费主循环（§4.1）只在非 test 环境拉起：conftest 骨架单测/TestClient 不起消费链
        consumer = None
        if settings.app_env != "test":
            from app.consumer.main import ConsumerApp

            consumer = ConsumerApp(settings)
            await consumer.start()
        yield
        if consumer is not None:
            await consumer.stop()

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
