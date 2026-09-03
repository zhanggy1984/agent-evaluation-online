# agent-evaluation-online 工程任务拆解（WBS）

> 目的：把 **solution.md（v3.5.2，error-only 一期定稿 + 部署边界）** 与 **solution_detail.md（v1.1，开发就绪详设）** 中"将要做的事情"拆成可执行的任务阶段与任务项，每项给**验证目标**，指导排期、认领与验收。本文不重述方案内容，只做**执行层拆解**并指向两文档锚点。
>
> 权威口径：功能范围 = detail §0.1（锁定 v3.5.1；v3.5.2 仅同步部署边界，不改变功能范围）；阶段门 = solution §15 P0~P2；测试用例全集 = detail §14.1~§14.4（S-1~S-5、E-1~E-22、性能护栏）。**Task #4（offline 配套方案，独立文档 + 独立评审）尚未产出，且已切两刀**：批 1（契约 + offline 收单 = 联调环 0/环 1 offline 侧）先行、批 2（判定器 + verifier no_fallback）随后。批 1 是阶段 3.8/阶段 4 与联调环 0~3 的前置输入。

## 阶段总览

| 阶段 | 主题 | 文档锚点 | 出口（本阶段验收） |
|---|---|---|---|
| 阶段 0 | 工程地基与部署接入（前置） | detail §1.5/§1.6/§13、solution §14 部署边界 | 主 compose 仅起 backend+frontend、seed 完成、infra 凭证/落权/索引模板就绪、**操作面契约回执（服务账号权限矩阵 ①~⑤）**、CI 绿灯 |
| 阶段 1 | **P0 平台骨架** | solution §15 P0、detail §1.7 P0 行、§14.1 | S-1/S-2/S-3 通过（§14.3：手工投事件可按 trace 查回） |
| 阶段 2 | **P1 两维落地**（链路 + 指标） | solution §15 P1、detail §1.7 P1 行、§14.1 | S-4 通过；看板出现真实 P50/P95/P99 + 全站 QPS 纵览（gq/cs/sp 接入） |
| 阶段 3 | **P2 回流闭环（error-only，online 侧）** | solution §15 P2 + §11、detail §1.7 P2 行、§6/§7 | E-1~E-22 中 online 侧用例通过 + Task #4 offline 侧改造通过（§14.3） |
| 阶段 4 | **集成测试与端到端验收（富化，含异常与边界死角）** | detail §14.1~§14.4、solution §11/§12/§16 | S/E 全量通过 + 性能护栏判据达标 + **T-4.13 异常场景 / T-4.14 边界死角场景全绿** + 安全/部署/网关联调通过 + 回归门禁口径验证 |
| 阶段 5 | 上线放量与运营 | solution §13.0 checklist、§15、§17 #14/#15 | 维度 3 开放验收（#4/#8/#10）+ 容量实测 + 与 infra 敲定项闭环 |

**执行轨道（三轨并行，非纯线性排期）**：阶段 0 → 1 → 2 → 3 串行是**平台轨**主干顺序（各阶段内部 job 与 API 可并行，detail §1.7 注），阶段 4 覆盖阶段 3 产物、阶段 5 在其后放量。但 solution §15 明示 **agent 整改与平台开发并行**、Task #4 offline 配套为独立仓，故整张阶段表只是**平台轨**视图——三条轨道独立推进、只在汇合点交汇，**任何一轨滞后只影响其汇合点，不阻塞另两轨的主体工作**：

| 轨道 | 内容（对应任务项） | 起点 | 汇合点 |
|---|---|---|---|
| **平台轨** | 阶段 0/1/2/3/4/5 主干（建站 → 看板 → 回流 → 集成 → 上线） | 阶段 0 | —（主轴） |
| **agent 整改轨** | agent 侧 SDK 接入改造（gq/cs/sp 插桩、cc 仅 HTTP 层、LLM 旁路、存量整改，= T-2.5 的内容） | **SDK 契约冻结（阶段 1.5 出口）即启动**，不等平台 P1 完成 | 阶段 2.5（真实 agent S-4 复验）、阶段 3.9/5.x 放量门禁 |
| **offline 配套轨** | offline 仓 v1 `regression_error` 改造，**Task #4 切两刀**：批 1 = 契约 + 收单/结构自检/激活/回写 + pull job（联调环 0/环 1）；批 2 = 判定器 + verifier no_fallback（= T-3.8 落点） | **批 1 契约先行**：Task #4-① 定稿即启动（独立方案独立评审，最先拉通双端）；批 2 不阻塞批 1/环 2 | 环 0 契约冻结 → 阶段 3.8（批 2）、阶段 4 E-1~E-22 offline 侧用例、阶段 5 回归门禁 |

通用验证基线（所有阶段适用）：
- backend：`pytest` 覆盖核心逻辑（Service/analyzer/converter 业务分支含正路径与关键异常路径；Controller/Repository/工具不强制，项目质量规范）；`python -m compileall` 编译过；lint 按 §1.5 规约；新增接口/消费者打印出入参（debug 级）。
- frontend：`npm run build` 通过；关键交互按 detail §9.3 逐条人工/组件级核验。
- 交付物边界：主 `docker-compose.yml` **仅 backend + frontend**；中间件一律走公共 infra 租户，连接串经 `.env` 注入（不入镜像、不入仓库）；`compose.infra.dev.yml` 非交付物。

---

## 联调闭环编排（online ↔ offline，环 0~3）

