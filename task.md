# agent-evaluation-online 工程任务拆解（WBS）

> 目的：把 **solution.md（v3.5.9，error-only 一期定稿 + 部署边界 + Task #4 契约修订与实现清单包 R-1~R-24 语义权威同步，含 R5-R7 auto-fixed 判据重构）** 与 **solution_detail.md（v1.12，开发就绪详设，含 Task #4 全部契约修订 B 包/R1~R24 落字 + §14.5 X 系列集成异常/边界用例登记 + 2026-09-08 阶段 1 尾项实现收口注记：前端栈 Vue 裁定 / auth 最小闭环边界 / trace 查询实测修正 + 阶段 2 平台轨 T-2.1~T-2.4 收口注记：metrics 链路实现钉定 / O-4 自研纯 Python t-digest / 7d mixed 读取口径 / dashboard 落地，见修订记录 v1.11/v1.12 与阶段 2 收口注）** 中"将要做的事情"拆成可执行的任务阶段与任务项，每项给**验证目标**，指导排期、认领与验收。本文不重述方案内容，只做**执行层拆解**并指向两文档锚点。
>
> 权威口径：功能范围 = detail §0.1（锁定 v3.5.1；v3.5.2 仅同步部署边界、v3.5.3/v3.5.4 仅同步 Task #4 契约语义，均不改变 v1 error-only 功能范围）；阶段门 = solution §15 P0~P2；测试用例全集 = detail §14.1~§14.5（S-1~S-5、E-1~E-29、性能护栏 + 集成异常与边界 X-1~X-13（= T-4.13/T-4.14 编号化登记，detail §14.5），E-23~E-29 = R-13~R-24 修订包端到端）。**Task #4（offline 配套方案，独立文档 + 独立评审）已切两刀、双批方案均已产出并历 R1~R3/R5-R7/R-1~R-24 修订包演进（逐批登记见下「联调闭环编排」环 0 bullet）**：批 1 = offline `error-backflow-phase1.md` **v0.2.2**（契约 + offline 收单 = 联调环 0/环 1 offline 侧，2026-09-03 评审通过，后续 R1~R3 落改确认 + code_detail 转译注记）先行；批 2 = offline `error-backflow-phase2.md` **v0.7.2**（判定器复现 + verifier no_fallback + R5-R7 auto-fixed 判据重构 = T-3.8 落点，2026-09-07 终审通过；R5-R7 及后续修订包消费语义已逐步落字 online detail v1.4→**v1.9** / solution v3.5.4→**v3.5.9**）。双批是阶段 3.8/阶段 4 与联调环 0~3 的前置输入。

## 阶段总览

| 阶段 | 主题 | 文档锚点 | 出口（本阶段验收） |
|---|---|---|---|
| 阶段 0 | 工程地基与部署接入（前置） | detail §1.5/§1.6/§13、solution §14 部署边界 | 主 compose 仅起 backend+frontend、seed 完成、infra 凭证/落权/索引模板就绪、**操作面契约回执（服务账号权限矩阵 ①~⑤）**、CI 绿灯 |
| 阶段 1 | **P0 平台骨架** | solution §15 P0、detail §1.7 P0 行、§14.1 | S-1/S-2/S-3 通过（§14.3：手工投事件可按 trace 查回） |
| 阶段 2 | **P1 两维落地**（链路 + 指标） | solution §15 P1、detail §1.7 P1 行、§14.1 | S-4 通过；看板出现真实 P50/P95/P99 + 全站 QPS 纵览（gq/cs/sp 接入） |
| 阶段 3 | **P2 回流闭环（error-only，online 侧）** | solution §15 P2 + §11、detail §1.7 P2 行、§6/§7 | E-1~E-29 主链 + 修订包语义通过 + Task #4 offline 侧改造通过（§14.3；E-23~E-29 双端/环 2 形态在阶段 4 验收） |
| 阶段 4 | **集成测试与端到端验收（富化，含异常与边界死角）** | detail §14.1~§14.4、solution §11/§12/§16 | S/E 全量通过 + 性能护栏判据达标 + **T-4.13 异常场景 / T-4.14 边界死角场景全绿** + 安全/部署联调通过 + 回归门禁口径验证（**2026-09-11 网关归属裁定**：「网关联调」下移 T-5.3 上线门，见 T-4.9 注） |
| 阶段 5 | 上线放量与运营 | solution §13.0 checklist、§15、§17 #14/#15 | 维度 3 开放验收（#4/#8/#10）+ 容量实测 + 与 infra 敲定项闭环 |

**执行轨道（三轨并行，非纯线性排期）**：阶段 0 → 1 → 2 → 3 串行是**平台轨**主干顺序（各阶段内部 job 与 API 可并行，detail §1.7 注），阶段 4 覆盖阶段 3 产物、阶段 5 在其后放量。但 solution §15 明示 **agent 整改与平台开发并行**、Task #4 offline 配套为独立仓，故整张阶段表只是**平台轨**视图——三条轨道独立推进、只在汇合点交汇，**任何一轨滞后只影响其汇合点，不阻塞另两轨的主体工作**：

| 轨道 | 内容（对应任务项） | 起点 | 汇合点 |
|---|---|---|---|
| **平台轨** | 阶段 0/1/2/3/4/5 主干（建站 → 看板 → 回流 → 集成 → 上线） | 阶段 0 | —（主轴） |
| **agent 整改轨** | agent 侧 SDK 接入改造（gq/cs/sp 插桩、cc 仅 HTTP 层、LLM 旁路、存量整改，= T-2.5 的内容） | **SDK 契约冻结（阶段 1.5 出口）即启动**，不等平台 P1 完成 | 阶段 2.5（真实 agent S-4 复验）、阶段 3.9/5.x 放量门禁 |
| **offline 配套轨** | offline 仓 v1 `regression_error` 改造，**Task #4 切两刀**：批 1 = 契约 + 收单/结构自检/激活/回写 + pull job（联调环 0/环 1，方案 = offline `error-backflow-phase1.md` **v0.2.2**）；批 2 = 判定器复现 + verifier no_fallback + R5-R7 auto-fixed 判据重构（= T-3.8 落点，方案 = offline `error-backflow-phase2.md` **v0.7.2**，历 R-1~R-24 修订包演进） | **批 1 契约先行**：Task #4-① 定稿即启动（独立方案独立评审，最先拉通双端）；批 2 方案已定稿、不阻塞批 1/环 2 | 环 0 契约冻结 → 阶段 3.8（批 2）、阶段 4 E-1~E-29 offline 侧用例（E-23~E-29 修订包端到端）、阶段 5 回归门禁 |

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
| 环 2 | **双端集成联调** | 同机双 compose + **本地共享 infra（../infra，已扩 ES/Kafka）**底座，契约**内网直连不经公共网关**；合成 error 事件驱动 E-1~E-29（E-23~E-29 修订包端到端）+ T-4.13/T-4.14 对端场景 | 两端 + 本地 infra | = 阶段 4 出口 | **本地 share-infra 完成 ES/Kafka 扩展**；环 0/环 1 绿 |
| 环 3 | **真实流量灰度** | agent 接入后真 error 触发；观察哨位/重推/requeue/停摆恢复真实现场 | 两端 + agent 整改轨 | 维度 3 开放验收 + 回流白名单放开 | 阶段 5 门禁 |

关键工程口径：
- **Task #4 切两刀（2026-09-03 裁定；双批方案 = offline `error-backflow-phase1.md` v0.2.1 / `error-backflow-phase2.md` v0.6.1，v0.6.1 于 2026-09-07 终审收口；现行 = 批 1 v0.2.2 / 批 2 v0.7.2，见上权威口径）**：**批 1 = 契约（环 0）+ offline 收单/结构自检/激活/回写 + pull job**，判定先用 stub/fixture 通管道；**批 2 = 判定器（executor 复现）+ verifier no_fallback + R5-R7 auto-fixed 判据重构（纯净 run + 跨版本稳定序列 K / reentry 同版本禁 auto-fixed，消费语义已落字 online detail v1.4 / solution v3.5.4，见下 B-10~B-12 bullet）**（= T-3.8 落点）。批 1 独立方案独立评审、先行；批 2 换真判定后回归不碰契约。
- **契约修订包 R1~R3 已入环 0（2026-09-03，Task #4-① 评审拍板）**：R1 = `pull/payloads` 响应逐 payload 附顶层 `assembled_ts`（offline 增量锚唯一来源）；R2 = ack 前置矩阵补 `invalidated(offline_cap_gap)→active` 自愈回写例外；R3 = ack 400（`ERR_CLUSTER_0003`）响应带当前 `offline_status`+`invalidate_reason`。**已落 detail v1.2（§7.2/§7.3/§8.7/§8.9 + 修订记录）**；环 1 stub/fixture 按修订形状造样例（offline 侧 `error-backflow-phase1.md` v0.2 已按其语义实现，§2/§12 标注依赖）；环 2 前双端对齐。
- **批 2 契约修订 B 包已入环 0（2026-09-03，Task #4-② 对接核查拍板）**：B-1(a/b/c) recheck 判定源限定终态 run + per-case 值域映射 + 多 run 选取序 + §8.7 status 取值集 / B-3 needs_review 源 = error-run na 三处同步（§1.4/§12.1/§7.6）/ B-4 na 批量聚合载体 `needs_review_batch` / B-5 fix_version 版本字面量域 + reentry 门控 = **等值+日期前缀门控** / B-6 run_status 注释纠错 + 归档保留语义 / B-7 本条登记。**已落 detail（§7.5/§7.6/§8.4/§8.7/§1.4/§12.1/§5.1⑥；solution_detail 修订记录已随 v1.3 起各批落字并 commit）**；环 1 stub/fixture 按修订形状造样例；环 2 补**批 2 双端闭环用例**：error run 终态字面量对表、per-case pass_fail 含 na、`na_case`+`error_type` 响应字段、recheck 轮询 status 值集；**S5 硬前提用例** = 被测 agent 发版 = offline manual/held_out run 达终态（发版未触发 offline 评测 → 该版本无 error run → 空回查 TTL，验证为流程前提非契约缺陷）；**S4 门控用例** = 同日 `r47`/`r100` 复发仅完全等值放行 reentry、同日不等值 **blocked 零落（v1.19 口径；非「只 count+1」，见下 v1.20 注）**；fix_version mismatch（人手 ≠ agent 自报）用例；**门控反例（v1.3 排查补；v1.20 派生口径修正）**：① 同日 hotfix——r47 claim/fixed 后同日 r48 上线仍复发 → 前缀同日 + 非等值 → **不 reentry（v1.19 起 merge 返 "blocked"、DB 零落，judged 行仍被 processed CAS=1 消费；旧文「只 count+1」已废）**，**断言 fixed cluster 详情经 `reentry_observe`（v1.20：后端读 MySQL `trace_judge_state` 保留窗现算，非前端 ES 派生）可见「同键新版本 r48 复发 N 次」提示（不静默）**；② 跨日 r100（fixed 后次日复发）→ 日期前缀更大 → reentry 开新 cluster；③ 非补零形态 `2026.9.3-r5` vs fix `2026.9.3-r5`（同串）→ 等值 reentry；vs `2026.9.3-r7` → 非日期形态回退等值 → count+1（fail-closed 预期）。
- **批 2 判定语义修订 B-10~B-12（auto-fixed 判据重构，R5-R7）已入环 0/环 2（2026-09-07，Task #4-② 终审通过；方案基线 = offline `error-backflow-phase2.md` v0.6.1）**：R5/B-10 纯净 run 前提——auto-fixed 仅接受「纯净可判」run（error run 达终态 {completed, partial_failed, timeout, cancelled} 且 run 级 na_case==0，纯净性由 online 消费侧从关联 run.na_case 派生、verify_run_record 不加纯净列）；不纯净 run 内 pass 行 → needs_review（reason `unclean_run`）；R6/B-11 跨版本稳定序列 K=2（默认可配、K=1 兼容单版）——自 claim fix_version 起连续 K 个纯净可判版本 run 均无 fail → verify passed → fixed（closed_by=auto_regression），fail 即时 reopen；**K-TTL 两时钟收敛**（K 满 → fixed 停钟 / claim TTL 先到 → 回退 open，K 观察/回查不延长 TTL）；R7/B-12 reentry 同版本禁 auto-fixed——generation>1 产物 claim 同已完成版本 → 旧 run pass 行 → needs_review（reason `reentry_same_version`，claim 级单条不产批）。**reason 值域 = {na, unclean_run, reentry_same_version}**（needs_review_batch 只承载 na/unclean_run、同 (run,error_type) 至多单条、整批单动作处置）。
  - **⚠️ 本条后半已部分失效（2026-09-14 标注，原文保留不改写）**：上句是本条**当时（2026-09-07 / detail v1.4）**的口径，其后两轮修订均已推翻——**v1.5 R-2**：`unclean_run` 触发窄化为「含**环境级** na 的 run 内 pass 行」，**批载体只承载 `unclean_run`**（纯 `na` 退批走 cluster 级单点，故「只承载 na/unclean_run」不再成立）；**v1.6 R-10**：值域 **3→4** 增 `input_truncated`。**现行权威 = `claim.py:32 REVIEW_REASONS` = {na, reentry_same_version, input_truncated}，且 `unclean_run` 不入 `needs_review` 态**（只经 batch 载体，`claim.py:9`）。见报告 §6 **F-20**。**已落字 online detail v1.4（§7.6 auto-fixed 判据 blockquote / §5.1 verify_run_record+needs_review_batch DDL / §7.5+§8.4 reentry 联动 / §10.1 claim TTL）与 solution v3.5.4（§10.4/§10.5/§7.2/§12.1/§15/§16）**；环 2 双端闭环用例 = phase2 §11.2 场景 14/15/16（纯净 run 环境污染不传导 fixed / K=2 单 pass 不 fixed、老 case 窗口截断中断 K → 诚实欠测 / reentry 同版本旧 run pass 转 reentry_same_version、改 claim 新版本走 R5/R6 正常判据）。
- **R-13~R-24 实现清单批（2026-09-07 逐问拍板；H7 批 B/C/低危 12 条已全 landed = detail v1.8/v1.9 + solution v3.5.8/v3.5.9 + phase2 v0.7.1/v0.7.2，方案与落点见 register R-13~R-24 行）——本 WBS 登记其中需落代码的实现/核对项**：**online 实现清单** = R-13 §6.2 同簇回填 input_truncated 刷新复制 + R-16 excluded_case_ids 落 runs list/detail 字段位 + R-21 `trace_judge_state.root_late_complement` 列 + 消费 step4 root-late 补判（detail §4.3④/§4.4/§6.2，环 2 E-28）+ R-24 requeue guard 状态域（detail §7.4/§9.4：fixed/inactive 禁 requeue、open/claim/needs_review 放行、不动 claim 锚点，环 2 E-29）；**Phase B code_detail 实施门禁** = R-20 pre-scan 报告（owner = offline 实施：扫现网 keyword_* 断言空字段依赖 + 合法空答清单 → R-12 text.py 空答 fail 修补带豁免白名单上线，**先于 R-12 code 落地**）；**offline 实施护栏** = R-19 code 一致性单测（executor 常量全集 ⊆ phase2 §6.4 标注清单 ∪ 调度/assertion 值域，环 0 静态核对项）+ R-22 收尾回填 na error_type 单测护栏（scanner 回收/orchestrator cancel/run 级超时收尾三路径回填 `scheduler_unexecuted` 非空断言）。环 0 契约冻结不因本批新增平台间契约字段（R-21 列在 online 判定态表、非 pull/回写契约）；环 2 用例随 detail v1.9 §14 E-28/E-29 并入。
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
- **T-1.4 trace 链路查询 API**：traceId/关键字自由输入；`(ts,parent,seq)` 树序还原；日志行分页懒加载；关键字检索 `collapse(trace_key)` + `from/size` 偏移深翻页（`offset ≥ 200` → 400 `ERR_TRACE_0002`）+ 限 7d + 超时 `trace_query_timeout_ms=3000` + 命中 ≤200（§14.4）。**验证目标**：S-1（手工投 request+llm_call+log，trace 可查、日志穿插、llm_call 高亮）、S-5（命中 error_msg + 深翻页 + 限流/上限生效）通过；单 trace 上千日志行首屏不拉爆。
- **T-1.5 obs-sdk 雏形**：logging handler + 事件打点（§2 样例三份可直接用于单测）；内存队列 → 批量 → kafka-python（§3.1）；可靠性与降级（写满丢弃并计数、本地持久卷可配路径、失败退避 ≤3 次、恢复补传，§3.2）；`agent_version` 注入（R5 打点源）。**验证目标**：SDK 单测（§2.2 样例逐字段）、断点重传冒烟；agent 进程内 kafka 故障时业务不阻塞（有界队列 + 丢弃计数）。
- **T-1.6 前端骨架**：登录 + 链路查询列表 + trace 详情（树时间轴 + 红显 + 日志穿插）。**验证目标**：S-1 在浏览器可查回（P0 验收人工步）。

**阶段出口**（solution §15 P0 / detail §14.3）：S-1、S-2、S-3 通过；手工投 Kafka 事件能按 trace 查回链路。

- **阶段 1 收口（2026-09-08，本阶段出口达成）**：T-1.3 / T-1.4 / T-1.6 + auth 隐式前置后端闭环全部落地（T-1.1/T-1.2 前批已绿）；**S-1 浏览器级 + S-5 curl 级验证全绿**。落地要点：前端栈定 **Vue3 + Vite**（auth 最小闭环 = T-1.6 登录页数据源 §8.1 隐式前置，随本批闭环；登录落点先指 `/traces`，dashboard 待阶段 2）；ES index template/ILM 由 infra `es-init` 落建（ik_max_word 中文分词 + ILM 30d，template 接管新建周 index），本仓交付物 `es-template/`；trace 查询三端点护栏全开（列表折叠去重 + `cardinality(trace_key)` 去重总数、详情 seq asc 结构序 + ≤500 截断、日志懒加载分页、body_search 正文保护 + 检索面收窄）。**四实测发现（detail v1.11 修订记录）**：① ES collapse 不改 hits.total → 列表去重总数须独立 cardinality agg，且折叠键须 concrete keyword 字段（不支持 runtime）；② SDK request 事件在中间件 finally 才 emit、ts 恒最大 → 详情 ts asc 会让根沉底，改 seq asc 创建序；③ nginx 反代目标须用 container_name `obs-backend`（共享 external network 上 `backend` alias 被 5 仓轮询占用 → /api 404）；④ `backend/.env` 会被 docker compose 按运行 CWD 加载并覆盖仓根 `.env`（DB_PASSWORD 错源 → Access denied），容器重建须 `--force-recreate` 才吃新 env。

---

## 阶段 2｜P1 两维落地（链路完整化 + 指标看板 + agent 接入）

> 目标：维度 1 补全到生产可用，维度 2 指标闭环 + 看板；agent 侧 SDK 接入真实流量。对应 detail §1.7 P1 行 + solution §15 P1。

- **T-2.1 L1/L2 分层判定（判定态持久化）**：analyzer classify + **judge_scan_job**（扫 `judged=0 ∧ ttl_until≤now` → classify → 写判定/归并 → judged=1，重复到期不重判）；per-trace 累积态三要素落 `trace_judge_state`，重平衡从判定态重建不回读 ES；残 trace 按已有子节点判定（detail §4.3/§6.1）。**验证目标**：单测覆盖 L1/L2 分类分支与 OR 门控（L2 = trace 动态事实 或 接口字典 llm=true）；judge_scan 到期补判、重复到期不重判；residual 子节点判定。
- **T-2.2 指标实时 agg + metrics API**：request/llm_call 双指标；`status∈{error,timeout,ok}` 互斥计数；1h/24h 实时 agg（date_histogram × percentiles p50/95/99 × filter）；时间窗路由（≤24h 实时 / 7d rollup）；**O-1 护栏**：agent 缺省=全站实时 agg 强制缓存 `metric_agg_cache_ttl_s=60` + 超时 `metric_agg_timeout_ms=3000`（§14.4）。**验证目标**：S-4 口径（request ok + llm_call error 计入失败率、不回流）；全站 24h agg P95 ≤5s（护栏判据）；缓存命中跳过 ES。
- **T-2.3 7d 小时级 rollup**：每小时预聚合 agent×interface×node×小时（写 rollup/t-digest index 的账号归属取 **T-0.2 权限矩阵 ②**，不自建权限假设）；t-digest 可合并草图；首启回填、迟到（≤6h）幂等重算、缺桶回退实时 + 页面标注、尾小时实时补齐（§5.3）。**验证目标**：迟到重算不双计；缺桶回退标注可见；**t-digest 跨小时合并 vs 全量重算 p95 误差 <1%**；每小时任务完成 ≤2min。
- **T-2.4 看板前端**：全站纵览 tab（QPS 时序 + 失败率/超时率叠加，缺省=全站）、概览卡（QPS/P50/95/99 + 1h/24h/7d）、接口明细（请求级/LLM 级双指标）、异常聚焦、『LLM 调用失败』下钻段（request ok + llm_call error/timeout → trace 列表，标注"降级/兜底现场，v1 不回流、L3 二期"）。**验证目标**：真实数据出 P50/P95/P99 + 全站 QPS 趋势；下钻从毛刺到受影响 trace 直达（F2 消费路径闭合）；二期质量出口整条隐藏不灰置（§9.3 UI 规则）。
- **T-2.5 agent 接入（SDK 改造）——agent 整改轨在平台阶段表的落点**：本项 = **agent 整改轨与平台轨的汇合核对**，非纯平台任务。agent 侧插桩改造（gq/cs/sp 接 SDK、cc 仅 HTTP 层 request 级指标与链路 D18、LLM 第二通道旁路逐一接入 + **打点包住裸调用、最终失败一律标 error（先记后传）**、存量整改对齐 detail §11.3 v1 只做 #1~#4/#6~#9、#5 二期延后）已在 agent 整改轨上随 **SDK 契约冻结（阶段 1.5 出口）提前启动**；本任务项承接平台侧条件（agent_credential/注册配置、dict_config 下发，solution §13.0 Step 1~3）就绪后的联调、灰度与收口。**验证目标**：solution §13.0 checklist #1~#3（放量门禁档）通过；S-4 在真实 agent 上复验（LLM 失败被业务兜底、request 200，trace 红显 + 失败率可见，§2.4 前提验收）。

**阶段出口**（solution §15 P1 / detail §14.3）：S-4 通过；任取线上请求 trace 可查；看板出现真实 P50/P95/P99 与全站 QPS 纵览（gq/cs/sp 接入）。

- **阶段 2 平台轨收口（2026-09-08，平台轨子集 T-2.1~T-2.4 实现 + 验证全绿；全量 P1 出口待 T-2.5）**：backend 单测 **237 passed** + lint 零告警；S-5 curl 级 + S-1 浏览器 e2e 全绿（detail v1.12 修订记录详录）。落地要点：① **T-2.1** L1/L2 判定（`analyzer/classify.py` 纯函数）+ judge_scan_job 落**独立 worker 进程** asyncio 自管循环（judge_scan 1min + rollup 整点，仿 consumer 心跳，非 APScheduler）；`judgement_json` 形状钉死 + R-21 root-late 补判接线（消费 step4 同事务 CAS 落 `{status,error_type,layer,hit,at}`，供 T-3.6 聚类取数不改）；残 trace 子节点 interface 回填（state.py 非 root 分支）；② **T-2.2** metrics 四端点（`/metrics/overview|interfaces|anomalies|llm-failures`，窗口 1h/24h/7d 路由）+ **O-1** = 进程内无锁缓存 key=`endpoint|agent('*' 全站)|window`、TTL 60s、agg 超时 3000（缓存命中跳 ES）；错误码 **`ERR_METRICS_0001` 复数前缀**确认；③ **T-2.3** 7d 小时级 rollup（`{env}.obs-metrics-rollup` 单 index + mapping dynamic:false + **doc_type group/meta** + 确定性 `_id=sha256(...)` 整小时覆写幂等 + `rollup-meta|{hour}` 廉价迟到探测）；**O-4 裁定变更** = PyPI `tdigest` → **自研纯 Python t-digest**（C 依赖在无 MSVC Windows 源码编译失败、用户确认自研，`store/tdigest.py`）；**7d mixed 读取口径拍板**：卡片分位仅并 rollup 覆盖小时 sketch、计数/error/timeout/序列实时整窗（精确超集）、interfaces 行级分位保持实时、rollup 缺失/异常降级整窗实时 + 响应 `source`/`fallback_hours` 标记；④ **T-2.4** dashboard（Vue3 `/dashboard` + 手写 SVG 折线 + 空态 4 型 + 7d mixed 横幅「部分时段回退实时口径（N 个整点小时无 rollup 覆盖）」）；登录落点 `/traces` → `/dashboard`。**验证**：demo/合成流量（gen_metrics_demo.py，非真实 agent 流量）→ 真实数据出 P50/P95/P99 + 全站 QPS 纵览；rollup 写侧 one-shot 重建 6 已完成小时、group 计数与 meta source_count 对齐；**真实 rollup data 上 7d mixed 分位 vs ES 实时重算偏差 p50 0.35% / p95 0.04% / p99 0.17%（<1% 达标）**；S-1 浏览器 e2e 完整 loop 复验。**T-2.5 真实 agent 联调 = defer agent 整改轨**：平台侧条件（agent_credential/dict_config 下发）已就绪，S-4 真实 agent 复验（gq/cs/sp 接 SDK、cc 仅 HTTP 层）待 agent 整改轨排期后串，本批看板能力以 demo/合成流量验收。

