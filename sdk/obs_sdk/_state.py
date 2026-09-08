"""进程级运行时状态（init 固化；logging/structlog processor 从这里取 sink 与 agent 元数据）。

独立模块避免 __init__ ↔ _logging/_structlog 循环 import。未 init 前 sink=None：所有 emit
路径走 no-op（agent 仓 import 期若日志先于 init 触发不崩，只是不上报——§11.1 要求 SDK init
在 agent 日志体系装配后执行，装配期日志本就该进业务日志流）。
"""
from __future__ import annotations

from typing import Optional

from obs_sdk._context import ProcessCtx
from obs_sdk._sink import Sink

process: ProcessCtx = {}          # {agent, agent_version}（init 固化）
sink: Optional[Sink] = None       # 上报出口（init 后置）
