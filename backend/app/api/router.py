"""API 路由组合（detail §8）：/api/v1 挂载面 = auth + traces（阶段 1 收尾批闭环）。

- auth（§8.1）：登录/刷新/登出/me——T-1.6 登录页数据源 + 全部 API 的鉴权前置。
- traces（§8.2）：链路检索/详情/日志懒加载——S-1 浏览器可查回出口的查询面。
- metrics（§8.4）/backflow（§8.7）/clusters（§8.5）等留空待阶段 2/3（config.py / api/__init__
  各接口由各自 router 按批接入；本文件不因未实现面而拒绝 import）。
"""
from fastapi import APIRouter

from app.api import auth, trace

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(trace.router)