- **阶段 2 平台轨前端 IA 重构 + agents 端点（2026-09-08 追加，detail v1.13 / register P1-2）**：T-2.4 dashboard 单页四段拆**五个一级菜单 1:1 落页**（总览 `/dashboard` / 接口 `/interfaces` / 异常 `/anomalies` / LLM 失败 `/llm-failures`，链路查询 `/traces` 接独立壳），每页只拉自身端点；metrics 新增 `GET /metrics/agents`（7d **纯实测去重** agent 列表，供 metric 页 + 链路页动态下拉，实测可见 cc/demo-agent）；共享 MetricFilterBar（agent + window，默认 24h/全站、localStorage 跨页持久化）；总览 **60s 自动刷新**对齐后端 60s 缓存；空态分页归位（异常/LLM 失败空 = 有效空态非 no_traffic）。**验证**：backend 单测 **243 passed**（agents +5）+ 本窗口新增后端 diff ruff 零新增；前端 vue-tsc + vite build 绿；S-1 浏览器 e2e 全绿（五菜单导航/高亮、总览 24h 实时 + 7d rollup 状态 + 60s 自动刷新 tick 渲染完好、接口双 tab、异常/LLM 失败真实行 + 下钻 trace-detail、链路页动态下拉过滤与空态、跨页 filter 继承、console 零报错）。

- **两批 commit 挑战点收敛（2026-09-08 追加，detail v1.14 / register 附录 A P1-3）**：对 `7dc95a6`（判定/rollup/metrics 后端批）+ `1a82c89`（前端 IA + agents 批）六挑战点逐点收口：① **1.1 判定固化 gate 语义（用户拍板接受现状、仅注记不动判定代码）**——gate 关闭窗内判 none 的 trace 因 `judged=1` 不重判 = 有意语义（「关闭即暂停该 agent 回流」，配置回摆不回填），归因看 `judgement_json.gate` 快照（detail §4.3 判定固化注）；② **1.2 7d 分位 vs 计数不同样本 → UI 字段级标注**——`MetricsOverview` 增 `covered_hours`（7d 已 rollup 覆盖小时数，1h/24h 恒 0），总览 7d rollup/mixed 渲染「分位基于 N 个已完成小时聚合（截至上一整点）」口径注（detail §8.3/§9.2/§9.3）；③ **1.3 series 边界桶 QPS 按实际覆盖宽折算**——`_overview_series` 逐桶 `covered_ms = min(ts+桶宽,end) − max(ts,start)`（首桶左越窗/尾桶进行中小时右越窗不再虚低爬坡；error/timeout_rate 分母仍桶内 count）；④ **2.1 agent 幽灵选择修复**——`GET /metrics/agents` 增 `{total,truncated}`（`distinct` cardinality 去重真实总数，缺 agg 回退 len 容 fake）+ MetricFilterBar 幽灵 agent warn 行/「清除为全站」按钮 + top100 截断 muted 提示 + `visibilitychange` 回前台 >60s 陈旧才重拉（非轮询）；⑤ **2.2 总览自动刷新 60s→45s + 可见性门**——45 < 后端 60s TTL 非整约 → 缓存存活期内多命中一次（实际后端查询约减半），interval 回调 `document.hidden/loading` 门 + 回前台 >15s 陈旧补一轮；⑥ **2.3 列表静默截断提示**——异常/LLM 失败增 `total/truncated`（anomalies body `track_total_hits: True`；llm-failures 折叠 total 走 `cardinality(trace_key)` agg——collapse 不改 hits.total），前端 section 上方 muted「窗口内共 N 条，仅显示最新 M 条」。**验证**：backend 单测 **249 passed**（基线 243 + 新增 6：partial 桶折算 2 / anomalies 截断 1 / llm cardinality 1 / agents truncated·fallback 2）+ 本窗口后端 diff ruff 零新增（es.py:199 基线遗留容忍行不碰）；前端 vue-tsc + vite build 绿。**交付状态（2026-09-15 订正）**：本节原写「未 commit 未 push（等授权）」，属**裸标记腐**——该批已随 `4707577`（detail v1.14 挑战点收敛落改收口）提交并推送，核实命令 `git merge-base --is-ancestor 4707577 origin/main` = 是（`4707577` 为 `origin/main` 祖先）；`revision-design-register.md` 附录 A 的 P1-3 行早已记「已 commit 已 push origin」，两处口径此前相反、以本行为错。

---

## 阶段 3｜P2 回流闭环（error-only，online 侧 + offline 配套）

> 目标：error 观察 → 聚类/去重 → 组装 → offline 拉取/激活 → 回归 → **结果推送（offline 推、online 判定）** → 人工处置 闭环。对应 detail §1.7 P2 行（analyzer 聚类/去重 → converter 信封+落库 → offline pull-API/回写/结果推送 → 前端回流页 → worker jobs → 端到端闭环验收）+ §6/§7。

- **T-3.1 聚类/去重与 cluster 生命周期**：error_cluster 归一化/聚类窗口（7d）/去重唯一索引（含 generation）；superseded 保留 passed 终态、复发重开代数 +1；only-count 不重复生成语义（§6.2）。**验证目标**：E-4（7d 内同键再现只 count+1 不重复建 link）、E-12（双实例同 offset 不重复建 cluster/link）通过；生命周期状态机单测。**[2026-09-09 P2-1 前半收口]：聚类归并写侧已实现（`analyzer/cluster.py` 共享内核 + `worker/cluster_job.py` 扫批 + worker/main `_cluster_loop` 15s + consumer root-late 内联归并 Fork B），backend 269 passed + cluster_probe 容器内真库 6/6 全绿（detail v1.15 / register P2-1）；E-4/E-12 端到端含 link 组装待 P2-2 assemble_job 落库后验。**
- **T-3.2 D19 信封组装（converter）**：evidence 区取数源 = error_cluster 快照 input 实文（脱敏 + 截断 ≤8K，不依赖 ES 回读）；assert 区含 no_fallback 断言 + **no_fallback_config 词表快照随 payload 下发**；组装质量下限自校验；快照缺 input 实文的残现场只计数不组装。**验证目标**：E-1（自动组装信封含 no_fallback_config → link=assembled → pull 可拉）、E-13（残 trace 快照缺 input → 只计数）通过；信封 schema 与 §7.1 逐字段对照。**[2026-09-09 P2-2 收口]：D19 组装已实现（`converter/no_fallback_cfg.py` resolve per-agent fallback_utterance + `converter/envelope.py` build_envelope/assemble_cluster 产 §7.1 逐字段信封 + `worker/assemble_job.py` 纯 60s 周期扫描组装（触发形态用户拍板）+ worker/main `_assemble_loop`），backend 287 passed + assemble_probe 容器内真库 8/8 全绿（含 A-3/E-13 快照缺只计数、A-4 空词表照建 words==[] fail-closed 载体、A-5 uk_link_current 二次组装 IntegrityError 双实例吸收）；link 生成 pipeline（open cluster → link assembled+pending）完整可用；E-1 端到端含 offline pull 待 P2-3 pull-API/ack 后验（detail v1.16 / register P2-2）。**
- **T-3.3 平台间契约（online 侧）**：pull-API（`offline_status=assembled` 拉取、`case_type` 白名单 v1 仅 `regression_error` + `schema_version`）；状态回写（draft/active/invalidated）+ **单错级结果接收**（v1.23 第 2/3 刀补：`POST /backflow/regression-results`，离线推、online 同事务判定，取代原「online 主动回查」）；ack 幂等（§7.3）；invalidated/rejected 重推展示 + admin requeue 复位 assembled（复用 payload_id）+ `assembled_ts` 刷新（§7.4）。**验证目标**：E-5（词表空 → 结构自检不通过 → offline 驳回 invalidated 回写；词条命中 → no_fallback fail）、E-6（admin requeue → 复位可拉）、E-15（ack 重放幂等）、E-22（requeue 刷新游标、增量 since_ts 重拉）通过。**[2026-09-09 P2-3 收口]：平台间契约已实现（`app/backflow/ack.py` pull 扫 + ack CAS 矩阵（含 R2 例外 gate link 现行 reason、R3 带态 400）→ `app/api/pull.py` /pull/payloads + /pull/ack（evaluator 预共享 secret Bearer，未配置 fail-closed）；`app/backflow/requeue.py` R-24 守卫复位 + invalidate + 批量（防抖 ≥5min 锚 = assembled_ts）→ `app/api/backflow.py` admin 三端点（require_admin）），backend 307 passed + pull_probe 容器内真库 HTTP 级 13/13 全绿（含 E-15 幂等 + 双 ack 交错、E-22 requeue 旧水位重拉可见、R2/R3 例外、viewer 403）；E-5/E-6/E-15/E-22 环 1 验（fake-offline HTTP 客户端走通状态机），E-6/E-22 集成复验待阶段 4 T-4.3（detail v1.17 / register P2-3）。** **[2026-09-16 补：requeue 守卫补 reason 门]**：`requeue_guard_errors` 此前**只看 offline_status / verify_status / cluster.status / 防抖**，不看 `link.invalidate_reason` ⇒ `offline_cap_gap` 的 link 可被人点 requeue。而**批量入口 `requeue_batch` 的候选 where 本就限 `online_content_gap`** ⇒ 同一语义两个入口、单点这处漏门（**前端 `linkCanRequeue` 复刻了同一漏判 ⇒ 按钮可见可点，非「只有 curl 能触发」**）。三个真实损失：①**假动作**（离线对 `offline_cap_gap` 只放 `ack_status ∈ {none,pending}` 重处理，这类行已 acked ⇒ 重推后必被跳过，admin 见 200 而零处理）；②**载荷分叉**（requeue 用现 cluster+现词表重渲染 `payload_json` 并刷新 `assembled_ts`，离线 inbox 仍是旧 `envelope_json`）；③**污染 R-7 可愈性计数**（`requeue_count` +1 ⇒ 前端把「从未被受理」读成「重推多次仍不行」）。**处置** = 守卫对 `offline_cap_gap` 一律拒（400 `ERR_CLUSTER_0003`，文案指向离线 §5.8 探测态自愈），前端同步不渲染按钮；**订正**：我此前称此坑「擦掉 online 侧 R2 例外判据 ⇒ 自愈永久失效」**不成立**——`_ACK_MATRIX['active']` 本就从 `("assembled","case_id")` 放行（`ack.py:41-44`），requeue 只是把 link 置回 assembled，功能上仍收 active；该句系**读单侧外推、未查矩阵全表**。验证：`test_backflow.py` 新增 2 条（cap_gap 拒 + 另两 reason 正对照），反事实短路 ⇒ **1 红 21 绿**；前端 spec 新增 2 条，反事实 ⇒ **1 红 40 绿**；后端全量 **482 passed**；前端该 spec **41 passed**；ruff 零新增。**未真机验**（无真机入口造 cap_gap link，本批不造数据）；detail §7.4/§9.4 已落字。**
- **T-3.4 人工处置状态机**：claim（必填 fix_version）→ 复核窗口 TTL → 回归 failed/超窗回退 open；置 fixed 需回归 passed 或 admin 复核（closed_by）；viewer 不单方 closed；reopen 流转；CAS 条件更新防竞态（§7.6）。**验证目标**：E-7（claim → **单错级结果接收并判定**（v1.23：offline 推 `POST /backflow/regression-results`，判定在端点内同事务）→ verify=passed → cluster fixed；同 run 他错仍红不阻塞）、E-8（TTL 超窗回退 open + conversion_record）通过。**[2026-09-09 P2-4 收口]：人工处置状态机 + 回查 verify 收口已实现**——claim.py 五端点全 CAS + conv 审计（claim fix_version 必填 + trim、claim_k 固化、TTL 14d；ignore/reopen/needs-review-resolve/fixed-review(admin)；viewer 不单方 closed；**ERR_CLUSTER_0002(409) 首用激活**）；verify.py 判定内核（环境/case 级 error_type 字面量表 R-19、route_verdict 判定映射 + R-15 截断优先、decide_k 相邻纯净 +1 R-17、judge_link 集成 uk_verify_run 幂等终态只读）；batches.py unclean 批 ensure_unclean_batch + resolve_batch（整批单事务 + R-9 语义）；~~offline_client.py 三读法 + `offline_base_url` 空停轮（复用 evaluator_service_secret Bearer）~~ **（v1.23 第 3 刀整删：判定数据源改结果推送载荷，online 零出站；`offline_base_url` 字段仅留 .env 兼容）**；claim_ttl_job（E-8）+ ~~recheck_job（E-7）~~ **rejudge_job（本地补判）** 各 60s；读面 3 GET 响应字段级钉死。backend 单测 **342 passed**（基线 307 + 35 test_backflow_claim）+ ruff 零新增；**claim_probe 容器内真库 HTTP 级 13/13 全绿**（C-3 E-7 verify_run_record×2 + fixed(auto_regression)、C-8 E-8 TTL 超窗回退、C-13 ~~recheck 编排~~ → 推送编排（v1.23：假 offline 读面改「直造 `verify_run_record` + 推送端点/`judge_link` 驱动」））；E-7/E-8 环 1 验、真机端到端（含单错级「同 run 他错仍红」）待阶段 4 T-4.4 环 2（detail v1.18 / register P2-4）。**
- **T-3.5 reentry 与终态守卫**：观察哨位 job（同键再现 → 新 cluster + 复发提示）；terminal 终态只读、迟到 run 结果只追加时间线（§7.5/§10.5）。**验证目标**：E-9（fixed 后同键再现 → 新 cluster + "线上仍复发"）、E-10（passed 后迟到结果不覆盖）通过。**[2026-09-09 P2-5 收口]：reentry 版本门控已实现**——`analyzer/cluster.py` 纯函数 `reentry_gate_allows`（B-5 等值 + 日期前缀门控：前缀相等仅完全等值放行、前缀不等按字符串序、任一侧非日期形态整体字面量等值、candidate None → False）+ `_merge_once` 接线（仅最高代 fixed ∧ fix_version 非空才咨询——inactive 终态 / UPDATE fixed 无 fix_version 无门控基础维持 P2-1 无条件开，S-3 零破坏；门控不过返新动作 "blocked" DB 零落（阻断可见性归 P2-6，**v1.20 定为后端读 MySQL `trace_judge_state` 保留窗现算**，推翻原「前端 ES 派生」）；过则建簇 gen+1 + conv(action="reentry", actor_user_id=None) 同 savepoint 落，E-12 twin 吸收回滚一并回滚 conv 不产孤儿，重查转 count 不重放门控）；载体 = 内联 cluster_job（用户拍板，不落独立 reentry_job）；E-10 终态只读补显式守卫 = `verify.judge_link` 入口 link 非 pending → no_progress（终态只读固化为 judge_link 局部不变量）。backend 单测 **352 passed**（基线 342 + 10 TestReentryGate 全分支矩阵）+ ruff 零新增；**cluster_probe 容器内真库 10/10 全绿**（S-7 E-9 reentry gen+1 + conv、S-8 同日不等值 blocked、S-9 早于 fix blocked、S-10 无门控基础回归护栏）；**claim_probe 14/14 全绿**（含 **C-14 E-10** 迟到 run 不覆写不追加）；E-9/E-10 环 1 验、真机端到端（E-9 线上复发 / E-10 迟到结果）待阶段 4 T-4.4 环 2（detail v1.19 / register P2-5）。**
- **T-3.6 worker jobs 集**：judge_scan_job/cluster_job/assemble_job/claim_ttl_job/**rejudge_job**/rollup_job（**v1.23 第 3/4 刀后 job 数 = 6**；`recheck_job` 已整删、`reentry_job` **从未存在**——同键再现内联 cluster_job；详见 `worker/__init__.py` docstring 与 detail §1.3）；分布式单飞（CAS 锁）；requeue 防抖 ≥5min。**验证目标**：时间驱动 job 单飞无重复执行（detail §1.3/§14.4 写侧判据）；job 失败退避 + 自监控计数可见。**[2026-09-09 P2-5 注]：`reentry_job` 不入本集**——用户拍板并归 T-3.5 **内联既有 cluster_job**（同键再现归并走 cluster_job 主链 + consumer root-late 内联同内核，门控评估 + conv(action="reentry") 随簇同 savepoint 落，独立 job 会双消费冲突），不落独立 reentry_job.py 文件。本集其余项（分布式单飞 CAS 锁 / 失败退避自监控 / requeue 防抖 ≥5min）已由 P2-3（requeue R-24 防抖锚 assembled_ts）/ P2-4（claim_ttl 60s + run→sleep 异常自愈同 judge/cluster）部分覆盖，整批收口留后续批次。** **[2026-09-10 T-3.6 结清（逐 job 核查，零新代码）]**：三项「剩余」的**代码全部已落地**——单飞 CAS（`judge_scan_job.py:103-112` `WHERE judged=0`+rowcount 判命中 / `cluster_job.py:79-89` `processed` CAS+`uk_cluster_dedup` 吸收 / `assemble_job.py:31-34,63-72` 候选排除 pending+`uk_link_*` savepoint 吸收 / `claim_ttl_job.py:63-74` 状态+到期 CAS）、失败退避（`worker/main.py:111-188` 六 loop 统一 `except → logger.exception + 定周期 sleep` 自愈，形态=定间隔重试非指数退避）、requeue 防抖（`requeue.py:29` `REQUEUE_DEBOUNCE_MINUTES=5`，守卫+CAS 落库双校验、锚 `assembled_ts`），且各自均有单测/探针（`test_worker_judge_scan` / `test_worker_cluster` / `test_converter_envelope` / `test_backflow_claim`；cluster_probe S-1~S-13 / assemble_probe A-5 / claim_probe C-8 / pull_probe P-11·P-12）。**未做项均不属本集**：① 双实例单飞并发验证 → **T-4.5**（本条原文即已排除）；② rollup 真实 ES 集成探针 → 集成阶段（`test_rollup.py` docstring 自陈；rollup 为确定性 `_id` 覆写幂等设计、不适用锁）。**「自监控计数」按 detail §14.4 写侧判据不计入本集**——该判据只要求「各时间驱动 job 单飞无重复执行」+「requeue 防抖 ≥5min 生效」，无 job 自监控项；worker 侧确无失败计数器/heartbeat/metrics 端点属实，若后续要补**须另行立 T 项并先定可见面挂靠**（consumer 侧 `DroppedCounter`/heartbeat `dropped` 属**事件丢弃**计数、与 job 失败无关，不可挪用）。**另随本条目收口修正 detail §1.3 周期口径漂移**（cluster 15s / claim_ttl 60s / ~~recheck 60s~~ → **rejudge 60s**（v1.23 第 3/4 刀：recheck 整删、rejudge 承接补判）/ reentry 撤销独立周期 = detail v1.22 + v1.23）。**
- **T-3.7 前端回流页**：错误聚类列表/详情；offline_status/verify_status 展示文案（assembled"待 offline 拉取"/draft"待 offline 确认"/invalidated 重推状态）；人工操作（ignore/claim/needs_review 处置/fixed 复核/case 级 invalidate 仅未激活）；claim 复核窗倒计时；二期入口（弃留墙/quality）整条隐藏（§9.3/§9.4）。**验证目标**：viewer/admin 操作集与 detail §9.4 一致；invalidated 文案含"仍在观察、窗口内不自动重生成、可重推、长期停留找平台"。**[2026-09-10 P2-6 收口]：前端回流页已实现**——「回流看板」第六个一级菜单 `/backflow` + 独立路由详情 `/backflow/clusters/:clusterId`（先例 TraceDetail 壳，非抽屉）：列表页 overview 卡（cluster 状态分布 / link verify 分布 / 待修复集本地近似 + 标注 / by_agent）+ 筛选（agent·interface·layer·status·watch）+ cluster 表（状态 pill / error_type / input_hash / **代表 trace `first_trace_id` 跳 trace 详情** / count / generation / first·latest ts / fix_version）+ 分页；详情页 links 表 + verify_runs 版本×pass/fail 时间线 + conversions 中文审计时间线 + 人工操作区（按 §9.4 门控置灰）+ claim 复核窗倒计时（1s tick + 45s 可见轮询）+ input_truncated 警示 + 未决 unclean 批挂起徽标 + 「处置整批」+ **reentry_observe 复发 caption**；admin-only（fixed-review / link invalidate / requeue）前端按 `role==='admin'` 隐藏 + 后端 require_admin 二次鉴权；**二期入口（弃留墙/quality）整条隐藏不渲染**；文案集中 `frontend/src/backflowLabels.ts`（offline_status/verify_status/reason 逐字 + cluster 状态中文 + conversion action 中文 + reentryCaption）。**blocked 复发读面实现形态修正**：前端无 ES 通道、ES 无 judged/root_input_hash/candidate 语义 → 改**后端读 MySQL `trace_judge_state` 保留窗现算**（`app/backflow/recurrence.py`，detail 响应 `reentry_observe {count,latest_version,since_ts,mode}`；claim R-5 版本预检做全 best-effort）。backend 单测 **385 passed**（基线 352 + 33 test_backflow_recurrence）+ 本批 diff ruff 零新增；前端 vue-tsc --noEmit + vite build 绿；环 1 验（假 offline/online 数据），真机浏览器 e2e 待阶段 4（detail v1.20 / register P2-6）。**
- **T-3.8 offline 判定语义改造（Task #4-② 驱动）——offline 配套轨批 2 在平台阶段表的落点**：本项 = **offline 配套轨批 2 的汇合核对**。批 1（契约 + 收单/结构自检/激活/回写 + pull job，判定用 stub/fixture 通管道）已在联调环 0/环 1 先行拉通双端；批 2 在 offline 仓随 **Task #4-② 方案定稿即启动**，本任务项记录其范围与验收口径。批 2 范围：v1 `regression_error` 子集**判定语义**——判定器（executor 对 error 现场复现的技术判定）+ verifier no_fallback（以 payload 内词表快照为准、空表 fail-closed）+ rejected 保留重扫自愈回写收尾；换真判定后回归不碰契约。**验证目标**：按 Task #4 方案定义；覆盖 E-1~E-22 中 offline 侧依赖项 + 回归 run 单错级口径（run_results.pass_fail 合成 = executor ∧ no_fallback）；批 1 已绿的对端用例在批 2 后重跑不回归。
- **T-3.9 online 侧 P2 门**（**验收门，非实现批**）：§11 #5 相关（该条 =「judge 放行开关」，属**二期、v1 不实装**，此处仅登记相关性，非一期待办）+ §14.3 P2 行（E-1~E-29 通过 + §11.5 维度 3 开放验收 checklist #4/#8/#10 + 兜底吸收埋点前提用例 S-4 真实 agent 复验 + 词表覆盖度对 §13.1 盘点）的 **online 部分先行全绿**。**本批先行范围**：E-16（judge_scan 到期补判、重复到期不重判）online 侧；E-18~E-21 的 online 侧可先行部分（consumer 停拉退避不提交空推进 / 判定源 = MySQL 判定态故 ES 不可用不影响回流 / MySQL 写失败不提交 offset + 退避自监控）——**不注入故障**，故障注入本体留 T-4.7。**不在本批**：E-23~E-29 环 2（阶段 4）；E-18~E-21 真机故障注入（T-4.7）；E-16 双实例单飞（T-4.5）；offline 侧全部（T-3.8）。**防漂移**：P2-N 编号**止于 P2-6**（P2-1~P2-6 = T-3.1~T-3.7 回流实现批，一一对位）；阶段 3 剩余项一律用 T 编号引用，**不再新编 P2-N**（detail v1.20 曾误写「P2-7 gate 门」，已撤销）。**闭环（2026-09-10）**：本验收门已实跑（A1 回归 / A2 端到端 / A3 checklist / A4 词表链路 / A5 报告），**查出 1 个阻塞项 = 兜底吸收误回流**（`request ok + llm_call error` 误产 L1 候选回流），**由 T-3.10 修复并验证通过**——本条目保持「验收门」定性、不转为实现批；其两项挂账（E-2/E-3 端到端需真实 agent、E-14 需 Kafka 注入）留集成阶段复验，不在此结清。
- **T-3.10 验收阻塞项修正：兜底吸收误回流判定语义 + E-17 补探针**（由 T-3.9 挖出；**修正批，不新编 P2-N**；detail v1.21 / register 附录 A T-3.10 行）：① **判定语义修正**——`analyzer/classify._collect_candidates` 加门控：`root_status == "ok"`（= request 成功返回答，子节点错误已被业务吸收）时**不取子节点候选**（**刻意不叠加 `root_ok`**——`root_status` 全仓唯一写点 = `consumer/state.py` 与 `root_ok` **同一条语句**置位 → 合取项恒真可证冗余；留单条件只押「root 终态」一个语义，不与派生布尔标志的将来定义漂移耦合），对齐 §6.1「兜底吸收现场不产 L1/L2 候选（L3 二期）」；门控落 `_collect_candidates` **局部**而非 `decide()` 前置（当前唯一生产调用方即 `decide()`，未来新增调用方自动继承不变量）。**判据刻意取 `root_status` 而非「`root_error_type` 为空」**——timeout root 按 §6.1 step5 同样不带 `error_type`，用后者会连带切掉 timeout 分支（未讨论的第二处行为变更）；残 trace（`root_status` 恒 NULL）与门控天然不相交。② **已知未决歧义 = 显式标注、本批不触碰**——step5（timeout 事件自身不产候选）对「timeout root 的子节点 error 是否参与」沉默，step4 又写 L2 用「request **或**子节点」；两条互斥原文未消解，**timeout root 的子节点候选维持改动前既有行为**（仍参与），待真实流量再定。③ **E-17 补探针 C-15**（原零覆盖）——reopen 后改 fix_version 再 claim → **新 link + 新 payload_id**（非复用旧 link）→ 新版本回归 passed → fixed，且旧 failed 时间线保留不覆写。**验证**：backend 单测 **388 passed**（385 + 3，既有用例零调整）+ 原缺陷复现点由 L1 归零为 none + claim_probe **15/15**（cluster 10/assemble 8/pull 13 零回归）+ 本窗口 diff ruff 零新增。**不在本批**：timeout 交界歧义（仅标注）、`root_late_*` 路径（零交集）、§6.1 step4 与 §2.5 L329 的原文歧义本身。
- **T-3.11 v1.23 文档↔代码反查遗留项登记**（**登记项，非实现批**；来源 = 2026-09-11 对 detail §8.1~§8.6 可证伪断言逐条反查，共 79 条 → 吻合 51 / 不符 6 / 悬空 18 / **代码有但文档无 4**；已处置者落 detail 就地订正注，本条目登记**未处置的四项**（①② 已于 2026-09-11 结清，现余两项）：
  - **① `interface=` 过滤（文档承诺、代码未交付）**：detail §8.2 曾写「支持 `interface=` 过滤」（与 `metrics.py` 新增同一笔 `7dc95a6` 写入），但端点 / loader / ES body 三层均无 `interface` 参、T-2.2 从未列入、前端 `metrics.ts` 未消费、测试零用例。**现状** = detail 已划删 + 作废注。**已结清（2026-09-11 用户裁定：永久不做）**：detail §8.2 该行已改「已裁定不做」，本项从四项中移除。**判据 = 从未实现 ⇒ 不存在会被本裁定破坏的调用方**（任何调用方即便传了该参拿到的也是未过滤结果，与今日逐字节相同）；**但不能说「无任何外部调用方」**——不能排除已有人按旧文档传了该参、一直以为在被过滤（实际拿到未过滤数据），该情形不可追溯、且与「删不删」无关；决策仍退化为纯产品取舍；且本端点返回**本就按 `interface` 分组**，过滤只增筛选便利、不增信息量。**归属 = 阶段 2（T-2.2），已了结**。
  - **② requeue 批量「可愈性标注」（已拍板设计被静默降级）**：register R-7（approved 2026-09-07）拍板「批量端点 **+ 可愈性标注 + 不愈行禁勾 / 强确认门控**」，并**显式否决**备选 B「仅批量端点不加标注」；实现（`de81255`）只落批量端点，`requeue.py` docstring 把可愈性改写成机制描述盖住缺口。**失败模式（本组唯一有实害者）** = admin 面对成批 `online_content_gap` invalidated 行被**无差别批量复位**，「版本不识别」类被反复误推——**正是 register 否决备选 B 的理由**。**现状** = detail 已划删 + 作废注 + `requeue.py` 注释标「与 register R-7 不符」。**已结清（2026-09-11 用户裁定：改判据）**——原判据经查**不成立**（**措辞更正：不是「不可实现」**，改判理由是**「原判据要区分的对象在跨端链路上不可达」**——2026-09-11 重估终版，此前「成本/收益不划算」的写法已作废）：① **「不愈类」到不了（2026-09-11 重估终版，前两版均误）**——`version_drift` 是**死分支**：其触发条件被 **online pull 层上游**挡死（版本不匹配 → 400 `ERR_PULL_0002` 拒单，`pull.py:88`，实测 `test_backflow.py:237`；`case_type` 非白名单 → 返空集，`pull.py:94`），offline 的声明与校验均为同一常量 `"1.0"`（offline `solution_detail.md:292`/`:309`）⇒ 收不到会触发它的信封 ⇒ **实害不成立**；② **「扩词表」腿作废**——ack 线路**有 `reason` 槽**（`api/pull.py:63`），值域卡在 3 粗码（`backflow/ack.py:25`），细分码须双端契约扩展 = **欠债、非不可能**；③ 失败模式**「无调用方」，非「关闭」（⚠️ 措辞订正）**——前端零批量入口已逐面取证为真（前端零引用 / offline 无 backflow 模块 / 两仓脚本零命中；生产代码唯一调用点 = 端点自身）；**⚠️ 但端点此刻是活的**，`require_admin` **只挡非 admin**，**admin 持 token 可 curl 直接触发**——**UI 是便利性问题、非可达性问题**。改用**行为数据判据**（`requeue_count` = 该 link 历史重推次数，口径**不含本次**），范围 = **单 link 路径**：`requeue_link` 返回该值（查在 `session.add` **之前**，`requeue.py:163`），读面 `_cluster_links`/`get_cluster_detail` **一次 `GROUP BY link_id` 成批取**（防 N+1），前端详情页 ≥`SUSPECT_REQUEUE_THRESHOLD`(=2) 转**双次强确认**。**可愈性「意图」（防 admin 反复无效重推）保留，判据替换**——但**门控强度实为降档**：原设计 = 不愈行**默认禁勾**（default-deny，覆盖批量勾选）；本实现 = 默认可点 + ≥阈值双确认（default-allow + warn），**仅单 link**。**已知局限（勿当已解决）**：① `requeue_count` **只在重推失败时累积**（成功即自愈、不进计数），区分不了「不可自愈」与「admin 手快、现场未补完就推」，**现有数据无法证伪**；② 口径不含本次 ⇒ **第 3 次**重推才触发。register **备选 C**（定时自动 requeue job）**仍否决**。**遗留两项（勿当已解决）**：**① 阈值 2 无数据支撑**——须按真实 `conversion_record` 分布调，且前端/后端**双份硬编码常量须同步改**；**② 批量路径已裁定不做、本条结清（2026-09-11）**——**两条实质理由**：㈠ 要防的**实害已证不可达**（`version_drift` 死分支 ⇒ 门控**没有要防的对象**，同 ①）；㈡ 残留的**后端半边无消费者**（端点唯一调用方 = curl 的 admin）。**⚠️ 当期事实、非理由**：前端批量重推入口整块不存在——「不愈行禁勾」是勾选框交互，**无框可禁**；**此系现状描述，非不可实现性论证**（UI 不存在是因为没人做，不是因为做不了）。**本裁定基于当期条件、日后真接批量入口时重开。****⚠️ 取证订正**：原文写「不可按 link 归因」**不准确**——成功行经 `requeue_link` **已逐行写带 `link_id` 的 conv**（`requeue.py:164-176`），`link_id=None` 聚合行**只汇总 skipped、且截前 8 条**（`requeue.py:237-256`）⇒ 真实缺口仅「skipped 行无逐行持久审计」，不足以支撑做。**与备选 B 的关系**：本裁定**实质采纳当年（2026-09-07）被否决的备选 B**，推翻依据 = 当年否决它的前提（实害真实）**已不成立**。**日后真接批量入口时重开本条**。register R-7 改判记录 + detail §7.4/§8.4/§9.3 三处划删注均已同步为「已裁定不做」——交付落在单 link 路径，勿误读为批量已做）。**归属 = 阶段 3（T-3.3），已了结**。
  - **③ 型 D 4 条（代码有、文档无；即反查分类中的「代码有但文档无 4」）**：~~`status` / `watch` 实有 4 值而文档写 2；`result_overdue` / `result_gap_suspected` 两个读面字段未进文档；logout body 契约未文档化；`/traces` total 去重口径未文档化~~。**已取证并结清（2026-09-14）**——逐条核对结果（**原登记摘要不可直接引用，两条与实际不符**）：
    - **`status` 半边 = 登记不实**：代码 `backflow.py:490` `Literal["open","claim","fixed","inactive","needs_review"]`（**5 值**）与 `solution_detail.md` §8.4 逐字相同 ⇒ **双侧一致，无需改**（原写「实有 4 值」把两个参数合并计数，本身不准）。
    - **`watch` 半边 = 确有漏**：代码 `backflow.py:491` `Literal["assembled","draft","active","invalidated"]`（**4 值**）vs 文档写「`watch=assembled/draft`」（**2 值**）⇒ **已补为四值全枚举**，落 `solution_detail.md` §8.4 就地订正注 + **v1.27**。
    - **`result_overdue` / `result_gap_suspected` 半边 = 远超「文档滞后」**：`result_gap_suspected` **两侧齐全**（§9.2/§8.4 有语义；前端 `types.ts:308` + `DetailView.vue:328` + 单测）；`result_overdue` **文档已写语义**（§8.4 / §9.3 状态文案「回查结果未达（疑似 offline 停摆），人工核查」）而**前端零消费**（`grep -rn "overdue" frontend/src/` **零命中**：无类型、无渲染、无单测）⇒ **这不是笔误，是呈现面缺失**，已**另立** `docs/integration-report.md` §6 **F-18**（同 F-13 家族；**入乙类、阶段 4 不补实现**），**前端面挂本条所属的 T-4.11 残留**。
    - **logout body 契约 / `/traces` total cardinality 两条**：**已于 2026-09-11（`105cd3e`）补毕**——本条登记当时未回填。
    - **教训**：型 D 的「代码有、文档无」有**三种不同成因**（文档笔误 / 文档缺字段名 / **实现缺呈现面**），**处置各不相同**；按摘要统一判「补文档即可」会把第三种记成笔误。同 [[existence-is-not-reachability]] 一族：**不核原文与实际对象，摘要本身就会骗人**。
  - **④ O-8 的 offline 侧实施要求无兜底（本组唯一指向对面仓者）**：detail §12.2 **O-8**（2026-09-11 新增）登记 cap 截断归因能力净损失（R-4 / R-16 随只读面整组作废），并把「`case_truncated` 本地诚实诊断 + 告警」定为 **offline 侧实施要求**；但该要求**无 T 项、无验收用例、无测试**——若 offline 侧实现推送时丢掉，**无人会发现**，届时净损失从「online 看不见」变成「两侧都看不见」。**待办 = 在 offline `error-backflow-task.md` 立一条验收项**；**offline 仓冻结中，须待解冻**（2026-09-11 用户裁定：本轮不动 offline，登记为待办）。本仓仅保留交叉指针。
  - **边界**：两项（③④）**均不阻塞**阶段 3/4 现有出口；③ 属登记、④ 待 offline 解冻。**② 已于 2026-09-11 结清（见上）**——其可愈性「意图」已以行为数据判据在**单 link 路径**兑现；**批量路径标注已于 2026-09-11 裁定不做、本条结清**（见上，**两条实质理由 = 实害不可达 / 残留后端无消费者**；「门控无 UI 可落」系**当期事实、非理由**）。**P2-N 编号仍止于 P2-6**，本条为登记项不新编 P2-N。

