"""统一错误码 + 异常→HTTP 映射（detail §8.9）。

骨架先落基础设施：AppError（业务异常，携带统一错误码与 HTTP 状态）、
exception handler 注册入口。具体错误码表（ERR_模块_序号）随 §8 API 全集实现逐条补齐。
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """业务异常：code = detail §8.9 统一错误码；http = 对外 HTTP 状态；detail = 可读信息。

    extra：可选的响应体附加字段（并入 {code, message} 顶层）。ack 前置不符（契约修订 R3，
    §8.7/§8.9 ERR_CLUSTER_0003）需带当前 offline_status + invalidate_reason 供 offline 对账
    ——extra 默认 None 不影响既有 {code, message} 响应形状。
    """

    def __init__(self, code: str, detail: str, http: int = 400, extra: dict | None = None):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.http = http
        self.extra = extra


def register_exception_handlers(app: FastAPI) -> None:
    """装配到 FastAPI：AppError → 统一错误体 {code, message}（+ extra 顶层字段）。"""
    @app.exception_handler(AppError)
    async def _app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        content = {"code": exc.code, "message": exc.detail}
        if exc.extra:
            content.update(exc.extra)
        return JSONResponse(
            status_code=exc.http,
            content=content,
        )
