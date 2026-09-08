"""统一日志（项目规范：新增接口/消费者打印入参出参 debug 级；注释/日志中文）。

骨架先落标准库 logging + 统一 JSON 化入口；structlog 可选集成（solution §11，
agent 侧 SDK 用 structlog 场景）后续按需补充——backend 本体不强制引 structlog。
"""
import logging
import sys

_CONFIGURED = False

# 项目统一 logger 名：日志按模块全名冒泡，根 logger 持 handler
_ROOT_NAME = "obs"


def setup_logging(level: int = logging.INFO) -> None:
    """一次性配置根 logger（幂等）。容器内由 app 启动时调用；测试自行调低。"""
    global _CONFIGURED
    if _CONFIGURED:
        return
    root = logging.getLogger(_ROOT_NAME)
    root.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """取模块 logger（name 形如 'obs.consumer' 或传 'app.consumer.main'）。"""
    setup_logging()
    return logging.getLogger(name if name.startswith(_ROOT_NAME) else f"{_ROOT_NAME}.{name}")


def log_in_out(
    logger: logging.Logger, fn_name: str, req: object = None, resp: object = None
) -> None:
    """出入参 debug 打点统一入口：接口/消费者处理入口与出口各调一次。

    只打可序列化摘要；含 PII/密钥的字段由调用侧自行裁剪后再传入。
    """
    logger.debug("%s 入参: %s", fn_name, req)
    logger.debug("%s 出参: %s", fn_name, resp)