- **T-3.12 系统管理面（admin）补实现 —— 阶段 3 欠债追补**（**2026-09-14 立**；来源 = 阶段 4 登记核对 #214，登记见 `docs/integration-report.md` §6 **F-19**）：**admin 管理面（Agent 与接口字典 / dict_config 配置 / 用户管理）在权威文档中是一期承诺，但全仓零实现、此前零 T 项跟踪。**
  - **权威依据（决定「欠债」而非「超承诺」）**：`solution.md` §12.1 逐字「页面归属阶段：……回流看板与系统管理（**P2**；**Agent/用户管理随 P0/P1 先行**）」，且 admin 权限范围明列「**Agent/接口字典**（llm 标记补标、归一化核对）、**dict_config 配置**、正文开关、**用户管理**」。P2 ↔ 阶段 3（本文件阶段总览映射）。
  - **实现现状（双向核对，非只信订正注）**：`app/api/router.py` 只挂 auth/traces/metrics/backflow/pull，**无 admin 路由**（该文件逐字写「clusters（§8.5）留空待后续阶段」）；detail §8.5/§8.6 两节自 v1.23 反查起已带「**本节整节未实现**」订正注。⚠️ **勿与 §8.3 混淆**：`metrics.py` 的 `/interfaces`、`/agents` 属指标面，**不是** §8.5 的 admin 端点。
  - **范围 = detail §8.5 七端点 + §8.6 三组端点**：`GET /agents`、`POST /agents/{id}/toggle`、`GET /agents/{id}/interfaces`、`PUT /interfaces/{id}`、`GET /agents/{id}/credential`（**已落地，2026-09-14**）、`POST /agents/{id}/credential/rotate`（**整条下移 T-5.3**，见下行）、`GET /agents/{id}/health`（**已落地**）；`GET /configs`、`PUT /configs`、`GET|POST /users`、`PUT /users/{id}`；以及 ~~**§8.5.1 疑似漏标自动补标**~~（`llm_suspect` 观察窗，`grep` 全后端**零命中**）——⚠️ **2026-09-14 裁定：此项 v1 不做**（见本条目批 2d 回填），**不在本条目范围内**。
  - **连带项（比两节本身大）**：① §8.9 `ERR_CONFIG_0001` **无抛出点**（admin 写入面缺失）；② §9.2 三个 admin 页面（`/admin/agents`、`/admin/configs`、`/admin/users`）**无数据源**（与 T-4.11「菜单按角色渲染」同源）；③ **正文开关配置入口**缺失——`body_search` 只作为**读侧参数**存在（`trace.py:109`），无写侧入口；④ `agent_credential` **表结构在、无执行逻辑**（`models/agent.py:79`）。
  - **⑤ 词表写入面（2026-09-14 由 T-5.4 追补登记；证据 = `docs/ops-manual.md` §2 + `docs/integration-report.md` §6 F-23）**：§8.6 `PUT /configs` 落地时，**`fallback_utterance`（D19 `wordlist_version` 的载体）必须一并实现「写入 + `version` 自增 + 审计」三项**——现状是**三项全无**（`converter/no_fallback_cfg.py:4-5` 与 `models/config.py:23-24` 的「变更 +1、admin-only」**均为注释**，无对应实现；`deps.py:44-47` 的 `require_admin` **无任何路由用于 admin 系统管理面**（⚠️ 2026-09-14 订正：原写「无任何路由使用」**是错的**——该依赖已被 **4 个 backflow admin 端点**在用：`api/backflow.py:776`/`:796`/`:820`/`:846`；把「没有 admin 写面」外推成了「依赖没被用」））。**⚠️ 为何单列**：只做端点会得到「能改但 version 不动、审计不落」的半成品，而 **version 是 D19 信封的组成部分** ⇒ 会静默污染下游判定语义；过渡期已因此**建议避免改词表**（见 T-5.4 回填）。
  - **与 T-5.3 的边界（防双记）**：T-4.10 已把「**凭证轮换的执行动作**」下移 T-5.3（上线门/安全边界）；本条立的是**端点与 UI 的实现**，**不重复登记执行动作**。
  - **⚠️ 三条显式声明（不改写已发出的结论）**：① **不追认推翻阶段 3 出口**——阶段 3 出口（下条）**已发出且仍有效**，本条是**事后发现的欠债追补**，性质同「回退对应阶段修复」（见阶段 4 抬头「发现缺陷回退对应阶段」）；② **阶段 4 出口不因本条挂起**；③ 编号依据 = 阶段 3 编号止于 `T-3.11`，顺位无冲突（**不新开阶段号**，避免扩展项目范围）。
  - **验收目标**：§8.5/§8.6 端点全绿（含 admin-only 二次鉴权 + **吊销即时生效**）；§9.2 三个 admin 页面数据源可用、菜单按角色渲染；`ERR_CONFIG_0001` 有抛出点；写侧配置变更留审计（`config_key` 粒度 + 旧/新值摘要，§13.5）；**授权与轮换的执行面按 T-5.3 的口径另行复验**。
  - **状态（2026-09-14 更新）**：**批 1（§8.6 配置 + 用户）已实现并验收完毕**（单测 478 passed / ruff 全绿 / 真库探针 31-31 PASS / 前端 type-check + 133 单测 / **浏览器 e2e 双账号**）；**§8.5.1 自动补标仍未开工**（详见下方批 2a-1 / 2a-2 / 2b 回填）。
    - ⚠️ **2026-09-14 最新**：§8.5 **整节已撤除**（用户拍板「过度设计」）⇒ 本条 `admin` 面的现状 = **只剩 §8.6 两面（configs / users）**，§8.5 全部代码/测试/页面/类型已删。见下方「撤除回填」。**⚠️ 范围订正（2026-09-14，批 2b 开工前取证）**：原写的「凭证**两端点**」**只剩一端点**——`GET /agents/{id}/credential` **已落地**；`POST .../credential/rotate` **整条下移 T-5.3**（三个执行动作全在 infra、新口令无来源，见批 2b 回填），**不记为本条欠债**。
  - **⚠️ 吊销机制订正（2026-09-14 实测）**：本条原文与 detail §8.6/§13.2 写的「禁用即吊销会话，**token version+1**」**与实现不符**——`user` 表**无 `token_version` 列**，且 `api/auth.py:4-8` 逐字「**不做 token-version 列迁移**」；实机机制 = **`user.status=0` + 撤销该用户全部未撤销 `user_session`（`revoked_at` 落时）**（T-4.10/F-8 已实测吊销即时生效）。**本批按既有机制实现，未加列去迁就文字**；`solution_detail.md` §8.6/§13.2/§13.5 三处措辞已同步订正。
  - **交付回填 · 批 1（2026-09-14；证据 = `backend/app/api/admin.py` + `tests/test_api_admin.py` + `tests/integration/admin_probe.py`）**：
    - ✅ **§8.6 端点**（`api/admin.py`，全部 `AdminUser` 依赖）：`GET /admin/configs?agent=`、`PUT /admin/configs`、`GET /admin/users`、`POST /admin/users`、`PUT /admin/users/{id}`。
    - ✅ **⑤ 词表三项**（写入面 / `version` 自增 / 审计）**随本批落地**：`fallback_utterance` 走同一写入路径不特判，其 `version` 即 D19 `wordlist_version`（探针 A-6b 实测「组装读侧读到新 version」）。
    - ✅ **`ERR_CONFIG_0001` 首次有抛出点**（非法 key / 值形状 / 越作用域 / agent 不存在 / 用户名重复；http=400；403 分支由 `ERR_AUTH_0002` 承担）。
    - ✅ **配置变更审计**：`conversion_record(action="config_change", cluster_id=NULL, detail=旧→新摘要)`；`detail` 超 1024 时**显式标注截断**（探针 A-3e + 单测实测）。
    - ⚠️ **② 三个 admin 页面：只做了 2 个**——`/admin/configs`、`/admin/users` 已落地并接入菜单（按角色渲染）；**`/admin/agents` 属 §8.5，未做**（故「三个」仍差一个）。
      - ⚠️ **2026-09-14 更新**：`/admin/agents` 曾于同日随批 2a-1 补齐、后**又随 §8.5 整节撤除**（见本条目「撤除回填」）⇒ **admin 页面就此定为两页，不再补第三个**。
    - ⚠️ **§13.5「审计可按 key/操作人筛选」未实现**：v1 只做 `action` + `actor_user_id` + 时间窗（用户 2026-09-14 拍板），**按 `config_key` 筛选登记为已知限制**（`detail` 为自由文本无索引，要做需加列 = 破零 DDL）。
    - ⚠️ **审计无读面**：配置变更行已落库，但**界面看不到**（跨 cluster 检索/导出归 `T-3.13`）⇒ 浏览器侧只能验「写入成功 + version 自增」，审计**只有 DB 证据**。
    - ⚠️ **未做**：③ 正文开关配置入口；④ `agent_credential` 轮换执行面（归 T-5.3）；§8.5 全部；§8.5.1 自动补标（需动消费主链路）。
      - ⚠️ **2026-09-14 更新**：「§8.5 全部」这句**字面重新成立**——§8.5 曾整节落地（批 2a-1/2a-2/2b，见下三处回填），同日**经用户拍板整节撤除**。⇒ 「未做」的性质已从**欠债**变为**显式裁定不做**，**不再是待办**。
    - ✅ **浏览器 e2e（2026-09-14 实测；`http://localhost:18080`，admin + 真 viewer 双账号）**：① admin 在 `/admin/configs` 写入后 UI 显示「`claim_ttl_days` 已保存：**version → 1**」且更新人变 `admin`——**不停在 UI 自述，另做 DB 取证**：审计行 `id=3154 action=config_change actor_user_id=1 cluster_id=NULL detail="global 配置 claim_ttl_days v0→1：null → 14"`（utf8mb4 复读，中文完整）；② admin 在 `/admin/users` 建号成功、列表即时刷新、出参不含口令；③ **退出后用真 viewer 账号登录**（**不是** localStorage 角色覆盖）⇒ 菜单两项**消失**、**直连 `/admin/configs` 得后端 403**（页面显示 `ERR_AUTH_0002 角色不足（需要 admin）`）⇒ **F-20 的「viewer 边界」在 UI 层也补齐**（探针层已用真账号闭合）；④ 测试账号 `e2e-viewer` **已删除**（含其 `user_session`，库内回到只剩 `admin`），配置行**保留**（值 = seed 默认，读侧等价）。
    - ⚠️ **顺带实测的部署语义（已同步写入 `docs/ops-manual.md` §2，防复踩）**：后端是**热挂载** ⇒ **新增模块（如 `api/admin.py`）必须 `docker compose restart backend`**，否则路由在运行进程里不存在、表现为**页面接口 404**（本批首访即撞上）；前端是**构建产物** ⇒ **必须 `docker compose build frontend && docker compose up -d frontend`**，**重启容器无用**（镜像里仍是旧 dist）。

  - **交付回填 · 批 2a-1（2026-09-14；证据 = `backend/app/api/admin.py` §8.5 段 + `tests/test_api_admin_agents.py` + `tests/integration/admin_agents_probe.py` + `frontend/src/views/AdminAgentsView.vue`）**：
    - ✅ **§8.5 字典面四端点**：`GET /admin/agents`（读 **MySQL `agent` 表**并带 `interface_count`——**不是** §8.3 的 ES 观测面；探针判据 = **含 `enable=0` 的 agent**，ES 面永远给不出）、`POST /admin/agents/{id}/toggle`（**[裁定]** 无 body、翻转 `enable`）、`GET /admin/agents/{id}/interfaces`（上限 500 + `truncated`）、`PUT /interfaces/{id}`。
    - ✅ **§9.2 三个 admin 页面齐**：`/admin/agents` 落地并接入菜单（按角色渲染）——批 1「三个只做了 2 个」的缺口**闭合**。
    - ✅ **两类新审计 action**：`agent_toggle` / `interface_dict_change`（`cluster_id=NULL`、`actor_user_id` 取真 id）；浏览器 e2e 已做 DB 取证（两条）。
    - **[裁定] 三条**（文档未定义处；按实机实现、不新造契约面）：① `llm_source` 只接受 `manual`；② `llm=1` 连带清 `llm_suspect`（**疑似漏标由人工确认解除**）；③ **不支持改 `interface` 串**——detail §8.5 入参本无该字段，且它是唯一键列 `uk_interface(agent_id, interface)`；探针 G-5f 实测「多余 `interface` 字段被忽略、串不变」。
    - ✅ **验证（独立验收面 = MySQL，**可全量验**）**：单测 **499 passed**（基线 478 + 新增 21）/ ruff 全绿 / **真库探针 20-20 PASS** / 前端 type-check + **133 单测** / **浏览器 e2e**（`/admin/agents` 渲染 + 启停 + 接口补标；用一次性探针账号，跑完连账号一起清理）。
    - ⚠️ **未覆盖（如实标注，不算通过）**：`_INTERFACE_MAX=500` 的**截断分支**未做容量型取证（需造 501 行）；`health` 端点不在本批（独立验证面 = ES 心跳）。
    - ⚠️ **顺带查出并处置的两处「替身 / 文档」不符**（`tests/_fakes.py`）：① `FakeAsyncSession.get()` 此前对 `User`/`UserSession` 以外的模型**恒返回 None**（已补 registry 主键查找，语义与真库同）；② 其自身注释称「列级 select 返回该列属性」，**实测仍返回整行**（2026-09-14）——故 `_interface_counts` 按整行计数，`select(Interface.agent_id)` 那种写法只在替身下崩。
    - ⚠️ **页面现状**：`.tbl`/`.err`/`.ok`/`.hint` 四个 class **在 `style.css` 中未定义**（批 1 两页同样如此，属全局占位现状）；本批**不补样式**（补会改动全站视觉），只登记。

  - **交付回填 · 批 2a-2（2026-09-14；证据 = `backend/app/api/admin.py` health 端点 + `backend/app/store/es.py` 心跳三函数 + `tests/test_api_admin_health.py` + `tests/integration/admin_health_probe.py` + `frontend/src/views/AdminAgentsView.vue` 展开行）**：
    - ✅ **§8.5 health 端点**：`GET /admin/agents/{id}/health` → `AgentHealthOut`（`last_seen_ts`/`report_1min`/`report_5min`/`dropped`/`sdk_connected`）。读 **ES `node=heartbeat`**（与 §8.3 的 ES 流量面无涉）；时间窗**复用** `keyword_search_days`（不新造配置键）。
    - ✅ **展开行内的 health 卡**：`/admin/agents` 展开时与接口字典**并行**拉取（`allSettled`——两个数据源各报各的错，ES 超时不吞掉字典）；`last_seen_ts=null` 显示「查询窗内无心跳上报」。
    - 🔴 **开工即查出两处真缺陷（此前「构件已写好」是假象）**：① `fetch_heartbeats` 取 `_hits_result(...).get("items")`，而该函数返回的键是 `hits`（`es.py:197`）⇒ **恒返回空列表**（接上端点后表现为「所有 agent 都无心跳」）；② `summarize_heartbeats` 的 `dropped` 原设计为**窗内求和**，但心跳里的 `dropped` 是 consumer **进程内累计快照**（`consumer/main.py:87` 逐字「按 (agent, reason) 累加，心跳任务定期快照」）⇒ 求和 = 把同一个数重复相加。**两处均已修**。
    - ✅ **「快照 vs 求和」有真数据对照（探针 H-2b）**：`good-question` 窗内 500 条心跳，端点返回 `{agent_mismatch:2, mask:2, schema:2}`（= 最新一条快照）；**若按原设计求和会得 `{agent_mismatch:1410, mask:598, schema:2628, es_fail:812}`**——差三个数量级。
    - ✅ **验证（独立验收面 = ES 心跳 + Kafka；本批可**近全量**验）**：单测 **512 passed**（基线 499 + 新增 13）/ ruff 全绿 / **真库真 ES 探针 12-12 PASS** / 前端 type-check + **133 单测**。
    - ✅ **探针覆盖了什么（含真链路）**：H-1 鉴权双证；H-2 与 ES **逐字段对齐**（`last_seen_ts` **等于** ES 最新 ts、`dropped` **等于**快照、`report_*` **等于** 真条数、`sdk_connected` 对齐 source 分布）；**H-3 走真 Kafka（`obs.selfmonitor`）造活心跳** → 端点见 `report_1min=1`、`last_seen_ts` = 发出的 ts、`sdk_connected=true`（**Kafka→consumer→ES→端点**全链）；H-4 空态；H-5 未知 id → 400。现场零残留（MySQL `admhb-%` 0 行 / ES `admhb-` 0 doc）。
    - ⚠️ **原计划的「向真实 agent 发脏 JSON 造 form A 心跳」未做**（用户 2026-09-14 批准的 A 方案中该项**改由存量真实心跳承担**）：consumer 的消费 loop 在**启动时**按 `_enabled_agents()` 固定建立（`consumer/main.py:123-127`），新插入的 agent 不会被消费 ⇒ 要现造只能打既有 4 个真实 agent，那会**污染它们的进程内 dropped 计数**（该计数是快照语义，一次污染会改掉此后所有心跳的读数）。故 form A 分支由 H-2 用**存量真实心跳**覆盖同一批字段；「form A 能被触发」属 consumer 机制面，已由 `d6_probe.s2` 的 `hb_visible()` 覆盖。
    - ⚠️ **未覆盖（如实标注，不算通过）**：`_HEALTH_SIZE=500` 的**截断分支**（需造 501 条心跳）——容量型未做；「`keyword_search_days` 配置值**真能改窗**」未在单测覆盖（替身 `execute` 路径的列级 select 返回整行 ⇒ `get_global_int` 恒回退默认；要修须改共享替身，**不属本批**）。
    - ⚠️ **`spool_pending` 不返回（裁定 4）**：detail §3.6（`:432`）心跳 body 定义了该字段，但**双端都无写入方**（平台侧心跳 doc 只有 `{node, agent, ts, dropped, source}`；SDK 侧 grep 零命中，2026-09-14 取证）——照批 1「按实机实现、订正文字、不为契约造字段」先例。
    - ✅ **同日第二轮：交付时提出的三条待议，逐条拍板后已落地**（用户 2026-09-14 逐条裁定）：
      - **① 丢弃计数口径提示上移进卡片**（拍板「上移到卡片内」）：卡片「丢弃计数」后加 `（进程内累计快照，重启归零）`（**仅 `dropped` 非空时显示**），页脚那段完整说明保留。理由 = 读数与口径提示原先隔着一整张表，误读方向是「以为数据恢复了」，属**安全性误判**而非美观问题。
      - **② 无心跳文案收窄**（拍板「改文案不越界」）：渲染文案 `未接入 SDK（查询窗内无心跳上报）` → **`查询窗内无心跳上报`**。
        - ⚠️ **性质订正（我上一轮判断错了，如实记账）**：我原说「后端这半边是诚实的，外推只发生在前端文案」——**错**。外推在 **§9.1 的判据定义里**（`no_agent` 逐字「该 agent 无 last_seen，**未接入 SDK**」，详情 `solution_detail.md:1238`），前端只是**照文档实现**。故正确落法不是改一个字符串，而是**文档与实现同步收窄**。
        - **站点全集 = 16 处 / 8 文件**（照「先 grep 定死全集再动手」）：**渲染面仅 1 处**（`AdminAgentsView.vue` 卡片），其余为注释 / docstring / 测试字符串 / `task.md` / `solution_detail.md` 引述。已全数收口；残留的「未接入」字样**均为订正上下文里的引述**（「原写「未接入 SDK」」之类），是留痕、不是漏改。
        - 同步订正 detail **§8.5（`:1134`）/ §9.1（`:1238`）/ §3.6（`:434`）/ §9.2 页面表（`:1253`）** 四处，各加「2026-09-14 措辞收窄」注，写明**该判据区分不了「从未接入」与「曾接入但断联超窗」**（窗 = `keyword_search_days`）。
        - 顺带订正 `AdminAgentsView.vue` 头部**我自己写的另一句过头话**：原写本页「能看到『接入但掉线』与『本来就没接』的差别」——本页只是**列出**两者，health 卡**区分不了**（两者都表现为「窗内无心跳」）。
      - **③ 立 `T-3.14`（health 批量面）**（拍板「立 T 项挂账」）：见本文件 T-3.14 条目——**标为容量型、缺输入（真实规模）**，写明触发条件与届时形态，**不实现**。⚠️ **容量型与欠债/补实现三种性质各自不同，已在条目内显式区分**，防后人把它当未完成项拉低进度。
  - **交付回填 · 批 2b（2026-09-14；证据 = `backend/app/api/admin.py` credential 端点 + `backend/app/api/schemas.py` + `tests/test_api_admin_credential.py` + `tests/integration/admin_credential_probe.py` + `frontend/src/views/AdminAgentsView.vue` 凭证区）**：
    - ⚠️ **范围订正：开工取证推翻原计划，「凭证两端点」实为「一端点」**（照「先评方向、再评方案」）。两条硬事实：**(a)** `rotate` 的三个动作（新 SASL 账号 / 撤旧 ACL / 断连接）**全在 infra**（detail §13.2 `:1430` 逐字），online **无执行面**——执行动作已由 T-4.10 下移 T-5.3；**(b)** **新口令无来源**：`agent_credential` dev 库 **0 行**、全仓除 models/alembic/文档外**零读写方**（2026-09-14 实测）⇒ 让 online 自造一个口令写进 `secret_cipher`，只会写出一条 **infra 侧永远对不上**的记录——**比空表更坏**（运维以为已轮换，broker 侧毫无变化）。**用户 2026-09-14 拍板「只做脱敏读面，rotate 整条下移」**。
    - ✅ **§8.5 凭证读端点**：`GET /admin/agents/{agent_id}/credential` → `AgentCredentialOut{agent_id, credential: {...} | null}`；字段 = `kafka_username` / `topic` / `active` / `rotated_at` / `created_at`。
    - **[裁定] 三条**：① **「脱敏」= 不回传 secret 字段、且端点连 `secret_cipher` 列都不读**（不取即不可能误传）——`secret_cipher` 存的是**密文**，对密文做掩码零信息价值；**不设 `has_secret` 之类恒真布尔位**（该列 `nullable=False`，「对象存在」已等价于「有 secret」，加一个恒真位反会被读成「可能没有」）。② **无凭证行 ⇒ 200 + `credential=null`**（合法态，非 404；404 会让前端分不清「agent 不存在」〔本面 400〕与「还没发凭证」——两者处置动作不同：前者查 id，后者催 infra）。③ **只读不写审计**（与 `/users`、`/configs` 列表同口径）。
    - ✅ **不依赖 `Fernet`**：`fernet_keys` 配了、`config.py:78` 启动强校验非空，但全仓 `Fernet`/`MultiFernet` **零使用点**（2026-09-14 取证）；本端点**不经过**该路径——不是「用它之前先补它」。**⚠️ 但这也意味着 `secret_cipher` 的加解密两端至今无载体**，属 T-5.3（与 SASL 发放通道一并定案）。
    - ✅ **前端**：`/admin/agents` 展开行加**只读**凭证区（第三块面，`allSettled` 各报各的错）；**无轮换按钮、也不留占位**（照批 1 先例：占位会被读成「功能在、只是没数据」）。
    - ✅ **验证（独立验收面 = MySQL `agent_credential` 真表）**：单测 **8 例** ⇒ 全量 **520 passed**（基线 512 + 8）/ ruff 全绿 / 前端 `type-check` 绿 + **133 单测**（基线保持）；真库探针 `admin_credential_probe.py` **10/10 PASS**。
    - ✅ **两条核心护栏（本批判据的重心）**：① 单测 `test_endpoint_never_reads_secret_cipher` 用**「一读 `secret_cipher` 就抛异常」的替身**钉住「不读取」——比 `assert "secret" not in body` 更严（后者只防「回传」，防不了「读了再抹」，而读了就可能进日志/异常栈）；② 探针 C-2 造**有/无凭证双侧对照**——**只测「没有」那一侧的话，「端点恒返 null」也会全绿**。
    - ✅ **反假绿实测**：临时让端点多回一个 `secret_cipher` ⇒ **C-4a/C-4b 立即转红、其余 8 项仍绿**；回滚并 `restart backend` 后复绿。（⚠️ **过程教训，已记**：我第一次用 Windows python 写 `/tmp/*.bak`、再到 Git Bash 里 `cp` **找不到该文件**——**两个 shell 的 `/tmp` 不是同一个目录**，回滚一度落空，靠手工 Edit 才复原。**跨 shell 的临时备份必须落仓内确定路径**。）
    - ✅ **零残留**：探针连跑两遍（幂等，均 10/10）后 `agent_credential` 全表 **0 行 ⇒ 0 行**（与开工前一致）、`probec-` 前缀 agent/user 各 0；探针自建自删。
    - ✅ **浏览器 e2e（2026-09-14 实测；`http://localhost:18080`，admin 账号真登录）**：`/admin/agents` 展开 `good-question` → **凭证区渲染空态文案**「尚未发放凭证（等 infra 发 SASL 账号后落库，非本页可操作）」+ 底部说明；**页面无任何轮换入口**（实测确认，非声明）；同屏 health 卡照常（**未因加第三块面而回归**）。
    - ⚠️ **未覆盖（如实标注，不算通过）**：`rotate` **无用例可写**（端点不存在）；`Fernet` 加解密**不经过**该路径、也无从验（全仓无实现）——探针里 `secret_cipher` 只是**普通字符串**，**不代表真加密语义已成立**；**浏览器 e2e 只验了 `credential=null` 空态**（dev 库 0 行，环境无「有凭证」的真实态），**不当全量验收**。
  - **交付回填 · 批 2d（2026-09-14）= 砍过设计，本批不实现任何功能**。用户当日拍板「online 和 offline 是否过度设计了，砍掉过设计的部分，只保留目标相关的」。评估口径 = **P2 核心链**（观测→聚类→组装→拉取→判定→回归回推→收口）：**online 侧 T-3.1~T-3.11 已全部落地**；~~**offline 侧批 1 已通管道、批 2 真判定零落地 ⇒ 整条链今天判不出一个真结果**~~ **⚠️ 2026-09-15 失效订正**：该判断作于批 2d（2026-09-14），而 **offline 判定主干随后已由批 C1（`d255de4`）落地** —— 实测 `runner/executor.py:67` 的 `execute_case` 有**真实 HTTP 实现**（adapter 调用 + 状态码分流），**非桩**。⇒ 「整条链判不出真结果」**已不成立**；~~当前判不出真结果的原因是**没有真实 agent 可打**（属 T-2.5 / S-4 的「等环境」，**不是代码没写**）~~ —— **⚠️ 2026-09-16 订正（该归因已证伪）**：agent **可打**（四 agent 容器在跑、契约全 200、obs_sdk 全接入），且 **offline 已真打并出分**（`eval_run` 3038/3660/3666，跨 15 天三次成功，见「真实 agent 端到端联调验收（2026-09-16）」）⇒ 当前判不出真结果的成因是**没有真实用户流量**（现为 0，故无真实 error 现场），**既不是没有 agent，也不是代码没写**。**原句划线留档**（2026-09-15 盘点中它曾被当作现况引用 —— 现在时措辞 + 无失效标记即会骗人）。余下三项**均不在此链上、且不解锁任何门**，按性质分别处置：
    - **① 批 2c §8.5.1 自动补标 → 不做。** 两条依据：**(a) 它替代的是一次点击**——人工补标端点 `PUT /interfaces/{id}` 已存在**且已验收**（批 2a-1 探针 G-5 实测 `llm 0→1` + `llm_source=manual` + `llm_suspect 1→0` 落库）；**(b) 代价不对称**——需新增**第 7 个周期 job**（`worker/__init__.py` docstring 明立「job 数 = 6」护栏），外加两处契约歧义裁定（原文对 `llm_suspect` 何时清 0、llm_call 是否按 `status` 过滤**均沉默**）与审计量治理（逐轮逐接口置位 ⇒ 单接口每晚约 288 条审计）。⇒ **`solution_detail.md` §8.5.1 整节已标注 v1 不做**（原文划线留档，附三条依据）；**不新增 job，job 数仍为 6**。
  - **撤除回填（2026-09-14，用户拍板）——§8.5 admin Agent 面整节撤除，上面三处「已落地」全部作废**：
    - **来路**：用户判「【系统管理-Agent】是过度设计，不是必须的」，选**整页连 health 卡一起砍**；在我告知 `POST /agents/{id}/toggle` 是 `backflow_allow` 核心链白名单门（`analyzer/classify.py:188/225`）的运行期唯一开关后，**仍确认 `GET /agents` + `toggle` 一并删**。已立为全局约定（`~/.claude/CLAUDE.md`「设计原则 · 不要过度设计和实现」）。
    - **站点全集（实测定死）**：后端 `admin.py` §8.5 段（六端点 + 四 helper + 四常量）+ `schemas.py` 七模型 + `store/es.py` 心跳读路径四符号（`build_heartbeat_body`/`summarize_heartbeats`/`fetch_heartbeats`/`_SOURCE_FORM_A`，**只被 health 消费 ⇒ 留下即死码**）；测试/探针六文件；前端 `views/AdminAgentsView.vue` + 路由 + 菜单 + `api/admin.ts` + `api/types.ts`；文档三处同步。**§8.6 面不受影响**。
    - **⚠️ 两处代价（明写）**：① `agent.backflow_allow` / `enable` **无运行期写入面**，只能改库或改 seed、**无审计**；② 「agent 有没有在报数」失去唯一界面 ⇒ **替代口径 = 直查 ES 事件 index 的 `node=heartbeat` doc**（全文见 `docs/integration-report.md` F-19「撤除」节）。
    - **连带作废**：`PUT /interfaces/{id}` 已删 ⇒ 批 2d 立下的「§8.5.1 改由**人工补标**承担」**替代方案无载体，`llm_suspect` 解除路径当前为空**；**`T-3.14`（§8.5 health 批量面）随之失去前提**（见该条目）。
    - **验证**：后端 `ruff` 全绿 + `pytest tests/ --ignore=tests/integration` **478 passed**（较 520 少 42 例 = §8.5 三测试文件）；前端 `vue-tsc --noEmit` 干净 + `vitest` **133 passed**；前后端 `grep` 零残留引用。**未覆盖**：浏览器 e2e 未做（可用「访问 `/admin/agents` 得 404」验）。
    - **② T-3.14 health 批量面 → 不做、结清。** 依据 = 该条**自陈**「纯性能/规模问题，功能面已完整」+ ~~已判「环境无输入」（6 个 agent 下逐查与批量查观测特征相同）~~ —— **⚠️ 2026-09-16 订正**：「环境无输入」这个前提**已证伪**（四 agent 在跑、offline 已真打）。**结清结论不变**，但依据**只剩前者**：批量面是**规模判别力**问题，需「多 agent × 大数据量」才使逐查与批量查产生可观测差异，而现下 4 个 agent 的**数据量仍不足以构成该判别力** ⇒ 缺的是**量级**，不是 agent 本身。
    - **③ T-3.13 审计读面与导出 → 降级为 SOP、结清。** `conversion_record` 就在 MySQL，**一句 SQL 即出**；做列表端点 + 导出面是锦上添花。**替代口径已落 `docs/ops-manual.md`**（跨 cluster 统计人工处置量的 SQL，标注为 **v1 正式口径、不再做读面**）。
    - **④ 前端**：`/admin/agents` 的「疑似漏标」列与其提示「（确认后自动解除）」**已移除**。依据 = 本项目自立的「**不做占位**」先例（批 1 `AdminConfigsView.vue` 头部注释：「占位会被读成『功能在、只是没数据』」），且该提示**在承诺一个永不发生的行为**——全仓**没有任何写点**能让 `llm_suspect` 变成 1 ⇒ 属**正确性**问题而非外观问题。**`llm_suspect` 列与 `PUT /interfaces/{id}` 的清零逻辑保留不动**（不写迁移，将来复活成本为零）。
    - ⚠️ **同族「契约有、载体无」第五例（本批实证，只登记不修）**：**`interface` 表在 dev 库 0 行、且全仓无 INSERT**（`SELECT COUNT(*)`=0；`app/` 内 `Interface` 仅被 **SELECT**——`analyzer/context.py:48-51` / `consumer/state.py:279-282` / `api/admin.py:449/518/554`，**无构造点**）；模型 docstring 写的「**事件自动注册**」**无载体**，**种子注释也指向同一个不存在的写点**——`core/seed.py:115` 逐字 `# interface 字典 = 空（自发现注册）`、`:13` 写「4 个 agent 行 + **空 interface 字典**」，而 seed 只 INSERT `agent` 行（`:114-130`）。（**两处注释都说「会自动注册」，实现都不存在**；agent 表那 4 行来自 **seed**，其 `route_source='auto_register'` 是种子里写死的枚举值，**不是**某处注册逻辑的证据。）连带：`llm_suspect=1` **零写点**（唯一写点是 `api/admin.py:573-576` 把 1 置回 0）；`llm_source` 的 `config`/`auto_observed` **零写点**（`api/admin.py:390` 逐字「本端点只产出『人工补标』」）；配置键 `llm_call_observe_window_min/threshold` **有 seed、零消费方**。**影响面（已修正，不夸大）**：`classify.py:115` = `error_type in L2_ERR_TYPES and (llm_fact or interface_llm is True)`——字典门是**附加**路径，trace 内 `llm_fact` 仍生效 ⇒ 表空是 **L2 判定退化（只靠 trace 内证据）**，**不是硬断**。**处置 = 只登记不修**：补 `interface` 自动注册写点属**同一类过设计**，应等~~真实 agent 接入（T-2.5）~~ **真实流量**产生后按真实需求定（**⚠️ 2026-09-16 订正**：agent 接入**已成立**，但 `interface` 表**至今仍 0 行** —— 恰说明「真实需求」**不会随接入自动产生**，要的是**有真实调用打到接口**）。
    - **验证（2026-09-14 实测）**：前端 `npm run type-check` ✓ + **133 单测全绿**（基线保持，**无用例断言被删的列**）；前端镜像已 `docker compose build frontend && up -d` 重建；浏览器打开 `/admin/agents`、展开 `good-question` ⇒ **health 卡与凭证区零回归**，页面新提示句已渲染。**后端零改动已证**：`pytest tests -q` = **520 passed**（与批 2b 末次同数）+ `ruff check app/ tests/` **All checks passed**。
    - ⚠️ **一条断言不可达（如实标注，不算通过）**：**浏览器验不到「列已删」**——dev 库 `interface` 表 0 行 ⇒ 接口字典表整块**不渲染**（页面出空态「该 agent 暂无接口字典行。」），**列头根本没出现，证不了它没了**。该改动的证据 = `vue-tsc` + 133 单测 + 重建后的构建产物，**不是**浏览器。要真验须造一行 interface 让表渲染——**判定为与核心流程无关的发散，未做**。
    - ⚠️ **本批顺带改正了批 2b 的一处误报**：批 2b 汇报称「ruff 全绿」，实为只覆盖了 `app/`——补跑 `tests/` 后**红 2 条**（均在我批 2b 新建的 `tests/integration/admin_credential_probe.py` 里的 E501 超长行）。**已修**，现 `ruff check app/ tests/` 归零。**教训**：本仓 pre-commit 静默失效（[[local-precommit-hook-gap]]），跑 ruff **必须显式带上 `tests/`**。

