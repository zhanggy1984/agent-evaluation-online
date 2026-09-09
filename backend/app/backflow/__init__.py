"""平台间契约与 backflow 回流域（P2-3 / T-3.3）：pull/ack + invalidate/requeue。

- backflow/ack.py：pull-API（§8.7 / §7.2）+ ack 前置矩阵落库（§7.3）。
- backflow/requeue.py：人工 invalidate + requeue 单点/批量（§7.4 R-24 / §8.4）。
纯逻辑（无 DB）+ DB 编排双分层，供 api 端点薄调、单测打纯函数、容器探针直调。
"""
