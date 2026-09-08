"""store：ES 客户端 + MySQL 元数据仓储（solution §14 目录）。

阶段 1 收尾批：es.py = 链路检索**查询层**（consumer/es.py 是写侧，对称独立，防漂移不复制
mapping）。后续 metrics 聚合（阶段 2 O-1）/ DB 仓储随批并入。
"""