- **T-3.13 审计读面与导出补实现**（**2026-09-14 立**，用户拍板；来源 = 阶段 5 T-5.4 运营清单，登记见 `docs/integration-report.md` §6 **F-23**）：**审计（`conversion_record`）当前只能逐个 cluster 打开详情看，无跨 cluster 检索、无导出**。运营诉求「统计某时间段内人工处置了多少条」**当前不可用**。
  - **⚠️ 性质声明（与 T-3.12 必须区分，否则两处会被当成同类）**：`T-3.12` = **权威文档承诺过、实现没做**（欠债）；**本条 = 上游设计（`solution.md` / `solution_detail.md`）零命中「导出」**（2026-09-14 实测 grep），系**由 T-5.4 运营清单提出** ⇒ 性质是「**运营需求驱动的补实现**」，**不是**「承诺未兑现」。**登记时勿套 T-3.12 的措辞**——F-19 定义欠债时明确要求「按『承诺过』而非『提过』判定」，本条**不满足该判据**，是**显式自主加范围**（用户已知悉此代价并拍板）。
  - **实现现状（双向核对）**：审计表 ✅ 在（`models/error_flow.py:143-162`）；读面 ⚠️ **仅内嵌于 `GET /backflow/clusters/{id}`**（`api/backflow.py:555-558/590-596/608`），**无独立列表/检索端点**；导出 ❌ **无**（全仓 grep `csv|export|StreamingResponse|FileResponse|Content-Disposition` **零命中**）。
  - **范围（待细化，`T-3.12` 开工时或独立排期时定）**：① 审计列表端点（至少支持 **时间窗 + agent + action** 三种筛选，与 cluster 详情内嵌返回同形状）；② 导出形态（CSV 或 JSON 流式；**须先定「导什么字段、给谁用」**，避免导出面泄漏内部 id/快照）；③ 归属前端页面（`/admin` 下或回流域内，与 T-3.12 ② 的「admin 页面无数据源」合并考量）；④ **权限 = admin-only**（复用 `deps.py:44-47` `require_admin`，与 T-3.12 同口径）。
  - **边界**：不阻塞阶段 5 出口，也不进上线门（**放量的硬门是 T-5.3，本条非安全/契约项**）；**阶段 4 内不实现**（阶段 4「只验收、不新增功能」）。
  - **状态**：**已结清（2026-09-14 用户拍板「降级为 SOP」，见本文件 T-3.12 批 2d 回填）**——② 导出形态（CSV/流式）**不做**；① 审计列表端点**不做**。**替代口径** = `docs/ops-manual.md` §审计 内给出跨 cluster 统计人工处置量的 SQL（`conversion_record` 就在 MySQL，一句 SQL 即出）⇒ **本条不再有实现待办**。⚠️ 原文三条「范围」保留仅供留档，勿再据此开工。