> 本 WBS 跨两个独立仓（online / offline）、两套发布节奏。"error 回流"端到端闭环（agent 线上 error → online 聚类组装 → offline pull/复现/判定 → 回写 → online 流转 → 观察哨位）按 **4 个环逐环收口**，避免一次性大联调。环 2 即阶段 4 的联调形态。

| 环 | 名称 | 内容 | 归属仓/对端 | 出口 | 依赖与门 |
|---|---|---|---|---|---|
| 环 0 | **契约冻结（先行）** | pull/回写/回查契约 + `schema_version` + `case_type` 白名单 + 双向认证 + 游标/ack 语义；跨仓共享契约文档；两端 stub 打样 | Task #4-① 产出（基准 = detail §7.3/§7.4） | 契约定稿；两端 mock 对同一批样例 payload 行为一致 | 先于一切 offline 改造；不等 infra |
| 环 1 | **单端 stub 自测** | online 用 fake-offline 客户端（online 仓 tests/ 基建）验 assembled→被拉→回写→requeue 状态机；offline 用 fixture payload（offline 仓 tests/）验收单/结构自检/激活/回写 | 两端各自仓内 | 仓内全绿、无需对端 | 不需 ES/Kafka 底座，可先于 infra dev 租户跑 |
| 环 2 | **双端集成联调** | 同机双 compose + **本地共享 infra（../infra，已扩 ES/Kafka）**底座，契约**内网直连不经公共网关**；合成 error 事件驱动 E-1~E-22 + T-4.13/T-4.14 对端场景 | 两端 + 本地 infra | = 阶段 4 出口 | **本地 share-infra 完成 ES/Kafka 扩展**；环 0/环 1 绿 |
| 环 3 | **真实流量灰度** | agent 接入后真 error 触发；观察哨位/重推/requeue/停摆恢复真实现场 | 两端 + agent 整改轨 | 维度 3 开放验收 + 回流白名单放开 | 阶段 5 门禁 |

关键工程口径：
- **Task #4 切两刀（2026-09-03）**：**批 1 = 契约（环 0）+ offline 收单/结构自检/激活/回写 + pull job**，判定先用 stub/fixture 通管道；**批 2 = 判定器（executor 复现）+ verifier no_fallback**（= T-3.8 落点）。批 1 独立方案独立评审、先行；批 2 换真判定后回归不碰契约。
- **契约修订包 R1~R3 已入环 0（2026-09-03，Task #4-① 评审拍板）**：R1 = `pull/payloads` 响应逐 payload 附顶层 `assembled_ts`（offline 增量锚唯一来源）；R2 = ack 前置矩阵补 `invalidated(offline_cap_gap)→active` 自愈回写例外；R3 = ack 400（`ERR_CLUSTER_0003`）响应带当前 `offline_status`+`invalidate_reason`。**已落 detail v1.2（§7.2/§7.3/§8.7/§8.9 + 修订记录）**；环 1 stub/fixture 按修订形状造样例（offline 侧 `error-backflow-phase1.md` v0.2 已按其语义实现，§2/§12 标注依赖）；环 2 前双端对齐。
- **底座决策（2026-09-03）**：**ES/Kafka 直接在本地共享 infra（../infra）创建**——share-infra docker-compose 内新增 ES 8.x + Kafka（KRaft）服务（infra 仓改造，前置依赖，见风险节），online/offline 双端连本地 share-infra（MySQL 分库、ES/Kafka 租户前缀隔离），online 侧落权对象 = 本地 share-infra 的 ES/Kafka/MySQL（受 T-0.2 权限矩阵约束）。`compose.infra.dev.yml` 不作主线（防双底座漂移），仅故障注入兜底。生产公共 infra 租户与网关 SSO（§17 #14/#15）是**上线门**、不阻塞 dev 联调。**此扩展同时是平台轨阶段 0/1 的硬前置**（S-1 冒烟与 P0 观测链即需 ES/Kafka），未完成前可用 `compose.infra.dev.yml` 临时过渡冒烟、不作为主线。
- **对端 stub 是测试基建**：fake-offline（online 仓）+ offline fixtures（offline 仓）随批 1 建立，后续能力迭代无需真实对端即可回归。
- **映射**：环 0→1 = offline 配套轨**批 1**；环 2 = 阶段 4（T-4.2/T-4.6/T-4.7/T-4.13⑤/T-4.14 对端场景在此串）；环 3 = 阶段 5。

---

## 阶段 0｜工程地基与部署接入（前置）

> 目标：让"环境可跑、依赖可连、命名可溯、交付边界正确"，先于任何功能开发。对应 solution §14 部署边界 + detail §1.5/§1.6/§13。

