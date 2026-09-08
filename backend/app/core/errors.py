"""统一错误码 + 异常→HTTP 映射（detail §8.9）。

骨架先落基础设施：AppError（业务异常，携带统一错误码与 HTTP 状态）、
exception handler 注册入口。具体错误码表（ERR_模块_序号）随 §8 API 全集实现逐条补齐。
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """业务异常：code = detail §8.9 统一错误码；http = 对外 HTTP 状态；detail = 可读信息。"""

    def __init__(self, code: str, detail: str, http: int = 400):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.http = http


def register_exception_handlers(app: FastAPI) -> None:
    """装配到 FastAPI：AppError → 统一错误体 {code, message}。"""
    @app.exception_handler(AppError)
    async def _app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http,
            content={"code": exc.code, "message": exc.detail},
        )