- **T-3.14 §8.5 health 批量面**（**2026-09-14 立**，用户拍板；来源 = T-3.12 批 2a-2 交付时提出的三条待议之三）：
  - **现状**：`GET /admin/agents/{id}/health` 是**逐 agent 单查**——`/admin/agents` 页每展开一行打一次，各查一次 ES（`size = _HEALTH_SIZE = 500`）。**无批量面**。
  - **⚠️ 性质声明（勿与上两条混，三条性质各不相同）**：`T-3.12` = 权威文档承诺过、实现没做（**欠债**）；`T-3.13` = 运营需求驱动的**补实现**；**本条 = 纯性能/规模问题，功能面已完整**。⇒ 属**容量型**（量级不足时判据无判别力，**不得按「本地能跑」判**），**不是「未完成项」**，**不得据它反向拉低阶段进度**。
  - **触发条件（写明以防被提前做）**：agent 量级或并发展开数达到「逐查可感变慢」时开做。**当前 6 个 agent 下，逐个查与批量查观测特征相同**（且展开是用户动作、并发远低于 agent 总数）⇒ 现在做也验不出差别。
  - **届时形态（现在不定死）**：`GET /admin/agents/health?ids=1,2,3`（内部 `_msearch`），或前端串行化/缓存。⚠️ **§8.5 文档未定义该端点** ⇒ 届时属**新增对外契约面**，须先订正文档再实现。
  - **边界**：不进上线门；阶段 4 内不实现。
  - **状态**：**已结清（2026-09-14 用户拍板「不做」，见本文件 T-3.12 批 2d 回填）**——依据 = 本条自陈「**纯性能/规模问题，功能面已完整**」+ ~~已判「环境无输入」~~（**⚠️ 2026-09-16 订正**：前提已证伪、依据收窄，**同批 2d 第 ② 条的订正注**）。**不实现，且从待办中移除**（保留原文仅为留档）。
  - **状态**：**未开工（缺输入：真实规模）**。
  - ⚠️ **2026-09-14 撤除后：前提消失，条目作废。** `GET /admin/agents/{id}/health` 与 `/admin/agents` 页**已随 §8.5 整节撤除**（见 T-3.12「撤除回填」）⇒ 「逐 agent 单查 vs 批量查」这个性能问题**已不存在载体**。本条**不再成立、不再推进**，保留原文仅为留档。（同时提示：本条目末尾两行「状态」自相矛盾——上一条称「已结清不做」，下一条称「未开工」，系两次回填叠加所致，**二者现均失效**。）
- **T-3.15 `judge_task.status` 模型↔库枚举分叉裁定**（**2026-09-14 立**，用户拍板；来源 = 批 C4b（offline）跑 `alembic check` 时暴露；登记位置依 **T-3.8** 先例 = 「offline 配套轨在平台阶段表的落点」）：
  - **事实（两侧逐字，均为 offline 仓，2026-09-14 实码实读）**：**库侧 5 值** —— `alembic/versions/a0711408024f_initial.py:355` `sa.Enum('pending','processing','done','failed','pending_human', name='judge_task_status')`；**模型侧 4 值** —— `app/models/run.py:17` `JUDGE_TASK_STATUS = ("pending","processing","done","failed")`，前一行注释逐字「pending_human（人工复核）7.5e 预留机制已随轻量化删除：真实 judge 不输出 confidence 永不触发」。**⚠️ 该四行上方的表头注释恰写「# MySQL ENUM 值定义（与 DDL 一致）」**（`run.py:10`）——这句在本条上不成立。
  - **真库实测（2026-09-14，容器内直连）**：`information_schema` 该列 `COLUMN_TYPE = enum('pending','processing','done','failed','pending_human')`；表内**行分布 = `{done: 1429, failed: 1}`** ⇒ **零 `pending_human` 行**，即该值**存在但从未被写入**。
  - **⚠️ 性质声明（勿与 T-3.12/T-3.13/T-3.14 混）**：本条**不是欠债**（无文档承诺过要删枚举值）、**不是容量型**、**也不是「实现没做完」**——模型侧收窄是**有意的**（注释已声明 `pending_human` 机制随轻量化删除），库侧的残余值来自**初始迁移的一次性 DDL 快照、此后再无人动它**。⇒ 性质 = **「实现有意收窄 + DDL 残留值」的一致性偏离**，处置方式**待裁定**，**不得据它判「judge 未完成」或拉低阶段进度**。
  - **待查/待裁三问（本轮只登记，均未决）**：**(a)** 是否补一条迁移去掉该枚举值——⚠️ MySQL 改 enum 会**重建表**（A 级 DDL），且若将来人工复核机制回归则等于白删，**收益未证**；**(b)** 若保留，读到该值的失败模式是否可接受——SQLAlchemy `Enum` 结果处理遇未声明值抛 **`LookupError`（非静默）**，即**不会静默错判**，但会把一个「本可解释」的状态变成 500，**需要按 `Enum(...)` 是否带 `validate_strings`/`native_enum` 实测确认**（**该实测本轮未做**）；**(c)** 该分叉使 `alembic check` **恒报红**，噪音**会掩盖真漂移**（本轮同类红里就混着 `agent_circuit.opened_at` 一处真漂移）——是「一次性裁定」还是「给 `alembic check` 建已知偏离白名单」，二选一。
  - **边界**：**不进上线门**（不改契约、不改状态机、零业务行为影响：库内零行 + 代码无写点）；**本批不实现任何 DDL 改动**，仅登记。**开工前置** = 先答 (a)(b)(c)，且 (a) 若做须走 A 级流程（改数据库）。
  - **附注 · 同批暴露的另一处漂移（2026-09-15 已拆为独立条目 → 见下方 T-3.16；原措辞「同类」存疑，那处性质待查）**：`agent_circuit.opened_at` **库侧 = `double`**（2026-09-14 实测），模型侧声明 `Float(precision=53)`（`app/models/misc.py`）——原登记称「属同一类『模型↔库形态偏离』、成因不同（本条是枚举值域、那处是浮点精度写法）、处置可分开」；⚠️ **2026-09-15 订正：第一条存疑**（那处模型与迁移**声明一致**，可能是 **alembic 比对假阳性**而非形态偏离，见 T-3.16），后两条仍成立。⚠️ **本条标题只含 `judge_task`**，勿把两处并作一个动作。
  - ✅ **施行记录（2026-09-15，三问已裁、裁定 (a) 已落地）**：新增迁移 offline
    `backend/alembic/versions/e5f6a7b8c9d0_shrink_judge_task_status_enum.py`（`down_revision='d4e5f6a7b8c9'`，
    `upgrade` 收窄为 4 值 / `downgrade` 把 `pending_human` 加回，**可逆无损**）。三问回填：
    - **(a) 做**（原「收益未证」不成立）。⚠️ **理由已补正**：不是「删干净」——零行 + 全仓 `pending_human`
      零写点 ⇒ `LookupError` **不可达**，单说「删干净」答不出「不做会出什么具体故障」。真收益在 **(c)**：
      该分叉使 `alembic check` **恒报红**，而**真漂移就混在这片红里**（`opened_at` 那处当时就没被独立注意到）。
    - **(b) 已实测（补做，原行「该实测本轮未做」已失效）**：SQLAlchemy 结果处理遇未声明值的路径 =
      `sqlalchemy/sql/sqltypes.py:1711-1724` `_object_value_for_elem`，找不到即 **`raise LookupError`**
      （逐字 `"'%s' is not among the defined enum values…"`）—— **显式抛错、非静默错判**，与原文推测一致，
      现为源码级证据。**但该失败模式在本场景不可达**（零行 + 零写点）⇒ **不构成「保留枚举值」的理由**。
    - **(c) 随本批消解**（走近路：删掉源头，不建白名单）。收窄后 `alembic check` 输出中
      **`judge_task` 已完全消失**，只剩 `agent_circuit.opened_at` 一处（**预期**，`task.md:239` 明说勿并作一个动作）。
    - **验收（全绿）**：A 真库 `upgrade head` → `COLUMN_TYPE = enum('pending','processing','done','failed')` 恰 4 值 ·
      B 行数 **1430 逐字不变**、分布 `{done:1429, failed:1}` 不变（改前已复核真值，未沿用 2026-09-14 快照）·
      C 见上 · D `upgrade→downgrade→upgrade` 往返三步每步回查列型与行数均符合预期 · E offline 全量单测
      **933 passed / 96 skipped**（与基线逐字一致）· F ruff 新文件**零命中**（借 online venv 配置；首次报 I001
      属新增命中，已修）。
    - **性质声明补正**：原文「**不是欠债**（无文档承诺过要删枚举值）」**结论仍成立，但理由要换** ——
      实为 `a9e6b4c2d8f1_drop_governance_features` 那次改造**声明的处置范围 = 模型 + 三张遗留治理表**，
      **枚举值从未进入该次范围**（不是「漏删」，是「从未进入视野」）。
    - **本批的绿不能证明**：`opened_at` 那处漂移已处理（**显式不碰**，`alembic check` 仍红一处）；其他表无同类
      残留（**由 `alembic check` 的全局比对兜住**，它报的是全集非抽样）；「人工复核机制不会回归」（回归须重写迁移
      把枚举值加回，成本与现在删掉相当 ⇒ 不构成「白删」顾虑）。
    - **交付**：**已 commit + 已 push**（offline `dev` `78f1345` / online `main` `7d6f269`，快进非 force，2026-09-15）。
      风险等级 A（真库 DDL，MySQL 改 enum 会**重建表**；本表仅 1430 行，重建瞬时完成）。
- **T-3.16 `agent_circuit.opened_at` 类型比对恒报差异**（**2026-09-15 立**，用户拍板单独立项；来源 = 批 C4b 跑 `alembic check` 时与 T-3.15 **同批暴露**，原先只挂在 T-3.15 附注下「以免再立一项」，现拆为独立条目）：
  - **事实（2026-09-15 实测，均由命令产出）**：真库 `information_schema.COLUMN_TYPE = double`；表内 **15 行**。（⚠️ 下方「模型侧 … `Float(precision=53)`」是**改动前**的原始取证，模型一行已于当日改为 `Double(asdecimal=False)` —— 见「施行记录」；此段保留原样不改写，以留取证痕迹。）**模型侧与建表迁移侧的声明一致** —— `app/models/misc.py:83` `mapped_column(Float(precision=53))` 与 `alembic/versions/c6f7a2d1e3b5_add_agent_circuit.py:30` `sa.Column('opened_at', sa.Float(precision=53), nullable=True)`；两处注释逐字同为「opened_at 必须 DOUBLE：MySQL FLOAT(单精度) 对 epoch 秒(1.7e9) 精度丢失（1787201704 → 1787200000）」。
  - **`alembic check` 判词（逐字）**：`Detected type change from DOUBLE(asdecimal=True) to Float(precision=53) on 'agent_circuit.opened_at'`。
  - **⚠️ 性质（与 T-3.15 **不是一回事**，别套同一套处置措辞）**：T-3.15 是**真值域分叉**（模型 4 值 vs 库 5 值）；本条**模型侧与迁移侧没有分歧**，分歧在「**模型声明**」与「**库反射结果**」之间 —— MySQL 把 `FLOAT(p)`（p>24）实际存为 `DOUBLE` ⇒ **两侧的 DDL 结果是同一个东西**，疑似 **alembic / SQLAlchemy 的比对表示差异（假阳性）**，而非库与模型实际不一致。~~**⚠️ 但这只是本轮从声明反推的假设，未实测证实**~~ ⇒ ✅ **2026-09-15 已实测证实**（见下方「待查 (1) 已实测结清」）。
  - ✅ **待查 (1) 已实测结清（2026-09-15，全部结论由命令产出）**：**假阳性证实，且有解**。六种候选写法经反射 metadata 比对（**不改仓内文件、不动库**）：现状 `Float(precision=53)` 与 `Float()` **报** `modify_type`；`Double()` / `Double(asdecimal=False)` / `mysql.DOUBLE()` / `mysql.DOUBLE(asdecimal=False)` **一律不报**。DDL 编译 + 真库**会话级临时表**实测（用完即 DROP）：`Float(precision=53)` → 编译 `FLOAT(53)` → MySQL 存成 **`double`**；`Double(asdecimal=False)` → 编译 `DOUBLE` → **同样存成 `double`** ⇒ **两侧逐字同形、改模型零 DDL 变化**。**判别力对照**：`FLOAT(24)` → `float`（证明实验不是「什么都报 double」）；另一个对照 = 不传 `compare_type=True` 时**连现状都测不出差异**（首跑即踩，见 `env.py:39` 显式传）。⚠️ **不能照 T-3.15 的办法办**：autogenerate 会建议 `alter_column(type_=Float(precision=53))`，而执行后库里**仍是 `double`**（同一次实测即证）⇒ **下次 `check` 仍报，死循环** —— T-3.15 那次「照 alembic 建议做就消红」在此处**恰好相反**。**推荐解 = 模型改 `Double(asdecimal=False)`**：零 DDL 变化，且显式保住 ORM 取值仍为 `float`（同时满足待查 3）。比对器**不看 `asdecimal`**（`Double()` 与 `Double(asdecimal=False)` 都不报）⇒ 该参数只影响语义、不影响消红。~~**尚未改模型，待拍板**~~ ⇒ **已落地（2026-09-15）**，见下「施行记录」。
  - ✅ **待查 (3) 已实测结清（2026-09-15，真库只读往返 + 类型对象实测）**：容器 `ai-eval-backend` 内对 `agent_circuit.opened_at` 走 ORM 取值 —— 表内 **15 行 / 2 行非空**，真行取值 `type = float`、值 `1789387624.9283097`（**非 Decimal、非 int，小数秒完整保留**）；另以 `literal(1787201704.25, 列类型)` 走一趟结果处理器 ⇒ 亦为 `float`。**结论：取值语义与改前一致**（改前 `Float(precision=53)` 的 `asdecimal` 同为默认 False ⇒ 亦返 `float`，已实测）。附带证据：单精度存 `1789387624.9…` 会丢到整数秒量级 —— **再次印证本列必须双精度**，即 C3 那个 bug 的注释所述。
  - ⚠️ **订正（2026-09-15）：原判「`asdecimal=False` 不可省：`Double` 默认 True ⇒ ORM 取值变 Decimal」是错的**（属「没证据就写出解释」，且这条被写进了代码注释）。实测四个取值：`Float(precision=53).asdecimal = False`、`Double().asdecimal = `**`False`**、`Double(asdecimal=False).asdecimal = False`，三者 `python_type` 均为 `float`；唯 `Double(asdecimal=True).python_type = Decimal`。⇒ **该参数写与不写完全等价**，保留它只是显式表达「本列取值须为 float」。**代码注释已按此订正**。**是否进一步简化为 `Double()`** 已于 2026-09-15 裁定 = **保留**（见下「待裁」条）。
  - ✅ **施行记录（2026-09-15，待查 (2) 裁定取第一支「改模型声明」，已落地）**：offline `backend/app/models/misc.py` 的 `opened_at` 行（**改动前 `:83` / 改动后 `:88`**）由 `Float(precision=53)` 改为 `Double(asdecimal=False)`，并补注释说明「为什么不写 `Float(precision=53)` = 死循环」。**零迁移、零 DDL**（两侧库内同为 `double`，**未新增任何迁移文件**）。三件套验证（全部由命令产出）：① `alembic check`（容器 `ai-eval-backend`）⇒ **`No new upgrade operations detected.`** —— **T-3.15 之后仅剩的这一处红至此清零**（T-3.15 的收益兑现：剩下的红每一处都是真的，本条修掉后全绿）；② offline 全量单测 **933 passed / 96 skipped** = 与基线逐字一致（零回归，且在**最终字节**上重跑确认）；③ ruff（借 online venv + online 配置 —— **offline 仓无任何 ruff 配置**，此为唯一可用门禁）⇒ 4 条**存量**（`I001@2` + `E501@35/40/57`），**零新增**（基线 5 条；顺带把 `E501@81` 那条存量超宽折掉）。**未验收**：无（三问全部结清）。**交付状态**：**已 commit + 已 push**（**2026-09-15 订正**：本节原写「未 commit / 未 push（等授权）」，属**裸标记腐**——该改动已于同日 `e7448a1`（offline `dev`）提交、并随 `e1d2ffe..e7448a1` **快进非 force** 推送；核实命令 `git merge-base --is-ancestor e7448a1 origin/dev` = 是）。
  - **待查/待裁**：**(1)** ~~先证实或证伪「假阳性」——最强判据 = 找出一个不产生任何 DDL 变化却能让 `alembic check` 静默的模型写法（候选 `Double()` / 方言 `DOUBLE(asdecimal=…)`）~~ **已结清，见上**；**(2)** ~~若确认假阳性，三选一：改模型声明（零迁移、零 DDL）/ 配 `compare_type` 豁免 / 只登记不修（判据同 T-3.15：答不出「不做会出什么**具体**故障」就不做）~~ **已裁定 = 取第一支「改模型声明」**（另两支否：`compare_type` 豁免 = 建白名单，只登记不修 = 留噪音源 —— 判据同 T-3.15，即「不做则 `alembic check` 恒红，真漂移混在这片红里」）；**(3)** ~~若走改模型，须确认 **ORM 取值语义不变**（该列是 epoch 秒 float，`asdecimal` 标志会影响返回类型）~~ **已实测结清**（见上「待查 (3)」）。
  - **待裁（新增，2026-09-15）**：`Double(asdecimal=False)` 是否简化为 `Double()` —— 两者**完全等价**（已实测，见上「订正」），保留显式参数的唯一价值是**表达意图**。**倾向保留**（本条根因就是「模型侧与反射侧表示不一致」，显式写出 `asdecimal` 是对「照判词里的 `asdecimal=True` 去对齐」这一误操作的钉子）；但按「简单就是美」也可去掉。✅ **2026-09-15 用户裁定 = 保留 `asdecimal=False`**（取「钉子」价值；代价 = 该参数**实际无作用**，已知并接受 —— 代码注释已逐字澄清「写与不写完全等价」，留着只为表明本列取值须为 `float`）。**本项至此无剩余待裁。**
  - **边界**：**零业务行为影响**（两侧 DDL 结果同为 `double`）；**本项若确认是对比问题则根本不需要 DDL**（表仅 15 行，即便要改库也极小）；**不进上线门**。
  - **与 T-3.15 的关系**：T-3.15 已于 2026-09-15 落地（offline `78f1345`）⇒ **截至该日的 `alembic check` 输出中，本条是唯一剩下的红**（这正是 T-3.15 的收益所在：让剩下的红每一处都是真的）。两处**勿并作一个动作**（T-3.15 附注原文即如此声明）。⇒ **2026-09-15 本条亦落地，`alembic check` 当前零报**（见「施行记录」）。