- **T-0.1 需求基线核对**：以 detail §0.1 为准核对范围（error-only v1、`regression_error` 单 case_type、R6 no_fallback 词表断言、offline 确认 gate 全归 offline）；确认 v3.5.2 部署边界已同步入 solution §3/§7.1/§14/§16/§17。**验证目标**：两文档范围无冲突；无二期物被误纳入（对照 detail §12.1 二期占位索引）。
- **T-0.2 公共 infra 接入申请与操作面契约（与 infra 协同）**：**dev 底座 = 本地共享 infra（../infra 扩 ES/Kafka 后的 share-infra，见联调闭环小节；生产公共 infra 租户按上线门单独走）**；MySQL/ES/Kafka dev 租户 endpoint + 最小权限账号；Kafka topic/ACL/consumer group 落权（先建 topic 后发凭证）；ES index template/ILM 模板提交；`{env}` 值域与命名登记（`{env}.obs` / `{env}.obs-*` / `{env}.obs.*`）；公共 API 网关域名与 SSO 前置条件沟通（§17 #14/#15、detail O-6/O-7）。**操作面契约（v3.5.2 缺口补：对 infra 托管资源的动作须成交付物，不能延续"自管时代内联动作"假设）**——随申请交付一张 **infra 服务账号与权限矩阵**并显式分列：① ES backend 写账号（事件/日志 index 写入）；② **rollup 写账号——每小时自建/写 rollup / t-digest index 的归属与配额（detail §7.1/§14.4 语境下该每小时写入隐含存在但从未成申请项，须显式落为申请条目，含 rollup index 的 ILM 与容量是否纳入租户档）**；③ ES 只读查询账号（7d rollup + 实时 agg，metrics/trace 查询用）；④ Kafka producer 账号（每 agent 凭证隔离，solution §13）；⑤ **consumer group 管理操作面——offset 提交/重平衡/增 partition 是 backend 日常动作，group 的创建/变更申请通道、是否含在首批落权内须确认**。另约定 **变更通道 SLA 与失败兜底**：账号/权限/template 申请回执的 SLA、超时或被拒时的负责人；任一依赖未就绪时平台的降级路径（如 rollup 写失败 → 看板缺口标注而非静默写崩，衔接 solution §16 公共 infra 共享/多租户耦合风险行）。**验证目标**：拿到最小凭证集（不入库、仅 `.env`）；权限矩阵 ①~⑤ 经 infra 回执核对（含 rollup 写归属、consumer group 操作面、变更 SLA 与降级路径）；topic 白名单与 ACL 回执核对通过；index template 就绪；env 值域与命名与 infra 登记一致；网关/SSO 敲定结论落为方案 §17 #14 的定案或明确 P0 前待办；矩阵/回执项进入 T-5.3 收口清单。
- **T-0.3 工程脚手架**：backend（app/api、consumer、store、analyzer、converter、worker、models、core）/ frontend / sdk / tests / docs 目录；`.editorconfig` / CONTRIBUTING（§1.5）；config 分层 + `.env` 注入（endpoint/账号/凭证不入镜像不入仓库）；统一日志（出入参 debug）。**验证目标**：`docker compose up` 仅起 backend+frontend 两服务且健康检查通过；backend 读 `.env` 连得上 dev 租户三个依赖（连通性探测为冒烟第一步）；lint 零告警。
- **T-0.4 编排交付物**：主 compose（backend+frontend）+ `compose.infra.dev.yml`（**非交付物**，不进主 compose/CI）+ 网络声明（backend 容器不映射 host 的 3306/9200/9092）。**验证目标**：`docker compose config` 校验通过；容器端口面只暴露 backend 服务口与 frontend；CI 产物清单不含 dev compose。
- **T-0.5 CI 骨架**：lint + pytest + 前端 build + 镜像构建；Alembic 初始迁移骨架挂入。**验证目标**：空仓 CI 全绿；任意代码变更触发同一套流水线。
- **T-0.6 种子与配置**：`seed.py` 建首 admin（`init_admin`，§13.1）+ 4 个 agent 行 + 空 interface 字典；`dict_config` v1 生效键按 detail §10.1 初始化（含 `fallback_utterance` 词表、聚类窗口、超时阈值、metric_agg 护栏键 O-1）。**验证目标**：`alembic upgrade head` 幂等；seed 可重复执行不产生重复行；词表按 detail §11.4 盘点落初值（空表 = fail-closed 预期，页面置守卫不生效提示）。

**阶段出口**：detail §1.6 前三条首日冒烟可达——主 compose 起服务 → migrate/seed → 手工投一条合法事件能落库可查（S-1 预演）。

---

## 阶段 1｜P0 平台骨架

> 目标：打通"事件 → 消费 → 校验 → ES → 可查"的纵向切片。对应 detail §1.7 P0 行：models+migrate → consumer（校验/脱敏/ES 分派）→ ES 索引 → api/trace 查询 → sdk 雏形 → 链路冒烟。

- **T-1.1 MySQL models + migrate（DDL 全集）**：按 detail §5.1 建全表 ①~⑩——含 `error_case_link` **cur_key 生成列**（仅 verify=pending 占位、终态自动释放、`uk_link_current (case_type, cur_key)`）、`trace_judge_state` 判定态（root_status/root_error_type/root_input_hash/processed + idx_judge_scan/idx_purge）、各去重/幂等唯一索引（含 generation）、agent_credential 加密列。**验证目标**：DDL 与 §5.1 逐列对照零差异；生成列语义用 SQL 自检（pending 时 cur_key=cluster_id、终态为 NULL）；`alembic upgrade head` 空库/重复执行均幂等。
- **T-1.2 consumer 主循环**：订阅 `{env}.obs.agent.*`，schema 校验（§4.2）、agent≠topic 拒绝、脱敏复核（§4.5 键级、平台不还原）、ES 分派（event_kind 分流、`_id=sha256(agent|trace_id|seq)`）、offset 与失败重试队列。**验证目标**：S-2（非法事件丢弃并计数、selfmonitor 可见）、S-3（同 trace 重放不重复行、判定不重复）通过。
- **T-1.3 ES 存储与索引**：双 index 周滚动（`{env}.obs-event-yyyyWW` / `{env}.obs-log-yyyyWW`）；template/ILM 策略提交 infra 落建；映射对齐 §2.1（text 中文分词、quality/session_ctx 二期不索引不采集）。**验证目标**：写入命中正确周 index；`_id` 幂等覆盖；二期字段 v1 不落索引；template 由 infra 侧生效（§7.1 索引治理）。
- **T-1.4 trace 链路查询 API**：traceId/关键字自由输入；`(ts,parent,seq)` 树序还原；日志行分页懒加载；关键字检索 search_after 深翻页 + 限 7d + 超时 `trace_query_timeout_ms=3000` + 命中 ≤200（§14.4）。**验证目标**：S-1（手工投 request+llm_call+log，trace 可查、日志穿插、llm_call 高亮）、S-5（命中 error_msg + 深翻页 + 限流/上限生效）通过；单 trace 上千日志行首屏不拉爆。
- **T-1.5 obs-sdk 雏形**：logging handler + 事件打点（§2 样例三份可直接用于单测）；内存队列 → 批量 → kafka-python（§3.1）；可靠性与降级（写满丢弃并计数、本地持久卷可配路径、失败退避 ≤3 次、恢复补传，§3.2）；`agent_version` 注入（R5 打点源）。**验证目标**：SDK 单测（§2.2 样例逐字段）、断点重传冒烟；agent 进程内 kafka 故障时业务不阻塞（有界队列 + 丢弃计数）。
- **T-1.6 前端骨架**：登录 + 链路查询列表 + trace 详情（树时间轴 + 红显 + 日志穿插）。**验证目标**：S-1 在浏览器可查回（P0 验收人工步）。

