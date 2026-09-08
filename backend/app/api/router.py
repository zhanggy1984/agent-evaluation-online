"""API 路由组合（detail §8）：/api/v1 挂载面 = auth + traces + metrics（阶段 2 T-2.2 接入）。

- auth（§8.1）：登录/刷新/登出/me——T-1.6 登录页数据源 + 全部 API 的鉴权前置。
- traces（§8.2）：链路检索/详情/日志懒加载——S-1 浏览器可查回出口的查询面。
- metrics（§8.4）：四端点实时指标（overview/interfaces/anomalies/llm-failures，T-2.2）。
- backflow（§8.7）/clusters（§8.5）等留空待后续阶段（各接口由各自 router 按批接入）。
"""
from fastapi import APIRouter

from app.api import auth, metrics, trace

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(trace.router)
api_router.include_router(metrics.router)