- **T-3.17 四仓镜像烤码与宿主 HEAD 漂移（「镜像≠宿主」）**（**2026-09-15 立**，用户拍板「立 T 项 + 先查清波及范围」；来源 = T-2.5 做「真机对照」时发现 gq 容器内 `_llm_error_type` 仍返回自由字符串 `TIMEOUT/NETWORK/HTTP_{code}` ⇒ 反查镜像烤入点，**结论与本条不限于 T-2.5**）：
  - **事实（2026-09-15，全部由命令产出）**：四仓 backend 源码经 `docker compose build` **烤进镜像**（`docker inspect .Mounts` 显示只有 data/cache 卷、**无源码挂载**）⇒ **宿主改文件对运行实例零影响**。四个镜像创建时点全部落在 **2026-09-08 13:09~14:09**，此后**未重建过任何一次**。烤入提交用「镜像内文件 `sha256` ↔ `git show <commit>:<path>`」**正面比对**定死：

    | 仓 | 镜像构建 | 烤入提交 | 宿主 HEAD | 落后 |
    |---|---|---|---|---|
    | good-question | 09-08 13:25 | **`5bd4e9c`** | `2eb0f4f` | 3 笔 |
    | customer-service | 09-08 13:54 | **`4dfad19`** | `befcc90` | 3 笔 |
    | smart-procurement | 09-08 14:09 | **`06d51ba`** | `79b0a85` | 3 笔 |
    | contract-check | 09-08 13:09 | **`480603f`** | `68dbff1` | 2 笔 |

  - **⚠️ 取证坑（必记，否则得出相反结论）**：宿主 checkout 是 **CRLF**、git blob 是 **LF**（实测 gq 该文件 412 行全带 `\r`，cs 499 行同）⇒ **不做 `tr -d '\r'` 归一就比对，会得出「镜像内容不属于任何提交」的假结论**（本轮首跑即踩，gq/cs 双双报不符，归一后逐字对上）。
  - **推论 1（幸运的一半）**：四个烤入提交**恰好就是四仓「§11.3 观测接入」那四笔**（gq `5bd4e9c` / cs `4dfad19` / sp `06d51ba` / cc `480603f`）⇒ **§11.3 的观测接入真机验收仍然有效**，不因本漂移作废。
  - **推论 2（失效的一半）**：四仓 **Sep 8 之后的一切代码改动从未上线** —— `llm_call.error_type` 白名单折叠（四仓各一笔 `2eb0f4f`/`befcc90`/`79b0a85`/`68dbff1`）+ 前端 nginx 运行时解析 + compose/`.env.example` 注记。**线上仍在产自由字符串 `error_type`**，随后的迁移**无一条删改**。
  - **推论 3（本主题直接相关）**：**值域卫生批「诊断有效、修复零真机证据」** —— `docs/integration-report.md` §2 序号 10（2026-09-15 真机复验）的 ES 证据全部由 `5bd4e9c` 等**旧码**产出，其措辞「正属值域卫生批**改码前**的自由字符串」隐含的对照面**实际不存在**（改后的码一次都没跑过）。**该条结论本身不假**（16 条真实 error 零候选 = 判据正确工作；L1 面真实输入充分性无判别力），但它描述的是**旧码行为**，**不得被读成「改完已验证」**。**⚠️ 2026-09-16 订正：「修复零真机证据」这一状态已解除（cs 仓）**——批 6a 重建后，cs 于 09-16 01:21~02:26 产出 **8 条真实 `error_type='llm_timeout'`**（ES `llm_call`，UUID trace、真实流量），**正是 `befcc90` 折叠后的白名单值** ⇒ **折叠码已在真机运行**；其中 `fd75aa34…` 已产出 cluster 3861 并跑通回流全链 ①~⑥。**但推论 3 的「对照面不存在」这一判断本身仍然成立且不可复用**：那 8 条是**新产**的证据，**不是**序号 10 那批 ES 证据的对照 —— 旧批数据至今仍全部来自旧码，不得回填。**另注（勿外推）**：gq/sp/cc 三仓**仍无**重建后的 error 样本（gq 唯一那条在重建前 / sp 全 ok / cc 无样本）。
  - **推论 4（T-2.5 本体）**：T-2.5 **从未整体验收**（`task.md:97`/`:101` 明确 defer agent 整改轨）⇒ **不存在「已作废的 T-2.5 验收结论」**；风险在**将来**——凡以四仓**运行实例**为证据面的验收，默认验的是 **Sep 8 的码**。
  - **四仓自身文档自 Sep 8 起零「已部署/已上线/重新构建镜像」记录**（逐仓 grep 无命中）⇒ **不存在「声称部署过」的假账**；缺的是**部署动作本身**，属**流程缺口**而非记录失真。
  - **边界（本批显式不做）**：**只登记 + 查清波及范围**，**不重建镜像、不重跑真机验收**。理由 = 重建属部署级动作，且「部署漂移」与「T-2.5 真机验收」是**两个验证面**，并作一批会让「重建引入的新问题」与「本批改动的问题」无法区分。
  - **待裁**：(1) ~~何时重建四镜像（与 T-2.5 真机复验的排期绑定）~~ **已于 2026-09-15 执行（批 6a，见下「施行记录」）**；(2) ~~重建后是否重跑 `integration-report.md` §2 序号 10 的真机复验~~ **已于 2026-09-16 裁定 = 不重跑，改用真机流量改判**（用户拍板；见下「本条结清」）；(3) ~~是否需一条**部署后置检查**（构建时把烤入提交写进镜像、或跑完验收核对实例指纹），防同类漂移复发~~ **已于 2026-09-16 裁定 = 只加流程约束（验收前必核指纹），不加代码/不加构建期 label**（见下「本条结清」）。
  - ✅ **施行记录（2026-09-15，批 6a = 「结构面」；用户拍板「先出重建镜像方案」后执行）**：**四仓 backend 镜像已全部重建并上线**，烤入提交追上重建当刻 HEAD：

    | 仓 | 重建后烤入提交 | 抽样指纹复验点 | 结果 |
    |---|---|---|---|
    | good-question | `94c27be` | `services/llm_service.py`、`services/chat_service.py`、`frontend/nginx.conf`（镜像内 `/etc/nginx/conf.d/default.conf`） | MATCH ×3 |
    | customer-service | `16f92c0` | `app/infrastructure/deepseek_gateway.py` | MATCH ×1 |
    | smart-procurement | `4fbd631` | `app/obs.py`、`app/ai/llm/deepseek_client.py` | MATCH ×2 |
    | contract-check | `68dbff1` | `app/obs.py` | MATCH ×1 |

    **判据面（不许读大）**：指纹复验是 **7 个抽样点的正面比对**（两侧 `tr -d '\r'` 归一后 `sha256`），**不是整个镜像的逐文件比对**；「MATCH」只证明**这些点**与宿主 HEAD 逐字节一致，**不证明镜像内其余文件无残留旧码**（未逐文件全比）。
    **容器确已换用新镜像**（`up -d` 重创，非「只构建」）：gq `rag-backend`/`rag-nginx`、cs `customer-service-backend-1`、sp `sp-app`/`sp-worker`、cc `contract-check-backend`（Healthy）/`contract-check-frontend`。探活实据：gq `/api/health` **200** + `/openapi.json` **200**；cs 日志 `Application startup complete` + `[obs] obs_sdk 已初始化 topic=dev.obs.agent.customer-service`；sp `sp-app` `health=healthy` + `/health/ready` **200**；cc backend `Healthy`。
    **⚠️ 现场事实（如实记，勿读成缺陷）**：`sp-app` 首启失败过 1 次（`[startup] 硬依赖不可用: ['mysql']，退出进程`，`RestartCount=1`）——**这是 sp 自身 `main.py:104-105` 的 fail-loud 设计行为，非本次镜像引入**（同一镜像第二次启动即成功且 healthy）。
    **不可逆保护**：重建前已把 7 个 `:latest` tag 备份为 `:pre-b6`（回退路径可用）。**顺带恢复**：`shared-neo4j`/`shared-redis`/`api-gateway` 当日 11:0x 前被停过，本次一并 `start` 恢复；三容器 `RestartPolicy=unless-stopped` + `RestartCount=0` ⇒ 当时为**手动停止**（非崩溃、非 OOM，`OOMKilled=false`）。
    **本批不覆盖（显式，勿被整批的绿盖过）**：① ~~**`integration-report.md` §2 序号 10 的真机复验未重跑**（属 6b 行为面）~~ **已于 2026-09-16 裁定 = 不重跑、改用真机流量改判**（见下「本条结清」②；**该项由此不再属「6b 未覆盖」**）；② **T-3.18 的「取消是否真落在那两个窗口」未观测**（本批只换码，不含触发）；③ ~~**offline/online 两个平台仓的镜像同样漂移**——批 4 的双 Host 修复**不在任何镜像里**，本次未重建。~~ **已于同日第二阶段重建并上线，见下条**。
    **推论 2 据此订正**：原写「线上仍在产自由字符串 `error_type`」**自本次重建起失效** —— 四仓 `error_type` 白名单折叠的**码已上线**（其**行为**的真机验收状态见下「本条结清」②：**cs 已取得**，gq/sp/cc 仍无样本）。
    **平台仓镜像重建（同日第二阶段，用户拍板后执行）**：`agent-evaluation-online`（`backend`/`worker`/`frontend`）与 `agent-evaluation-offline`（`backend`/`frontend`）的镜像**同样停在 Sep 8 旧码**，本轮一并重建并 `up -d` 上线 —— 备份 5 个 `:pre-b6p`；指纹复验 **offline `app/core/http.py` ↔ `4cdc3de` MATCH**（**批 4 的 R-26 修复所在文件**）、**online `app/api/deps.py` ↔ `8f320f3` MATCH**（批 5 的写守卫）；容器 `obs-backend` / `ai-eval-backend` healthy、`obs-worker` Up，**三者 restarts=0**。⇒ **「批 4 的真机验收在平台上验不到」这一缺口就此消除**。
    **⚠️ 归属订正（我一度判错，如实记）**：批 4 的 `backend/app/core/http.py` 提交在 **offline 仓**（`15ed376`），**online 仓的 `core/` 本就没有该文件** —— 我初次比对时把「online 镜像里没有 `http.py`」误读成「镜像缺文件」，实为我搞错了仓归属，**不是缺陷**。
    **仍未覆盖（勿被本条的绿盖过）**：`BACKFLOW_ENABLED=false`（compose 默认值 + 根 `.env` 无该键）⇒ offline 的 pull_loop / reconcile_loop **依然没跑**，回流链仍无「运行中 loop」证据；详见 offline `error-backflow-task.md`「风险与关注」段。
  - ✅ **本条结清（2026-09-16，待裁 ②③ 同日拍板；**纯文档，无代码改动**）**：
    **② 裁定 = 不重跑，改用真机流量改判。** 依据（命令产出，非推断）：09-15 之后 ES `llm_call` **78 条**（ok 69 / error 9）；9 条 error = `llm_timeout`×8（cs，09-16 01:21~02:26）+ `NETWORK`×1（gq，09-15 03:17）。cs 折叠提交 `befcc90` 的 `_ERR_TYPE_MAP` 把 `TIMEOUT`→`llm_timeout` ⇒ **那 8 条是新码产出的白名单值**，其中 `fd75aa34…` 已产出 cluster 3861 并跑通全链 ①~⑥。⇒ **序号 10 原判「容量型·无输入」被推翻** —— 零候选的成因是**旧码把输入过滤掉了**（自由串不在 `LLM_ERR_TYPES`，`_layer_for` 返 None 后逐值跳过），不是量不够。**落地（4 站点同源订正）**：`docs/integration-report.md` §2 序号 10 行 + `revision-design-register.md` 「A-值域卫生」行第②层 + 本文件推论 3 + offline `error-backflow-pending-phases.md` C-1 行。**⚠️ 未验边界（不得被「已改判」盖过）**：证据**只覆盖 cs 一仓** —— gq 唯一那条 error 在重建前、sp 的 13 条 `llm_call` 全 ok、cc 零 `llm_call` 样本 ⇒ **gq/sp/cc 的折叠后行为仍无真机样本**；且**旧批 ES 证据至今仍全部来自旧码，不得回填**。
    **③ 裁定 = 只加流程约束，不加代码、不加构建期 label。** 落地 = `docs/integration-report.md` **§0 口径声明新增第 6 条**：凡以「运行实例」为证据面的条目，**取数前必先核「实例烤入提交 == 宿主 HEAD」**并把结果写进该条证据。**为什么不选 label 方案（记录理由，防后人重提）**：漂移的根因**不是查不到**（本次 sha256 比对一上午即查清），是**没有任何动作会触发去查** ⇒ 构建期写 label 只让核对变便宜、**不解决根因**；把核对绑在「以实例为证据面的验收」这个**既有动作**上，才是给出时机。**边界（如实标注）**：本约束**无自动化载体**，靠执行人遵守；`docker inspect` 上**没有**烤入提交标记，核对仍需逐文件 sha256 比对（宿主 CRLF / git blob LF ⇒ 两侧须 `tr -d '\r'` 归一）。

- **T-3.18 sp `chat()`（非流式）的 obs 记账取消窗口（已结清 — 同日改判为补齐）**（**2026-09-15 立**，源起 = 同批修「流式生成器弃用黑洞」时顺带查明；**立条时用户拍板「登记不修」，随即因下述自查而改判为「补齐」，同日落地 `4fbd631`**）：
  - **事实**：`smart-procurement/app/ai/llm/deepseek_client.py` 的 `chat()` 有两处**待取消悬点**——① 成功路径 `await self._circuit.record_success()` 在 `_obs_llm_ok` **之前** ⇒ 取消落在 Lock acquire 上时**成功调用丢 ok**；② 失败路径处理器内的 `await record_failure` / `await asyncio.sleep` ⇒ 取消时 `_obs_llm_error` 未执行，**账目半截**。`asyncio.CancelledError` 承 `BaseException`，`except Exception` 不接 ⇒ 结构性成立。上游触发与流式侧同为客户断连；唯一差别是协程没有 `aclose()`/GeneratorExit 那条独立出口。
  - **⚠️ 改判的起因（立条时我的理由错了一处，当场自查订正）**：我原以「窗口窄」判不修，但那**只对悬点① 成立**；悬点② 的窗口 `asyncio.sleep(delay)`（退避 **0.5~4s**）与流式批刚补的第二出口**同形同宽**。⇒ **拿「窗口窄」当不修理由是错的**，用户据此错前提做的决定已当场重新拍板。
  - **落地**：两处守卫 + 2 例单测（两个悬点**各自**驱动 —— 流式侧已踩过「只驱动一处时删掉另一处照样全绿」）。验证 = 全量 **370 passed**（上笔 368，+2）/ 覆盖率 **70.59%** ≥ 45% / 判别力对照两组均红（A 拆成功路径守卫 ⇒ 红在 `ok_mock.call_count==0`；B 把退避守卫的 `CancelledError` 换成 `GeneratorExit`（协程内永不触发）⇒ 红在 `err_mock.call_count==0`）。
  - **本条未验收（不得被「已结清」盖过）**：① **真机层未复验**（四仓镜像烤入点早于本批，见 T-3.17）；② **取消在真机是否真落在这两个窗口，未观测**（本批补的是「落了就不丢账」，不是「一定会落」）；③ **gq / cs / cc 三仓排查现状** = gq **已排查、判不同形**（记账在 `finally`，且该处函数体是同步生成器、无 await ⇒ 无取消悬点）；cs **同日排查并补齐**（见下条）；cc **同日排查、判不同形**（见下条）。
  - **同日续：cs 同形窗口已排查并补齐（`16f92c0`，cs 仓 `dev`，**已 push = `befcc90..16f92c0` 快进非 force**，与 T-3.18 sp 那笔同日推）**：`customer-service/backend/app/infrastructure/deepseek_gateway.py` 的 `chat()` 有**三处**（比 sp 多一处）——① 成功路径 `await _breaker_reset` ② 失败路径 `await _breaker_fail` ③ `_call` 内部（含换 Key 的退避等待）。三处**记账均已提到各自 await 之前** + `recorded` 标志防重复记；窗口③ 另加 `except asyncio.CancelledError` 兜底补记 error（**机理 = 处理器内抛出的异常不被兄弟 `except` 子句接住** ⇒ 原先直接冲出函数，既无 ok 也无 error）。窗口③ 的退避 `_LLM_RETRY_BACKOFF = (0.1, 0.2)` **窄于** sp 侧 0.5~4s，但机理同形。验证 = 全量 **403 passed / 3 skipped**（改前同套件 400）+ 判别力对照三组（分别按改前语义变异：整块记账挪到 `_breaker_reset` 之后 / 挪到 `_breaker_fail` 之后 / 关闭取消兜底）⇒ 三条各自红在对应用例断言上。**⚠️ 首轮对照是我自己的变异写错**：把 `if False: pass` 插进处理器却把原记账块留在原处 ⇒ **变异是空操作、报绿是假绿** ⇒ 变异脚本必须先断言「替换确实改动了文本」。同批暴露：失败路径的两处 `recorded = True` 因兄弟子句机理**非承载**（改动它们不影响可观测行为），承载的是「记账前置」本身。**本条未验收** = 同 ①②（`16f92c0` 未上线，镜像是旧码）；ruff 本机不可用（宿主/online/offline 三处 venv 均无）。
  - **同日续：cc 排查结论 = 不同形，本族无缺陷、不补码（仅登记）**：① **流式黑洞该仓无载体**（`contract-check/backend` 的 `app/` 全局 `grep stream` **零命中**）；② **两个 LLM 出口全同步**（`app/llm/llm_client.py` 的 `call_json`、`app/llm/tool_client.py` 的 `call_with_tools` 内 `await` / `async` **零命中**）⇒ `record_llm_ok` / `record_llm_error` 都是**普通同步语句**，**不存在「记账排在 await 之后」的悬点**，sp/cs 的修法在此无对应物；③ **执行体在工作线程**（`check_task_service.py:207` `await asyncio.to_thread(_run_flow, task_id)`、`extractor.py:528` `ThreadPoolExecutor`；cc 自陈「to_thread 的图线程无法强制中断」）⇒ 任务被取消（含软超时 `wait_for`）后线程照跑到收尾，**账晚到而非丢失**。**未取证（不据此下结论）** = `obs.py:8` 自陈 `record_llm` 强依赖 request span（`sdk _require_span` 无 span 不产事件），而 cc 的账在取消后才由线程记出——**那时 span 是否仍在属 obs_sdk 侧行为，本轮未读 obs_sdk 源码**，属**另一条链**（span 上下文，非取消窗口族）。⇒ **四仓（gq / cs / sp / cc）排查面就此闭合**。

**阶段出口**（solution §15 P2 / detail §14.3，error-only）：E-1~E-29 主链 + 修订包语义通过——其中 E-23~E-29（R-13~R-24 修订包端到端）的双端/环 2 形态在阶段 4 验收（E-1~E-22 online + offline 配套，含 §11.5 维度 3 开放验收 checklist #4/#8/#10 + 兜底吸收埋点前提用例 S-4 真实 agent 复验 + 词表覆盖度对照 §13.1 兜底逻辑盘点）。

- **T-3.19 sp `config_service.load_all()` 收尾审计日志写法错 ⇒ 启动日志「系统配置加载跳过」是假警报**（**2026-09-15 立**，来源 = 批 6a 重建 sp 镜像后翻 `sp-app` 启动日志时发现；用户拍板「登记」）：
  - **事实（全部由真机命令产出）**：`smart-procurement/app/services/config_service.py:101` 的 `logger.info("config.load_all", count=len(rows))` 传了 `count=` 关键字参数，而**本模块的 logger 是标准库 logger**（`:21` = `logging.getLogger(__name__)`，**不接受任意 kwargs**）⇒ 抛 `TypeError: Logger._log() got an unexpected keyword argument 'count'`。该调用位于 `load_all()` 的**最后一行** —— 缓存 `_cache` 填充与 `_last_full_load` 更新**均已完成之后**（`:96-101`）。
  - **级别依赖（决定了它「有时炸有时不炸」）**：标准库 `Logger.info` 先做 `isEnabledFor(INFO)` 过滤，**被过滤时根本走不到 `_log`**。实测对照（同一容器、同一镜像、同一份代码）：root 级别 = 默认 `WARNING` ⇒ `load_all: OK (no raise)`；以 `logging.getLogger().setLevel(logging.INFO)` 拉起后重跑 ⇒ `load_all RAISED: TypeError ...` **逐字复现容器启动日志**。⇒ **该缺陷仅在 INFO 级别开启时暴露**（本部署 `setup_logging` 开了 INFO，故容器每次启动必触发）。
  - **⚠️ 本条的落点与「报错」的字面相反（后续引用必须照此，勿按日志字面转述）**：`app/main.py:115-119` 以 `try/except` 包住 `config_service.load_all()`，异常统一打印 `[startup] 系统配置加载跳过: {e}`。但**同一次调用中实测 `_last_full_load > 0` 为真**（该赋值在抛异常的日志行**之前**执行）⇒ **缓存实际已填充完毕，配置并未被跳过**。**「跳过」是假警报**。**我最初照日志字面判「系统配置整段被跳过」，已被自己的探针推翻**，登记口径以此处的订正版为准。
  - **真问题（这才是值得修的理由）**：① `main.py:119` 的**同一句话承载两类互斥失败** ——「加载真失败」与「加载成功但收尾日志写法错」，**二者不可区分**；且 `except` 分支只 print、不 re-raise ⇒ **真失败时同样打印「跳过」且启动照常**，排障时无法据日志判定到底哪一类；② 被吞掉的是 **TypeError 而非配置错误**，掩盖了「本模块 logger 用法与其余模块不一致」这一事实（sp 其余模块用 structlog 风格 `logger.info("event", key=...)`，此处**混用两种日志库**）。
  - **现状与边界（2026-09-15 当刻）**：**本批只登记，未修**。修法极小（改标准库风格 `logger.info("config.load_all count=%d", len(rows))`，或统一换 structlog），但改的是 sp 仓**运行期代码**、需重走单测与镜像重建，按「一批一验收」另立。**行为影响 = 零**（缓存已填充；`get_all` 的 TTL 兜底路径同此理）；**不进上线门**。**⇒ 已于 2026-09-16 修复并推送 `de5a77b`（sp 仓），见下条续记。**
  - **未取证（不得据本条外推）**：① **未全仓 grep** sp 其余模块是否还有同型「stdlib logger 传 kwargs」调用（本轮只看 `config_service.py` 这一处）——**2026-09-16 已取证，见下条续记**；② 未核「`system_config` 表零行」是否另有问题 —— 实测 `cache_size_after: 0` 指表内无自定义行，与模块 docstring「DB 只存有自定义值的行，未覆盖的键回落默认值」的设计**一致，属正常**。
  - **2026-09-16 续：已修并推送（sp 仓 `dev`，`de5a77b`；**已 push = `4fbd631..de5a77b` 快进非 force**）**：
    - **修法（用户拍板选 A）** = 换 structlog 绑定：`config_service.py:21` `logging.getLogger(__name__)` → `structlog.get_logger()`，`import logging` → `import structlog`（按 ruff I 规则归入第三方块），与 sp 其余 **39 文件**同款。**未选** stdlib `%`-格式改法 —— 那只治 `:101`，`:159` 的 `keys=[...]`/`operator=` 仍需另改，且在同一文件里留下第二种写法。**连带**：`pyproject.toml` 的 `[tool.pytest.ini_options]` 加 `log_level = "INFO"`。
    - **⚠️ 补记原登记遗漏的症状（本轮排查新发现；原登记只覆盖 `load_all` 启动路径）**：**写路径 `PUT /config` 返回 500** —— `app/api/v1/config.py:63` 只捕 `ConfigError`，`set_configs` 收尾 `:159` 的同型 TypeError 穿透 ⇒ 500；而**配置实际已生效**（`session.commit()`(`:152`) 与 `flush_score_cache`(`:155-158`) 均在抛错行之前）⇒ **用户可见的「报 500 但已改成功」不一致**。**⇒ 原登记「行为影响 = 零」只对启动路径成立，写路径有用户可见症状。**
    - **补记原登记「未取证①」（现已取证）**：AST 扫全仓 `logger.<level>(...)` 是否传非 `%` 位参数 + 逐个判定 logger 绑定形态 ⇒ **sp 恰 2 处**（`:101` `count=` / `:159` `keys=`+`operator=`），**gq / cs / cc 各 0 处**；绑定形态 = 39 文件 `structlog.get_logger()`、2 文件 `logging.getLogger`（含本文件）、**零导入期绑定**（假设漏洞已封堵）。
    - **判别力证据（三级，缺一不可）**：① **改前**：默认级别 `pytest tests/unit/test_config_service.py -q` = **7 passed**，同命令加 `-o log_level=INFO` = **2 failed / 5 passed** ⇒ **既有测试本就覆盖这两处，是日志级别把它挡住了**（`isEnabledFor` 为假 ⇒ `_log` 不被调用 ⇒ kwargs 被静默丢弃）；② **改后**：两跑法均 **7 passed**；③ **反事实** = 把绑定临时还原为 stdlib，在**加了 ini 项的默认跑法**下自报 **2 failed / 5 passed** ⇒ ini 项确实堵住盲区（非摆设）；还原后残留 0。
    - **回归与静态检查**：全量 `370 passed / 118 deselected`（与加 ini 项**前**逐字一致）；ruff 借 online venv（**sp venv 无 ruff**）逐规则对照 —— 改动文件 HEAD 版与工作区版**均 `All checks passed`** ⇒ **零新增**。（全仓存量 **321** 处红，非本批引入、未处理。）
    - **⚠️ 订正上条续记的误判：真机层已于同日复验通过，且「需 sp 镜像重建」不成立**：`smart-procurement/docker-compose.yml:78` 的 `- ./app:/app/app:ro` 表明 **`app/` 是 bind mount** ⇒ 宿主源码改动**无需重建镜像**，只需重启容器（本次 `docker compose up -d` 输出**无任何 build 步骤**）；`de5a77b` 改的 `app/services/config_service.py` **正在挂载范围内**（`pyproject.toml` 不在，但那是测试配置、不进运行期）。
    - **真机验收证据（2026-09-16）**（下引行号为**验收当时** `docker logs sp-app | grep -n` 的序号，日志增长后会变 —— **定位以事件内容与时刻为准，勿据行号回查**）：
      - **启动路径 = 同容器内前后对照**（最强档）：`RestartCount=1`，日志是**同一容器实例**的连续流（镜像、挂载点均未变），仅代码不同 —— 行 **41**（10 小时前，旧码）`[startup] 系统配置加载跳过: Logger._log() got an unexpected keyword argument 'count'`；行 **614**（今日，新码）`{"count": 0, "event": "config.load_all", "level": "info", "timestamp": "…"}` **且无「加载跳过」** ⇒ 症状消失 + 事件**真打出来了**（非被 structlog 静默丢弃）。
      - **写路径**：`PUT /api/v1/config`（body `{"items":[{"key":"llm.temperature","value":0.3}]}`，取当前值以免改状态）返 **HTTP 200**；日志同时打出 `{"keys": ["llm.temperature"], "operator": "U-001", "event": "config.set", …}` —— **该行即 `:159`**，其正常打出 + 200 直接证明 500 成因已消除。
      - **⚠️ 证据分档（勿混为一谈）**：写路径**没有**「旧码实测 500」的对照（10 小时前未打过该请求）；「旧码必 500」由三条合成 —— 本仓单测反事实（stdlib 绑定下 `-o log_level=INFO` = 2 failed）+ 真机行 41 证明**同类调用在真机确实抛同型异常** + `api/v1/config.py:63` 只捕 `ConfigError`。
      - **验收副作用（如实记）**：为验写路径**真的写了一次** `llm.temperature=0.3`（值未变，但 `updated_at`/`updated_by` 被刷新为 U-001）。
      - **环境状态**：为验收拉起了整套共享 infra + sp 三容器（此前 **26 个容器全 Exited**，Docker Desktop 未运行）。
    - **同批发现、与本案无关（仅登记）**：ⓐ sp 全量跑法有个坑 —— `pytest`（无参、走 `testpaths`）在**收集期**即中断（`Defining 'pytest_plugins' in a non-top-level conftest`），根因 = `tests/unit/conftest.py:14` 的 `pytest_plugins = []` 在 configure 之后才被导入；**必须带参数** `pytest tests/unit tests/integration`（370 passed）。ⓑ **sp 的 pre-commit 覆盖率门禁是真跑的**（`app/` 布局 + `tests/unit` 在场，**未**落入 `backend/` 布局那条死代码），本次报 370 passed / 70.59% ≥ 45%。

---

## 阶段 4｜集成测试与端到端验收（富化）

> 目标：把阶段 1~3 的**单元级产物按真实依赖串起来**，验证跨模块/跨平台/跨环境行为，覆盖 detail §14.1~§14.4 全量用例 + 部署/网络/安全/前端联调。此阶段**只验收、不新增功能**，发现缺陷回退对应阶段修复后重跑。
>
> 运行环境约定：backend/frontend 走主 compose（真实部署形态，不含中间件）；**中间件全连本地共享 infra（../infra，2026-09-03 决策：ES/Kafka 直接在 share-infra 创建；online 侧落权对象 = 本地 share-infra，MySQL 分库 + ES/Kafka 租户前缀隔离）**；本阶段对端场景（T-4.2/T-4.6/T-4.13⑤ 等）在环 0/环 1 绿后于环 2 串（见联调闭环小节）；故障注入以本地 infra/编排层注入优先（停容器/断网段/杀 broker 进程），污染共享实例风险高时用独立 dev 实例兜底，`compose.infra.dev.yml` 不作主线。
> 每任务出口 = 该组用例全绿 + 对应缺陷单清零 + 在集成报告登记。
> **异常与边界死角覆盖口径**：分三层归位——**infra 层故障注入** = T-4.7（E-18~E-21）；**脏数据/畸形输入/检索/平台间契约/埋点前提** = T-4.13（新增）；**时序/窗口/数量级/并发/词表死角** = T-4.14（新增）。T-4.13/T-4.14 含 detail 已编号用例的集成复验 + task.md 追加补充场景；追加场景已编号化为 **detail §14.5 X-1~X-13**（T-4.13 组 ①~⑥ = X-1~X-6、T-4.14 组 ①~⑦ = X-7~X-13），T-4.13/T-4.14 为 X 系列来源容器、验收以 X 编号为权威口径，防用例口径漂移。
>
> **⚠️ 完成状态的权威源（2026-09-15 立，防「两处记载打架」）**：本段 **T-4.1~T-4.14 是任务定义**，其**完成/剩余状态以 `docs/integration-report.md` §2「真剩余」表为权威**（该表用删除线逐条记录已完成部分与残留）；`task.md` 内**只对例外条目**做回填（如 T-4.7、T-4.10）。⇒ **读到某条无回填 ≠ 该条没做**，先查 report §2。（立此规的来由：2026-09-15 全量盘点时，「task.md 无回填」被误读为「做完没勾」，实为**分工不同** —— 照误读去补 11 处回填，会在本仓造出**第三份**完成记录。）