**阶段出口**（solution §15 P0 / detail §14.3）：S-1、S-2、S-3 通过；手工投 Kafka 事件能按 trace 查回链路。

---

## 阶段 2｜P1 两维落地（链路完整化 + 指标看板 + agent 接入）

> 目标：维度 1 补全到生产可用，维度 2 指标闭环 + 看板；agent 侧 SDK 接入真实流量。对应 detail §1.7 P1 行 + solution §15 P1。

- **T-2.1 L1/L2 分层判定（判定态持久化）**：analyzer classify + **judge_scan_job**（扫 `judged=0 ∧ ttl_until≤now` → classify → 写判定/归并 → judged=1，重复到期不重判）；per-trace 累积态三要素落 `trace_judge_state`，重平衡从判定态重建不回读 ES；残 trace 按已有子节点判定（detail §4.3/§6.1）。**验证目标**：单测覆盖 L1/L2 分类分支与 OR 门控（L2 = trace 动态事实 或 接口字典 llm=true）；judge_scan 到期补判、重复到期不重判；residual 子节点判定。
- **T-2.2 指标实时 agg + metrics API**：request/llm_call 双指标；`status∈{error,timeout,ok}` 互斥计数；1h/24h 实时 agg（date_histogram × percentiles p50/95/99 × filter）；时间窗路由（≤24h 实时 / 7d rollup）；**O-1 护栏**：agent 缺省=全站实时 agg 强制缓存 `metric_agg_cache_ttl_s=60` + 超时 `metric_agg_timeout_ms=3000`（§14.4）。**验证目标**：S-4 口径（request ok + llm_call error 计入失败率、不回流）；全站 24h agg P95 ≤5s（护栏判据）；缓存命中跳过 ES。
- **T-2.3 7d 小时级 rollup**：每小时预聚合 agent×interface×node×小时（写 rollup/t-digest index 的账号归属取 **T-0.2 权限矩阵 ②**，不自建权限假设）；t-digest 可合并草图；首启回填、迟到（≤6h）幂等重算、缺桶回退实时 + 页面标注、尾小时实时补齐（§5.3）。**验证目标**：迟到重算不双计；缺桶回退标注可见；**t-digest 跨小时合并 vs 全量重算 p95 误差 <1%**；每小时任务完成 ≤2min。
- **T-2.4 看板前端**：全站纵览 tab（QPS 时序 + 失败率/超时率叠加，缺省=全站）、概览卡（QPS/P50/95/99 + 1h/24h/7d）、接口明细（请求级/LLM 级双指标）、异常聚焦、『LLM 调用失败』下钻段（request ok + llm_call error/timeout → trace 列表，标注"降级/兜底现场，v1 不回流、L3 二期"）。**验证目标**：真实数据出 P50/P95/P99 + 全站 QPS 趋势；下钻从毛刺到受影响 trace 直达（F2 消费路径闭合）；二期质量出口整条隐藏不灰置（§9.3 UI 规则）。
- **T-2.5 agent 接入（SDK 改造）——agent 整改轨在平台阶段表的落点**：本项 = **agent 整改轨与平台轨的汇合核对**，非纯平台任务。agent 侧插桩改造（gq/cs/sp 接 SDK、cc 仅 HTTP 层 request 级指标与链路 D18、LLM 第二通道旁路逐一接入 + **打点包住裸调用、最终失败一律标 error（先记后传）**、存量整改对齐 detail §11.3 v1 只做 #1~#4/#6~#9、#5 二期延后）已在 agent 整改轨上随 **SDK 契约冻结（阶段 1.5 出口）提前启动**；本任务项承接平台侧条件（agent_credential/注册配置、dict_config 下发，solution §13.0 Step 1~3）就绪后的联调、灰度与收口。**验证目标**：solution §13.0 checklist #1~#3（放量门禁档）通过；S-4 在真实 agent 上复验（LLM 失败被业务兜底、request 200，trace 红显 + 失败率可见，§2.4 前提验收）。

**阶段出口**（solution §15 P1 / detail §14.3）：S-4 通过；任取线上请求 trace 可查；看板出现真实 P50/P95/P99 与全站 QPS 纵览（gq/cs/sp 接入）。

---

## 阶段 3｜P2 回流闭环（error-only，online 侧 + offline 配套）

