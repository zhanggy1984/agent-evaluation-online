r"""API 路由组合（detail §8）：/api/v1 挂载面 = auth + traces + metrics + backflow + pull + admin。

- auth（§8.1）：登录/刷新/登出/me——T-1.6 登录页数据源 + 全部 API 的鉴权前置。
- admin（§8.6，T-3.12 批 1）：配置管理 + 账号管理（admin-only）。
- traces（§8.2）：链路检索/详情/日志懒加载——S-1 浏览器可查回出口的查询面。
- metrics（§8.4）：四端点实时指标（overview/interfaces/anomalies/llm-failures，T-2.2）。
- backflow（§8.4，P2-3）：回流簇读面 + 结果推送接收（平台 JWT / evaluator 静态 secret）。
  ⚠️ **批 50（#33）订正**：本行原写「admin 人工 invalidate/requeue 单点+批量」——**该写面已随
  批 35-A/B 整体删除**（`backend/app` 内零命中），人工处置面现已不存在。
- pull（§8.7/§8.2 域外，P2-3）：平台间 evaluator 服务凭证增量拉取 + ack 回写
  （独立凭证面，不接平台 JWT）。
- clusters（§8.4）：**无独立 router——cluster/link 路由由 `backflow.router` 承载**。
  ⚠️ **批 50（#33）订正**：本行原写「**12 条**……（overview、clusters 列表/详情、
  claim/ignore/reopen/needs-review-resolve/fixed-review、needs-review-batches/{id}/resolve、
  links 三动作、regression-results）」——**该清单里的写端点已全部删除**，只剩 4 条（实测
  `grep -nE '^@router\.' backend/app/api/backflow.py`）：`overview`(373) /
  `clusters`(413) / `clusters/{cluster_id}`(475) / `regression-results`(829)。
  **数字与清单都以该命令为准，别照抄本行。**
  ⚠️ 本行原写「clusters（§8.5）留空待后续阶段（由各自 router 按批接入）」——**两处均误且引入于
  阶段 1（`76611d2`）后未随批更新**：① clusters 属 §8.4 不属 §8.5；② 它不空，早已随回流批落地。
"""
from fastapi import APIRouter

from app.api import admin, auth, backflow, metrics, pull, trace

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(trace.router)
api_router.include_router(metrics.router)
api_router.include_router(backflow.router)
api_router.include_router(pull.router)
api_router.include_router(admin.router)