- **T-4.1 链路与冒烟集成（S-1~S-5）**：跨 consumer→ES→API→前端 全链路复验冒烟用例，含真实前端渲染。**验证目标**：S-1~S-5 在集成环境全绿；trace 详情页大 trace 懒加载不卡；关键字检索限 7d/超时/上限在网关侧同样生效（**2026-09-11 裁定：「网关侧」下移 T-5.3 上线门**——阶段 4 环境无网关，且环 2 明写「不经公共网关」；7d/超时/上限的**后端侧**行为仍在本条验）。
- **T-4.2 error 回流主链端到端（E-1~E-4）**：制造透传 LLM 错误 → L1 落 cluster → 自动组装信封（含 no_fallback_config）→ link=assembled → **offline 定时 pull**（真实 offline 仓）→ 结构自检激活 → 回归 run → **offline 结果推送（`POST /backflow/regression-results`）** → 看板状态流转。**验证目标**：E-1/E-2（含 OR 门控兜首次 llm_call 前程序错误）/E-3（重试自愈不回流）/E-4（窗口内不重复）全绿；时间线在聚类详情可视化正确。
- **T-4.3 词表守卫与重推自愈（E-5/E-6/E-22）**：词表空 → fail-closed（结构自检不过、判 inconclusive 不静默 pass）；词表命中 → no_fallback fail；offline 驳回（能力缺）→ online 展示重推状态；admin requeue（内容缺）→ 复位 assembled 重新可拉。**验证目标**：E-5/E-6/E-22 全绿；payload 内词表快照与当前 dict_config 变更互不 retroactive 影响已激活 case；requeue 防抖 ≥5min 生效。
- **T-4.4 人工处置 / 结果推送判定 / reentry / 终态守卫集成（E-7~E-10、E-17）**：claim 填 fix_version → 回归 run → **单错级判定**（同 run 他错仍红不阻塞）；TTL 超窗回退；fixed 后再 claim 新版本 → 同 cluster 新 link（新 payload_id）；reentry 复发反馈；终态只读。**验证目标**：E-7/E-8/E-9/E-10/E-17 全绿；CAS 并发（双 admin/viewer 同时置状态）无覆盖竞态；conversion_record 审计链完整。
- **T-4.5 判定执行方与积累态集成（E-13/E-14/E-16）**：残 trace（root 未达）按子节点判定；SSE/分批到达等窗口补全；`judge_scan_job` 到期补判（judged=0 ∧ ttl_until≤now → classify → judged=1）不重判；多实例并行消费幂等。**验证目标**：E-13/E-14/E-16 全绿；judge_scan 调度与 job 单飞在双实例下验证。
- **T-4.6 平台间契约集成（E-11/E-12/E-15）**：offline 停摆（pull 停）→ assembled 已待 N 天超阈值**提示性标记**（不自动告警、不设 online 时钟）；offline 恢复继续拉取不丢（含恢复积压限速/按序拉取）；pull/ack/回写重放幂等。**验证目标**：E-11/E-12/E-15 全绿；恢复后无一次性灌入大量陈旧 case 的峰值（限速生效）；双时钟不引入。
- **T-4.7 故障注入（E-18~E-21，对应 detail §14.2 三连）**：**Kafka broker 停** → consumer 停拉退避挂起（不提交空推进）→ 恢复续拉不丢、判定态补齐；**ES 不可用** → 事件落待补写 spool 或显式丢弃 + rollup 缺口标注，判定/聚类/回流不受影响；**MySQL 不可用** → 判定态写失败**不提交 offset + 退避自监控**（禁"丢弃并提交"）；**网关/offline 不可达** → **（v1.23 改被动探测，对齐 detail §14.2 E-21）**online 已无出站调用，「回查退避重试 / 超上限」这一触发源**已消失**；改为「**超时未收到结果推送**」判定——claim 侧以 `claim_ttl_expire` 转换记录 + 残留 `fix_version`  ∧ 现行 pending link 零 `verify_run_record`、或 assembled 待 N 天超阈 → 统一提示「回查结果未达（疑似 offline 停摆），人工核查」；不设 online 时钟。**验证目标**：E-18~E-21 全绿；各注入点 selfmonitor 计数可见；恢复自愈无需人工干预（除显式告警项）；**offline 停摆场景须验「标记出现且不误报」两向**（含 detail §8.7 的四个抑制条件）。
  - **执行结果回填（2026-09-13 / 2026-09-14；证据 = `docs/integration-report.md` §1 / §2 序号 1 / §6 F-4、F-13）**：**E-18 Kafka / E-19 ES / E-20 MySQL 三条已于 2026-09-13 真机注入全部通过**（E-20 是 E-19 的反向分支：允许丢+计数 vs 明令禁止）；**E-19 的「该小时 rollup 缺口标注」半边已于 2026-09-14 定性 = 设计要求明确、本仓无实现对象**（F-13，阶段 4 不补实现，**非「未验」**）；**E-21 自 v1.23 起即 offline 停摆被动探测、不含网关注入**，其判据面已由 `push_probe#S-7`~`#S-12` 覆盖（§1）⇒ **本条无剩余项**。
  - **⚠️ 标题注订正（2026-09-14）**：原标题括号内曾写「『+ 网关』已于 2026-09-11 裁定下移 T-5.3 上线门」——**归因错**，**已删**。下移 T-5.3 的网关半边**只属 T-4.1 / T-4.9**；E-21 的触发源是在 v1.23 改被动探测时**即已消失**（「online 已无出站调用」），**与网关无关**（detail §14.2 E-21 行 2026-09-11 订正逐字声明「本行标题的『网关』不含网关注入」）。报告 §2 序号 1、§4.1 连带影响两处同源错已一并订正。
- **T-4.8 性能护栏验收（§14.4 全量判据）**：rollup 迟到重算幂等 + t-digest 合并误差；O-1 缓存/超时护栏；检索/看板限流熔断；写侧 P95；job 单飞。**验证目标**：全站 24h agg P95 ≤5s；`metric_agg_cache_ttl_s=60` / `metric_agg_timeout_ms=3000` 生效；trace 检索 `trace_query_timeout_ms=3000`、命中 ≤200；判定态表单行 upsert P95 ≤10ms；rollup 每小时 ≤2min；**t-digest 跨小时合并 vs 全量重算 p95 误差 <1%**；索引/聚合在 500 事件/s 档下无告警。
- **T-4.9 部署/网络/网关与公共 infra 联调**（**2026-09-11 网关归属裁定**：本条的**网关半边**——公共 API 网关拓扑、终止 TLS、`{env}` 子域/路径、前端登录走网关、SSO 透传，以及验证目标里的「E-21 网关场景全绿」「绕过网关直连 backend 被拒」——**整块下移 T-5.3 上线门**。依据 = 环 2 明写「契约内网直连不经公共网关」（`task.md:41`）+ `task.md:50`/`:173`「网关 SSO 是上线门、不阻塞 dev 联调」+ `docs/infra-access-matrix.md:51`「网关/SSO = 上线门（T-5.3）」。**⚠️ 2026-09-11 二次订正（初版依据句有误，已作废）**：初版写「阶段 4 环境**物理上无网关**（仓库零网关实现产物）」——**错**：只查了 online 仓、未查 infra 仓；真相 = shared infra **已有**公共 API 网关运行时（`../infra/api-gateway`，nginx `listen 8099` / `{name}.local`），但**无 online 的 server 块与 upstream**（online 接入尚未发生）。**故理由收窄为一条**：阶段 4 的联调形态（**环 2**）设计上即「内网直连不经公共网关」，**要验网关必须先改环 2 的定义，而改联调形态不属于「只验收、不新增功能」**。**❗显式声明：这不是能力限制，是边界划分**——网关运行时已存在、online 侧加一个 server 块即可验（`resolver 127.0.0.11` + `set $upstream` 运行时解析，加完即生效），**日后不得拿本条当「做不了」的证据**。**⚠️ 2026-09-14 收窄（实测）**：上句**只对「转发面」成立**——实测 `infra/api-gateway` 仅 `listen 8099` 明文、**无 443 / 无证书 / 无 `auth_request` / 无 JWT 模块** ⇒ 「加一个 server 块」能解决**路由可达**，**解决不了** §17 #14 里的「终止 TLS / 鉴权 / backend 仅接受网关来源」三项；**「网关就位」≠「§17 #14 已落」**。另：`online` 在网关侧**零 server 块、零 upstream**（`eval.local` 指的是 **offline**），故「online 接入尚未发生」这半句仍准。详见 `docs/infra-access-matrix.md` §4 提问单。**保留语**：若后来决定把网关提前到阶段 4，则该改的是环 2 自己的定义，本条需翻案并补「网关就位」前置。非网关半边仍在本条验）：交付物边界（仅 backend+frontend）；`.env` 注入与凭证不入镜像；`{env}.` 前缀在库/index/topic/consumer group 全链路一致；**公共 API 网关**（终止 TLS、`{env}` 子域/路径、内部 JWT、前端登录走网关）；offline↔online 平台间走内网不经公网网关；backend 容器不映射 3306/9200/9092；浏览器仅达网关。**验证目标**：E-21 网关场景全绿；绕过网关直连 backend 被拒；SSO 敲定项（§17 #14）按定案复验（最简：登录取代网关 SSO；若强制 SSO → 带签名身份透传头验签）；`{env}` 值域与 infra 登记一致。
- **T-4.10 安全集成验证（solution §12 + detail §13 全块）**：平台用户域——JWT 短效 access + refresh、**token version 吊销即时生效**、口令散列 + 失败锁定、admin 禁用即吊销、viewer/admin 前端拦截 + 后端二次鉴权；agent 上报域——Kafka SASL/TLS + topic ACL（每 agent 凭证隔离、topic 不可互写）、消费侧未授权 topic **丢弃并计数告警**、agent_credential 加密轮换、每 agent 上报/回流量级速率闸；平台间——双向认证 + 最小 API 面（pull-API case_type 白名单，非白名单返回空集）。**验证目标**：越权访问被拒（角色矩阵）；伪造 topic 投毒被 ACL 挡 + 告警可见；吊销后旧 token 立即失效；凭证轮换不中断消费；速率闸触发阈值熔断。
  - **执行结果回填（2026-09-14；证据 = `docs/integration-report.md` §6 F-21）**：**平台间半边（pull-API `case_type` 白名单 + 鉴权 fail-closed）已部署层复验 6/6 通过**——经前端 nginx `:18080` → `obs-backend:8000` 真机 HTTP：无 Bearer / 错误 Bearer → **401** `ERR_PULL_0001`（两种文案可区分）；正确 Bearer + 白名单 → **200**（**库内确有 4 条可拉**）；正确 Bearer + 非白名单 → **200 空集**（非 400、非全量；**先种数据造对照才有判别力**）；错 `schema_version` → **400** `ERR_PULL_0002`；`ack` 真 payload → **200** 且 **DB 复核 `offline_status=draft`**。**配置订正**：`EVALUATOR_SERVICE_SECRET` 的生效来源 = **根目录 `.env`**（compose 插值），compose 注入的**空 env var 会遮蔽 `backend/.env` 的文件值**（pydantic-settings 优先级 env > file）⇒ 只写 `backend/.env` 时**静默不生效**（实测容器内 `len=0`）；落点已收敛为**单一来源**，重建后 `len=64`。**本条其余半边**（JWT 短效/吊销、口令散列 + 失败锁定、Kafka SASL/ACL + 未授权 topic 丢弃计数、凭证加密轮换、每 agent 速率闸）**已于 2026-09-13 经 F-8 裁定整体下移 T-5.3**，不因本条复验改变归属。**未验边界**：宿主直连 backend 端口（该端口当前未映射、形态不存在）、凭证轮换执行动作（属 T-5.3）。
- **T-4.11 前端端到端联调（§9.3/§9.4 全条）**：登录 → 菜单按角色渲染；看板/链路/回流三类页与 API 数据联动；状态文案逐条（assembled/draft/invalidated/claim 倒计时/pending-fix 标注"近似 offline 权威集"）；空态（全站无数据不误读、二期入口隐藏不灰置）；**needs_review v1 边缘出现**（claim 回归 error run 结果行的判定产物才出现：na 结果行 → reason `na`；reentry 同版本 claim 旧 run pass 行 → reason `reentry_same_version`；复现输入截断 → reason `input_truncated`——**三者皆 claim 级单条走 cluster 级 `needs-review-resolve`**；**`unclean_run` 不入 `needs_review` 态**（只经 `needs_review_batch` 批载体、批引 cluster 保持 claim，v1.8 R-14），reason 值域 = **{na, reentry_same_version, input_truncated}**（⚠️ 2026-09-14 订正：原写 `{na, unclean_run, reentry_same_version}` —— **`unclean_run` 不入 needs_review 态**（只经 batch 载体，v1.8 R-14 / `claim.py:9`）、且漏了 `input_truncated`；权威 = `claim.py:32 REVIEW_REASONS`，见报告 §6 **F-20**），§10.5）。**验证目标**：detail §9.3 关键交互逐条通过；浏览器端无死功能入口（F1/F3/F4 收敛验证）；admin 操作留审计。
- **T-4.12 回归门禁口径与维度 3 开放验收（solution §11 + §13.0 checklist）**：发布回归硬门禁并列口径在 offline 集成环境验证；error 用例技术判定 ∧ no_fallback 词表断言合成 pass_fail；`fallback_utterance` 词表覆盖度对照 §13.1 兜底逻辑盘点（新增兜底话术即补词表）；checklist #4/#8/#10 放量门禁 + 维度 3 开放验收两档各过。**验证目标**：回归假绿（换词/变体/动态前缀）在词表残余承认范围内可观测（§16 登记）；门禁 fail-closed 生效；维度 3 开放验收通过后才放开回流白名单。
- **T-4.13 异常场景集成（脏数据/畸形输入/检索/契约/埋点前提；组 ①~⑥ = 验收用例 X-1~X-6，detail §14.5）**：把"坏输入"与"异常流"按真实依赖串起来验证，防各组件单测各绿、串起来错。覆盖——① **消费侧 schema 异常**：缺必填字段/字段类型错/多余未知字段/整体 null 事件 → S-2 拒绝路径集成复验（丢弃 + selfmonitor 计数）；topic 与 agent 不匹配、白名单外 agent 事件拒绝（detail §4.2）；② **脱敏死角（§4.5）**：脱敏键不存在、值已是掩码形态、超长值、嵌套异常层级 → 不炸、不二次脱敏、可追踪；③ **埋点前提（§4.2/§5.1，对应六方向评审 Finding 4 口径）**：制造一次 LLM 裸调用失败被业务 catch 转兜底返回 200 → 断言 `request ok + llm_call status=error` 先记后传、trace 子节点红显、失败率计数不丢（与 T-2.5 的 S-4 真实 agent 复验呼应）；④ **检索注入与转义**：关键字含引号/通配符/保留字符/中文分词边界词 → 查询不报错、不误命、不返回错误 scope；search_after 末页后再翻稳定返回空；⑤ **平台间契约异常**：pull-API 收到 case_type 非白名单 → 返回空集；schema_version 不匹配 → 拒单并计数；回写字段非法/状态越界 → 幂等拒绝不污染状态机；⑥ **大对象边界**：payload 超 Kafka 上限、evidence 实文恰 8K/超 8K 截断、缺 input 残现场只计数（E-13 集成复验）。**验证目标**：①②⑤⑥ 各异常路径丢单有计数、不误入正常链路；③ 前提用例通过（基础可见性从承诺变验收）；④ 检索注入无异常无越权 scope；所有注入点恢复后自愈、无静默吞错。
- **T-4.14 边界死角场景集成（时序/窗口/数量级/并发/词表；组 ①~⑦ = 验收用例 X-7~X-13，detail §14.5）**：专盯"临界值、边界条件、竞态窗口"三死角，与 detail 已编号用例互为补强。覆盖——① **时间边界**：事件 ts 为未来/1970/UTC 与本地时区交界 → 周 index 归属与 date_histogram 分桶正确；跨周切换事件落在前后两周的检索去重不重不漏（§2.1 周滚动）；② **窗口边界**：error 同键恰在 7d 聚类窗边缘再现（第 7 天 vs 第 8 天）→ count+1 vs generation 新开（E-4 补强）；指标窗恰 24h（实时）与 24h+1s（rollup 路由切换）；rollup 迟到恰 6h 幂等重算、超 6h 不再重算、缺桶回退实时 + 页面标注、尾小时实时补齐（§5.3）；③ **判定时序边界**：judge_scan 到期瞬间补判、重复到期不重判（E-16 补强）；④ **数量级边界**：trace 检索命中恰 200 与超 200 截断、末页后翻；单 trace 日志上万行首屏懒加载不拉爆（S-5 补强）；⑤ **并发/竞态边界**：双实例同 offset 不重复建（E-12 复验）、CAS claim/requeue 与 offline pull 并发、requeue 防抖恰 ≥5min 边界、ack 幂等重放与并发拉取交错（E-15 复验）；⑥ **词表边界死角**：空表/极短表 fail-closed（E-5 复验）；动态前缀/拼接/大小写/换行/空白差异/超长词/重复词在词表残余承认范围内行为可观测（§16 登记口径，不要求全拦，要求"假绿时可被抽查发现"）；⑦ **保留期边界**：ILM 30 天删除后检索与看板缺口标注行为（衔接 T-5.2）。**验证目标**：①②③⑦ 边界值两侧行为各按预期、无越界错配；④ 限值/上限行为稳定不报错；⑤ 并发交错无覆盖竞态、审计链完整；⑥ 假绿残余可观测可抽查、fail-closed 生效。

- **T-4.15 「7d 聚类窗口」设计要求、实现为零 —— 登记项**（**2026-09-15 立**，来源 = 当日全量盘点；性质同 T-3.15/T-3.16 = **登记项**，不是验收任务）：
  - **事实（均由命令产出）**：detail §6.2 要求「同键持续静默超窗 → cluster 转 inactive」，实测**整条未实现** —— `cluster_window_days` 在代码内**零读取点**（全仓唯一写点 = `backend/app/core/seed.py:46` 的默认值）；`analyzer/cluster.py` 候选取数零时间谓词；`pick_merge_target` **不接收时间输入**；`inactive` 唯一赋值点 = 人工 `ignore`。⇒ 验收用例 **X-8 前半「第 7 天 vs 第 8 天」无判别对象**（report §6 F-12 同判）。
  - **为什么要立本条**：该缺口**此前只存在于 `docs/integration-report.md` §6 F-12**（含 2026-09-14「本阶段不补实现」的拍板），`task.md` **无任何条目** ⇒ **光读台账读不出这个缺口**。本条目是**补登记，不是新增需求**。
  - **待裁**：补实现 / 维持「只登记不修」。判据同 T-3.15：答不出「不做会出什么**具体**故障」就不做 —— 目前能答的是「`inactive` 永不自动发生 ⇒ 聚类只能靠人工 `ignore` 收敛」，**是否构成故障待定**（这是它至今未被判为欠债的原因）。
  - **同族三条（处置口径宜一并裁定）**：F-12（本条）· F-13 rollup 缺口写侧标注（会话台账 `#228`）· F-18 `result_overdue` 前端呈现（`#227`）—— 同属「**阶段 4 发现的设计要求无实现对象**」，性质与「前提不可达」「容量型」均不同。

**阶段出口**：S-1~S-5、E-1~E-29、性能护栏判据全绿（E-23~E-29 修订包端到端于环 2 串，依赖 **offline 侧结果推送面就位**——`POST /backflow/regression-results` 按 §8.7 载荷表投递，含必填 `prev_terminal_version`；**R-4/R-5 只读面已随 v1.23 整体作废，不得再作为依赖项**）；T-4.13/T-4.14 异常与边界死角补充场景全绿 = detail §14.5 **X-1~X-13 全绿**（追加项已编号化回填，以 X 为权威口径）；安全/部署/前端联调通过；所有缺陷单清零并回归；输出一份集成测试报告（用例→结果→缺陷溯源映射，对应 detail §14.3）。

---

## 阶段 5｜上线放量与运营

- **T-5.1 灰度放量门禁**：按 solution §13.0 checklist 放量门禁档逐步放 agent 流量；观察窗内核对无告警、无漏采、指标口径与预估值一致。**验证目标**：checklist #1~#3 放量档全绿；观测数据连续 7d 无断档。
  - **状态（2026-09-14，用户拍板）= 环境无输入，归并 `#219` 跟踪**（**「环境无输入」指缺真实流量 / 长周期 / infra 回执，不指缺 agent** —— ⚠️ 2026-09-16 订正见下）：**不记「未验」，记「无法开工」**——本条要的是**真实用户灰度流量**与**连续 7d 观测窗**，本环境两者皆无（~~无真实 agent 接入 = 卡 `T-2.5`/`S-4`~~ —— **⚠️ 2026-09-16 订正**：**agent 接入已成立**（四容器在跑 / 契约全 200 / obs_sdk 全接入 / offline 已真打并出分）；**卡点重述为「缺真实用户流量」**，`T-2.5`/`S-4` **不再是本条前提**。**结论不变 —— 仍无法开工**）。**开工所需输入**：① **真实用户流量**接入并分流（agent 侧接入已就绪，见「真实 agent 端到端联调验收（2026-09-16）」）；② ≥7 天不间断运行窗口；③ 放量档定义（solution §13.0 checklist #1~#3）与预估值基线。**⚠️ 不得以「本地造流量」替代**——容量/灰度类判据在量级不足时跑绿 = **把无判别力包装成有判据**（同 [[criterion-structural-vs-capacity]] 的两次教训）。
- **T-5.2 容量与索引实测**：Step 3 灰度实测定容量档（≤500 事件/s 档核对、租户分配档确认）；index 周滚动 + ILM 30 天真实删除验证。**验证目标**：容量档与 infra 实际分配一致（solution §7.1 容量行）；ILM 到期删除有测试数据佐证；rollup/实时双路在该档下 P95 达标。
  - **状态（2026-09-14，用户拍板）= 环境无输入，归并 `#219` 跟踪（`#219` 的容量型批次 6 条 + 本条三项 = 同一批）**（**⚠️ 2026-09-16 订正**：本条的输入**与 agent 接入无关** —— 三项分别缺「infra 分配回执 / 真实量级 / 时间」，agent 接入成立与否都不改变它们；「环境无输入」此处只是对 `#219` 整批的统称，**逐项内容全部有效、不因该订正而失效**）：**逐项拆「缺什么输入」**——① **容量档/租户分配** = 缺 **infra 的实际分配回执**（本地无论如何压不出「与 infra 分配一致」这个结论，压测完了仍要重测）；② **≤500 事件/s 档核对** = 缺**真实量级**流量（本地造流 ≠ 该档）；③ **ILM 30 天真实删除** = 缺**时间**（policy 已登记 `min_age: 30d`，`es-template/obs-ilm-policy.json:15-20`，但**「到期真删」只能等真实到期**——调小 `min_age` 去"验证"属于**改配置 + 改变了被验对象**，**不做**；`T-4.14 ⑦`「保留期边界」同此，已在 :181 标「衔接 T-5.2」）。**⚠️ 不得以「缩短 min_age 验一次」代替**：那验的是**另一条 policy**，不是上线要跑的那条。