> 目标：error 观察 → 聚类/去重 → 组装 → offline 拉取/激活 → 回归 → 回查 → 人工处置 闭环。对应 detail §1.7 P2 行（analyzer 聚类/去重 → converter 信封+落库 → offline pull-API/回写/回查 → 前端回流页 → worker jobs → 端到端闭环验收）+ §6/§7。

- **T-3.1 聚类/去重与 cluster 生命周期**：error_cluster 归一化/聚类窗口（7d）/去重唯一索引（含 generation）；superseded 保留 passed 终态、复发重开代数 +1；only-count 不重复生成语义（§6.2）。**验证目标**：E-4（7d 内同键再现只 count+1 不重复建 link）、E-12（双实例同 offset 不重复建 cluster/link）通过；生命周期状态机单测。
- **T-3.2 D19 信封组装（converter）**：evidence 区取数源 = error_cluster 快照 input 实文（脱敏 + 截断 ≤8K，不依赖 ES 回读）；assert 区含 no_fallback 断言 + **no_fallback_config 词表快照随 payload 下发**；组装质量下限自校验；快照缺 input 实文的残现场只计数不组装。**验证目标**：E-1（自动组装信封含 no_fallback_config → link=assembled → pull 可拉）、E-13（残 trace 快照缺 input → 只计数）通过；信封 schema 与 §7.1 逐字段对照。
- **T-3.3 平台间契约（online 侧）**：pull-API（`offline_status=assembled` 拉取、`case_type` 白名单 v1 仅 `regression_error` + `schema_version`）；状态回写（draft/active/invalidated）+ 单错级回查；ack 幂等（§7.3）；invalidated/rejected 重推展示 + admin requeue 复位 assembled（复用 payload_id）+ `assembled_ts` 刷新（§7.4）。**验证目标**：E-5（词表空 → 结构自检不通过 → offline 驳回 invalidated 回写；词条命中 → no_fallback fail）、E-6（admin requeue → 复位可拉）、E-15（ack 重放幂等）、E-22（requeue 刷新游标、增量 since_ts 重拉）通过。
- **T-3.4 人工处置状态机**：claim（必填 fix_version）→ 复核窗口 TTL → 回归 failed/超窗回退 open；置 fixed 需回归 passed 或 admin 复核（closed_by）；viewer 不单方 closed；reopen 流转；CAS 条件更新防竞态（§7.6）。**验证目标**：E-7（claim → 单错级回查 → verify=passed → cluster fixed；同 run 他错仍红不阻塞）、E-8（TTL 超窗回退 open + conversion_record）通过。
- **T-3.5 reentry 与终态守卫**：观察哨位 job（同键再现 → 新 cluster + 复发提示）；terminal 终态只读、迟到 run 结果只追加时间线（§7.5/§10.5）。**验证目标**：E-9（fixed 后同键再现 → 新 cluster + "线上仍复发"）、E-10（passed 后迟到结果不覆盖）通过。
- **T-3.6 worker jobs 集**：cluster_job/assemble_job/claim_ttl/recheck_job/reentry_job/judge_scan_job/rollup 等；分布式单飞（CAS 锁）；requeue 防抖 ≥5min。**验证目标**：时间驱动 job 单飞无重复执行（detail §1.3/§14.4 写侧判据）；job 失败退避 + 自监控计数可见。
- **T-3.7 前端回流页**：错误聚类列表/详情；offline_status/verify_status 展示文案（assembled"待 offline 拉取"/draft"待 offline 确认"/invalidated 重推状态）；人工操作（ignore/claim/needs_review 处置/fixed 复核/case 级 invalidate 仅未激活）；claim 复核窗倒计时；二期入口（弃留墙/quality）整条隐藏（§9.3/§9.4）。**验证目标**：viewer/admin 操作集与 detail §9.4 一致；invalidated 文案含"仍在观察、窗口内不自动重生成、可重推、长期停留找平台"。
- **T-3.8 offline 判定语义改造（Task #4-② 驱动）——offline 配套轨批 2 在平台阶段表的落点**：本项 = **offline 配套轨批 2 的汇合核对**。批 1（契约 + 收单/结构自检/激活/回写 + pull job，判定用 stub/fixture 通管道）已在联调环 0/环 1 先行拉通双端；批 2 在 offline 仓随 **Task #4-② 方案定稿即启动**，本任务项记录其范围与验收口径。批 2 范围：v1 `regression_error` 子集**判定语义**——判定器（executor 对 error 现场复现的技术判定）+ verifier no_fallback（以 payload 内词表快照为准、空表 fail-closed）+ rejected 保留重扫自愈回写收尾；换真判定后回归不碰契约。**验证目标**：按 Task #4 方案定义；覆盖 E-1~E-22 中 offline 侧依赖项 + 回归 run 单错级口径（run_results.pass_fail 合成 = executor ∧ no_fallback）；批 1 已绿的对端用例在批 2 后重跑不回归。
- **T-3.9 online 侧 P2 门**：§11 #5 相关 + §14.3 P2 行 online 部分先行全绿（E-16/E-18~E-21 中 online 侧场景在集成阶段复验）。

**阶段出口**（solution §15 P2 / detail §14.3，error-only）：E-1~E-22 全部通过（online + offline 配套，含 §11.5 维度 3 开放验收 checklist #4/#8/#10 + 兜底吸收埋点前提用例 S-4 真实 agent 复验 + 词表覆盖度对照 §13.1 兜底逻辑盘点）。

---

## 阶段 4｜集成测试与端到端验收（富化）

