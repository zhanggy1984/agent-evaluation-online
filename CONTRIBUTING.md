# CONTRIBUTING（agent-evaluation-online）

> 依据 solution_detail §1.5（命名与口径约定）+ 团队协作规范。代码标识符英文，注释/文档/日志中文。

## 命名与口径

- DB/字段：`snake_case`；表前缀见 detail §5.1；时间列 `DATETIME(3)` 存 **UTC**；展示层本地化。
- 事件字段：`snake_case`；`@timestamp`（ES）毫秒 epoch。
- API：REST，`/api/v1/...`；分页统一 `page/page_size`，返回 `{items, total, page, page_size}`。
- 错误码：`ERR_模块_序号`（detail §8.9），业务异常一律经 `core/errors.AppError` 抛。
- 时间窗口统一口径：错误聚类窗口 7d，以 error_cluster 首现时间滚动（detail §1.5）。

## Backend 质量基线（task.md「通用验证基线」）

- 单测覆盖核心逻辑：Service/analyzer/converter 业务分支（正路径 + 关键异常路径）；Controller/Repository/工具不强制。
- `python -m compileall` 编译过；`pytest` 通过（新增 async 测试自管 session/事务，禁跨测试共享连接）。
- 新增接口/消费者打印出入参（debug 级，`core/log.log_in_out`）。
- 交付物边界：主 `docker-compose.yml` 仅 backend + frontend；中间件连共享 infra，连接串经 `.env` 注入（不入镜像不入仓库）。

## 运维命令（本地 dev 底座）

- 本地三中间件：`docker compose -f D:/study/aiprojcet/infra/docker-compose.yml up -d mysql elasticsearch kafka`（宿主直连端口：mysql 33061 / ES 39200 / Kafka 39092；容器内经服务名 `mysql`/`elasticsearch`/`kafka`）。
- 迁移：`cd backend && .venv/Scripts/python.exe -m alembic upgrade head`（DDL 用迁移账号 obs_migrate）。
- 种子（**执行门 = T-1.1 落表后**；表缺失 seed 明确报错）：`cd backend && .venv/Scripts/python.exe -m app.core.seed`——init_admin（§13.1）+ 4 agent 行 + 空 interface 字典 + dict_config v1 基线（§10.1）；幂等，可重复执行，不覆盖已有人工配置。

## 提交纪律

- commit message 中文；双仓（online/offline）分开提交；改动契约/文档版本锚需同步更新修订记录。
- `*Api.java` 类对外契约禁止擅自变更（本仓为 Python/FastAPI，对应地为对外 HTTP 契约与信封 schema——变更需先在方案层评审）。
- 一次性验收脚本不入仓库（见 .gitignore 的 `backend/verify_*.py` 等模式）——指开发期临时写在 `backend/` 根目录、跑完即弃的那类。
- **常驻集成测试**（`backend/tests/integration/*.py`）相反，**必须入库**：它们有前缀隔离 + 幂等清理 + 退出码，可反复运行，且 `ci.yml` 的 `probe` job 直接引用其中四个当真库门禁——删掉 CI 即断。判据是「**能否被 CI 反复执行**」，不是「是不是探针」（两类都叫探针，正是原措辞的歧义来源）。
- 上述两类脚本里的「测试凭据」均指进程内构造的**假值**（如 `_MOCK_SECRET = "probe-claim-secret"`，仅为满足 `Settings` 的 jwt 长度校验），与 `.env` 注入的真实凭据无关；真实凭据严禁入库（见 .gitignore 首条）。