- **T-5.3 与 infra 收口**：网关/SSO 定案闭环（§17 #14）；**网关联调与验收**（**2026-09-11 自阶段 4 下移**：公共 API 网关拓扑落地、终止 TLS、`{env}` 子域/路径、前端登录走网关、SSO 透传验签，以及原 T-4.1「网关侧生效」/ T-4.7「E-21 网关场景」/ T-4.9「绕过网关直连 backend 被拒」三项断言的验收）；env 值域与命名登记生效（§17 #15）；topic ACL / ES template / 网络策略回执三方核对；**操作面契约收口（T-0.2 交付物核销）**：服务账号权限矩阵 ①~⑤ 与 rollup 写归属、consumer group 操作面、变更通道 SLA 回执复核，权限变更申请单归档。**验证目标**：§17 #14/#15 两行由"待敲定"转"已落"并在 solution.md 标注；T-0.2 矩阵/回执项全部核销、无未决变更单；上线时任一待办残留则阻断放量。
  - **定案进度回填（2026-09-14；证据 = `solution.md` §17 #14 行 + v3.5.12 修订记录 + `docs/infra-access-matrix.md` §4）**：**§17 #14 已拆半**——**#14a（SSO）已定** = 平台内部自持 JWT、**登录取代网关侧 SSO**（依据 = 实测实现已符合：`core/security.py:18/38/49-56` HS256 access 15min + 不透明 refresh 7d、`deps.py:26-35` 只读 `Authorization: Bearer`、全仓零网关注入头依赖 ⇒ **零实现成本**；备选「infra 前置 SSO + 签名透传头 + 验签」**当前不可实现**——infra 全仓 `oidc|oauth|sso|keycloak|casdoor` **零命中**、compose 无认证服务、**无对接对象**）；⚠️ **该定案带条件、非永久**（若 infra 强制前置 SSO 则按备选重定）。**#14b（网关拓扑）仍待 infra 回执**——四点提问单见 `docs/infra-access-matrix.md` §4（TLS 终止层 / online 是否需 server 块 / 「backend 仅接受网关来源」落哪层 / `{env}.` 与 infra `{name}.local` 命名维度关系）。**事实面订正（勿沿用旧口径）**：`task.md` 本节早前句「网关运行时已存在、online 侧加一个 server 块即可验」**只对转发面成立**——实测 `infra/api-gateway` 仅 `listen 8099` 明文、**无 443/无证书/无鉴权**、**online 零 server 块**；且**「backend 仅接受网关来源」在 online 侧是零实现**（无 `TrustedHostMiddleware`/来源校验，仅有「backend 不映射宿主端口」部署缓解）⇒ 本条「绕过网关直连 backend 被拒」断言**当前无实现对象**，落地形态待 Q3 回执后分工。
  - **容量/灰度批次的归并声明（2026-09-14，用户拍板）**：**`T-5.1`（灰度放量门禁）与 `T-5.2`（容量与索引实测）已归并至本条（`#219` 批次）统一跟踪**——理由 = 二者与本条接收的容量型批次**缺的是同一类输入**（真实流量 / 长周期真实到期 / infra 实际分配回执）。**⚠️ 归并 ≠ 降级**：两条的**验收目标原样有效**（见各自条目的「状态」注），**不记「未验」而记「环境无输入、无法开工」**（**⚠️ 2026-09-16 订正**：「环境无输入」= 缺**真实流量 / 长周期 / infra 回执**，**不指缺 agent** —— agent 接入已证实成立），并已逐条写明**开工所需输入**。**故本阶段（阶段 5）的出口不因这两条而未达成——它们是「无输入则无法开工」而非「有输入未做」**；此区分须在阶段 5 复盘时据实引用，**不得**据本条把「未做」写成「已验」或反之。
- **T-5.4 运营清单与交接**：TTL 告警/顶置提示 owner 明确（offline 拉取/确认 owner 归 offline；online 仅"已待 N 天"展示不设时钟）；保留期与审计导出；看板口径文档（双指标、rollup 缺口标注语义）交付；**回归假绿残余承认 + 词表维护流程**（新增兜底话术即补词表、admin-only 留审计）写入运营 SOP。**验证目标**：运营手册与实现行为一致；维度 3 开放验收项（checklist #4/#8/#10）在真实 agent 上最终复验通过。
  - **交付回填（2026-09-14；证据 = `docs/ops-manual.md` + `docs/integration-report.md` §6 F-23）**：**已交付 `docs/ops-manual.md`**（此前全仓**无任何 SOP/runbook 成品件**）——形态 = **每节带「实现现状」栏**，故本条的验证目标「手册与实现行为一致」**在写作层面即可核**。
    - **✅ 已达成的交付项**：① 归口一览（§0，含「无告警通道」「不设 online 时钟」两条否定口径——`api/backflow.py:320/421` 逐字「不落列、不设时钟」，`waiting_days` 是**展示值、不触发动作**，运营期**不得当告警用**）；② 看板口径文档（§4：双指标 `request`/`llm_call` 语义 + 「LLM 级失败 ≠ request 级故障」+ **rollup 缺口语义 = 读侧现算**）；③ 保留期（ILM 30d 已登记）+ 审计现状；④ 假绿残余与挂账边界 7 条（§5）。
    - **⚠️ 两条实现缺口（手册照实标注，不写成已有能力）**：**① 词表（`fallback_utterance`）维护流程当前无执行载体**——无写入端点（`api/router.py:13-20` 只挂 5 个 router）、`require_admin` 无路由使用、**无审计落点**、**无 version 自增实现**（`models/config.py:23-24` 与 `no_fallback_cfg.py:4-5` 的「变更 +1、admin-only」**均为注释**）⇒ 本条要求的流程**写得出、做不了**。**归口 = `T-3.12`（本文件 :135）范围内、已在册不新立**；**在此显式列为 T-3.12 的验收内容**（§8.6 `PUT /configs` 落地时须一并含**写入 + `version` 自增 + 审计**三项，**勿只做端点**）。⚠️ **过渡期风险**：T-3.12 落地前改词表**只能改库**，会造成 **`wordlist_version` 失真**，而该 version 是 **D19 信封**组成部分 ⇒ **过渡期应避免改词表**。**② 审计导出零实现**（跨 cluster 检索亦无：审计仅内嵌于 cluster 详情端点，`api/backflow.py:555-558`）——**已于 2026-09-14 用户拍板立 `T-3.13`**（见上，本文件 T-3.13 条目）；⚠️ **性质 = 运营需求驱动的补实现**（上游设计零命中「导出」），**与 T-3.12 的欠债性质不同**，勿并成同类。（**我原建议「定为 v1 边界、不立 T 项」未被采纳**；未采纳的理由我未记录用户陈述，故此处只记决策结果，不代写理由。）
    - **❌ 验证目标有一半不可达（如实标「未达成」，非「已验」）**：「维度 3 开放验收项在**真实 agent** 上最终复验」**~~卡 `T-2.5`/`S-4`（无真实 agent）~~ → 卡点重述为「缺真实用户流量」**（**⚠️ 2026-09-16 订正**：agent 接入**已成立**、offline 已真打并出分；`T-2.5`/`S-4` 不再是本条前提。**「未达成」的结论不变**），**阶段 5 内无法完成**——不得因手册已交付而把本条整体记绿。

**阶段出口**：维度 3 开放验收全绿 → 开放回流白名单；上线复盘记录容量/告警/假绿残余基线，作为二期（L3 quality、C2 会话型回归）排期输入。

---

## 风险与关注（本 WBS 层面的依赖与假设）

- **轨道与前置依赖**：Task #4 offline 配套方案已定稿（双批：批 1 = offline `error-backflow-phase1.md` **v0.2.2**（契约 + 收单先行 = 联调环 0/环 1）；批 2 = offline `error-backflow-phase2.md` **v0.7.2**（判定语义 + R5-R7 auto-fixed 判据重构 = T-3.8，2026-09-07 终审收口后历 R-1~R-24 修订包演进）），方案层面已解除对 **offline 配套轨**与平台轨在阶段 3.8/4.x 汇合的阻塞（实施随 offline 仓排期；平台轨 online 侧、agent 整改轨不受阻）；**本地共享 infra（../infra）扩 ES/Kafka 是平台轨阶段 0/1 的硬前置与环 2 的门（2026-09-03 决策，infra 仓改造、本地可自控节奏）**——未完成前 S-1 冒烟/P0 观测链用 `compose.infra.dev.yml` 临时过渡（非主线）；网关 SSO 与生产公共 infra 租户（§17 #14/#15）是上线门、不阻塞 dev 联调；agent 整改轨仅依赖 SDK 契约冻结，不依赖 infra 到位。
- **假设**：公共 infra 各租户以 `{env}.` 前缀隔离互不可见；词表覆盖度缺口（漏词/变体）在 v1 属如实存在（solution §16 承认），不阻塞闭环、仅登记。
- **已销（2026-09-07 回填收口）**：T-4.13/T-4.14 中**超出 detail §14 已编号用例**的追加场景（埋点前提用例、检索注入/转义、时间/窗口/数量级/词表边界死角等）已编号化为 **detail §14.5 X-1~X-13**（「集成异常与边界用例」，detail v1.10 修订记录已登记）——集成验收统一以 detail §14.5 X 编号为权威口径，task T-4.13/T-4.14 为来源容器，两文档用例集已对齐、无需再回填。
- **边界**：L3 quality/会话型回归/collector 组件不入本 WBS（v1 不实装，detail §12.1 二期占位索引为准）。

---

## 任务清单对账（2026-09-16）

**背景**：Claude Code 任务清单（会话内工具、**非本仓文件**）累积 10 条 pending，对账发现它**不可作为「下一步做什么」的导航** —— 其中混着「已完成未更新」「登记项」「已裁不验」三类，却被写成同形的「待办」。判据 = **只认台账白纸黑字 + 行号**，不认印象。

**结果 10 → 3**：

| 条目 | 判定 | 依据（逐字摘引 + 行号） |
|---|---|---|
| T-3.15（原记「三问未决」） | **已结清** | 本文件 `:240`/`:263`「三问已裁、(a) 已落地……已 commit + 已 push」（offline `78f1345` / online `7d6f269`）|
| T-3.17（真机证据对账） | **已结清** | 本文件 `:295`/`:305`/`:313`「四仓 backend 镜像已全部重建并上线……✅ 本条结清（2026-09-16）」|
| C-5 规格引用行号漂移 | **登记项·不排期** | `offline/error-backflow-pending-phases.md:842`「判 P3 登记项、**只登记不改**」|
| T-4.15「7d 窗口」/ `inactive` 状态 | **登记项·不排期** | 本文件 `:379`「性质同 T-3.15/T-3.16 = **登记项，不是验收任务**」|
| R-8 自愈支 + online R2 例外 | **已裁·不验** | `pending-phases.md:732`「无真机证据 —— 用户裁定不真机验」⚠️ **不等于「已结清」**：这是**明知的永久边界**，据实记「已裁·不验」，不得写成「做完」 |
| 乙项 requeue reason 门 | **两侧拆明** | online 半已落码（本文件 `:115`，482 passed）；offline 半 `pending-phases.md:741`「**仍为登记项**」|

**仍为真待办（3 条）**：C-3 lint 门禁缺口（offline 无 CI、ruff 本机不可用）· `manual_invalidate` 竞态对账未真机触发 · offline §4 未验清单（**6 条** —— 原记「5 条」已过期，第 6 条 2026-09-16 新增）。

**本节的用途**：下次有人（含 AI）看到任务清单只剩 3 条时，能查到这里为什么、以及被移出的 7 条去了哪。**不得据「清单只剩 3 条」推断「项目接近完成」** —— 本仓阶段目标【闭环可用】已于 2026-09-16 收官；剩余 3 条属维护面（补门禁 / 补证据），**做完不产生新目标**。

---

## 真实 agent 端到端联调验收（2026-09-16）

**背景**：本台账与 `docs/` 多处（站点全集见文末）长期记「无真实 agent / 卡 T-2.5·S-4 / 环境无输入」，
并据此把 T-5.1 / T-5.2 / T-5.4 与「维度 3 开放验收」判为「无法开工」。
**2026-09-16 据实核查，该前提不成立** —— 四个 agent 早已部署、已接 SDK，且平台**已经真实评测过它们并出分**。

### 一、四层实证

| 层 | 结论 | 证据 |
|---|---|---|
| 服务部署 | ✅ 四个 agent 容器均在跑 | `docker ps`：`customer-service-backend-1` / `contract-check-backend` / `sp-app` / `rag-backend`(gq) |
| 契约可达 | ✅ 四家 `/api/contracts` 全 **HTTP 200** | `curl localhost:{8080(gq)\|8000(cs)\|8003(cc)\|18002(sp)}/api/contracts` |
| SDK 接入 | ✅ 四层全齐：代码插桩 + 配置项 + 构建接线 + `.env` **`OBS_ENABLED=true`** | 各仓 `.env`（gq:56 / cs:43 / cc:14 / sp:75）+ 各 `docker-compose.yml` 的 `additional_contexts: obs-sdk` |
| 观测链 | ✅ 四家端到端（Kafka → 消费端 → ES → 查询 API） | 见下 |
| **评测链** | ✅ **离线平台真打真实 agent 并出分** | run **3666 / 3660 / 3038** |

### 二、观测链证据（online 侧）

- 四个 agent topic 均有数据：`dev.obs.agent.good-question` **2760** / `customer-service` **215** /
  `smart-procurement` **53** / `contract-check` **1**（`dev.obs.selfmonitor` 3388 = 心跳 1/min）。
- **`llm_call` 深度已验三家**（含 `model` + `usage` 三分量 + 正确 `parent`）：
  gq（2 条）、cs（5 条，源自一次 21 秒/5 次 LLM 的真实对话）、sp（2 条，源自一次 58 秒的评审）。
  cc 按设计仅 request 级（`solution_detail.md:1402`）。
- **本次可控触发**：分别 `curl` cs/cc/sp 的 `/api/contracts`，三家 topic 各 **+1**，
  且三家的 `trace_id` 经 online 查询 API **精确回查命中**、`ts` 与 Kafka 原文**逐位相同**
  （cc `1789536205227` / cs `1789536203221` / sp `1789536207312`）。
- 一条无 `llm_call` 的 trace 经 Kafka 原文对证 = **agent 未发**（缓存命中未调 LLM），**非下游丢失**。

### 三、评测链证据（offline 侧）+ 交叉验证法

真实 agent 的 run 记录（`eval_run`，跨 15 天、三次成功、分数各异 ⇒ 非复制的绿）：

| run | agent | 套件 | 时间 | 用例 | 结果 | score |
|---|---|---|---|---|---|---|
| 3038 | gq | gq 真实业务评测(22) | 2026-09-01 10:01→10:03 | 22 | 22 pass / 0 fail | 99.83 |
| 3660 | gq | gq 真实业务评测(22) | 2026-09-15 12:07→12:11 | 22 | 19 pass / 3 fail | 92.20 |
| 3666 | sp | smart-procurement 接入示例(8) | 2026-09-16 02:33→02:35 | 8 | 7 pass / 1 fail | 86.12 |

**交叉验证（本轮新增的硬证据手段）**：run 3666 执行窗口内，online 于 **09-16 02:35:00~02:35:17**
采到 sp 的真实业务调用 `POST /api/v1/reviews` → `/score` → `/chat`（连续多组，对应用例节奏）。
两套系统各自的独立记录在时间轴上吻合 ⇒ **确证 offline 真打了 agent**，一次排除「桩执行」与「假绿」两种干扰。

### 四、复核方法（照此可独立复现）

```bash
# 1) 服务与契约
docker ps --format '{{.Names}}\t{{.Status}}'
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/contracts   # cs；gq:8080 / cc:8003 / sp:18002

# 2) Kafka 侧（容器内脚本无 PATH，须绝对路径；Git Bash 须 MSYS_NO_PATHCONV=1）
MSYS_NO_PATHCONV=1 docker exec shared-kafka /opt/kafka/bin/kafka-get-offsets.sh \
    --bootstrap-server localhost:19092 --topic 'dev.obs.agent.*'
MSYS_NO_PATHCONV=1 docker exec shared-kafka /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server localhost:19092 --topic dev.obs.agent.good-question --partition 0 --offset 2759 --max-messages 1

# 3) online 查询面（平台无宿主端口映射，须容器内访问；token 由 admin 登录取得）
MSYS_NO_PATHCONV=1 docker exec obs-backend python3 -c "
import os, json, urllib.request as U
b=json.dumps({'username':'admin','password':os.environ['ADMIN_PASSWORD']}).encode()
r=U.Request('http://localhost:8000/api/v1/auth/login',data=b,headers={'Content-Type':'application/json'})
tok=json.loads(U.urlopen(r).read())['access_token']
q=U.Request('http://localhost:8000/api/v1/traces?agent=good-question&trace_id=<TID>',headers={'Authorization':'Bearer '+tok})
print(json.loads(U.urlopen(q).read()))"

# 4) offline 侧 run 记录
MSYS_NO_PATHCONV=1 docker exec ai-eval-backend python3 -c "
from app.core.config import Settings
from sqlalchemy import create_engine, text
u=Settings().sqlalchemy_url.split('://',1)
e=create_engine(u[0].split('+')[0]+'+pymysql://'+u[1])
with e.connect() as c:
    print(list(c.execute(text('select id,agent_id,status,total_case,pass_case,agent_score,started_at from eval_run where agent_id in (2297,2298,2299,2300) order by id desc limit 10'))))"
```

### 五、本验收证不了什么（显式声明，勿外推）

- **真实用户流量仍是 0** —— 上述全部是「平台主动打 agent」产生的流量。T-5.1（灰度放量门禁）要的是
  **真实用户**的灰度流量 + 连续 7d 观测窗，**这一层未变，仍不可达**。
- 容量型结论（T-5.2 / T-3.14）**不因此改变** —— 它们要的是量级，不是「链路通」。
- 维度 3「在真实 agent 上复验」**仍需真实流量**，本验收不覆盖。
- `llm_call` 深度只验了 gq/cs/sp；cc 无 `llm_call` 样本（设计如此，但其「折叠后行为」仍无样本）。

### 六、据此需订正的台账站点（**逐条判、不打包**）

`无真实 agent` 类表述的实际站点数 = **13 处**（⚠️ **本行原写「10 处」，同日订正、旧数与旧行号一并作废**：旧数系凭上一轮记录搬来，且旧列的 `task.md:97`/`:101`/`:291` 经逐行回查**均非此主张**——`:97`/`:101` 是任务定义与「demo 流量非真实 agent」的**事实陈述**、`:291` 讲「T-2.5 从未整体验收」**且仍成立**。现数由 `-o` 模式 `.{0,25}(无真实|缺真实|没有真实|无真实流量|环境无输入|等环境|等真实|卡 T-2.5|卡输入|真实 agent 可打|随时可打).{0,35}` 在**两仓**全部 `*.md` 上实测定死）。
**其中并非全部作废**：凡指「需**真实流量**」的仍成立，只是措辞把「无流量」写成了「需接入 agent」。
**✅ 订正已完成（2026-09-16，逐条判、不打包）**：统一口径 = **只订正「卡在哪」（卡点性质），不动「卡不卡」（结论一律保持「未达成 / 无法开工」）**。13 处 = online **12** + offline **1**：

| 站点 | 原主张 | 判定 | 处置 |
|---|---|---|---|
| `task.md:201` | 「没有真实 agent 可打」 | **直接失实** | 划线 + 改述为「缺真实用户流量（故无真实 error 现场）」 |
| `task.md:209` | T-3.14 结清依据含「环境无输入」 | 前提失实、**结论不变** | 依据**收窄到只剩**「功能面已完整 / 规模判别力需量级（现 4 agent 但数据量不足）」 |
| `task.md:212` | 「应等真实 agent 接入（T-2.5）后按真实需求定」 | 部分失实 | 改「等**真实流量**」+ 记「`interface` 表**仍 0 行** ⇒ 需求不随接入自动产生」 |
| `task.md:230` | T-3.14 留档原文含「环境无输入」 | 同 `:209`（留档句**不改**） | 追加订正注、指向 `:209` |
| `task.md:392` | T-5.1「真实 agent 的灰度流量…无真实 agent 接入 = 卡 T-2.5/S-4」 | 归因失实 | 卡点改「缺真实用户流量」+ 「开工所需输入 ①」同步改写 |
| `task.md:394` | T-5.2「环境无输入」 | **不实** | 加注澄清：本条输入**与 agent 接入无关**（缺 infra 回执 / 量级 / 时间），**逐项内容全部有效** |
| `task.md:397` | 「不记『未验』而记『环境无输入』」 | 措辞歧义 | 加注「『无输入』指流量 / 周期 / 回执，**不指 agent**」 |
| `task.md:402` | T-5.4「卡 T-2.5/S-4（无真实 agent）」 | 归因失实 | 划线 + 重述为「缺真实用户流量」，**「未达成」不变** |
| `docs/ops-manual.md:127` | 边界表第 6 条「卡输入：需真实 agent 接入」 | 归因失实 | **正文改**（手册是**现行件**，不能只加注）+ 文末加订正条 |
| `docs/ops-manual.md:142` | 交接清单末行「需真实 agent，卡 T-2.5」 | 同上 | 同上 |
| `docs/integration-report.md:142` | F-23 补登笔「卡 T-2.5/S-4」 | 历史笔 | 划线 + 订正注（不重写历史陈述） |
| `docs/integration-report.md:943` | 乙类归口笔同上 | 历史笔 | 同上 |
| offline `error-backflow-pending-phases.md:62` | P4-3「`T-5.x` 缺真实 agent」 | 归因失实（表头已锚「**当时状态 2026-09-15**」） | 保留原述 + 订正注 |

**未改的相邻项（有意，勿误读为漏改）**：`task.md:97` / `:101`（任务定义 / 「demo 合成流量非真实 agent 流量」的事实陈述）、`:291`（「T-2.5 从未整体验收」**仍成立**）、`solution_detail.md:29`（「v1 上线前库内无真实流量」指**线上**，仍成立）、offline `:456` / `:467`（离线库内无真实**样本**，另一主张）。

#### ⚠️ 新归因的证据等级（**务必连着读**，上表 13 处均受此约束）

上表把卡点改述为「缺真实用户流量」，但**这个新归因的证据等级低于它证伪的那个**：证伪「无真实 agent」用的是**四层实证**（容器在跑 / 契约 200 / SDK 全接入 / offline 真打出分），而「无真实用户流量」的证据**分两层，且两层结论相反** —— 实测依据（2026-09-16）：

- **trace 面 structurally 无调用方信息**：`request` 文档字段全集 = `schema_version / event_kind / trace_id / agent / agent_version / interface / node / seq / ts / duration_ms / status / extra / trace_key`，**无任何来源标识**；唯一扩展位 `extra` 的白名单 = `{request_id, task_id, job_id, conv_id, sub_agent, prompt_kind}`（`solution_detail.md:396`，**全是业务标识**），且明文「任何新增扩展键须**回平台评审加白**」。
- **① trace 面：结构性不可验** —— 靠 trace 数据**永远分不清**调用方是真实用户、offline 评测、还是探针（理由见上一条）。
- **② 旁路 access log：可判，且两源旁证一致（2026-09-16 实测）**：
  - `contract-check-frontend`：唯一访问者是 `127.0.0.1 … "Wget"`（healthcheck，**无真人**）。
  - `sp-web`（`access.log -> /dev/stdout`，**可查**）：**277 条请求行，来源 IP 全部为 `172.23.0.1`**（Docker 网桥网关 = 宿主机），UA = `python-httpx/0.28.1` ×270 + Chrome ×6 + `curl/8.18.0` ×1 —— **无一例外是自动化脚本或本轮我方浏览器 e2e**；时间范围 **2026-08-31 ~ 09-01**，之后再无。
  - ⇒ **两源一致指向「无真实用户流量」**。
- **③ 未采信的源（照实记，勿当证据）**：`customer-service-nginx` 的 stdout **全空** —— 按「**空输出 ≠ 负面证据**」的口径，**该源存疑（可能是取证失败而非无访问），不作旁证**。
- ⚠️ **本段自身的一处订正**：本段初版写「`customer-service-nginx` / `sp-web` 的 access log **未输出到 stdout**（查不到）」—— **错**。实测两者均为 `access.log -> /dev/stdout` 符号链接、**完全可查**。错因 = **把第一次 `docker logs` 的空/仅 notice 输出读成了「日志未出 stdout」**（[[grep-scope-is-not-whole-repo]] 同族：把「我没取到」当成「不存在」）。该错句已随本批第一笔推送，同笔订正。
- 本环境**无公网入口**，故「无真实用户流量」近乎自明 —— 但**「自明」不是「已验证」**，更不等于**生产环境**的未来流量为 0（那是未知，取决于上线）。

⇒ **引用这句时须带等级**：它是「**缺该输入 —— trace 面不可验、旁路两源旁证一致**」，仍**不是「实测为 0」**（日志有留存窗口；gq 容器未运行、其前端无从查）。凡以它为开工前提的判断（上表 13 处），结论不受影响（都仍是「无法开工」）。**本环境无公网入口**，故该结论近乎自明 —— 但**「自明」+「旁证」仍不等于证明**，更不代表**生产环境**上线后无流量（那是未知，取决于上线）。