> 目标：把阶段 1~3 的**单元级产物按真实依赖串起来**，验证跨模块/跨平台/跨环境行为，覆盖 detail §14.1~§14.4 全量用例 + 部署/网络/安全/前端联调。此阶段**只验收、不新增功能**，发现缺陷回退对应阶段修复后重跑。
>
> 运行环境约定：backend/frontend 走主 compose（真实部署形态，不含中间件）；**中间件全连本地共享 infra（../infra，2026-09-03 决策：ES/Kafka 直接在 share-infra 创建；online 侧落权对象 = 本地 share-infra，MySQL 分库 + ES/Kafka 租户前缀隔离）**；本阶段对端场景（T-4.2/T-4.6/T-4.13⑤ 等）在环 0/环 1 绿后于环 2 串（见联调闭环小节）；故障注入以本地 infra/编排层注入优先（停容器/断网段/杀 broker 进程），污染共享实例风险高时用独立 dev 实例兜底，`compose.infra.dev.yml` 不作主线。
> 每任务出口 = 该组用例全绿 + 对应缺陷单清零 + 在集成报告登记。
> **异常与边界死角覆盖口径（本轮补充）**：分三层归位——**infra 层故障注入** = T-4.7（E-18~E-21）；**脏数据/畸形输入/检索/平台间契约/埋点前提** = T-4.13（新增）；**时序/窗口/数量级/并发/词表死角** = T-4.14（新增）。T-4.13/T-4.14 含 detail 已编号用例的集成复验 + task.md 追加补充场景，追加项若验收采纳须回填 detail §14 登记，防用例口径漂移。

