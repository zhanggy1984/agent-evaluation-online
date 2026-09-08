"""api：路由全集（detail §8.1~§8.9）。无 HTTP ingest——上报只走 Kafka（§3.3）。

阶段 1 收尾批已挂：auth（§8.1）+ traces（§8.2），组合在 api/router.py（main.py include
prefix=/api/v1）。metrics/clusters/cases/agents/config/offline 随阶段 2/3 由各自 router 接入。
"""