- **T-4.1 链路与冒烟集成（S-1~S-5）**：跨 consumer→ES→API→前端 全链路复验冒烟用例，含真实前端渲染。**验证目标**：S-1~S-5 在集成环境全绿；trace 详情页大 trace 懒加载不卡；关键字检索限 7d/超时/上限在网关侧同样生效。
- **T-4.2 error 回流主链端到端（E-1~E-4）**：制造透传 LLM 错误 → L1 落 cluster → 自动组装信封（含 no_fallback_config）→ link=assembled → **offline 定时 pull**（真实 offline 仓）→ 结构自检激活 → 回归 run → 回写 → 看板状态流转。**验证目标**：E-1/E-2（含 OR 门控兜首次 llm_call 前程序错误）/E-3（重试自愈不回流）/E-4（窗口内不重复）全绿；时间线在聚类详情可视化正确。
- **T-4.3 词表守卫与重推自愈（E-5/E-6/E-22）**：词表空 → fail-closed（结构自检不过、判 inconclusive 不静默 pass）；词表命中 → no_fallback fail；offline 驳回（能力缺）→ online 展示重推状态；admin requeue（内容缺）→ 复位 assembled 重新可拉。**验证目标**：E-5/E-6/E-22 全绿；payload 内词表快照与当前 dict_config 变更互不 retroactive 影响已激活 case；requeue 防抖 ≥5min 生效。
- **T-4.4 人工处置 / 回查 / reentry / 终态守卫集成（E-7~E-10、E-17）**：claim 填 fix_version → 回归 run → **单错级判定**（同 run 他错仍红不阻塞）；TTL 超窗回退；fixed 后再 claim 新版本 → 同 cluster 新 link（新 payload_id）；reentry 复发反馈；终态只读。**验证目标**：E-7/E-8/E-9/E-10/E-17 全绿；CAS 并发（双 admin/viewer 同时置状态）无覆盖竞态；conversion_record 审计链完整。
- **T-4.5 判定执行方与积累态集成（E-13/E-14/E-16）**：残 trace（root 未达）按子节点判定；SSE/分批到达等窗口补全；`judge_scan_job` 到期补判（judged=0 ∧ ttl_until≤now → classify → judged=1）不重判；多实例并行消费幂等。**验证目标**：E-13/E-14/E-16 全绿；judge_scan 调度与 job 单飞在双实例下验证。
- **T-4.6 平台间契约集成（E-11/E-12/E-15）**：offline 停摆（pull 停）→ assembled 已待 N 天超阈值**提示性标记**（不自动告警、不设 online 时钟）；offline 恢复继续拉取不丢（含恢复积压限速/按序拉取）；pull/ack/回写重放幂等。**验证目标**：E-11/E-12/E-15 全绿；恢复后无一次性灌入大量陈旧 case 的峰值（限速生效）；双时钟不引入。
- **T-4.7 故障注入（E-18~E-21，对应 detail §14.2 三连 + 网关）**：**Kafka broker 停** → consumer 停拉退避挂起（不提交空推进）→ 恢复续拉不丢、判定态补齐；**ES 不可用** → 事件落待补写 spool 或显式丢弃 + rollup 缺口标注，判定/聚类/回流不受影响；**MySQL 不可用** → 判定态写失败**不提交 offset + 退避自监控**（禁"丢弃并提交"）；**网关/offline 不可达** → 回查退避重试、超上限提示"回查失败待人工"。**验证目标**：E-18~E-21 全绿；各注入点 selfmonitor 计数可见；恢复自愈无需人工干预（除显式告警项）。
- **T-4.8 性能护栏验收（§14.4 全量判据）**：rollup 迟到重算幂等 + t-digest 合并误差；O-1 缓存/超时护栏；检索/看板限流熔断；写侧 P95；job 单飞。**验证目标**：全站 24h agg P95 ≤5s；`metric_agg_cache_ttl_s=60` / `metric_agg_timeout_ms=3000` 生效；trace 检索 `trace_query_timeout_ms=3000`、命中 ≤200；判定态表单行 upsert P95 ≤10ms；rollup 每小时 ≤2min；**t-digest 跨小时合并 vs 全量重算 p95 误差 <1%**；索引/聚合在 500 事件/s 档下无告警。
- **T-4.9 部署/网络/网关与公共 infra 联调**：交付物边界（仅 backend+frontend）；`.env` 注入与凭证不入镜像；`{env}.` 前缀在库/index/topic/consumer group 全链路一致；**公共 API 网关**（终止 TLS、`{env}` 子域/路径、内部 JWT、前端登录走网关）；offline↔online 平台间走内网不经公网网关；backend 容器不映射 3306/9200/9092；浏览器仅达网关。**验证目标**：E-21 网关场景全绿；绕过网关直连 backend 被拒；SSO 敲定项（§17 #14）按定案复验（最简：登录取代网关 SSO；若强制 SSO → 带签名身份透传头验签）；`{env}` 值域与 infra 登记一致。
- **T-4.10 安全集成验证（solution §12 + detail §13 全块）**：平台用户域——JWT 短效 access + refresh、**token version 吊销即时生效**、口令散列 + 失败锁定、admin 禁用即吊销、viewer/admin 前端拦截 + 后端二次鉴权；agent 上报域——Kafka SASL/TLS + topic ACL（每 agent 凭证隔离、topic 不可互写）、消费侧未授权 topic **丢弃并计数告警**、agent_credential 加密轮换、每 agent 上报/回流量级速率闸；平台间——双向认证 + 最小 API 面（pull-API case_type 白名单，非白名单返回空集）。**验证目标**：越权访问被拒（角色矩阵）；伪造 topic 投毒被 ACL 挡 + 告警可见；吊销后旧 token 立即失效；凭证轮换不中断消费；速率闸触发阈值熔断。
- **T-4.11 前端端到端联调（§9.3/§9.4 全条）**：登录 → 菜单按角色渲染；看板/链路/回流三类页与 API 数据联动；状态文案逐条（assembled/draft/invalidated/claim 倒计时/pending-fix 标注"近似 offline 权威集"）；空态（全站无数据不误读、二期入口隐藏不灰置）；**needs_review v1 通常不出现**（回归 infra-error 边缘触发才出现）。**验证目标**：detail §9.3 关键交互逐条通过；浏览器端无死功能入口（F1/F3/F4 收敛验证）；admin 操作留审计。
- **T-4.12 回归门禁口径与维度 3 开放验收（solution §11 + §13.0 checklist）**：发布回归硬门禁并列口径在 offline 集成环境验证；error 用例技术判定 ∧ no_fallback 词表断言合成 pass_fail；`fallback_utterance` 词表覆盖度对照 §13.1 兜底逻辑盘点（新增兜底话术即补词表）；checklist #4/#8/#10 放量门禁 + 维度 3 开放验收两档各过。**验证目标**：回归假绿（换词/变体/动态前缀）在词表残余承认范围内可观测（§16 登记）；门禁 fail-closed 生效；维度 3 开放验收通过后才放开回流白名单。
- **T-4.13 异常场景集成（脏数据/畸形输入/检索/契约/埋点前提）**：把"坏输入"与"异常流"按真实依赖串起来验证，防各组件单测各绿、串起来错。覆盖——① **消费侧 schema 异常**：缺必填字段/字段类型错/多余未知字段/整体 null 事件 → S-2 拒绝路径集成复验（丢弃 + selfmonitor 计数）；topic 与 agent 不匹配、白名单外 agent 事件拒绝（detail §4.2）；② **脱敏死角（§4.5）**：脱敏键不存在、值已是掩码形态、超长值、嵌套异常层级 → 不炸、不二次脱敏、可追踪；③ **埋点前提（§4.2/§5.1，对应六方向评审 Finding 4 口径）**：制造一次 LLM 裸调用失败被业务 catch 转兜底返回 200 → 断言 `request ok + llm_call status=error` 先记后传、trace 子节点红显、失败率计数不丢（与 T-2.5 的 S-4 真实 agent 复验呼应）；④ **检索注入与转义**：关键字含引号/通配符/保留字符/中文分词边界词 → 查询不报错、不误命、不返回错误 scope；search_after 末页后再翻稳定返回空；⑤ **平台间契约异常**：pull-API 收到 case_type 非白名单 → 返回空集；schema_version 不匹配 → 拒单并计数；回写字段非法/状态越界 → 幂等拒绝不污染状态机；⑥ **大对象边界**：payload 超 Kafka 上限、evidence 实文恰 8K/超 8K 截断、缺 input 残现场只计数（E-13 集成复验）。**验证目标**：①②⑤⑥ 各异常路径丢单有计数、不误入正常链路；③ 前提用例通过（基础可见性从承诺变验收）；④ 检索注入无异常无越权 scope；所有注入点恢复后自愈、无静默吞错。
- **T-4.14 边界死角场景集成（时序/窗口/数量级/并发/词表）**：专盯"临界值、边界条件、竞态窗口"三死角，与 detail 已编号用例互为补强。覆盖——① **时间边界**：事件 ts 为未来/1970/UTC 与本地时区交界 → 周 index 归属与 date_histogram 分桶正确；跨周切换事件落在前后两周的检索去重不重不漏（§2.1 周滚动）；② **窗口边界**：error 同键恰在 7d 聚类窗边缘再现（第 7 天 vs 第 8 天）→ count+1 vs generation 新开（E-4 补强）；指标窗恰 24h（实时）与 24h+1s（rollup 路由切换）；rollup 迟到恰 6h 幂等重算、超 6h 不再重算、缺桶回退实时 + 页面标注、尾小时实时补齐（§5.3）；③ **判定时序边界**：judge_scan 到期瞬间补判、重复到期不重判（E-16 补强）；④ **数量级边界**：trace 检索命中恰 200 与超 200 截断、末页后翻；单 trace 日志上万行首屏懒加载不拉爆（S-5 补强）；⑤ **并发/竞态边界**：双实例同 offset 不重复建（E-12 复验）、CAS claim/requeue 与 offline pull 并发、requeue 防抖恰 ≥5min 边界、ack 幂等重放与并发拉取交错（E-15 复验）；⑥ **词表边界死角**：空表/极短表 fail-closed（E-5 复验）；动态前缀/拼接/大小写/换行/空白差异/超长词/重复词在词表残余承认范围内行为可观测（§16 登记口径，不要求全拦，要求"假绿时可被抽查发现"）；⑦ **保留期边界**：ILM 30 天删除后检索与看板缺口标注行为（衔接 T-5.2）。**验证目标**：①②③⑦ 边界值两侧行为各按预期、无越界错配；④ 限值/上限行为稳定不报错；⑤ 并发交错无覆盖竞态、审计链完整；⑥ 假绿残余可观测可抽查、fail-closed 生效。

**阶段出口**：S-1~S-5、E-1~E-22、性能护栏判据全绿；T-4.13/T-4.14 异常与边界死角补充场景全绿（超出 detail 编号的追加项已回填 detail §14 登记）；安全/部署/前端联调通过；所有缺陷单清零并回归；输出一份集成测试报告（用例→结果→缺陷溯源映射，对应 detail §14.3）。

---

## 阶段 5｜上线放量与运营

- **T-5.1 灰度放量门禁**：按 solution §13.0 checklist 放量门禁档逐步放 agent 流量；观察窗内核对无告警、无漏采、指标口径与预估值一致。**验证目标**：checklist #1~#3 放量档全绿；观测数据连续 7d 无断档。
- **T-5.2 容量与索引实测**：Step 3 灰度实测定容量档（≤500 事件/s 档核对、租户分配档确认）；index 周滚动 + ILM 30 天真实删除验证。**验证目标**：容量档与 infra 实际分配一致（solution §7.1 容量行）；ILM 到期删除有测试数据佐证；rollup/实时双路在该档下 P95 达标。
- **T-5.3 与 infra 收口**：网关/SSO 定案闭环（§17 #14）；env 值域与命名登记生效（§17 #15）；topic ACL / ES template / 网络策略回执三方核对；**操作面契约收口（T-0.2 交付物核销）**：服务账号权限矩阵 ①~⑤ 与 rollup 写归属、consumer group 操作面、变更通道 SLA 回执复核，权限变更申请单归档。**验证目标**：§17 #14/#15 两行由"待敲定"转"已落"并在 solution.md 标注；T-0.2 矩阵/回执项全部核销、无未决变更单；上线时任一待办残留则阻断放量。
- **T-5.4 运营清单与交接**：TTL 告警/顶置提示 owner 明确（offline 拉取/确认 owner 归 offline；online 仅"已待 N 天"展示不设时钟）；保留期与审计导出；看板口径文档（双指标、rollup 缺口标注语义）交付；**回归假绿残余承认 + 词表维护流程**（新增兜底话术即补词表、admin-only 留审计）写入运营 SOP。**验证目标**：运营手册与实现行为一致；维度 3 开放验收项（checklist #4/#8/#10）在真实 agent 上最终复验通过。

**阶段出口**：维度 3 开放验收全绿 → 开放回流白名单；上线复盘记录容量/告警/假绿残余基线，作为二期（L3 quality、C2 会话型回归）排期输入。

---

## 风险与关注（本 WBS 层面的依赖与假设）

- **轨道与前置依赖**：Task #4 offline 配套方案未产出（已切两刀：批 1 契约 + 收单先行 = 联调环 0/环 1；批 2 判定语义 = T-3.8），只阻塞 **offline 配套轨**与平台轨在阶段 3.8/4.x 的汇合（平台轨 online 侧、agent 整改轨不受阻）；**本地共享 infra（../infra）扩 ES/Kafka 是平台轨阶段 0/1 的硬前置与环 2 的门（2026-09-03 决策，infra 仓改造、本地可自控节奏）**——未完成前 S-1 冒烟/P0 观测链用 `compose.infra.dev.yml` 临时过渡（非主线）；网关 SSO 与生产公共 infra 租户（§17 #14/#15）是上线门、不阻塞 dev 联调；agent 整改轨仅依赖 SDK 契约冻结，不依赖 infra 到位。
- **假设**：公共 infra 各租户以 `{env}.` 前缀隔离互不可见；词表覆盖度缺口（漏词/变体）在 v1 属如实存在（solution §16 承认），不阻塞闭环、仅登记。
- **待办（跨文档一致性，2026-09-03 确认）**：T-4.13/T-4.14 中**超出 detail §14 已编号用例**的追加场景（埋点前提用例、检索注入/转义、时间/窗口/数量级/词表边界死角等）须回填 detail §14 登记——**执行时点：阶段 4 启动前**（随 Task #4 方案定稿或下一次 detail 修订窗口一并处理）；未回填前集成验收以 task.md T-4.13/T-4.14 为准，回填后以 detail §14 编号为权威口径，两文档用例集对齐。
- **边界**：L3 quality/会话型回归/collector 组件不入本 WBS（v1 不实装，detail §12.1 二期占位索引为准）。
