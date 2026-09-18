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
    - **`result_overdue` / `result_gap_suspected` 半边 = 远超「文档滞后」**：`result_gap_suspected` **两侧齐全**（§9.2/§8.4 有语义；前端 `types.ts:308` + `DetailView.vue:328` + 单测）；`result_overdue` **文档已写语义**（§8.4 / §9.3 状态文案「回查结果未达（疑似 offline 停摆），人工核查」）而~~**前端零消费**~~（`grep -rn "overdue" frontend/src/` **零命中**：无类型、无渲染、无单测）⇒ ~~**这不是笔误，是呈现面缺失**~~，已**另立** `docs/integration-report.md` §6 **F-18**（同 F-13 家族；**入乙类、阶段 4 不补实现**）。**⚠️ 2026-09-17 失效标注：该缺口已闭合** —— 前端**已实现**（`types.ts` + `backflowLabels.ts` + `DetailView.vue` + 单测四件套，44 passed / `vue-tsc` exit 0），F-18 已加失效标注。**保留未验部分 = 未做浏览器实测**（`obs-frontend` 当时 Exited 未变）。
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
    - **✅ 已达成的交付项**：① 归口一览（§0，含「无告警通道」「不设 online 时钟」两条否定口径 —— **⚠️ 2026-09-16 订正：「无告警通道」一条已拆半改判，见 `T-5.5`（「不设 online 时钟」一条不受影响、原样有效）** ——`api/backflow.py:320/421` 逐字「不落列、不设时钟」，`waiting_days` 是**展示值、不触发动作**，运营期**不得当告警用**）；② 看板口径文档（§4：双指标 `request`/`llm_call` 语义 + 「LLM 级失败 ≠ request 级故障」+ **rollup 缺口语义 = 读侧现算**）；③ 保留期（ILM 30d 已登记）+ 审计现状；④ 假绿残余与挂账边界 7 条（§5）。
    - **⚠️ 两条实现缺口（手册照实标注，不写成已有能力）**：**① 词表（`fallback_utterance`）维护流程当前无执行载体**——无写入端点（`api/router.py:13-20` 只挂 5 个 router）、`require_admin` 无路由使用、**无审计落点**、**无 version 自增实现**（`models/config.py:23-24` 与 `no_fallback_cfg.py:4-5` 的「变更 +1、admin-only」**均为注释**）⇒ 本条要求的流程**写得出、做不了**。**⚠️ 2026-09-16 订正（本段过半已作废，勿再引用）**：上列三个「无」**实测全部不成立** —— `api/admin.py:162` 已有 `PUT /configs`，docstring 逐字「键/形状校验 → upsert → `version + 1` → 写审计（`config_change`）→ 清读缓存」，并明写「`fallback_utterance` 走同一路径不特判：其 `version` 即 D19 `wordlist_version`」⇒ **写入端点 / version 自增 / 审计落点三项均已在 T-3.12 批 1 落地**（单测 478 passed / 真库探针 31-31 / 浏览器 e2e 双账号）。本段写于批 1 落地之前 ⇒ **词表维护流程缺口不存在，过渡期「避免改词表」的风险随之消解；勿据本段立任何任务。**~~**归口 = `T-3.12`（本文件 :135）范围内、已在册不新立**；**在此显式列为 T-3.12 的验收内容**（§8.6 `PUT /configs` 落地时须一并含**写入 + `version` 自增 + 审计**三项，**勿只做端点**）。⚠️ **过渡期风险**：T-3.12 落地前改词表**只能改库**，会造成 **`wordlist_version` 失真**，而该 version 是 **D19 信封**组成部分 ⇒ **过渡期应避免改词表**。~~**② 审计导出零实现**（跨 cluster 检索亦无：审计仅内嵌于 cluster 详情端点，`api/backflow.py:555-558`）——**已于 2026-09-14 用户拍板立 `T-3.13`**（见上，本文件 T-3.13 条目）；⚠️ **性质 = 运营需求驱动的补实现**（上游设计零命中「导出」），**与 T-3.12 的欠债性质不同**，勿并成同类。（**我原建议「定为 v1 边界、不立 T 项」未被采纳**；未采纳的理由我未记录用户陈述，故此处只记决策结果，不代写理由。）
    - **❌ 验证目标有一半不可达（如实标「未达成」，非「已验」）**：「维度 3 开放验收项在**真实 agent** 上最终复验」**~~卡 `T-2.5`/`S-4`（无真实 agent）~~ → 卡点重述为「缺真实用户流量」**（**⚠️ 2026-09-16 订正**：agent 接入**已成立**、offline 已真打并出分；`T-2.5`/`S-4` 不再是本条前提。**「未达成」的结论不变**），**阶段 5 内无法完成**——不得因手册已交付而把本条整体记绿。

- **T-5.5 上线告警通道与回流断流自检（G3）**（**2026-09-16 立**，用户拍板；来源 = 本日「距上线闭环还差哪些」范围梳理，逐条取证后立项）：**系统级告警（漏采/断档、offline 停摆、inbox ack 积压、ES 容量）在权威文档中从未被裁定，却被 `docs/ops-manual.md` §0 一行否定连带取消**。本条建立四项判据与一个主动出口。
  - **⚠️ 性质分半（勿并成一种——本文件 `:218` 明令「性质不同勿套错措辞」）**：
    - **offline 侧 ack 告警 = 欠债**——规格里**写了**：offline `error-backflow-phase1.md:369`「404 → **即时告警**端到端连通性 + `ack_status='blocked'` + `last_error`，不静默长期重试」、`:347`「重放持续失败 → `last_error` 累计 + 日志告警」、`:624`「blocked 行需**运维面板可见**（inbox 管理查询）+ 人工复位入口」；而**实现整块缺失**（`backflow_client.ack` 对非 200 只抛、响应体从不解析；两个调用点只 log+return；`blocked` 值域第四值零赋值点）——该结论已由 **#324 独立证成**，权威处 = offline `error-backflow-status.md` O-D.4。**性质 = 规格承诺过、实现没做**（同 T-3.12）。
    - **通道本身（webhook 出口）= 自主加范围**——上游规格 `grep webhook` **两侧零命中**，属运营需求驱动的补实现（同 T-3.13 性质）。
  - **为什么今天才立**：`ops-manual.md` §0 把 `waiting_days` 的 TTL 裁定（`api/backflow.py:320/421`「不落列、不设时钟」）**通用化成了整行否定**「告警发出 ❌ 无通道」，把两件事**合并成一件事**——**(a) TTL 类告警确实不要（裁定正确）**；**(b) 系统级告警从未被裁定过**。且**与 T-5.1 自相矛盾**：T-5.1 放量门禁要求「观察窗内核对**无告警**」，而系统无告警通道 ⇒ **该句没有主语**。
  - **不做会出的具体故障**（本仓判据「答不上就不做」，此处答得上）：**offline 停摆或 ack 卡住时无人知晓，错误回流静默断流**。同形已踩两次（R-28 恢复路径被自家谓词挡死；T-3.19 sp 启动日志假警报），二者**均只能靠翻日志才发现**。
  - **四项归属与判据载体（逐项取证）**：

    | # | 项 | 归属 | 载体 | 现成 |
    |---|---|---|---|---|
    | ① | 观测漏采/断档 | online | `consumer/main.py` `_selfmonitor_loop` | ⚠️ **函数体未读，待取证** |
    | ② | offline 停摆 | **无归属** | —— | ❌ **需新建** |
    | ③ | inbox `ack_status != 'acked'` 积压 | offline | `error_backflow_inbox` + 索引 `idx_status_ack(status, ack_status, updated_at)` | ✅ 全现成 |
    | ④ | ES 容量水位 | online | `consumer/main.py` `self._es` | ✅ client 现成 |

  - **⚠️ 本条查出的结构性洞（比四项本身更重）**：「offline 停摆」在现有架构里**没有任何观测点**——① offline **自己检测不了自己**（进程死了就不打日志，判据随之消失）；② online 侧**零 ack 记载**（`models/error_flow.py:69` `ErrorCaseLink` 有 `payload_id`，但全 models `grep acked|push_status|delivered` **零命中**）⇒ online **不知道信封发出去后有没有被收**。**故 ② 只能做到「卡死」、做不到「进程死」**；后者需 infra healthcheck 或 online 侧新增 ack 记载（**设计变更，不在本条内**）。**如实标注，不得读作「四项已齐」。**
  - **通道形态（2026-09-16 用户拍板）**：新增 `core/alert.py` 薄封装（`async def notify(level, title, detail)`）+ 配置项 `ALERT_WEBHOOK_URL`；**未配置 ⇒ 降级为 `logger.warning`**（不配也能跑、不阻塞部署）；用两侧已有 `httpx`，**不引依赖**。**这是本条唯一一处 A 级改动（改配置）。**
  - **阈值（2026-09-16 用户拍板）**：`_STALE_MINUTES = 10`，**模块常量**（同 `_INTERVAL` 既有惯例，**不新增第二个配置项**）。依据 = offline `runner/pull_loop.py:34` `_INTERVAL = 30.0`（pull 周期 30s）× 20 轮 ⇒ 容忍 online 重启/网络抖动，**避免误报吃掉告警可信度**（`chronic-noise-defeats-gate` 的老路）；正常 ack 为**秒级**（`_ack_active` 内同步 HTTP）⇒ 10min 对观察窗足够快。
  - **判据（不排除任何 `ack_status` 值）**：`ack_status <> 'acked' AND updated_at < NOW() - INTERVAL 10 MINUTE`；门禁 `backflow_enabled=false` 时不告警（同 `cap_gap_probe` 门禁形态）。**不排除 `blocked`**——`none`/`pending`/`blocked` 三者语义**都是「回写没成功」**，排除 `blocked` 会让最需人介入的状态静默。（**自订正**：立条初稿曾担心「不排除则永不触发」，**方向反了**。）
  - **方案内置修正（防首版即成噪音源）**：60s 周期直发会**刷屏** ⇒ **只在告警集合变化时发**——新进入告警态发一条（带新增 `payload_id`）、集合清空发「已恢复」、集合不变只 `logger.debug`。**这是状态比较，不是去重平台。**
  - **批次切分（按仓切 = 按验证面切）**：**批 1** = ③ ack 积压 + 通道基建（`alert.py` / 配置项 / 判据循环 / 注册 / 单测）；**批 1b** = ②半 僵尸锁检测（**前置 = 先勘察锁形态**——DB 锁 or 文件锁未取证，**不掺没勘察完的进批**）；**批 2** = online 侧 ①④（**第一步是取证**：读 `_selfmonitor_loop` 函数体确认 ① 是否已被部分覆盖，**不是写码**）；**② 进程死** = 不在本轮。
  - **批 1 验收**：单测（判据真/假两分支 + 降级路径 + 集合变化三态）+ **真库探针**（正向：造 `pending` + `updated_at` 回拨 11min → 断言触发；**负对照**：造 `acked` 同样回拨 → **断言不触发**；恢复：改回 `acked` → 断言发「已恢复」）；**连跑两遍才算验收**。
  - **⚠️ 探针写的是真表**：`ai_evaluation.error_backflow_inbox`——**勿写固定水位**（会腐，见 `memory-status-markers-rot`）：造前当场取 `select count(*), sum(ack_status='acked') from error_backflow_inbox;`（2026-09-17 复核 = **25 行、25/25 `acked`**；本句原写的「实机 12 行、12/12」已过时）。探针**必须**用 `probe-ackstale-<uuid>` 前缀唯一化（`probe-repeatability-and-unique-input`），**造前记基线水位、造完当场删、撤销后回读**（`self-injected-fault-looks-like-real-defect`：人为故障与真缺陷**逐字同形**）。
  - **不做（边界）**：不建告警服务 / 不建表 / 不建页面 / 不做分级·静默·去重·告警历史 / 不引第三方 SDK。
  - **未验边界**：②「进程死」**无观测点**（见上）；① 是否已有基础**未取证**；通道 URL 属**环境输入**，落地以「未配置降级」形态交付。
  - **➜ 2026-09-17 施行记录：批 1 已实施并真机验收通过（⚠️ 实施仓 = offline，非本仓）**。落码 = `app/core/alert.py`（通道；未配 `ALERT_WEBHOOK_URL` ⇒ 降级 `logger.warning`）+ `app/runner/ack_stale_probe.py`（判据循环 60s，`GET_LOCK` 单飞）+ `main.py:164-166` 注册 + 单测 160 行 + 真库探针。**验收 = 单测 7 passed；真库探针连跑两遍各 `15 passed / 0 failed`（含负对照「同样回拨 11min、只差 `ack_status` 一行」+「`probe_once` 结果 == 独立直查期望集」两写法互证）；撤销回读 `probe_residue = 0`**。**⚠️ 未验边界（勿被绿盖过）**：真实 webhook HTTP 出站（未配 URL ⇒ 走降级分支，只断言 `notify` **被调用**）、`_INTERVAL` 真每 60s、多 worker `GET_LOCK` 互斥 —— **三者均无真机证据**；**①④ 未动、② 只做得到「卡死」、批 1b 未做** ⇒ **本条未完结**。权威记录 = offline `error-backflow-status.md` **O-D.4**（该条的「失效条件 ②」自此由本告警自动接管，不再靠人记得）；`docs/ops-manual.md` §0 与 §5 第 5 行的「当前仍未实现」已同步订正。
  - **⚠️ 本条与 T-5.7/T-5.6 的关系（2026-09-17 追加）**：`docs/real-traffic-request.md:40`「上线告警｜**正在收口**」一句**经查为真**（所指即批 1），**该件无需因本条改动**；但 `:42`「技术侧不欠账」在 ①④② 未做 + 批 1b 未开工的前提下**仍不成立**，留待后续处置。

- **T-5.6 上线门：真实链路端到端（G1 六条改判接收项）**（**2026-09-16 立**，用户拍板；来源 = `docs/integration-report.md` §3）：
  - **改判**：§3 六条（T-4.2 offline 半边 / T-4.3 真实驳回 / T-4.6 恢复拉取 / T-4.12 全条 / 阶段出口 E-23~E-29 环 2 / T-4.13 ⑤ 真实对端）**从「本阶段不可开工」改判为「上线门必做项」**——**「本阶段」是时间限定，不是需求取消**。这些验不了就是没验；上线后 offline 必须真跑。
  - **失效条件（挂闸）**：**真实流量到位后 N 天内未完成 ⇒ 阻断放量**。**N 待定**，随放量档定义（T-5.1 / solution §13.0 checklist #1~#3）一并裁定。
  - **保留原判定的部分**：六条**当前确实无法开工**（缺真实 offline 行为 / 真实对端）⇒ 本条**不是「现在开工」而是「登记为上线门并挂闸」**，避免它继续被时间限定词藏住。
  - **落地前须做**：`docs/integration-report.md` §3 标题与表前加改判块（**权威现场就地改判**）；本条为其**平台阶段表落点**（先例 = T-3.8「offline 配套轨在平台阶段表的落点」）。

- **T-5.7 真实用户流量归口与请求（**2026-09-16 立**，用户拍板；来源 = 本日「距上线闭环还差哪些」取证）**：
  - **归口裁定（用户拍板 2026-09-16）**：真实用户流量**归业务/产品侧，不归 infra**。⇒ `docs/infra-access-matrix.md` §4（网关四项）**原样不动**（它完整且面向 infra，缺的只是「发出去」这个动作，非文档）；另立对外请求件。
  - **交付物** = `docs/real-traffic-request.md`（**2026-09-16 起草**）：面向业务/产品侧的接入请求，含「我方已就绪（对方无需等待）」+ 请对方明确的三件事（哪个 agent 先上 / 量级 / 起点时间）+ 拿到后的时间线 + 挂闸。
  - **⚠️ 本件尚未发出、收件人未定**（`docs/real-traffic-request.md` 头部「提交人 / 收件方」两处**未落实到具体人名**——2026-09-17 改为**角色占位**形态，**不代表已指派**）——**「起草了」≠「要了」**。**待办 = 用户填对口人并发出**；发出后此处回填发出日期与对口人，再据此推 T-5.6 的 N。
  - **为什么单独立条**：本项自 2026-09-14 起被登记为「环境无输入、无法开工」，但**从未有「向谁要」的载体**——不是缺文档，是**没有归口**。台账里长期以「等」的形态存在，等于把外部排期问题伪装成内部待办。
  - **取证订正（同轮查出，只登记不擅改）**：T-5.1 `:392` 把「**放量档定义**（solution §13.0 checklist #1~#3）」列为开工所需输入，但 `solution.md:619` **该 checklist 就在本仓**（放量门禁 `#1/#2/#3/#6/#7/#9` + 维度 3 开放验收 `#4/#8/#10`）⇒ 「放量档定义」**不缺**；真实缺的是 checklist #2 要用的**预估值基线**。**⚠️ 未穷举 `#219` 批次上下文，故只标可疑、不判死**（原句重音可能落在「与预估值基线」上）。

- **T-5.8 阶段 B/C：4 agent 回流闭环「前置补齐 + 端到端验证」**（**2026-09-16 立**，用户拍板；来源 = 用户令「阶段 B 和 C，4 个 agent，验证场景要充分，尽量补足一些」）：
  - **本条同时是该批次的持久化载体**（用户 2026-09-16 提出「怕 compact 后丢失，先持久化」）——批次排期原先**只存在于会话上下文**，未落任何台账；立此条即补上。
  - **批次划分**：**阶段 A = 复核既有回流样本**（3 条「对不上」的 link，2026-09-16 已完结，**未查出任何缺陷**；⚠️ 样本主要来自验收/探针批次而非真实流量 ⇒ 只证明「链路能正确运转」，**不证明「真实场景下正确」**）；**阶段 B = 前置补齐**（使 4 个 agent 具备走完回流闭环的前提，**走真实 admin API `PUT /admin/configs`，不改任何 agent / platform 代码**）；**阶段 C = 端到端验证**（4 agent × 多场景，观察七环）。
  - **⚠️ 本条含一处对 D18 的例外，显式登记（防后人读成缺陷）**：`solution.md:65` **D18** 明写「**contract-check（后台任务型）第一版只出 request 级指标与链路，维度 3 不纳入**」，另在 `:121` / `:365` / `:392` / `:609` / `:649` 五处复述（`§13.1 #9` = `:649`）。⇒ **线上 cc `backflow_allow=0` 是设计值、不是缺陷**（**2026-09-16 取证订正**：本人上一轮汇报据 `backflow_allow=0` + 空词表把 cc 判为「走不完 e2e 的障碍」并据此提问，**该前提作废**）。**本次依用户两次拍板（2026-09-16）把 cc 纳入维度 3** —— 记为**对 D18 的临时例外**，**不改 `solution.md` 原文**；若例外长期保留，须另立 D18 修订（当前**未立**）。
    - **🔄 同日内即撤销该例外（2026-09-16，用户拍板）**：C1 七环本体实测证明该例外的**立论前提不成立**。纳入 cc 的隐含假设是「cc 本可成簇，只是配置把门关了」——**实测为两层结构不可达**：① **值域外**：根侧 `error_type` = `TIMEOUT` / `CANCELLED` / `INTERNAL_ERROR`（`contract-check/backend/app/service/check_task_service.py:179-180`），三者全在 `classify._layer_for` 承认的 11 词（L1 七类 ∪ L2 四类）**之外**；② **结构解耦**：`run_task_async`（同文件 `:184`）是 `asyncio.create_task` **后台异步**，那个合成 `POST /internal/check-tasks/{id}/run` span **派发完即返** ⇒ root 与 LLM 故障不在同一条 HTTP 生命周期上，**即便开门也不成簇**。⇒ **cc 回归 D18「维度 3 不纳入」**，`solution.md` 原文**不动**（其本就写着 cc 不纳入，无需改）。
    - **⚠️ 撤销的是「例外」这一口径，不是「那次改库动作」这一事实**：阶段 B 施行记录（下条）里 `contract-check` 词表 `[]→3 条` + `backflow_allow 0→1` 是**已发生的真实操作，原地保留、不回滚**。理由：① `backflow_allow` 保持 1 与改回 0 在**行为上完全等价**（两层不可达 ⇒ 两种取值都产不出候选），不做不会出任何具体故障；② 该列**无运行期写入面**（`api/admin.py:8` 自陈「只能改库/seed、无审计」），再改一次 = **再留一笔无审计痕迹**。⇒ 处置 = **只登记，不动库**。
    - **⚠️ 与第一批「seed 事实订正」同源的一处**：`seed.py:122` 是 `ON DUPLICATE KEY UPDATE updated_at = updated_at`（存在则保持原样）⇒ D18 的 `backflow_allow=0` **从未落库过**，改建前实测即 =1。故「cc 的 allow 取值」**不取决于阶段 B 那一次改库**——它本来就不是 0。**勿把这两处当两件事重复登记。**
    - **⚠️ 由本条引出、只登记不擅改的一处**：`analyzer/classify.py:8` 注释称「cc 双保险 = `agent.backflow_allow=0`（seed D18）+ `backflow_enabled`」——实测**该双保险只剩一重**（`backflow_allow` 实为 1，仅 `backflow_enabled=false` 仍在），**方向 = fail-open（少一重）**。**不影响 cc 现状**（两层不可达，候选本就产不出），故**本轮不改注释**，登记备查。
  - **阶段 B 起点快照（2026-09-16 取证，4 agent 就绪度）**：
    - `good-question`：`backflow_allow=1`，词表 **5 条**（v6）——**待复核是否覆盖真实兜底话术**（⚠️ 首轮本表误记为「6 条」，实为把**版本号 v6 当成了条数**；2026-09-16 执行阶段 B 回读时订正）
    - `customer-service`：`backflow_allow=1`，词表 1 条（v2）——**同上**（注：`.tmp-probe/c1_write_wordlist.py`（今早 10:20）曾按其源码 `rule_engine.py:21 DEFAULT_REPLY` 写过一轮）**【该临时探针及其余 19 个已于 2026-09-17 清理，见 T-5.13。原文保留是为记「当时用什么做的」，不是可复跑的入口】**
    - `contract-check`：`backflow_allow=0` + 词表 `[]`（v1）——**缺口 = 开闸 + 词表**
    - `smart-procurement`：`backflow_allow=1` + 词表 `[]`（v1）——**缺口 = 词表**
    - 另：`agent` 表第 5 行 `probe-unknown-agent`（id 853，词表 2 条）**是探针残留**，不在 4 家之内，**勿计入就绪度**。
  - **✅ 阶段 B 施行记录（2026-09-16 完成，用户批准「照草案全量写入」）**：
    - **执行脚本** = `.tmp-probe/b_write_wordlists.py`（临时探针，未提交；经 `docker exec -i obs-backend python -` 以 stdin 灌入容器执行）。**【该探针已于 2026-09-17 清理，见 T-5.13】**
    - **结果（以回读库内实值核对，未采信接口回执）**：`smart-procurement` 词表 `[]`→**11 条**（`v1→v2`，11/11 逐字命中）；`contract-check` 词表 `[]`→**3 条**（`v1→v2`，3/3 逐字命中）+ `backflow_allow` **0→1**（`affected=1`）。**4 家最终态：cc allow=1/v2/3 条、cs allow=1/v2/1 条、gq allow=1/v6/5 条、sp allow=1/v2/11 条**。
    - **⚠️ 顺带查出、须记（防后人照抄那份探针）**：`.tmp-probe/c1_write_wordlist.py`**【已于 2026-09-17 清理，见 T-5.13 —— 清理正因本句：一个已知必 404 却「自报成功」的脚本留着就是雷】**（今早 10:20）用的 `BASE` 拼出的是 **`/api/admin/configs`**，而真实路径是 **`/api/v1/admin/configs`**（`api/admin.py:56` `prefix="/admin"` + `main.py:70` `include_router(api_router, prefix="/api/v1")`）⇒ **该探针若真跑过必然 404**，其「自报成功」不可信；**cs 现存那 1 条词表的实际来源本轮未查明**（`dict_config.updated_by` / `updated_ts` 未查）。**不影响 cs 现状正确性**（值是 cs 源码 `rule_engine.py:21 DEFAULT_REPLY` 逐字），但**「谁写的」在台账上仍是空白**。
    - **开闸走的不是 API**：`agent.backflow_allow` **无运行期写入面**（`app/api/admin.py:8` 自陈「只能改库/seed、无审计」），故本轮为**直接 UPDATE**（**无审计留痕**）；seed 为 `ON DUPLICATE KEY UPDATE updated_at = updated_at`（`seed.py:122`）⇒ **存在则保持原样，改库不会被启动 seed 覆盖**（已核）。
  - **🔄 阶段 C 施行记录（进行中，2026-09-16）**：
    - **C2 / C3 / C3b（判定面）—— ✅ 已验**。探针 = offline `.tmp-probe/c2c3_wordlist_judge.py` + `.tmp-probe/c3_real_answers.py`（临时，未提交）。**均用 offline 真实算子 `KeywordNotContainsOp` 跑，非复写匹配逻辑**：
      - **C2 命中面**：4 家兜底回话（**刻意嵌在更长文本里**，兼验「子串」语义而非全等）⇒ **4/4 判 fail**，符合。
      - **C3 不误伤面（自造回话版）**：4/4 PASS —— ⚠️ 但此版回话**是我自己写的**，落「入参自造」盲区，**不足为据**，故另起下条。
      - **C3 不误伤面（真实样本版 = 真正有判别力的那条）**：取 offline `eval_result.answer` **线上真实历史回答**（`JOIN eval_run ON agent_id`）逐条过算子 ⇒ **gq 279 条 / cs 153 条 / cc 174 条 / sp 91 条，合计 697 条；命中 4 条、全部落在 cs**，且该 4 条**逐字等于** cs 词表条目（= cs 历史上真实降级过 4 次）⇒ **属「真兜底、该命中」，不是误伤 ⇒ 假红 = 0**；其余 3 家真实样本**零命中**。**此条同时构成 C2 的真实数据佐证**（命中面在真实数据上成立，不只是在我造的回话上成立）。
      - **C3b 空答**：4 家 ×（空串 / 纯空白）= **8/8 判 fail**（R-12 空话术证据）。
      - **结论一句话**：词表在 **697 条真实回答**上表现为「**零误伤 + 命中真实兜底 4 次**」。
    - **C1（主链路七环，4 家）—— 🔶 只做了「数据/契约层」的两侧对账，七环本体 ❌ 未跑**（详见下条）；**C4 / C5（复用既有探针抽样）—— ❌ 未做**。
    - **C1 · 数据/契约层 两侧对账（2026-09-16 完成；探针 = online `.tmp-probe/c1_dual_side_online.py`**【已于 2026-09-17 清理，见 T-5.13】** + offline `.tmp-probe/c1_dual_side_offline.py`（**offline 仓那份未动**），均临时未提交）**：
      - **取数面先穷尽确认（不按表名猜）**：online **全库 13 表 / 142 列**内搜 `payload|envelope|wordlist` ⇒ 只命中 `error_case_link.payload_id` / `payload_json` 两列（**online 无独立信封表**，早前按表名猜 `backflow*` 得零命中）；offline 侧 = `test_case.backflow_envelope`（信封**原文副本**，`models/case.py:59`）。
      - **A 存在性**：6 个真实 `payload_id` 在 online 侧 **6/6 命中**。
      - **B 逐字一致**：`no_fallback_config`（words **原序原大小写** + `wordlist_version`）**两侧 6/6 逐字相同**，`cluster_id` 亦一一对应（3861/3860/3859/3856/3841/3840）；且 `config_ref.wordlist_version` 与 `no_fallback_config.wordlist_version` 两处同源自洽 ⇒ **信封在传输与落库环节未被改写**。
      - **offline 侧内部一致性**：`sanitize_words(信封 words)` == `case.assertions[0].args.keywords` ⇒ **真实回流 6/6 相符**；`op=keyword_not_contains`、`args.path=answer` 6/6 相符。
      - **⚠️ 我自己的判据写错过一次（假红，已订正，留档防复现）**：首版 ① 写成「信封 words **逐字等于** 断言 keywords」，报 **16/17 不符**；dump 原始值 + 类型后定案 = **不是缺陷**，差异仅一条 `"AI 暂时不可用"` vs `"ai 暂时不可用"` —— 信封留**原文**、断言存 `sanitize_words` **净化后**（strip→lower→去重），**两者本就该不等**。改用**真实 `sanitize_words` 函数**重判 ⇒ 6/6 全绿。**教训 = 判据里别自己重写规范化/匹配逻辑，直接调被测代码那个函数**（同 [[unreachable-assertion-vs-false-red]]：同一片红，须回查实现才知该信谁）。
      - **16/17 里另 11 条 = 探针残留，非缺陷**：`payload_id` 为字面量 `probe-c1..c5`、`agent=None`、早于词表机制 ⇒ 信封无 `no_fallback_config`，而断言里却有个**信封中没有**的关键词 `抱歉，我暂时无法回答`。**已 grep 定性**：该串是 offline 仓**探针自造常量**（`backend/tests/integration/{auto_schedule,circuit_domain,error_run,push,reconcile,shared_pool}_probe.py` 六文件 `KEYWORD=`），**非产品侧硬编码兜底** ⇒ **「空表 fail-closed」（`pull_loop.py:178`）未被绕过**；处置 = 登记为残留（见「撤销面」），不计入不符。
      - **⚠️ 顺带查出、须记（口径级）**：`4b1801ce` / `7cdf6182` 的 `wordlist_version=4` 与现行 **v6 词条逐字相同** ⇒ **`wordlist_version` 不是内容指纹**，改版本号可以不改内容 ⇒ **不能用它检测/断言「词表内容变了」**。
      - **本条能证明什么 / 不能证明什么（不许被这片绿盖过）**：证明「**信封从 online 构造 → 传输 → offline 落库 → 构造 case 断言**这一路的载荷与规范化**两侧一致、未失真**」；**不证明七环跑通** —— 本条**不发任何新 error、不产生新回流样本**，是对**既有**样本的静态对账。
    - **C1 七环本体 · 施行预案（2026-09-16 立，用户拍板「四家硬推，逐家注入→触发→立即还原」；⚠️ 截至立此条时**尚未注入任何故障、系统干净**）**：
      - **驱动方式（已取证）**：环①~③ 由 `obs-worker` 四个 job 循环自动跑 —— `cluster_job` 15s / `assemble_job` 60s / `judge_scan_job` 60s / `claim_ttl_job`（`app/worker/main.py:35-41`）；环④~⑥ = offline `ai-eval-backend` 的 pull_loop / runner / 回推；环⑦ = online verify。**无 tick 端点、无 scheduler**，全靠 worker 轮询。⚠️ **但「等 2 分钟」是错的（2026-09-16 实测推翻）**：trace 的 `ttl_until` = `root_ts + 360s`（`trace_judge_window_s`=60 + `trace_judge_grace_s`=300）⇒ **trace 要过 6 分钟宽限才被判**（`judge_scan_job.py:84` 扫描谓词 = `judged=0 ∧ ttl_until<=now`）⇒ **端到端起板 6~7 分钟**，不是 2 分钟。等短了会把「还没到点」读成「注入无效」。
      - **注入面（已逐容器回读实际进程值，非读 .env 文件）**：4 家统一走 `DEEPSEEK_BASE_URL`，原值 = gq `https://api.deepseek.com/v1`、cs `https://api.deepseek.com`、cc `https://api.deepseek.com`、sp `https://api.deepseek.com/v1`（`sp-app` 与 `sp-worker` 两个容器都有）。⚠️ compose 是 `${DEEPSEEK_BASE_URL:-...}`（**create 时求值**）⇒ 改 `.env` 后必须 `docker compose up -d` **重建**，`docker restart` 无效（同 [[hot-mount-is-not-process-reload]]）。
      - **注入必须让「根请求失败」，否则故障白造（本预案最关键的一条）**：`analyzer/classify.py:17-19`（T-3.10）明写**子节点候选以 `root_status != "ok"` 为前提** —— agent 若把 LLM 异常 catch 成 200 + 兜底话术，即「兜底吸收现场」，**不产 L1/L2 候选**。故黑洞地址须造成**根请求失败/超时**，且**须逐个实证**（不能假定某家一定会 5xx）。
      - **触发面无现成装置（本预案最大成本项，出选项时曾低估）**：online 仓**零 curl 样例**；`e2e_seed.py` / `backflow_e2e_seed.py` 均**不触发 agent**（前者直接在库内建 cluster，**绕过环①观测**）⇒ 4 家的鉴权 + 建会话流程要从零摸；**cc 额外要文件上传 + 后台任务轮询**（文件型、`asyncio.create_task` 后台流，无 HTTP lifecycle 覆盖 LLM）。
      - **顺序铁律**：**逐家**「注入 → 重建 → 触发 → **立即还原 → 重建** → 再等待观察」。还原插在等待之前，使故障暴露面最短 —— 预算耗尽时不会留下「某家 LLM 还指着黑洞」的最危险残留态。
      - **造故障前基线水位（2026-09-16 容器内 UTC 07:49:21 = 本地 15:49 取证，`error_cluster` 22/max 3861、`error_case_link` 21/max 2243、`verify_run_record` 16/max 828、`conversion_record` 69/max 3243）** —— 事后据它区分「我造的红」与真缺陷（同 [[self-injected-fault-looks-like-real-defect]]，前例 = cs LLM 指黑洞产出 4 笔假红 run 3662–3665）。
      - **撤销面**：逐家把 `DEEPSEEK_BASE_URL` 写回上列原值 + `up -d` 重建 + **回读容器内进程值确认**（不信「文件已写/容器已 up」）；造完**当场**把「这批红是我造的 + 起止时刻 + 撤销动作」写进两仓台账。
    - **C1 七环本体 · 施行记录（第一批：gq + cs；2026-09-16 容器内 UTC 07:56~08:16）**：
      - **注入手法（已实证）**：各 agent 仓 `.env` 的 `DEEPSEEK_BASE_URL` → `http://127.0.0.1:9`（容器内该端口无监听 ⇒ **立即 ECONNREFUSED**，不挂起；挂起会永远等不到错误事件）→ `docker compose up -d <svc>` 重建 → **`docker exec <c> printenv DEEPSEEK_BASE_URL` 回读进程内值**。触发后**立即**写回原值 + 重建 + 再回读。
      - **⚠️ 新增必备一步：重建后必须等就绪（`/healthz` 200）再触发**。首轮 cs 未等，触发打在启动窗口上返 **502**，被读成「失败了」——实为**假信号**（真因：容器还没起完）。
      - **结果 ①【cs】✅ 环② 走通**：`cluster 3865 / customer-service / POST /api/v1/sessions/{id}/messages / L1 / llm_connection / status=open / count=1 / first_ts 08:16:00`（基线 3861 ⇒ 增量唯一且归属明确）。判定书 `gate` 四项全 true、`candidate_error_sets=[{llm_connection, evidence=root, count=2}]`。**注入窗口 = 08:09:17 触发 → 08:09:25 还原已回读**。
        - **cs 反直觉但关键的一对观测**：黑洞下客户端收到 **HTTP 200 + `fallback_utterance` 兜底话术**（`total_tokens=0`），**但该请求的根事件仍是 `root_status=error / root_error_type=llm_connection`** ⇒ cs 的兜底只作用在 SSE 给客户端那一层，**没有把根事件吸收**。与 gq 恰成对照（下条）。**此差异只记录事实、不作机制解释**（未查 cs 实现为何如此）。
      - **结果 ②【gq】❌ 环② 按设计不可达**：trace 18493（注入那次）`root_status=ok / root_error_type=None`，`err_summary.entries=[{error_type:"llm_connection", error_msg:"[Errno 111] Connection refused"}]`，判定书 `layer=none`、候选集空。⇒ **子节点埋点完全正常，是根部被吸收**，命中 §6.1「兜底吸收现场（request ok + llm_call error）不产 L1/L2 候选」——**这是 v1 明写的设计行为，不是缺陷**。
        - **顺带证伪一个既往印象**：gq 现有 5 簇（3856~3860）的 `first_trace_id` 是 `clm-good-question-1` / `b6b1-e2e-2026091511…` 这类**手工构造 ID** ⇒ 它们是**探针直接播种进簇表的（绕过环①）**，**不是真实流量**。同类：`probe-c2-push` 的 3847~3854。
      - **⚠️ 我自己的三处探针缺陷（均差点造成假结论，逐条记以免重犯）**：
        1. **`c1_trigger_cs.py` 判 `建会话 != 200` 提前 return** —— 该接口成功返 **201**，于是**消息压根没发出去**，却与「触发了但没成簇」**同形**。修：判 `>=300` 才算失败。（同类：[[unreachable-assertion-vs-false-red]]）
        2. **`c1_wait_cluster.py` 用 pymysql 默认 `autocommit=False`** ⇒ 连接首条 SELECT 即开事务，**InnoDB REPEATABLE READ 下此后全程同一快照**，轮询 420s 看到的永远是旧数据，**差点把 08:16 已成的簇 3865 写成「环②不可达」**。修：`autocommit=True`。**凡轮询脚本必须显式开 autocommit**。
        3. **把「建会话 201」与「建会话 200」当同一件事**（同上第 1 条根因：只按自己脑中的状态码写判据，没按被测接口的契约）。
      - **结果 ③【sp】❌ 环② 不可达（与 gq 同因，已实测非推断）**：trace 18521（注入那次）`root_status=ok / root_error_type=None`，`err_summary=[{error_type:"llm_connection", error_msg:"Connection error."}]`；**过 TTL 后判定书实测** `layer=none`、`candidate_error_sets=[]`（`decided_at 08:31:56`）。SSE 侧 = `meta→thinking→error→usage→done` + HTTP 200 + 「LLM 调用失败，请稍后重试」。注入窗口 08:25:50 触发 → 08:26 已还原回读。
      - **结果 ④【cc】按裁定跳过注入，留证两条**：① **触发面在**——正常上传 `data/test-contracts/good.pdf` 成功（`task_id=640`），并落 trace **18524** `POST /internal/check-tasks/{id}/run`、`llm_fact=1` ⇒ **后台任务确实产事件**（**推翻我此前「后台任务可能连事件都产不出」的未验推断**，该推断当时已标注无证据，现证伪）；② **门是关的**——`backflow_enabled='false'`（v1），且 `agent.backflow_allow` **实测 = 1**（非 `seed.py:40` 声明的 0）。
        - **⚠️ 由②带出的事实订正（非本轮 C1 目标，但须记）**：`seed.py:122` 用 `ON DUPLICATE KEY UPDATE updated_at = updated_at` ⇒ **已存在的 agent 行永不被种子订正**，故 D18 的 `backflow_allow=0` **从未落库**。`classify.py:7-9` 文档所称「cc 双保险」**实际只有一重在工作**（`backflow_enabled`）。方向是 **fail-open**：谁按文档去翻 `backflow_enabled`（以为另一重还兜着），cc 会当场打开。**未改动任何值**，仅登记。
      - **⚠️ 本轮踩到的三处操作坑（都产生过假信号）**：
        1. **sp 的 compose 服务名是 `app`，`sp-app` 只是 `container_name`** ⇒ `docker compose up -d sp-app` 报 `no such service: sp-app` 并**空跑**，而该命令在管道尾接 `tail`，**`set -e` 不触发**（管道退出码取末命令）⇒ 脚本继续跑完，产出一次「容器全程持原值的正常调用」。**救场的是预案里那条「回读容器内进程值」**——`printenv` 显示原值才没把它当成注入结果。**凡注入脚本，回读不是可选项**。
        2. **`localhost` 在 sp 上走 `::1` 返 502**（同一地址 curl 走 IPv4 返 200）⇒ 探针一律写 `127.0.0.1`。
        3. **sp 的 SSE 是 `id:/event:/data:` 三段式**（事件名在 `event:` 行，不在 data 内）⇒ 首版解析只读 `data` + 找 `type` 字段，**全漏**，误报「未调用 LLM」。
      - **cs 的规则短路（选输入必须用判别器，否则注入窗口空转）**：`{"content":"我要退货 ORD-20240801-001"}` 在**黑洞下仍成功作答**且 `total_tokens=0` —— 走的是规则短路（`intent=order_query` + 本地 `query_order` 工具），**根本没调 LLM**。⇒ **触发前先用 `usage.total_tokens>0` 判定「这次真的调了 LLM」**（正常 `你好，请介绍一下你自己` = 1685 tokens、`你们的售后政策是什么` = 5068 tokens）。**判据 = token 数，不是回答内容**。
      - **本批结论的边界（不许被 cs 的绿盖过）**：只走通 **环②**；环③（assemble→link）**尚未等够**，环④~⑦ 未验。且 cs 的这一簇是本批唯一的真实增量。
    - **C1 七环本体 · 施行记录（第二批：cs 环③~⑦ **全通**；2026-09-16 容器内 UTC 08:16~08:46）**：
      - **环③ 组装 ✅**：`error_case_link 2244`（cluster 3865 / payload `4bf40a77-a25a-478b-8cd6-fd515cb1fed4`）+ `conversion_record 3244`（`action=assemble`，08:16:54）。
      - **环④ 拉取 ✅**：offline `error_backflow_inbox 16`（`status=case_created` / `ack=acked`）→ `test_case 4076`（08:17:18）→ **ack 回写 online**：`link.offline_status` 由 `assembled` → **`active`**、`case_id=4076`。
      - **⚠️ 环⑤ 的入口是「信号 run」，不是「回流 case 建成」——本轮最重要的根因发现**：
        - error_regression run 的唯一自动入口 = `orchestrator.maybe_auto_schedule()`，挂在 **`_finish` 末尾**，语义 =「**信号 run（manual/held_out）到达终态**」。**没有任何东西会因「回流 case 建成」而建 run**——回流 case 只是坐进 error suite 等下一个信号。
        - **cs 的信号 run 全部停在 2026-09-01**（最后一条 `3026`）⇒ 该函数 **15 天未被触发**。**这不是缺陷，是本环境没有发版/手测流量**（与既往「缺真实用户流量」是同一根因的第二个面：那个卡采集面，这个卡**信号面**）。
        - **`_decide_schedule` 按 `version` 查 latest error run** ⇒ 复用旧 version 会被那条 `completed` 挡成「不建」；**必须用一条从未用过的新 version** 才走「首建」分支——这正是真实发版的路径。
        - 施行：建 **manual run 3699**（suite 2158 / version `c1-signal-20260916`，刻意可辨认以免被后人读成真实发版）→ 终态 `completed`（17 用例，16 pass/1 fail，score 96.56）→ **触发 error run `3700`**（`trigger_signal_id=3699`，**`case_ids=[4076, 4075]`**——回流 case 4076 被带入；对比历史 3662~3665 均为 `[4075]`）。
      - **环⑤ 判定 ✅**：`eval_result 4798`（case 4076）`pass_fail=pass`、`total_tokens=1500`（确证真调 LLM）；`assertion_results`（JSON 字符串）解析后 = `[{"op":"keyword_not_contains","args":{"path":"answer","keywords":["系统繁忙，请稍后再试，或通过在线客服或留言转人工。"]},"pass":true,"actual":"<cs 真实作答>",...}]` —— **断言明细落库（C-4）在这条真机链上验到**，关键词正是黑洞注入时 cs 返的兜底话术。
      - **环⑥ 回推 ✅**：`verify_run_record 830`（`link_id=2244`、`run_id=3700`、`case_pass=1`、`run_status=completed`）+ `conversion_record 3246`（`action=regression_result`）。
      - **⚠️ 环⑦ 的前置是「人工 claim」——第二个根因发现**：`verify.judge_link` 首句 `if not fv or not case_id: return no_progress`；簇的 `fix_version` **只在 claim 时由运营指定**。未 claim ⇒ **判定链根本不启动**（不是判成 pending，是压根不判）。cs 实测 `fix_version=NULL` / `status=open`。
        - **⚠️ 代做动作（自造物自带标记）**：本轮由探针代做 `POST /api/v1/backflow/clusters/3865/claim`（`fix_version=c1-signal-20260916`，k=2，复核窗至 09-30）。**真实运营里这是人工业务动作**；`conversion_record 3247` 的 detail 已逐字写入 note「C1 七环验收：探针代做的认领动作（非真实运营）」。**后人勿读成真实认领**。
        - `claim_k=2` ⇒ 需**连续两次纯净 pass**。第二轮建 manual run **3701**（version `c1-signal-20260916-2`）→ error run **3702** → `verify_run_record 832`。
        - **结果：`error_cluster 3865.status → 'fixed'`；`error_case_link 2244.verify_status`：`pending → 'passed'`；`conversion_record 3250` `action='auto_fixed'`，detail 逐字「K 满纯净序列（c1-signal-20260916→c1-signal-20260916-2 连续2版纯净 pass）」。**
      - **⚠️ gq / sp / cc 的环②~⑦ 定案：按规格不可达，不动任何代码（用户拍板）**：
        - **规格依据**（回读原文，不靠印象）：`solution_detail.md:323`「LLM 最终失败**无论上层是否 catch 转兜底**，`llm_call` 一律 `status=error`……异常先记后传（先记 error 事件、再抛给业务兜底分支）」；`:1561` X-3 把「被业务 catch 转兜底返回 200 → `request ok + llm_call status=error`」定义为**基础可见性前提**（进指标 + trace 红显），**不产候选**。
        - **gq / sp**：业务刻意 catch 转兜底 ⇒ root 恒 ok ⇒ 落 T-3.10「兜底吸收现场（request ok + llm_call error）v1 不回流（L3 二期）」象限。**这是规格正确执行，不是缺陷**；其 `llm_call` 子节点 error 均已如实落库（符合 X-3 指标面前提）。
        - **⚠️ 三家的根侧 error_type 全部落在 L1∪L2 值域之外**（本轮实测 + 读码，**这是「即便根失败也回流不了」的第二道闸**）：gq `main.py:90/94/253` = `CLIENT_DISCONNECT` / `HTTP_{code}` / `UNHANDLED_EXCEPTION`；sp `core/middleware.py:33/37/59` **同构同值**；cc `check_task_service.py:179-180` = `TIMEOUT` / `CANCELLED` / `INTERNAL_ERROR`。而 `classify._layer_for` 只认 11 个值（L1 七类 + L2 四类）⇒ **判不到任何层**。**四家里只有 cs 通，是因为其业务层显式把 LLM 故障透传成 `llm_connection`**（`cs` 的兜底只作用在 SSE 给客户端那一层，没吸收根事件）。
        - **cc 更彻底一层**：`run_task_async`（`check_task_service.py:184`）是 `asyncio.create_task` **后台异步**，那个 `POST /internal/check-tasks/{id}/run` **派发完即返**，root 与 LLM 故障**结构上解耦** ⇒ 即便开门也不成簇。**故 `dict_config backflow_enabled` 保持 `false` 不动，门不开**（避免一次注定无效的配置变更）。
        - **⚠️ 措辞订正（自纠）**：我在本轮汇报中一度把此现象称为「**双端契约缺口**」，**该措辞过重、已收回**。正确表述 = SDK 接入模板给出的根侧状态码**规格未赋 L1/L2 值**，故判不到层；而 §2.5 的 L2 四类落点也在**子节点**（`:314` db/redis 失败）⇒ **v1 本就不在根侧认任何非 LLM 状态码**，行为自洽。
        - **🔴 2026-09-16 订正：上面两条「cc」的定案均被真机实测推翻（**仅 cc，gq/sp 的结论不变**）**：
          ① **`cc` 的 `llm_call` 子节点走的是白名单值域** —— `contract-check/backend/app/obs.py:140 llm_error_type()` 把 LLM 异常映射为 `llm_connection` / `llm_timeout` / `llm_rate_limit` / `llm_other`（docstring 自陈「平台错误分类白名单值域，**口径对齐 cs**」）。故**本条的判据取的是子节点 `error_type`，不是根侧那个值域**——把根侧 `TIMEOUT/CANCELLED/INTERNAL_ERROR` 当「第二道闸」，**属判据取错了面**。
          ② **「结构解耦 ⇒ 即便开门也不成簇」被实测推翻**：cc 已实测产出 **10 个 L1 簇**（`error_cluster` 3866~3875，`layer=L1` / `error_type=llm_connection`，interface 含 `POST /internal/check-tasks/{id}/run` 与 `GET /api/tasks/{id}/result`）⇒ 后台 `asyncio.create_task` 并不阻止成簇。
          ③ 顺带订正 `:525` 的处置前提：cc 的 `dict_config backflow_enabled` 实测**本就是 `true`（v1，`updated_by='seed'`，非本批次改动）**，不存在「门不开」——「保持 false 不动」一句与库内实值不符。⇒ **cc 的七环在本轮已真实走通（①~⑦），见下「第三批」。**
      - **新增探针（`online/.tmp-probe/`、`offline/.tmp-probe/`，均未提交）**：`c1_signal_run.py`（造信号 run + 等终态）、`c1_claim_cluster.py`（代做 claim）。**【2026-09-17 清理时发现：`c1_signal_run.py` 在被清理的 20 个文件里**根本不存在** ⇒ 本条引用**在清理之前就已是空证据**（正是第三十一笔为 C2 探针转正所要防的那种形态 —— 「引用的资产可能早不存在」，见 memory `no-evidence-still-explained`）；`c1_claim_cluster.py` 本轮已清理，见 T-5.13】**两处踩坑已写进脚注：① offline 响应有 `{code,data}` 信封，token 不在顶层；② `_ver_key` 对非数字段记 0 ⇒ `c1-signal-20260916` 与 `c1-signal-20260916-2` 同归一为 `(0,)`，故都能 ≥ claim 的 fix_version。
      - **本轮人工造物的清单（供后人区分自造 vs 真实，勿混）**：manual run **3699 / 3701**（探针造，version 带 `c1-signal-` 前缀）、error run **3700 / 3702**、cluster 3865 的 **claim**、`online` 侧 `vrr 829/830/832`、`conv 3245~3250`。**真实流量侧的唯一样本 = cs trace `d1994368`（黑洞注入那次）。**
    - **C1 七环本体 · 施行记录（第三批：cc 环①~⑦ **全通**；2026-09-16）**：
      - **本批的核心是一处「参数口径」修复，不是代码缺陷修复**（本批只改了 cc 一个文件 + 一个探针，见下）：
        - **现象**：cc 的候选**成了簇（环②③ ✓）却卡在环④** —— `error_backflow_inbox 20`（同 agent 同接口、`task-645`）`status='rejected'`、`reject_code='online_content_gap'`。**判别力干净：与行 21 的变量只有 `file_path` 一个。**
        - **根因**：online 侧 `evidence.input` 没有下游（offline 评测）能用的路径键。offline 契约 `prepare` 走 multipart，取 `{case.input.file_path}`，且出站前有白名单 `_assert_inside_uploads`（`offline backend/app/adapters/base.py:84`，realpath 必须落在 `/app/uploads` 内）⇒ **online 给的路径必须是「离线容器内」的路径**。
        - **修法（用户拍板「拉齐两边的参数，不是共享卷」）**：cc 合成 span 的 `input` 按**下游口径**写成 `{"task_id": N, "file_path": "/app/uploads/<原始文件名>"}`；`file_path` 取自 `ContractFile.file_name`，**两侧指同一份文件**（离线评测时正是从该路径把这份原件传上来的，multipart 用 `basename` 作文件名，`base.py:73`）。**共享真实文件靠两边口径一致，不靠共享卷。**
        - **对照实证**：行 21 `status='active'` / `reject_code=None` / `case_id=4077`（10:21:22）✅ vs 行 20 `rejected`/`online_content_gap`；**端到端旁证**：cc 于 10:24:52 新建 `task=650, file=61`，与 offline `run 3706` 的 `started_at=10:24:52` **逐秒吻合** ⇒ 离线**真读到了** `/app/uploads/b1_missing_date.pdf` 并上传。
      - **⚠️ 两处「我以为对不对」的事实订正（同一族：跨仓套用）**：① **cc 代码是烤进镜像的、无源码 bind mount** ⇒ `docker compose restart` 对代码改动**无效**，须 `up -d --build backend`（`/app` 是 bind mount 是 **sp** 的事实，**跨仓套用是本 session 第二次犯**）；② 改 `.env` **只需**重建容器（`docker-compose.yml:28` 是 `env_file: ./backend/.env`，注释自陈「本地文件，不入镜像」）—— 我曾口误称「烤进镜像」。
      - **✅ 环⑥ 回推（本批两条机制级新发现）**：
        - **新发现 A —— 环⑥ 有两条独立触发路径，此前台账只记了一条**：`fire_auto_schedule`（挂在信号 run 收尾，§5.3）**之外**，还有 **`reconcile_loop` 的「版本差集对账」（`_INTERVAL=60s`）** —— `anchors`（该 agent 有 manual/held_out **终态** run 的 version）减 `_have_versions`（**已有 error_regression run** 的 version），差集非空则每周期补建 1 个（`reconcile_loop.py:88-115`）。**⚠️ 两条路径本轮只有前者被真机跑到**（见下「触发路径已由日志定案」）；**`reconcile_loop` 这条本轮的绿不能算数** —— 它是读码所得的「存在性」事实，**未取得运行证据**。**而「差集对账能补建 `0.2.0` 之外的版本」这一判断，其前提已在库内核对**：`2299` 的 error_regression **按 version 去重后实测为 5 个** = `0.1.0` / `0.2.0` / `1.16.0` / `1.16.1` / `0.2.1`（查法：`select distinct version from eval_run where agent_id=2299 and trigger_type='error_regression'`）。⇒ 同版确不再建，而 `0.2.1` 是本轮新增的那个。
        - **新发现 B —— `version` 不在 `agent` 表**（该表**无 `version` 列**），完全由 `POST /api/runs` 的**调用方**给出（`api/runs.py:280` `version=body.version`）⇒ **「造版本变更」零配置改动**。
        - **施行**：`POST /api/runs`（`agent_id=2299` / `suite_id=2159` / **`version=0.2.1`** / `manual` / **`case_ids=[3141]` 定向 1 例**，最小成本）→ run 3707 `completed` → **自动补建 error run `3708`**（`trigger_signal_id=3707` **确证因果链**；`case_ids=[4082,4081,4080,4079,4078,4077]` 六例，对**健康的 cc**）→ **六例全 `pass`** → 于 **14:25:46.5** 推送 online：`verify_run_record 837~842`（`bound_version='0.2.1'` / `case_pass=1` / `run_status='completed'`）。
        - **✅ 触发路径已由日志定案（原稿两处凭印象，均订正）**：`ai-eval-backend` 日志（同一 `trace_id` 贯穿）逐毫秒为 ——
          `14:25:08.968 run 3707 _finish 进入（status=running）` → `14:25:08.974 _finish 完成（status=**scoring**）` → **`14:25:08.995 error run 建单：agent=2299 version=0.2.1 signal_run=3707 cases=6`** → `14:25:09.015 run 3708 error 开始复现 6 个 case`；3707 真正 `completed` 在 14:25:18（scoring 走完）。
          ① **实际走的是 `fire_auto_schedule`（信号 run 收尾钩子），不是 `reconcile_loop`** —— 后者虽存在（见新发现 A），**本次事件未用到**。原稿写「自动补建」未区分二者，且曾写「60s 内补建」（实为**同一毫秒级链**，无 60s 分量）。
          ② **顺带订正「信号 run 到达终态」的准确语义**：钩子在 **`_finish` 转入 `scoring` 时**就触发，**不是**等 `completed` —— `scoring` **不在** `_NON_TERMINAL = ('pending','running')` 里（`reconcile_loop.py:36`），故 `_signal_anchors` 把它算作可锚的「终态」。这同时解释了「3708 的 `started_at`(14:25:09) 早于 3707 的 `finished_at`(14:25:18)」这处看似矛盾的值。
        - **干净对照**：同一 link 2249 的历史行 `833~836`（0.1.0 / 1.16.0 / 1.16.1 / 0.2.0）**全部 `case_pass=None` / `run_status='partial_failed'`**（当时 cc 正被注入搞坏）。
      - **✅ 环⑦ 收口（第三个根因发现 + 一处代做动作）**：
        - **根因**：`verify.judge_link` 首句 `if not fv or not case_id: return no_progress`（`verify.py:240-243`）⇒ **簇不认领则判定链根本不启动**；`fix_version` 只在 **claim** 时由运营指定（`backflow/claim.py:107`）。与 cs 批的发现同源，**本条第二次独立复现**。
        - **新发现 C —— 认领后由 `rejudge_job` 重判，不依赖新推送**：`worker/rejudge_job.py:_scan_candidates` 扫 `status=='claim' ∧ 有现行 pending link` 的簇 → 对**已落库行集**重放 `judge_link`（周期 `REJUDGE_INTERVAL_S=60`，`worker/main.py:41`）。
        - **施行（用户拍板「认领，`claim_k=1`」）**：`POST /api/v1/backflow/clusters/3870/claim`（`fix_version=0.2.1`、`k=1`、TTL 14 天）。
        - **结果**：`conv/3271` claim（14:29:06.033，actor=1）→ **`conv/3272` `action='auto_fixed'`（14:29:09.059）**，detail 逐字「K 满纯净序列（0.2.1→0.2.1 连续1版纯净 pass）」；簇 3870 `status='fixed'`、link 2249 `verify_status='pending'→'passed'`。**worker 自打日志为独立佐证**：`14:29:09 INFO [obs.worker.rejudge] rejudge 补判收敛: cluster=3870 link=2249 outcome=fixed_auto`（`_apply_auto_fixed` 全仓**唯一**调用方 = `verify.py:412` 的 `passed` 分支 ⇒ 收口非人工写入）。
      - **⚠️ 本批自造物清单（供后人区分自造 vs 真实，勿混）**：**注入窗口 #1** ≈ 09-15 17:11 本地 ~ 09-16 14:17:58 UTC、**#2** 14:17:21→14:17:58 UTC（`.env` 的 `DEEPSEEK_BASE_URL` → `http://127.0.0.1:1`，已还原并回读进程内值 = `https://api.deepseek.com`）；**cc 簇 3866~3875**；**inbox 行 17/19/20/21/22~25**；**error run 3706/3707/3708**；**manual run 3707**；**簇 3870 的 claim**（`note` 已逐字写明「⑤⑥⑦ 闭环真机验证（0.2.1 为验证用版本）」）；`conv 3265/3271/3272`。**真实流量侧样本 = cs 的 inbox id=16。**
        - **⚠️ 一处自造缺陷（探针）**：`online/.tmp-probe/c1_cc_trigger.py`**【已于 2026-09-17 清理，见 T-5.13】** 原**写死** multipart 文件名 `good.pdf` ⇒ 会让 cc 记下 offline 侧不存在的名字（回流 case 的 `file_path` 指向空文件）。已修 = `os.path.basename(PDF)`，与离线出站口径（`base.py:73`）一致。
        - **⚠️ 一处作废的实验（不许读成「验过了」）**：**窗口 #2 的再注入**基于**错误前提** —— 当时我误以为环⑥ 按「信号」触发，实为按 `(agent, version)` 判且 `0.2.0` 已被 run 3706 占位 ⇒ **task 651 的 case 注定拿不到 run**。该实验**作废**；**但它仍产出真实后果**：case **4082** 已建（簇 3875），此后被 run 3708 一并跑到（`pass`）。**cc 已于 14:17:58 还原，无残留注入。**
      - **⚠️ 一处已知边界（未证伪）**：`ContractFile.file_name` 以「**该 sha 首次上传的名字**」为准（`save_uploaded_file` 命中去重即复用、**不更新 `file_name`**）⇒ 若首次上传名在 offline `/app/uploads` 下不存在，**case 仍会建出**，直到重放时才读不到文件。本轮两个同内容文件恰好都在 offline uploads 才未暴露。
      - **本条能证明什么 / 不能证明什么**：证明 **cc 的七环 ①~⑦ 端到端真实走通**（含 ⑥ 的两条触发路径、⑦ 的 claim→rejudge→auto_fixed）；**不证明**「cc 在全量真实流量下稳定」——本批的 error 样本**全部来自我注入的故障**，无一条真实流量。
      - **未验收边界（显式标，不许被这片绿盖过）**：① **`claim_k=2` 的 `seq≥2` 分支真机未验**（纯函数 `decide_k` 有单测；本批用 `k=1` 只覆盖 `seq=1`）；② 簇 3871~3875 **保持 `open`**，未认领；③ 上条「首名不在 offline」的路径未验。
      - **代码改动（✅ 已提交 cc 仓 `d53be2f`，5 文件 / 162 insertions / 27 deletions）**：`backend/app/api/files.py`（置 `request.state.obs_input`）+ `backend/app/main.py`（四条出口带出）+ `backend/app/obs.py`（`end_request` 增 `input` 形参）+ `backend/app/service/check_task_service.py`（新增 `_obs_task_input()`、`_end_task_span` 增 `input_payload` 口子、四处出口传入）+ `backend/tests/test_obs_wiring.py`（同步改 + 新增 `TestObsTaskInput` 4 例）。单测 **24 passed**；全量 **416 passed / 1 failed**（`test_manifest_fields` 为既有失败，HEAD 上同样红）。
      - **⏳ 未认领项（不是本批产物）**：`task 647~650` 的来源未查明（cc 坏着时**每分钟一次**的上传，每个造出独立 cluster + case）；其后代 case 4078~4081 **已在 run 3708 一并跑到**。
    - **⚠️ 覆盖面如实声明（不许被上面那片绿盖过）**：本轮至今**未产生任何真实 error → 回流样本**；C2/C3 验的是「**词表 × 算子**」这一层，**不能读作「4 家闭环已走通」**——那是 C1 的事。
  - **词表写入的三条硬约束（取证自 offline；写错即假红/假绿，故先定死口径）**：① 匹配 = **子串**（`assertions/ops/text.py:33` `k.lower() in val.lower()`，两侧 lower）；② `KeywordNotContainsOp` 默认 `match="all"` ⇒ **任一关键词命中 `answer` 即判 fail**（= 该 run 落入兜底、回归不通过）；③ `sanitize_words`（`core/error_payload.py:130-153`）= strip→lower→弃空→**弃 `len>200`**→保序去重；**空表 fail-closed**（`runner/pull_loop.py:178` 净化后为空 ⇒ 驳回 `empty_words`，整案收不下）。⇒ **词表条目 = 「一旦作为子串出现就说明这是兜底回话」的辨识性片段**；`MAX_WORD_LEN=200` 使整句安全（无「写长了被静默丢弃」风险）。
  - **阶段 B 待写词表草案（cc / sp；逐条带出处。⚠️ 写前须用户过目——词表归属属运营/业务知识，允许「盘不全」，但不允许编）**：
    - **sp（`smart-procurement`）—— 源码硬编码常量、逐字进 `answer`**：
      1. `根据当前标书内容，未找到与您问题直接相关的信息。` ← `app/ai/agent/agent_loop.py:65` `_NOT_FOUND_ANSWER`
      2. `抱歉，我还没完全理解您的问题。` ← 同文件 `:72` `_UNKNOWN_ANSWER`
    - **sp 降级/拒答提示**（`app/ai/rag/degradation.py:25` `DegradationHint`，8 条逐字）：
      3. `该标书正在解析中，请稍后再试`（`PARSING`）　4. `未找到与该问题相关的依据`（`NO_EVIDENCE`）
      5. `语义检索暂不可用，以下分析仅基于结构化数据`（`SEMANTIC_DOWN`）　6. `AI 推理引擎暂不可用，已切换为人工评审模式`（`LLM_DOWN`）
      7. `核心数据暂不可用，请稍后重试`（`MYSQL_DOWN`）　8. `未识别到有效分数，请人工评分`（`NO_SCORE`）
      9. `LLM 输出分数超出范围，已忽略，请人工评分`（`SCORE_OUT_OF_RANGE`）　10. `AI 未返回有效内容，请人工评分`（`EMPTY_OUTPUT`）
      - ⚠️ **第 3~10 条的落地位置未坐实**：`services/review_service.py:357/427/432` 显示其挂在 SSE `hint` 字段（`thinking` / `score` / `done` 事件），而 offline `core/assembler.py:57` **只把事件类型为 `answer` 的分片拼进 `answer`** ⇒ 这 8 条**可能根本不进 `answer`**。**处置 = 照收（防御性冗余，误伤风险≈0：这些措辞不会出现在正常回话里），但不得据此为「覆盖率」背书**；坐实需查 sp 的 SSE→统一事件映射（**未查**）。
    - **sp LLM 转述项**（`agent_loop.py:88` `_RETRIEVAL_UNAVAILABLE_HINT` **要求 LLM 在回答开头写出**该句 ⇒ 取**核心片段**而非整句，以覆盖改写）：
      11. `检索暂不可用，答案可信度偏低，未经标书验证`
    - **cc（`contract-check`）—— `answer` 构造函数 `app/service/check_task_service.py:436-450`**：
      12. `合同校验失败：任务处于失败状态，未产出有效校验结果` ← `:438`
      13. `合同校验已取消，未完成校验` ← `:440`
      14. `合同校验未完成（当前状态：` ← `:444`（**动态尾**，子串匹配天然覆盖任意 status 值）
      - **存疑、暂不列入（列此以免后人重复盘）**：`合同校验完成，待人工审核`（`:442`，是终态但非失败态）；`合同校验完成，未检出违规项`（`:445`，SUCCESS 基线，**绝不能收**——收了每次正常通过都判 fail）。
      - **未收入（经判定不属兜底面）**：`main.py:53` 的 500 响应体（HTTP 层，不进 `answer`）；`check_task_service.py:689`「文件解析失败」与 `extractor.py:488`「合同文本为空或过短」（均为 **400 / 异常路径**，不构成一次已完成的 run 的 `answer`）。
  - **阶段 C 验证场景清单（4 agent 全覆盖，按「验证面」切分而非按端点数）**：
    - **C1 主链路七环**：真实 error → 观测→聚类→组装→拉取→判定→回归回推→收口 全环走通（**4 家各跑**；唯一能证明「该 agent 能走完闭环」的场景）
    - **C2 `no_fallback` 命中面**：喂**兜底回话**的回归 run ⇒ **必须判 fail**（验本轮新写词表；4 家各跑）
    - **C3 `no_fallback` 不误伤面**：喂**正常回话**的回归 run ⇒ **必须不判 fail**（验词表假红；**与 C2 成对，缺 C3 则「判据」只验了一半**）
    - **C4 状态机恢复**：`requeue` / 重推路径（**复用既有 `r27_positive_seed.py` / `r28_requeue.py` 装置**，抽样，不重复建）
    - **C5 告警面**：停摆 / 积压 / `cap_gap` 探测（**复用 offline `cap_gap_probe_loop` / `ack_stale_probe_loop`**，抽样）
    - **⚠️ 场景充分性的边界（如实标，不许被 C1~C5 的绿盖过）**：C1~C5 的输入仍由**我方自造**，与「真实用户触发的 error」不是一回事（真实流量缺失归 T-5.1 / T-5.6）；**本批次证明「4 家在自造输入下闭环正确」，不证明 T-5.6 的验收目标**。
  - **撤销面（如何回到起点）**：cc `backflow_allow`（0→1）与 cc/sp 词表写入**均可由同一 admin API 反向覆盖**（写回 `0` / 写回 `[]` 即恢复原值，`dict_config.version` 自增留痕）；**阶段 C 探针造出的样本须在收口时清理并登记**（条数 + id 区间 + 清理动作）。
  - **阶段 C 起点基线（2026-09-16 15:31:57 取证，造样本前）**：`error_cluster` 22（max id 3861）/ `error_case_link` 21（max 2243）/ `verify_run_record` 16 / `conversion_record` 67 / `inbox` 12（max id 12）；末尾 cluster = 3861 `cs·llm_timeout·open`、3860 / 3859 `gq·claim`。
  - **复核命令（本条目全部「现状」断言均可由它重取，勿凭印象）**：
    `docker exec obs-backend python -c 'import os,pymysql; c=pymysql.connect(host=os.environ["DB_HOST"],port=int(os.environ.get("DB_PORT") or 3306),user=os.environ["DB_USER"],password=os.environ["DB_PASSWORD"],database="dev.obs",charset="utf8mb4"); cur=c.cursor(); cur.execute("SELECT a.name,d.config_value,d.version FROM dict_config d JOIN agent a ON a.id=d.agent_id WHERE d.config_key=%s ORDER BY a.name",("fallback_utterance",)); [print(r) for r in cur.fetchall()]'`
    （`shared-mysql` 容器**无** `DB_USER`，只有各业务库的 `MYSQL_*` ⇒ 查询须借 `obs-backend` 容器自身的连接串；**此法不回显凭据**。）

- **T-5.9 gq/sp 七环「B 方案」：根事件透传 + 观测入参透传**（**2026-09-17 立**，用户拍板；来源 = 用户令「**我还是要 gq 和 sp 的七环跑通**」）：
  - **⚠️ 本条与前条的拍板冲突，以本条为准**：`:521-526` 的定案是「gq/sp 按规格不可达、**不动任何代码**」（有实测判定书 `layer=none` 撑着）。用户 2026-09-17 明确改口要求跑通 ⇒ **由「判死」转为「改造」**。旧条**不改写**（它如实记录了当时的裁定与证据），此处显式声明口径变更。
  - **断口（读码取证，非推断）**：`analyzer/classify.py:156` 子节点候选**仅在 `root_status != "ok"` 时收集**（T-3.10 兜底吸收门控）；gq/sp 的 LLM 异常被业务吞成 SSE error 帧后**生成器正常结束** ⇒ HTTP 200 ⇒ 出口 `end_request("ok")` ⇒ 根终态 ok ⇒ 撞门。**子节点那条 `llm_connection` 因此永远进不了候选**（值域卫生批已让两家 `llm_call.error_type` 折叠到白名单，值域不构成障碍）。
  - **方案 = B（扩面，两处缺一不可）**：① **根事件透传**（LLM 硬失败 → root 记 error）；② **观测入参透传**（`obs_input`）。**② 不可省**——`converter/envelope.py:92-97`「快照缺 input 实文（`input_snapshot` 空）→ **只计数不组装返回 False**」⇒ 只改 ① 会在**环③**断（`evidence.input` ← `cluster.input_snapshot` ← trace request 事件的 `input` 字段）。**参照实现 = cs**（`main.py:44-73` 出口读 health + `utils/trace.py:19-33` 可变 dict + `deepseek_gateway.py:229/244/261` 置位），cs 注释自陈「记 ok 会让平台把真实故障当作『已被业务吸收』切掉」。
  - **⚠️ 「标记放 LLM 记录出口」已证伪（2026-09-17 二订正 —— 我前两版框法均错）**：gq `llm_service.py:220` 是**每次尝试都记 error**（该函数 docstring `:200-202` 自陈「每次重试都是完整付费调用 → 各记 1 条」），而 `stream_round1_with_retry:422-423` 对 **429/5xx 且未流出任何事件**的情况**会退避重试** ⇒ 重试成功后用户拿到完整回答，却已被标 error = **假红**（把降级当故障的上游化，与我们要修的错正好相反）。⇒ **标记点必须选在「用户可见降级真正产生处」**，即 gq 的 **6 个吞点**（`chat_service.py` 667/830/863/899/966/992 各加一行）。
**gq 记忆压缩那处（`chat_service.py:420`）不标** —— 压缩用 LLM 失败不影响用户拿到回答，标了会把健康请求记成 error。**sp 侧不可照搬此结论**：其 `deepseek_client.py` 9 处同时含「配置错误不重试」与「重试耗尽：最终失败」两类，须在复制那一批**另行核实最终失败点**。
**吞点实测（穷尽模式，仅供范围核对）**：gq = 6 处 LLM 异常吞点（`chat_service.py` 667/830/863/899/966/992）+ 2 处业务 error 帧（594/600「会话不存在」，**非 LLM、不在 B 范围**）；sp = 4 处（`agent_loop.py` 201/205/264/267）+ 2 处路由级 catch-all（`reviews.py:241`/`:311`，第二层吞，咽喉标记后同样覆盖）+ 1 处明写「**吞异常返 None**」（`conversation_service.py:203`）。
**③ 查出的盲区（关键词法永远命中不到）**：**「LLM 正常结束但返回空」走兜底话术、不抛异常 ⇒ 咽喉标记不触发**。gq = `chat_service.py:1027` 落 `_EMPTY_ANSWER_FALLBACK`；sp = `agent_loop.py:114`「AI 未生成有效回复」。**已拍板（2026-09-17）= 不纳入** —— 只覆盖抛异常路径。理由：① 与 cs 完全对齐（cs 也只标异常路径），两家可比；② **纳入也拿不到真机证据**：注故障用的 LLM 黑洞产生的是**超时异常**、不产生空返回，写了就是「无消费方的实现」。⇒ **空返回另立待办，不在本批**（判断条件/是否有重试/是否仅限主对话，均**未查**）。
  - **两家的结构差异（决定实现形状）**：sp 的两条 SSE 路由（`api/v1/reviews.py:201` / `:251`）**没有 `request` 参数**，而写入点在 `agent_loop` **深处**（离路由还有几层）⇒ `request.state` 路线走不通 ⇒ **两家统一用 contextvar 持可变 dict**（cs 同形；cs 注释已写明「标量赋值传不回中间件，故用 dict」）。**勿一家用 contextvar、另一家用 request**——口径必须一致，否则复制 sp 时必踩。
  - **开工前三件只读检查（用户 2026-09-17 拍板落本条）**：
    - **① 环④ 装载闸：已实跑，两家均通过（2026-09-17 起栈后）** —— cfg 由 `ai_evaluation.agent.adapter_config` 原样落盘（**未转写**，避免抄错模板），再用 `offline backend/.venv/Scripts/python.exe` 直调 `check_input_wiring`：gq `{case.input.content}` → `[]`；sp `{case.input.question/bid_id/dimension_id}` → `[]`。
      **正对照（判别力证明，不可省）**：改喂空 dict，gq 报 1 条、sp 报 3 条「…在 evidence.input 中不可达」⇒ 判据不是恒绿，上面的 `[]` 有意义。
      ⇒ **两家环④ 不构成阻塞**（与 cc 当初卡在环④ 的情形不同）。
    - **① 的判据（保留，供复跑）** —— 函数 = `offline backend/app/adapters/engine.py:65`；调用样例 = `offline backend/tests/test_pull_loop_reject.py:333`。**判据 = 真跑函数，不许肉眼看模板**（肉眼看模板正是 cc 那轮踩过的坑）。
    - **② 查 `backflow_enabled`** —— ⚠️ **`backflow_allow` 已有实测记录、勿重复查**（`:452-455` 阶段 B 起点快照：gq=1 / sp=1）。**未查的是 `backflow_enabled`**（`classify` gate 的另一重）。复核命令（⚠️ 列名取自 `classify.py` gate 的四个键，起栈后**先 `SHOW COLUMNS FROM agent` 确认再跑**）：
      ⚠️ **订正：`backflow_enabled` 根本不是 `agent` 表的列** —— `agent` 实有列 = `id / name / display_name / base_url / enable / route_source / backflow_allow / created_at / updated_at`。`backflow_enabled` 是 **`dict_config` 的 per-agent 键**（`analyzer/context.py:15`、`consumer/state.py:39`，缺键回退 True）。复核命令（⚠️ **借容器的 `Settings()` 取连接串，不回显凭据**）：
      ```
      docker exec -i obs-backend python - <<'PY'
      from app.core.config import Settings
      import pymysql
      s = Settings()
      c = pymysql.connect(host=s.db_host, port=s.db_port, user=s.db_user,
                          password=s.db_password, database=s.database, charset="utf8mb4")
      cur = c.cursor()
      cur.execute("SELECT a.name, d.config_key, d.config_value FROM dict_config d "
                  "JOIN agent a ON a.id = d.agent_id WHERE d.config_key='backflow_enabled'")
      print(cur.fetchall())
      cur.execute("SELECT id, name, backflow_allow FROM agent")
      print(cur.fetchall())
      PY
      ```
      **实测结果（2026-09-17）**：`backflow_enabled` 四家（cc/cs/gq/sp）**全 `true`**；`agent.backflow_allow` 四家**全 1** ⇒ **两家回流开关无阻塞**（与 cc 当初 `allow=0` 的情形不同）。
      ⚠️ **现成探针 `online backend/tests/integration/backflow_allow_probe.py` 只覆盖 cc / cs 两行**，不含 gq/sp，**用它证不了本条**。
    - **③ 吞点全量 grep** —— 今天是**关键词命中法**（命中「LLM 调用失败」），**不是穷尽法**：换措辞写的吞点（熔断专用文案、降级引导语、兜底话术分支）不会被命中。**结论须连 grep 范围一起报**（范围 = 两仓 `backend/` 全包根，非单文件）。
  - **已发现、登记备查的两处不一致（不在本批擅改）**：① **sp 断路器「同因不同果」**——流**开始前**熔断 OPEN ⇒ 路由直接 503（`reviews.py:211`）⇒ root 记 `HTTP_503`（**值域外，不产候选**）；流**中途** `CircuitOpenError` ⇒ error 帧 + 200 ⇒ 改后标 `llm_other` **能**产候选。**同一个「AI 不可用」两种形态、一种能回流一种不能。** ② **漏标记即静默退化**——逐点标记意味着将来新增兜底点若忘标记，会**静默回到今天的状态且无任何告警**；本批**不建机制兜底**（不造无人用的抽象），只在台账写明。
  - **批次已拍板（2026-09-17）= gq 先行**：gq 单独一批（2 处标记 + `obs_input` 透传）→ 真机跑通七环 → 验收；绿了再复制 sp。理由：两家**结构不同**（gq 路由带 `request`、sp 路由不带且出口分散 10 处）⇒ 本来就不是同一批；先把「标记 + 透传 + 七环验收」链在一家跑通，第二家是**复制**而非探索。符合「可单独出方案、可单独验收」。
  - **未做（如实声明）**：~~**代码改动面 = 0，尚未动手**~~ **⚠️ 2026-09-17 失效标注：本句已被本条自己的施行记录（`:633` 起）推翻 —— gq 侧实际落了 4 改 1 新增并已提交 `1945ac9`、真机七环验收通过。出现原因是施行记录**追加在后**、而本行未回改；见 T-5.14**。三件只读检查 ① ② ③ **均已实跑**（结论见上，各带复核命令与正对照）；仍空白的只有「空返回兜底」的判断条件/是否有重试/是否仅限主对话（已另立待办）。⚠️ 本条立条时环境曾停（容器全 Exited），上述结论**是后来起栈才取得的**，非立条当时所有。

  - **施行记录（2026-09-17，gq 一家已跑通七环）** —— ⚠️ **本段与 `:599-601`、`:630` 的「6 个吞点各加一行」「2 处标记」口径不一致，以本段为准**（旧条不改写，同 `:596` 惯例）。偏离原因见下「为何不是 6 个吞点」。
    - **实际落码形状 = 1 处置位 + 1 处撤销 + 1 处入参透传**（`git status` 实测：**4 改 1 新增**，`chat_service.py` **未改**）：
      - `backend/utils/trace.py`（+39）：新增 `llm_health_var`（contextvar 持**可变 dict**，非标量——标量赋值传不回中间件）+ `mark_llm_hard_fail(error_type)`（只取首次；上下文缺失时 **fail-loud 打 ERROR 日志**，不静默）+ `unmark_llm_hard_fail()`。
      - `backend/services/llm_service.py:221`：`stream_chat` 的 `except` 内、**在 `record_llm` 之前**置位 —— `record_llm` 本身抛异常也不影响标记。（`llm_error_type(exc)` 复用既有值域折叠，落平台白名单词。）
      - `backend/services/llm_service.py:432`：`stream_round1_with_retry` 重试分支、**在 `time.sleep` 之前**撤销。
      - `backend/main.py`（+31/-9）：中间件在 `obs = _obs()` **之前**置入 `health: dict = {"hard_fail": False, "error_type": None}` 并 `llm_health_var.set(health)`；`_obs_end` 增 `health` 形参，优先级 = **断连 > LLM 硬失败 > HTTP 状态码 > ok**；三处调用点回填。`main.py:275` 的 `UNHANDLED_EXCEPTION` 分支**有意不动**。
      - `backend/api/chat.py:54`（+3）：`request.state.obs_input = body.model_dump()`，**放在归属校验之前**（403/404 也是要归因的 trace，缺现场建不出簇）。
      - `backend/tests/test_llm_hard_fail_marker.py`（新增，6 例）：mock 边界必须是 **`_stream_chat_http`** —— 只 monkeypatch 更外层的 `llm_stream_chat` 则置位点根本不执行，用例只验了撤销、形同虚设。
    - **为何不是 6 个吞点（口径变更的决定性理由 = 撤销）**：`stream_chat` 的 `except` 是 **6 个吞点共同经过的唯一咽喉**，放一处即全覆盖；假红风险（首轮 429 → 重试成功）由 `stream_round1_with_retry` 的**撤销**消掉，`test_retry_then_success_must_stay_ok` 把这条锁死。反过来若按原设计摊到 6 个吞点，每处都要自行回答「这是不是最终失败」，**每处都是一次可能答错的机会**，而咽喉处答案唯一。⇒ 原 `:599` 的结论「标记点必须选在 6 个吞点」**本身没错**（它当时要解决的是「标在记账出口会假红」），只是**撤销**这个手段出现后，咽喉点重新变成更优解。
    - **真机七环验收（2026-09-17，全部为实测，非推断）**：
      - **反例（无注入）**：trace `gqaccept1-220ab86ee8e1` → `root_status=ok` ⇒ **不是「一律记 error」**；同轮确认 `interface` 归一为 `POST /api/chat/{id}`、`input_snapshot` 已落（证明 `obs_input` 生效）。
      - **正例（注 LLM 黑洞）**：`/etc/hosts` 将 `api.deepseek.com` 指向 `127.0.0.1` ⇒ SSE 返 `event: error` 且 **HTTP 200**（正是本批要治的病理）⇒ trace `gqaccept2-ec9de3b906aa` 落 `root_status=error` / `root_error_type=llm_connection`（白名单词）。
      - **①②**：判定四闸全真 → 簇 **3880**（`first_trace_id` = 上述 trace，`error_msg=[Errno 111] Connection refused`）。
      - **③**：link **2255**（`source_trace_id` = 上述 trace；此前历史 link 的 source 全是 `task-NNN` 桩）。
      - **④**：离线 inbox **27** / case **4083**，2s 内 ack（`ack_status=acked`、`reject_code=None`）。
      - **⑤**：建真实信号 run **3709**（手动，suite 2161，version `2026.09.17-verify`，22 case）→ 平台自动派生 error run **3710**（`error_regression`，6 case）。
      - **⑥**：`conversion_record` **3279** `action=regression_result`（名 run 3710 / cluster 3880 / link 2255 / case 4083）。
      - **⑦**：认领（`POST /api/v1/backflow/clusters/3880/claim`，`fix_version=verify-20260917`，`claim_k=2`，TTL 至 2026-10-01）⇒ conv **3280 claim**；再以新 version `2026.09.17-verify2` 建 run **3711** → 派生 error run **3712** → conv **3290 regression_result** → **conv 3291 `auto_fixed` / `closed_by=auto_regression`**（detail 自陈「K 满纯净序列…连续2版纯净 pass」）⇒ 簇 **3880 `fixed`**、link 2255 `verify_status=passed`；`verify_run_record` **848**(run 3710) + **854**(run 3712)，两条相邻纯通过、`seq=2 >= claim_k=2`。
      - **环境事实（省下次的排查时间）**：**gq 无 bind mount ⇒ 改后端码必须重建镜像**（cs/sp 有 `./app:/app/app:ro`，重启即可）。本轮的改动是靠重建镜像生效的——**若未重建，① 环不会出 error**，即七环第一步就断。
      - **⚠️ 自造故障标注（必须可区分于真缺陷）**：gq 于 **2026-09-17 00:43:53 起**被人为切断 LLM 约 3 分钟，手法 = 容器内 `/etc/hosts` 注入（`sed -i` 在该文件上**不可用**——bind mount 不允许 rename，报 `Device or resource busy`；须改为 `grep -v … > /tmp/h.new && cat /tmp/h.new > /etc/hosts`）。**撤销动作 = 同法回写 + 回读 `grep -c` 得 0**，并验 DNS/TCP 恢复。本轮产出物（簇 3880 / link 2255 / 2 条 trace / conv 3273·3279·3280·3290·3291 / inbox 27 / case 4083 / run 3709·3710·3711·3712）**全是我造的红，不是真缺陷**；注入前基线水位 = trace store 155 行、`llm_*` 计数 0。
    - **⚠️ 本轮验收的三条限制（勿读大）**：① **终态证据强度弱**——两轮 pass 用的是**同一个 case 4083**，其输入为自造元指令文本（`注入验收 278b4ae0：…请回答一个全新问题以避开缓存？`），gq 按「元指令」拒答而通过 ⇒ 它证明的是**判定链路走得通**，**不证明** gq 修复后行为正确；② **`fix_version=verify-20260917` 是显式验收标注值**，平台 **R-7 软提示常亮**（`未观测到 good-question@verify-20260917 评测 run`），改用真实版本字面量重认领被拒（`ERR_CLUSTER_0003`，claim 态不允许该迁移），**无端点可改** ⇒ 记载为**已知且可解释**，非缺陷；③ 平台自动 detail 把 `fix_version` 与 `bound_version` 并列表述为「连续2版」，两者不是同一类东西 —— 属平台文案取数口径，**未动**。
    - **复核命令（本条「现状」断言均可由它重取，不借印象）**：
      ```
      MSYS_NO_PATHCONV=1 docker exec obs-backend python -c "import os,pymysql; c=pymysql.connect(host=os.environ.get('DB_HOST') or 'localhost',port=int(os.environ.get('DB_PORT') or 3306),user=os.environ['DB_USER'],password=os.environ['DB_PASSWORD'],database='dev.obs',charset='utf8mb4'); cur=c.cursor(); cur.execute('SELECT id,status,fix_version,claim_k FROM error_cluster WHERE id=3880'); print(cur.fetchone()); cur.execute('SELECT id,verify_status FROM error_case_link WHERE id=2255'); print(cur.fetchone()); cur.execute('SELECT id,run_id,case_pass,bound_version FROM verify_run_record WHERE link_id=2255 ORDER BY id'); print(cur.fetchall()); cur.execute('SELECT id,action,closed_by,detail FROM conversion_record WHERE cluster_id=3880 ORDER BY id'); [print(r) for r in cur.fetchall()]"
      ```
      ⚠️ `DB_NAME` 在该容器内可能是**空串**（`os.environ.get('DB_NAME','dev.obs')` 取到 `''` ⇒ `No database selected`），须写 `or 'dev.obs'`；`verify_run_record` **无 `verify_status` 列**（查询须先 `SELECT *`，勿凭列名猜）。
    - **未做/未提交（如实声明）**：① ~~**未提交任何东西**（gq 仓 4 改 1 新增、online 仓本条均在**工作区**）~~ **⚠️ 2026-09-17 失效标注：已提交并推送 —— gq `1945ac9`（4 改 1 新增）+ online `ea3d008`。本句写于提交之前，属「状态类断言落笔即腐」（见 T-5.14）；同一段的 `:652` 也记了该笔内容，读时以本条为准。**；② **单测与回归**：gq 侧新增 6 例已跑（见 `test_llm_hard_fail_marker.py`），**服务进程端到端未验**（沿用既有裁定：不补）；③ **「空返回兜底」仍不纳入**（`:602` 口径不变）；④ **sp 尚未开工** —— 复制那一批须**另行核实**其 `deepseek_client.py` 9 处的最终失败点（`:600` 已记「sp 侧不可照搬此结论」），以及 sp 路由**无 `request` 参数**这一结构差异（`:603` 已定：两家统一用 contextvar）。

- **T-5.9b sp 真机注入验收（2026-09-17，**已收口**：环①② 真机打通、「环③ 未通」已定因并**转出为独立批次**）**：
  - **⚠️ 自造故障标注**：sp **于宿主 10:56:09 起**被人为切断 LLM（容器内 `/etc/hosts` 注入 `127.0.0.1 api.deepseek.com`；手法同 gq：`grep -v … > /tmp/h.new && cat /tmp/h.new > /etc/hosts`，且**须 `-u root`**——容器以非 root 跑，默认 `exec` 报 `Permission denied`）。**撤销动作 = `docker restart sp-app`**（运行时重生成 `/etc/hosts`），回读 `grep -c 'api.deepseek.com' /etc/hosts` = **0 行 / 总 7 行 = 基线**。本轮产出物（trace `97d26c9a…` / `a397b18e…` / `4f9aa511…`）**全是我造的红，不是真缺陷**。注入前基线水位 = sp trace **33 行**（`agent='smart-procurement'`）、最新 `updated_ts` 2026-09-17 02:26:59。
  - **已验证（新代码在容器内生效）**：`docker exec sp-app python -c "from app import obs; hasattr(obs,'mark_llm_hard_fail')"` → `True`。sp-app 日志三处 `llm.retry`（`attempt=2/3`，`error=Connection error.`）+ 三处 `review.stream_error` ⇒ 确实走到「重试耗尽」分支。**关键否定证据 = 该窗口内 sp-app 日志无任何 `llm_health 上下文缺失` ERROR** ⇒ `llm_health_var.get()` 在业务层拿到的是 dict，**contextvar 跨层可见**（此前只有单测级证据）。
    ⚠️ **本段两处已作废（2026-09-17 同日订正）**：① 原写「`end_request` 形参含 `input`」并据此判「新代码生效」—— 该形参**正是本轮故障源**（镜像内 sdk 无此形参），读到它是**红**不是绿；② 原写「**A 组置位点被真实触发**」—— 该窗口日志里的 `llm_connection` 事件来自**既有的 `record_llm_error`**，与本批置位点无关，**当时没有任何证据能区分二者**。**真正的置位点证据在第二段窗口**（见下条两源互证）；上列日志证据仍然成立，但只证明「走到了重试耗尽分支」，**不证明置位**。
  - **✅ 已定性（2026-09-17 同日订正；原文两种猜测 ①event 未发出 ②平台未消费 —— 两条都不对，故整段改写，勿引旧版）**：真因 = **本轮我引入的 `input=` 回归**。sp **镜像内烤入的 obs_sdk 是旧版**，`end_request` 形参为 `['status','error_type','error_msg','output','duration_ms','extra']` —— **无 `input`**；宿主 `sdk/obs_sdk/__init__.py` 才有 `input`。我按**宿主源码**给 `app/obs.py` 的 `end_request` 加了 `input=` 并在中间件传值 ⇒ 每次请求出口抛 `TypeError`，被 `app/obs.py` 的 `except Exception: logger.debug(...)` **吞成 debug 日志** ⇒ **一条 request 事件都不产出** ⇒ root 恒不到 ⇒ `root_ok=0 / root_status=None`。**取证**：改前（02:20Z）与改后（03:27Z）的 ES 原始事件对照 —— 注入窗口内 `node=request` **零条**，窗口外两条俱在；加容器内 `inspect.signature` 形参实读。**用户拍板止血 = 「直接去掉 `input=` 传参，环③ 单独开一批」** ⇒ `input` 链已连根去掉（`app/obs.py` 的 `set_obs_input` 与 `end_request` 的 `input` 形参、`app/core/middleware.py` 四处 `input=payload`、`app/api/v1/reviews.py` 两处调用全部删除，`reviews.py` 回到 HEAD 同形）。**新增回归锁** = `tests/unit/test_llm_hard_fail_marker.py::test_end_request_passes_only_supported_kwargs`（按**旧版 sdk 签名**起桩，多传任何 kwarg 即 TypeError 转红）。
    ⚠️ **教训（比本缺陷本身更值钱）**：`app/obs.py` 全篇的 `except Exception: logger.debug(...)`（观测边带不炸业务的既有设计）**把「契约不匹配」与「边带偶发故障」折叠成同一个静默分支** ⇒ 整个 agent 的观测哑掉而**无人察觉**、台账上表现为「判定即 ok」。**该兜底模式在四 agent 仓普遍存在**，未改动、列为登记项。
    ⚠️ **本次验收一度误报**：原文曾写「`end_request` 形参含 `input`」并据此判「新代码生效」—— **该句本身是故障源被当成了功绩**，已随本订正作废。
  - **第二段自造故障窗口（2026-09-17，止血后重做）**：宿主 **11:28:24 ~ 11:28:59**（UTC 03:28:24→03:28:59，**共 35 秒**）；注入前已记基线 = ES `node=request` **34 条 / 最新 ts 1789615661461**。**只发一次请求**（断路器 threshold=5，单请求重试累 4 次 ⇒ 第一发能走完，第二发起被闩死，见上条）。撤销 = `docker restart sp-app`，回读 `grep -c deepseek /etc/hosts` = **0**。
  - **✅ 验收证据（决定性，两源互证）**：
    - **ES 原始事件**（trace `…1fbdd98ee7f1`）：`node=request status='error' error_type='llm_connection' error_msg='LLM 调用失败，用户本轮未拿到正常回答'`。**该文案只存在于 `_obs_finish` 的 health 分支** ⇒ 证明 `mark_llm_hard_fail` 置位 → contextvar 可变 dict → 出口读取，**整条链真机跑通**（此前只有单测级证据）。
    - **平台侧入库**：`trace_judge_state` 该行 `root_ok=**1**` / `root_status=**'error'**` / `root_error_type='llm_connection'`。对照止血前同表 4 行全为 `root_ok=0 / root_status=None`。⇒ **七环 ①观测→②判定在 sp 上首次真机打通**，判定侧门控 `root_status != "ok"` 已开闸。
    - **请求侧**：HTTP **200** + SSE 帧序 `meta → thinking → error → usage → done`（账面「正常结束」）——正是环② 断的原型；出口靠 health 而非状态码记 error。
  - **🔴 环③ 仍未通，且已定因（非缺陷、是已知边界）**：`error_cluster` 中 sp **零行**。查得 `worker/cluster_job.py:58`（**Fork A**）—— `root_input_hash` 为 NULL 的行**候选不建簇不计数**，只置 `processed=1`。而 sp 的 `root_input_hash` **恒为 NULL**，因为**入参透传正是被止血去掉的那条链**。⇒ **用户「环③ 单独开一批」那一批是 sp 七环的必要条件**，不是可选项。复核：`select judged,processed,root_input_hash from trace_judge_state where agent='smart-procurement'` 全部 `None`。（另注：该行 `judged=0` 属**预期**，非缺陷 —— 判定窗口 `ttl_until` 未到，`judge_scan_job.py:84` 判据 = `judged=0 ∧ ttl_until<=now`。）
  - **🔴 本轮新发现（非本批引入，待回读规格后再定性）**：**sp 断路器闩死**。路由层前置 `if get_client().circuit_state == "OPEN": raise 503`（`app/api/v1/reviews.py:211`/`:258`）在 `acquire()` **之前**判 `circuit_state`，而状态机只在 `_CircuitBreaker.acquire()` 内做 OPEN→HALF_OPEN 迁移 ⇒ **reviews 这条链**一旦 OPEN 就走不到迁移 ⇒ 自愈永不发生，直到重启容器。实测：第 3 次请求起 503（`0.007s` 返回），且 `docker restart` 前 4 分钟内多次重试**全部 503**。
    - **⚠️ 2026-09-17 两处订正 + 结清**。**① 行号腐**：上面引的 sp `reviews.py:211`/`:258` 现为 **`:229`/`:279`**（文件已移位，属 memory `memory-status-markers-rot` 的「行号引用腐」）。**② 断言过强**：原文「**没有任何请求**会再调用 `acquire()`」**实测不成立** —— sp `app/api/v1/closeouts.py`（`/close` `/prescreen` `/disqualify`）→ `fraud_detection_service.py:503` → `get_client().chat()` → `acquire()`，**该路由无断路器前置门**（全仓 `circuit_state` 只出现在 `reviews.py:191/229/279`）⇒ 有 closeouts 流量时自愈会被**别的入口**触发。准确说法 = **「reviews 自身无自愈能力，解锁要靠他人流量偶然经过」**。原实测（4 分钟内全 503）仍然有效：那段时间里确实没有 closeouts 流量到达。
    - **处置（2026-09-17 已修，sp 仓）**：抽出同步 `_CircuitBreaker._maybe_half_open()`，由 `acquire()` **与 `state` 属性**共同调用（`app/ai/llm/deepseek_client.py`）——路由唯一读到的面就是 `circuit_state`，让它也参与到期迁移，门才能在窗口过后自行放行；**单一真相源仍在`_CircuitBreaker` 内**（没把到期判断复制进路由，避免两处漂移）。**定性 = 实现缺口而非有意设计**：sp 自己的 `task.md` 降级路径测试行写明「断路器半开探测｜连续成功 1 次｜**断路器自动 CLOSE，AI 功能恢复**」，自动恢复是**承诺过的**（判据依 memory `implementation-odd-is-not-defect`：先回读规格再定性）。
    - **验证（含判别力对照，2026-09-17）**：新增**经过路由**的用例 `tests/integration/test_degradation_api.py::test_circuit_self_heals_after_window_through_route` —— 旧用例用**写死 `circuit_state` 的 MagicMock**、单测**直接调 `acquire()`**，**两者都绕过了那道门**，这正是假绿来源。实测：`tests/unit` **378 passed**；`test_degradation_api.py` **6 passed**（原 5 + 新 1）；`test_review_api.py` + e2e 合计 **19 passed**（e2e 另 1 个 **环境 error**，与改动无关：`tests/e2e/conftest.py:72` 线程内 MySQL 连接被拒 ⇒ 真错被线程包装吞成 `KeyError: 'v'`，发生在 fixture setup）。**判别力对照**：临时把 `state` 改回纯读 ⇒ 新用例**转红**；且**先 `grep -c` 确认替换确实改动了文本**（防 sp `task.md` 记过的「变异是空操作 ⇒ 报绿是假绿」重演），事后已还原。
    - **未做/未变**：**cs 仓同缺口未动**（cs 熔断拒绝同样在 `:201` 的 `try` 之外，见 `docs/sp-seven-ring-plan.md:120-121`）；**closeouts 无门只作事实记录、未动其代码**（不碰无关代码）；**未重建 sp 镜像**（本地单测/集成绿，**容器内仍是旧码**，真机行为未复验）。**⚠️ 2026-09-17 订正：本批之后镜像已重建**（实测镜像创建 = `2026-09-17T03:51:02Z` = 北京 11:51，由 T-5.11 的 input 链触发，见该条 §硬闸与镜像）；且 sp 有 `./app:/app/app:ro` **bind mount** ⇒ app 码本就不靠重建生效。复核：`docker exec sp-app python -c "from app.ai.llm.deepseek_client import _CircuitBreaker as C; print(hasattr(C,'_maybe_half_open'))"` ⇒ **True**（断路器修复在容器内确已生效）。见 T-5.14。
  - **覆盖缺口（如实记）**：`agent_loop.py` 的 **B 组 2 处本轮未被真机覆盖** —— 熔断请求在**路由层**即被 503 拒绝，根本没进 agent；本轮覆盖到的是 `reviews.py` 的 **HTTP_503 出口**，不是 `agent_loop` 的 error 帧出口。
  - **复核命令**：
    ```
    docker exec obs-worker python -c "import os,pymysql; c=pymysql.connect(host=os.environ.get('DB_HOST') or 'shared-mysql',port=int(os.environ.get('DB_PORT') or 3306),user=os.environ['DB_USER'],password=os.environ['DB_PASSWORD'],database=os.environ.get('DB_NAME') or 'dev.obs'); cur=c.cursor(); cur.execute(\"SELECT trace_id,root_status,root_error_type,root_ok,updated_ts FROM trace_judge_state WHERE agent='smart-procurement' ORDER BY updated_ts DESC LIMIT 5\"); [print(r) for r in cur.fetchall()]"
    docker logs sp-app --since 20m 2>&1 | grep -iE "llm_health|llm\.retry|stream_error"
    ```
    ⚠️ 该容器 `DB_NAME` 为**空串**（须 `or 'dev.obs'`）；`ai-eval-backend` 容器**无 `dev.obs` 读权限**（`Access denied for user 'evaluation'`），须走 `obs-worker`/`obs-backend`。

- **T-5.10 C2 负对照探针前提腐 → 改为自造负对照行**（2026-09-17；用户拍板选项「探针自造负对照行」）：
  - **症状**：`backend/tests/integration/backflow_allow_probe.py` 2026-09-17 实测 **红 3/7**（`cc 层=none` / `cc gate.backflow_allow=False` / `cc 未建簇`）。
  - **根因（非缺陷）**：探针硬断言 `cc gate.backflow_allow is False`（seed D18 的 `allow=0`）**且不自设该状态**；cc 七环开通时该值已 **0→1** ⇒ 负对照的参照物没了，探针**结构性恒红**，且红的样子与真缺陷同形 —— 属「长期固定红 ⇒ 被读成噪音 ⇒ 真信号淹没」。**memory 里「转正后 7/7」是开通前的事，勿据此认为它还绿。**
  - **改法**：负对照改为探针**自造临时 agent**（`probe-c2-negative`：`backflow_allow=0` / `enable=1` / `route_source='manual'`，其余取库默认），跑完即删；绿不再依赖生产数据「碰巧长成某样」。
  - **顺带消掉一条旧归因边界（实质改进，不只是修红）**：临时 agent **不写** per-agent `backflow_enabled` 键 ⇒ 走「缺键回退 True」（`analyzer/context.py:29`）⇒ gate 上**只有 `backflow_allow` 一条为假**。新增**归因守卫断言** `gate.backflow_enabled is True`：将来该默认值若被翻成 False，探针会**红**，而不是静默退回旧版的「双保险」（旧版 allow=0+enabled=false 两条同时为假，只能证「这一对关闸生效」，**归因不到单条**，见 §5.8 ② 订正）。
  - **验收证据（2026-09-17 真机，非推断）**：**连跑 2 遍**，均 **8/8 全绿**；gate 实打印 `{'agent_exists': True, 'agent_enabled': True, 'backflow_allow': False, 'backflow_enabled': True}`（归因守卫实测成立）；两遍簇 id **3878 → 3879**（递增 ⇒ 真跑新一轮，非复用上轮行）；残留复核 = 临时 agent 行 0 / `c2-` 未判行 0 / 探针簇 0，`agent` 总行数回到 **5**；`ruff` 对改动文件 **All checks passed**。
  - **复核命令**（⚠️ Git Bash 下**必须**加 `MSYS_NO_PATHCONV=1`，否则 `/app/...` 被转成 Windows 路径，报 `No such file` —— 看着像探针不存在，实为路径转换）：
    `MSYS_NO_PATHCONV=1 docker exec obs-backend python /app/tests/integration/backflow_allow_probe.py`
  - **未做/未变**：是否纳入 CI 真库探针 job **仍未拍板**（前置不变 = 先核该 job 的库有没有 seed 出 cs 行）；~~**本条未提交**~~ **⚠️ 2026-09-17 失效标注：已提交 —— `91dec82`（`test(probe): C2 负对照探针改为自造负对照行（T-5.10）`），工作区 clean。本句与 T-5.9 `:659` / T-5.11 `:732` 是同一型「状态类断言落笔即腐」，见 T-5.14。**（本条主题为 C2 探针，**不属七环收口范围**，仅因同类缺陷就地标注，未展开。）

- **T-5.11 sp 环③ 建簇打通（B 方案：sp 侧补埋点透传）**（2026-09-17；用户拍板「我还是要 gq 和 sp 的七环跑通」+ 选 B 方案）：
  - **症状**：sp 七环跑到 ② 即断 —— `error_cluster` 长期 **0 行**（对照 gq 11 行），后三环全部无输入。
  - **根因（`cluster_job.py:58` Fork A，非平台缺陷）**：建簇判据是 `if row.root_input_hash and row.interface:`；而 sp 的 `root_input_hash` **恒 NULL** ⇒ 候选行只被标 `processed=1`，**根本不进建簇分支**。⇒「环③ 单独开一批」是**必要条件、非可选项**，不能靠「再跑一遍」达成。
  - **上游再追一层**：该值唯一写入口是 `consumer/state.py` 的 `if event.input is not None:` ⇒ 依赖 sdk `end_request(input=...)`。sp 侧三个 SSE 出口**从未传过 `input`** ⇒ 平台侧永远是 NULL。
  - **改法**（4 个文件 + 2 个单测）：
    - `app/obs.py`：`end_request` 增 `obs_input` 形参并透传给 sdk。
    - `app/core/middleware.py`：`_obs_finish` 增 `obs_input`，出口读 `request.state.obs_input`（三处调用点全传）。
    - `app/api/v1/reviews.py`：新增 `_obs_input_for()`（**刻意不含 review_id** —— 每次新建评审 id 都不同，纳入会让同问题复发的 hash 分散、聚类退化成「一错一簇」；`bid_id`/`dimension_id` 由评审记录反查）；`/chat` 与 `/score` **两个 SSE 接口都覆盖**（用户拍板）。**写在 gen 外**——gen 惰性，写在里面则中间件收口时 `request.state` 仍无值。
    - `tests/unit/test_llm_hard_fail_marker.py` / `test_obs_wiring.py`：锁出参面；**旧的反向断言（要求 sdk 不含 input）已随本条删除**。
  - **硬闸与镜像**：sp 镜像**必须重建**（sdk 改动烤进镜像，`./app:/app/app:ro` 热挂载只覆盖 `app/`，见 §11.3 同族事实）。重建前打回滚 tag `smart-procurement-app:pre-ring3` → `9a899db7bc0d`。重建后 `obs_sdk` = **0.1.2（含 input）**，硬闸实测通过：
    `docker exec sp-app python -c "import inspect, obs_sdk; print(inspect.signature(obs_sdk.end_request))"`
  - **依赖漂移（已量、已界定）**：`filelock 3.32.6→3.32.7` / `platformdirs 4.11.8→4.11.9` / `pyproject_hooks 1.2.0→1.3.3` —— **全是构建工具链，无业务依赖变动**。
  - **改前单测/静态验证**：sp `tests/unit` **378 passed**；ruff 对**同形目录**比对 HEAD **36 → 工作区 30 条，无新增**（⚠️ 必须 flat-dir 对 flat-dir：目录布局会漂移 isort 的 first-party 判定，跨形比对得出的差值无意义）。
  - **真机验收证据（2026-09-17，双源交叉）**：
    - 源 1（产出端）：`docker exec -u root sp-app` 向 `/etc/hosts` 写黑洞 → `/chat` 连发**两次同一问题**，两条 SSE 均落 error 帧；`trace_judge_state` 该 trace 行 `root_input_hash` **非空**、`input_snapshot_clean` = `{"question": "请结合评分标准，重点说明团队资质这条维度的关键扣分点", "bid_id": "BID-027", "dimension_id": "DIM-LOT-008-1"}`。
    - 源 2（判定端）：TTL 到期后该行 `judged=1/processed=1`，**`error_cluster` id=3881 / layer='L1' / error_type='llm_connection' / count=2 / generation=1 / status='open'`** ⇒ 两条同问落进**同一簇**且**计数递增**，正是用户选定的验收档。
    - **③ 之后链路亦已真机前进（本条范围外，如实记）**：`conversion_record` 3292 组装（05:34:58，payload_id `7345301f-5087-420c-b33d-16eb6efc07ce`）→ 3293/3294 回归 run **3713（sp@0.1.0）/ 3714（sp@0.2.1）** 均 completed → `error_case_link` id=**2256** → case_id **4084**，`offline_status='active'`、`verify_status='pending'`。
      - ⚠️ **`verify_status='pending'` 是 by design 的停驻态，不是「⑥ 没通」**（本条初稿在此处读错过一次，后人勿复犯）：`pending` 是**现行 link 的占位态**（`cur_key` 生成列只在 pending 时取 `cluster_id`，`models/error_flow.py:110`），推进到 `passed` 需 `fix_version`，而 `fix_version` **只由 claim 写入**；推送端点的判定段被 **`cluster.status=='claim'` 守卫**挡下（`worker/rejudge_job.py:12-14` 注释明写「**必须挡**」）⇒ 未认领的簇，link **必然**恒挂 pending。**它的成因是 ⑦ 未做，与 ⑥ 无关。**
    - **⑥ 独立复核（2026-09-17，用户令「另起一条不经过本推导的路径」；结论 = ⑥ 为真，且证据强于初版）**：
      - **证据源 = offline 生产者日志**（`ai-eval-backend`，JSON 结构化）—— 独立于 online 库、独立于本条推导：3713~3717 **五条 run 全部由 `app.runner.reconcile_loop` 差集对账补建**（逐分钟一条、一版一条；锚 run 分别 = `2480/2487/2506/3027/3666`），各「收尾完成 `status=completed pass=1 fail=0 na=0`」。
      - **跨进程对接 5/5 全中**（offline 收尾 ts → online `conversion_record.ts`）：3713 `05:36:06.374→.391`（**+17ms**）/ 3714 `.766→.780`（**+14ms**）/ 3715 `.326→.345`（**+19ms**）/ 3716 `.185→.201`（**+16ms**）/ 3717 `.634→.651`（**+17ms**）。两条独立时钟、两套独立记录 ⇒ **一次排除桩执行与假绿**（同 cs/cc 用过的手法）。
      - **平台侧自陈「已接受」**：5 条 `conversion_record(action=regression_result)` 的 `detail` 均 `cases=1 dropped=0` ⇒ 关联到 link 2256，**非 orphan、非 dropped**；对应 `verify_run_record` id=**855~859**（`case_pass=1`）。⚠️ **判据不是我定的**：cc 的 ⑥ ✅ 证据（`:543`）同形，其对照坏版本行（`:548`）为 `case_pass=None`/`partial_failed` —— sp 这 5 行落在「好」的那一侧。
      - **5 个 `bound_version` 不是串号**：载荷 `raw_json` 逐条 `agent=smart-procurement` + `trigger_signal_id=3881`；`prev_terminal_version` 首尾相接成环 ⇒ 一轮**版本扫掠**（cc 的 link 2249 历史同为 5 版，同形，属正常）。
      - **顺带结掉一笔旧账**：cc 批 `:541` 明写环⑥ 的第二条触发路径 `reconcile_loop`「**本轮的绿不能算数，未取得运行证据**」。**sp 这一轮给了它首个运行证据**（5 次差集对账补建，日志逐字）⇒ **该缺口就此关闭**。
      - **未取到的第三源（如实记，勿读成「验过没问题」）**：原计划再取 nginx `api-gateway` access log 作第三源，`docker logs` 在该窗口**零命中**，**未取到**。
      - **复核命令**：`docker logs ai-eval-backend --since 2026-09-17T05:30:00 2>&1 | grep -E "建单|差集对账|收尾完成" | grep 2297`（`2297` = sp 在 offline 的 `agent_id`）。
    - **结论**：**sp ①~⑥ 首次真机贯通（⑥ 已独立复核）；⑦ 收口未做**。
  - **⑦ 未做的判据（不是「差一点」，是硬前提缺失）**：簇 3881 仍 `status='open'` / `fix_version=None` / **`claimed_by=None`** ⇒ **从未被 claim**，而 **claim 是 ⑦ 的硬前提**。故本条**不得**记成「七环全通」。
  - **⚠️ 自造故障数据 —— 保留并全量标注**（用户拍板；依据 `self-injected-fault-looks-like-real-defect`：人为故障在共享观测面留下的红与真缺陷**逐字同形**，唯一区分手段是标注）：
    - 注入窗口 **2026-09-17 05:27:56Z ~ 05:28:26Z**（hosts 黑洞）；**撤销动作 = `docker restart sp-app`**（`docker restart` 会重生成 `/etc/hosts`，故重启即复原，已回读确认）。
    - 带标记的生产数据：簇 **3881** / case **4084** / run **3713·3714·3715·3716·3717** / `verify_run_record` **855~859** / `conversion_record` **3292~3297** / `trace_judge_state` 中两条 `llm_connection` 行 / `error_case_link` **2256**。**读这些行时必须先回来看本条**。（3715~3717 由 `reconcile_loop` 自动补建，是注入链的**下游产物**，同样属自造面。）
  - **复核命令**（⚠️ 库列名不可凭记忆写，先 `show columns from <表>`；下同）：
    - 簇：`docker exec obs-worker python -c "…"`，SQL = `select id, layer, error_type, count, generation, status from error_cluster where agent='smart-procurement' order by id desc limit 5`
    - 判定态：`select trace_id, root_status, judged, processed from trace_judge_state where agent='smart-procurement' order by updated_ts desc limit 5`
    - ⑦ 是否开工：`select id, status, claimed_by, fix_version from error_cluster where id=3881`
  - **未做/未变（勿读成已完成）**：**本条已提交并推送** = sp `3b2c504`（`382dc82..3b2c504`，5 文件 +94 −40）/ online `439fb8a`（`ea3d008..439fb8a`，只提交 `task.md`），**两笔均快进非 force**、推送后 `git status -sb` 无 ahead/behind（⚠️ 本行初稿写「未提交、未推送」，是**在提交之前**写的，已回改 —— 状态类断言落笔即腐，见 `memory-status-markers-rot`）；gq 侧**未动**；sp 断路器闩死（路由层先于 `acquire()` 判 OPEN ⇒ 自愈永不发生）**未定性、未处置**（**⚠️ 2026-09-17 已变质**：已定性与已处置，见本文件 sp 批记录 `674` 行的结清块）；fail-soft 兜底**仅登记**（**仍未处置**）。

- **T-5.12 sp 环⑦ 收口打通（claim 簇 3881）**（2026-09-17；用户拍板参数「k=2 + fix_version=0.2.1」）：
  - **⚠️ 本条推翻 T-5.11 末尾的「⑦ 收口未做」** —— 那句在写下时是**真的**（当时 `claimed_by=None` 从未 claim，而 claim 是 ⑦ 的硬前提），本条是**状态迁移**，不是订正旧错。读 T-5.11 那两句时必须接着读本条。
  - **①~⑦ 首次真机贯通**：`观测→聚类→组装→拉取→判定→回归回推→收口` 环③ 由 T-5.11 打通，⑦ 由本条打通 ⇒ **sp 七环全通**。
  - **为什么用 `k=2`（本条的增量，不是「镜像 cc」）**：cc 的簇 3870 用的是 `k=1`，`verify.decide_k` 里 `seq` 累积到 2 的那条分支**真机从未验过**（只有单测覆盖）。`k=2` 逼出多步累积 ⇒ 本条补上该分支的**首个真机证据**。
  - **开工前的静态推演（先算后跑，事后逐字吻合）**：输入全已查实 —— 5 版 payload 全 `pass_fail="pass"` / `error_type=null`（**无环境级 na**）/ `cluster.input_truncated=0` ⇒ `route_verdict` 每版均落 `count_k`。取 `fv=0.2.1` → `_ver_key` `(0,2,1) < latest 1.16.0 的 (1,16,0)` ⇒ 过「fix_version 未发版」水位守卫。eligible = {0.2.1, 1.16.0} → 0.2.1 判 `count_k` 得 `seq=1` → 1.16.0 的 prev `0.2.1` **在** `_agent_versions('smart-procurement')` 内（已独立查库确认 = `[0.1.0, 0.2.0, 0.2.1, 1.16.0, probe-b-sp-1]`）⇒ 无 gap ⇒ `seq=2 ≥ 2` ⇒ 终态 `passed`。
  - **真机结果（三处指纹，缺一不可）**：
    - `error_cluster` **3881**：`open` → **`fixed`**，`fix_version=None` → **`0.2.1`**，`claim_due_ts=2026-10-01T05:56:12Z`（TTL 14d）。
    - `error_case_link` **2256**：`verify_status` `pending` → **`passed`**。
    - `conversion_record` **3299**：`action='auto_fixed'`，`detail='K 满纯净序列（0.2.1→1.16.0 连续2版纯净 pass）'` —— **`连续2版` 即 k=2 分支走通的字面证据**。
    - claim 审计行 **3298**：`action='claim'`，`detail` 含 `{"fix_version":"0.2.1","k":2,"ttl_days":14,"note":"…"}`。
    - 驱动方 = `worker/rejudge_job`（60s 轮询，**claim 后无需再推**；worker 日志 `rejudge 完成` 逐分钟可见）。
  - **⚠️ 诚实性标注（本条最关键的一条，勿删）**：簇 3881 的 error **是我自己 injected 的**（hosts 黑洞 05:27:56Z~05:28:26Z，已撤销，见 T-5.11），而那 5 个版本号**没有任何一个真修了什么**，它们只是版本扫掠的产物。claim 的语义是「运营指定修复版本」，写 `auto_fixed` = **给一个从不存在的缺陷开具修复证明**。处置沿用 cc 簇 3870 先例：**claim 的 `note` 逐字写明验证用途**，原文 = 「sp 七环 ⑦ 验收：探针代做的认领动作（非真实运营）；本簇 error 系自造故障（hosts 黑洞，已撤销），0.2.1 为验证用版本，非真实修复」。**代做动作 + 自造缺陷双重性质已同时落库**，读 3881 / 3299 前先读本句。
  - **回滚路径（无一键撤销，事先已知）**：claim → open 有三条既有路径 —— 回归 failed（`verify`）/ TTL 超窗（`claim_ttl_job`，本条 2026-10-01 到期）/ fixed-review `approve:false`。
  - **本条验到 / 未验到（不许让绿盖住）**：
    - **验到**：`count_k` 多步累积（`seq 1→2`）、K 满终态 `passed`、`_apply_auto_fixed` 全链、`rejudge_job` 无新推送驱动判定。
    - **未验到**：`needs_review(input_truncated)` 分支（`input_truncated=0`，本簇天然走不到）；`gap_version` 分支（已独立查库确认不命中）；`fixed_auto` 之外的另两个终态（`reopened` / `needs_review`）。
  - **复核命令**（⚠️ 库列名不可凭记忆写，先 `show columns from <表>`）：
    - 三处指纹一次取：`docker exec obs-worker python -c "…"`，SQL = `select id,status,fix_version,claim_due_ts from error_cluster where id=3881` + `select id,verify_status from error_case_link where cluster_id=3881` + `select id,action,detail from conversion_record where cluster_id=3881 and id>=3298 order by id`
    - 驱动方证据：`docker logs obs-worker --since <claim 时刻> 2>&1 | grep "rejudge 完成"`
    - 探针脚本（**代做动作的原始载体**）：`.tmp-probe/c1_claim_sp_3881.py`（**已于 2026-09-17 清理，见 T-5.13**；清理前未跟踪，docstring 内含 fix_version / k / note 三项的逐条理由）。**该动作本身仍可复核、不依赖脚本存活**：`conversion_record` 3298 的 `detail` 逐字保留了 `{"fix_version":"0.2.1","k":2,"ttl_days":14,"note":"…"}` 四项 —— 台账的复核命令**不该指向临时文件**，本条下面的 SQL 才是权威入口。
  - **未做/未变**：~~gq 侧**未动**（其七环仍未开工）~~ **⚠️ 2026-09-17 失效标注：gq 七环当日**已全通**（T-5.9 实施 + 真机验收，簇 3880 `fixed` / link 2255 `passed`）。⚠️ 此句**写时即为假**（写在 gq 实施 11:41 之后，却沿用了实施前的状态）⇒ 它不是腐化、是当时就错，见 T-5.14**；~~sp 断路器闩死、fail-soft 兜底 —— 同 T-5.11，仍**仅登记未处置**~~ **（⚠️ 2026-09-17 在此行之后变质：断路器已定性与已修，见 `674` 行结清块；fail-soft 兜底仍**仅登记**）。**
  - **提交指纹（回填）**：online **`2a3f3b8`**（`6d0898e..2a3f3b8`，只提交 `task.md`，1 文件 +22），**快进非 force**，推送后 `git status -sb` 无 ahead/behind。⚠️ 本条正文初稿写「**未提交、未推送**」，那是**提交之前**写的、已回填（与 T-5.11 同型，状态类断言落笔即腐，见 `memory-status-markers-rot`）。探针脚本 `.tmp-probe/c1_claim_sp_3881.py` 清理前**未跟踪、未提交**；**2026-09-17 已连同其余 19 个一并清理**（本句落笔时写的「与其余 20 个同处置」当时尚未定，同日由 T-5.13 落实为「转正 2 删 18」）。

- **T-5.13 `.tmp-probe/` 清理：转正 2 / 删 18 + 台账引用订正**（2026-09-17；用户拍板选项「转正 2 删 18 + 订正台账」）：
  - **由来**：`.tmp-probe/` 20 个文件**未跟踪且不在 `.gitignore`** ⇒ 每次 `git status` 都冒 `?? .tmp-probe/`（噪音源久留会长成 `chronic-noise-defeats-gate` 那种「报惯了没人读」）；且其中 `c1_write_wordlist.py` 是**已知必 404 却会「自报成功」**的脚本（见 :460），留着就是给后人埋雷。
  - **转正 2 个**（`backend/tests/integration/`，与既有 `*_probe.py` 同目录同跑法）：
    - `ring_baseline_probe.py` —— 造故障**前**的水位快照（四张主表 + `trace_judge_state` + agent 名→id 映射），stdout 出 JSON。
    - `ring_state_probe.py` —— 按 agent 报环①②③落点行，`--baseline <json>` 做差。
    - **转正时必须改的一处**：原 `c1_rings.py` 把 **2026-09-16 那次验收的基线写死成常量**（`BASE={3861,2243,828,3243}`）⇒ 换个 agent（下一件 gq）或隔几天再跑，「新增≤」一栏就算错、而输出仍像正常结果。转正版**取消默认基线**：不给 `--baseline` 就只打绝对值、不打差（差必须由调用方当次的快照提供）。
    - **实跑验证（转正不跑等于没转正）**：容器内 `docker exec obs-backend python /app/tests/integration/ring_baseline_probe.py > /tmp/bl.json` + `…ring_state_probe.py smart-procurement --baseline /tmp/bl.json` ⇒ 跑通，并顺带在输出里看到 sp 全链现状（簇 3881 `fixed`、link 2256 `passed`）。`ruff check` 两文件 **All checks passed**。
    - **⚠️ 实跑当场抓出一个真缺陷（已修）**：`COALESCE(MAX(id),0)` 在 pymysql 下返回 **`Decimal`**，JSON 往返（`default=str`）后又变 **str** ⇒ 相减 `TypeError`。**败在 fail-loud 上，没有静默成错值**；两处已显式 `int()` 并在代码里留注释（同族见 memory `shape-mismatch-yields-silent-zero`：驱动返回形状不符时别指望它替你归一）。
  - **删除 20 个（逐名列举，非「删了那一堆」）**：`b_write_wordlists.py` `c1_baseline.py` `c1_cc_trigger.py` `c1_claim_cluster.py` `c1_claim_sp_3881.py` `c1_dual_side_online.py` `c1_gate_check.py` `c1_online_tables.py` `c1_rings.py` `c1_trigger_cs.py` `c1_trigger_sp.py` `c1_wait_cluster.py` `c1_watch.py` `c1_write_wordlist.py` `good-question.json` `pending_links.py` `r28_requeue.py` `smart-procurement.json` `sp-deps-after.txt` `sp-deps-before.txt` ⇒ 目录已 `rmdir`。**⚠️ 未跟踪文件无 git 历史，删除不可逆**（用户已知悉）。
  - **台账引用订正（站点全集先 grep 定死，非凭印象）**：`grep -n "tmp-probe" task.md docs/*.md` = **9 处命中，全在 `task.md`，`docs/` 零命中**；逐处加内联标记指向本条，行号 = `453` / `458` / `460` / `463` / `470` / `531` / `555` / `749` / `751`。其中 **`463` / `470` / `531` 混合引用 offline 仓的 `.tmp-probe/` 路径 —— 那些文件不在本仓、本轮未动**，只对 online 侧路径加标记。
  - **🆕 清理过程顺带查出的一笔旧账**：`:531` 引用的 **`c1_signal_run.py` 在被清理的 20 个文件里根本不存在** ⇒ 那条引用**在本轮清理之前就已是空证据**（第三十一笔为 C2 探针转正，防的正是这种形态；memory `no-evidence-still-explained` 的子面）。已在该处就地标注。
  - **口径（本条的产出，供后续引用）**：**台账的复核命令不该指向临时文件路径**。证据要么入库（转正）、要么别引；一次性载体的价值在结论入账那一刻就兑现了，留下路径只会随清理变成空引用。后续新写复核命令请直接给 **SQL / `docker logs` / 已转正探针路径**。
  - **未做/未变**：offline 仓的 `.tmp-probe/`（`c2c3_wordlist_judge.py` / `c3_real_answers.py` / `cs_cases.py` / `why_stopped.py` 等）**未动** —— 那是另一仓的事，且本轮未扫其全集（**不许把「online 侧清完了」读成「两仓都清了」**）；`.gitignore` **未改**（不把噪音源盖起来，删掉它）。

- **T-5.14 gq/sp 七环「全通」收口 —— 写实 + 陈旧状态订正**（2026-09-17；用户拍板「按『已全通』收口」）：
  - **由来**：用户令「4，gq 七环出方案」。本件开工**先回仓复取事实**，发现**该命题的前提已不存在** —— gq 七环当日已实施、已真机验收、已提交（T-5.9）。进一步复核发现 **sp 亦已全通**（T-5.11 环③ + T-5.12 环⑦）⇒ **用户总目标「我还是要 gq 和 sp 的七环跑通！」两家均已达成**。本条的产出因此**不是方案，而是把状态写实**。
  - **⚠️ 本条的元价值 = 一次「视图 ≠ 账本」的实证，记下来防复犯**：「gq 七环未开工」这句在**四处**记录中存活（`docs/gq-seven-ring-plan.md:3`、`task.md:659`、`task.md:754`、memory 台账；写作中又补查出 `task.md:631`，**故陈旧站点全集 = 6，不是 4**，见下），而实物早已 `fixed`/`passed`。**我本轮因此被误导两次**：第一次直接给出「gq 未做」的判断；第二次基于该判断向用户推荐了「转做 sp 环③ 方案」——而 sp 环③ 同样早已完成。**第二次的直接成因 = grep 模式用任务号（`T-5.9`）而非概念词**（「七环全通」/「环③ 打通」）⇒ 整条漏掉 `T-5.11`/`T-5.12`。模式构造纪律见 memory `multi-site-doc-edit-enumerate-first`、`task-list-is-a-view-not-a-ledger`。
  - **实物复核（本条全部为现场实查，不引台账二手结论）**：
    - **gq**：`error_cluster` **3880** `status=fixed` / `fix_version=verify-20260917` / `claim_k=2`；`error_case_link` **2255** `verify_status=passed`；`verify_run_record` **848**(run 3710) + **854**(run 3712) 两条均 `case_pass=1`；`conversion_record` 3273 assemble / 3279 regression_result / 3280 claim / 3290 regression_result / **3291 `auto_fixed`（`closed_by=auto_regression`）**。
    - **sp**：`error_cluster` **3881** `status=fixed` / `fix_version=0.2.1` / `claim_k=2` / `first_trace_id=d005ea43…`（**真 trace，非 `task-NNN` 桩**）；`error_case_link` **2256** `verify_status=passed`（`source_trace_id` 同上）。
    - **对照（防把桩行误读成七环产物）**：`error_cluster` 3874 / 3875 的 `first_trace_id` 仍是 `task-650` / `task-651` **桩**、`status=open` ⇒ 历史遗留，与本件无关。
    - **运行侧旁证**：sp `trace_judge_state` 中 `root_input_hash IS NOT NULL` **7 行**（T-5.11 定因时该值「恒为 NULL」）、`root_status='error'` **6 行**；gq `root_error_type LIKE 'llm%'` **1 行**（T-5.9 记的基线为 **0 行**）。
  - **陈旧状态站点订正（站点全集先 grep 定死再动手；模式 = `未动手|未提交|未推送|未开工|尚未开工|改动面 *= *0`，online 仓 **19 命中**，其中**与本件相关的 6 处**如下。⚠️ 其余 **13 处属别的主题**（§8.5 admin / T-3.13 / 探针清理等），**未动** —— 19 不是本件的改动数。
    ⚠️ **本条初稿报的是「4 处」，那是我第二次数错**（漏 `task.md:631` 与 `docs/sp-seven-ring-plan.md:210`）。**漏因与上一次同源**：我把「七环」嵌进筛选模式去缩范围，而 `:631` / `:210` 那两行**根本没有「七环」二字** —— 恰是 `multi-site-doc-edit-enumerate-first` 所讲「**连『有几处』这个数目本身也是结论，不许凭印象报**」。⇒ 教训升级：**先按概念词穷举、再人工分类，不要用「概念词 + 状态词同现」去缩范围**，后者会把「同一主题但换了个说法的行」整片滤掉）**：
    - `docs/gq-seven-ring-plan.md:3`：原文「状态：待审、**未动手**（代码改动面 = 0）」⇒ 就地订正为「已实施并验收」。该文件 `:1` 标题**早已**写「已实施并验收」⇒ 同一文档自我矛盾。
    - `task.md:659`：「**未提交任何东西**」⇒ 就地加失效标注（gq `1945ac9` / online `ea3d008`）。属「写于提交之前」的落笔即腐。
    - `task.md:754`：「gq 侧**未动**（其七环仍未开工）」⇒ 就地加失效标注。**此句写时即为假**（写在 gq 实施 11:41 之后），**不是腐化**。
    - `task.md:678`：「**未重建 sp 镜像**（…容器内仍是旧码…）」⇒ 就地订正。实测镜像创建 = `2026-09-17T03:51:02Z`（= 北京 11:51，由 T-5.11 的 input 链触发）、`sp-app` 启动于 `05:28:30Z`；且 sp 有 `./app:/app/app:ro` bind mount ⇒ app 码本就不靠重建生效。
    - `task.md:631`（**初稿漏报的第 5 处**）：「**代码改动面 = 0，尚未动手**」⇒ 已被**本条自己的**施行记录（`:633` 起）推翻（gq 实落 4 改 1 新增 + 已提交 `1945ac9`）。成因 = 施行记录**追加在后**、本行未回改。
    - `docs/sp-seven-ring-plan.md:210`（**初稿漏报的第 6 处**）：「**状态**：本方案**未开工、未改任何文件**」⇒ 与**该文档自己的抬头**（`:3`「改动点 A **已实施、已真机验收**」）直接矛盾。实际进度 = A `382dc82`；B 撤出后由 T-5.11（环③）+ T-5.12（环⑦）补完 ⇒ sp 七环全通。**同文档两处结论相反**，与 `gq-seven-ring-plan.md` `:1`↔`:3` 同型。
  - **🔴 仍未验（不许让上面两处 `fixed` / 两处 `passed` 盖过去）**：
    1. **两家七环的 error 全是我注入的**（gq：`/etc/hosts` 黑洞，00:43:53 起约 3 分钟；sp：05:27:56Z~05:28:26Z）⇒ **至今没有任何一条真实用户流量走完七环**。这是「七环跑通」这条结论的**最大边界**，也是「放量前」必须跨过的一道。
    2. **gq 终态证据弱**：两轮 pass 用的是**同一个 case 4083**，其输入为**自造元指令文本**，gq 按「元指令」拒答而通过 ⇒ 证明的是**判定链路走得通**，**不证明** gq 修复后行为正确。
    3. **gq `fix_version=verify-20260917` 是显式验收标注值** ⇒ 平台 **R-7 软提示常亮**（「未观测到 good-question@verify-20260917 评测 run」）；改用真实版本字面量重认领被拒（`ERR_CLUSTER_0003`，claim 态不允许该迁移），**无端点可改** ⇒ 记载为**已知且可解释**，非缺陷。
    4. **T-5.11 的第三源（nginx `api-gateway` access log）该窗口零命中、未取到** ⇒ ⑥ 的独立复核只有**两个**源（offline 生产者日志 + 平台侧自陈），**不是三个**。
    5. **T-5.12 未验到的三支**：`needs_review(input_truncated)` / `gap_version` / `reopened`·`needs_review` 另两个终态。
  - **复核命令（一条取全，不借印象）**：⚠️ **库列名不可凭记忆写，先 `show columns from <表>`** —— 本条写作时我自己就因猜列名（`agent_name` / `root_input_hash`）**连报两次 `1054 Unknown column`**，这正是「凭印象写库命令」的现场代价。
    ```
    docker exec obs-backend python -c "import os,pymysql; c=pymysql.connect(host=os.environ.get('DB_HOST') or 'localhost',port=int(os.environ.get('DB_PORT') or 3306),user=os.environ['DB_USER'],password=os.environ['DB_PASSWORD'],database=os.environ.get('DB_NAME') or 'dev.obs',charset='utf8mb4'); cur=c.cursor(); cur.execute('SELECT id,status,fix_version,claim_k FROM error_cluster WHERE id IN (3880,3881)'); print(cur.fetchall()); cur.execute('SELECT id,verify_status FROM error_case_link WHERE id IN (2255,2256)'); print(cur.fetchall()); cur.execute('SELECT id,run_id,case_pass FROM verify_run_record WHERE link_id IN (2255,2256) ORDER BY id'); print(cur.fetchall())"
    ```
  - **未做/未变**：cs 仓断路器同缺口**未动**；`fail-soft 兜底`**仍仅登记**（用户 2026-09-17 已拍板不处置 ⇒ **不是待办**）；`.env.c1bak` **未删**；offline 仓 `.tmp-probe/` **未动**；`docs/real-traffic-request.md` 的两处（提交人 / 收件方）**未落实到具体人名**（2026-09-17 改为角色占位形态，**不代表已指派**）—— 它正是上面「仍未验」第 1 条的唯一出路，属**用户侧动作**。

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

**结果 10 → 3**（2026-09-16 首次对账）**→ 1**（同日二次订正，见本节末「仍为真待办」）：

| 条目 | 判定 | 依据（逐字摘引 + 行号） |
|---|---|---|
| T-3.15（原记「三问未决」） | **已结清** | 本文件 `:240`/`:263`「三问已裁、(a) 已落地……已 commit + 已 push」（offline `78f1345` / online `7d6f269`）|
| T-3.17（真机证据对账） | **已结清** | 本文件 `:295`/`:305`/`:313`「四仓 backend 镜像已全部重建并上线……✅ 本条结清（2026-09-16）」|
| C-5 规格引用行号漂移 | **登记项·不排期** | `offline/error-backflow-pending-phases.md:842`「判 P3 登记项、**只登记不改**」|
| T-4.15「7d 窗口」/ `inactive` 状态 | **登记项·不排期** | 本文件 `:379`「性质同 T-3.15/T-3.16 = **登记项，不是验收任务**」|
| R-8 自愈支 + online R2 例外 | **已裁·不验** | `pending-phases.md:732`「无真机证据 —— 用户裁定不真机验」⚠️ **不等于「已结清」**：这是**明知的永久边界**，据实记「已裁·不验」，不得写成「做完」 |
| 乙项 requeue reason 门 | **两侧拆明** | online 半已落码（本文件 `:115`，482 passed）；offline 半 `pending-phases.md:741`「**仍为登记项**」|

~~**仍为真待办（3 条）**：C-3 lint 门禁缺口（offline 无 CI、ruff 本机不可用）· `manual_invalidate` 竞态对账未真机触发 · offline §4 未验清单（**6 条** —— 原记「5 条」已过期，第 6 条 2026-09-16 新增）。~~

**➜ 二次订正（2026-09-16 同日，逐条回查；上句三条已动其二、余一条半）**：

| 原记条目 | 现状 | 依据 |
|---|---|---|
| C-3 lint 门禁缺口（**ruff 本机不可用**） | **半结清**：「ruff 本机不可用」已订正（可借 online venv 的 `ruff.exe` 0.16.6；offline 已固化 `backend/ruff.toml`，判据随仓走）；**仍成立的一半 = 「offline 无 CI」**，状态 = **未排期** | offline `error-backflow-pending-phases.md` §6.3 C-3 行（`121d7cf` 之前批次） |
| `manual_invalidate` 竞态对账**未真机触发** | **已结清**：**原措辞作废**——实情是「**未实现**」而非「没机会验」（ack 非 200 分流整体缺失）；经影响面评估（触发条件两侧实测零次）判「**不补**」，附可自动触发的失效条件 | offline `9734ffc`（改判）+ `5c62838`（裁决）；权威处 = offline `error-backflow-status.md` O-D.4 |
| offline §4 未验清单（**6 条**） | **已收束**：4 条可验项结清（含 2 条**证伪**）、2 条标 **`【不可关闭】`** 并带失效条件、不再排期；§7 约定「只能缩短」已改写 | offline `0630827` / `ef6dbcb` / `96d7e20` / `121d7cf` |

**仍为真待办 = 1 条**：**offline 尚无 CI**（C-3 剩余的一半；`ruff.toml` 判据已在仓内，缺的是**自动跑它的门禁**）。
**⚠️ 两条不许读错**：① 「已结清」的是**该条待办**，不是「那个缺口修好了」—— `manual_invalidate` 那条是**判不补**（缺口留着、失效条件挂着）；② 「不可关闭」不是「已验」，是**性质上验不掉**。

**本节的用途**：下次有人（含 AI）看到任务清单只剩 1 条时，能查到这里为什么、以及被移出的 9 条去了哪。**不得据「清单只剩 1 条」推断「项目接近完成」** —— 本仓阶段目标【闭环可用】已于 2026-09-16 收官；剩下这 1 条属维护面（**补门禁**——offline 无 CI），**做完不产生新目标**。

---

## 真实 agent 端到端联调验收（2026-09-16）

**背景**：本台账与 `docs/` 多处（站点全集见文末）长期记「无真实 agent / 卡 T-2.5·S-4 / 环境无输入」，
并据此把 T-5.1 / T-5.2 / T-5.4 与「维度 3 开放验收」判为「无法开工」。
**2026-09-16 据实核查，该前提不成立** —— 四个 agent 早已部署、已接 SDK，且平台**已经真实评测过它们并出分**。

### 一、四层实证

| 层 | 结论 | 证据 |
|---|---|---|
| 服务部署 | ✅ 四个 agent 容器均在跑 | `docker ps`：`customer-service-backend-1` / `contract-check-backend` / `sp-app` / `rag-backend`(gq) |
| 契约可达 | ✅ 四家 `/api/contracts` 全 **HTTP 200** （**⚠️ 边界见下**） | `curl localhost:{8080(gq)\|8000(cs)\|8003(cc)\|18002(sp)}/api/contracts` |
| SDK 接入 | ✅ 四层全齐：代码插桩 + 配置项 + 构建接线 + `.env` **`OBS_ENABLED=true`** | 各仓 `.env`（gq:56 / cs:43 / cc:14 / sp:75）+ 各 `docker-compose.yml` 的 `additional_contexts: obs-sdk` |
| 观测链 | ✅ 四家端到端（Kafka → 消费端 → ES → 查询 API） | 见下 |
| **评测链** | ✅ **离线平台真打真实 agent 并出分** | run **3666 / 3660 / 3038** |

> **⚠️ 本表证什么、不证什么（2026-09-17 补记，用户指示）**：
> **本表证明的是「agent 接入已成立」，不是「有真实用户在打这些 agent」。** 这两件事极易被混为一谈
> —— 尤其第 2 行「**契约可达**」：`/api/contracts` 全 200 只说明**服务在跑、契约端点可达**
> （**2026-09-17 已当场复核**：四容器 `Up`、四家仍全 200、四容器 `obs_sdk` 仍在位），
> 它**与「有没有人用」零关系**：一个 7×24 空转的 agent 同样会返回 200。
> ⇒ 本表**成立与否**，都不改变「**缺真实用户流量**」这个结论（该事实当时为 **0**）；
> 它取消的只是「**无真实 agent / 卡 `T-2.5`·`S-4`**」这个**旧归因**，别把「归因被取消」读成「卡点被解决」。
> ⇒ 本表及其「观测链」各计数（gq 2760 / cs 215 / sp 53 / cc 1、本次可控触发各 +1）
> **全部是平台与评测侧主动打 agent 造的**（同 `docs/real-traffic-request.md:26`「平台上跑过的全部流量都是平台自己主动打 agent 造的」）
> ⇒ **属自造流量**，按 `task.md:392`（T-5.1 那条，逐字「**⚠️ 不得以『本地造流量』替代**」）的口径**不得替代真实流量**，**不解锁维度 3 开放验收**。

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

---

## 浏览器端 UI 验收（2026-09-17）

> **本批边界（先读）**：只验「浏览器 UI 打开 / 登录 / 操作 → 数据在 online 页面上的呈现」。
> **不验**生产流量、不验真实用户路径。批 1 的绿**只覆盖**「页面可达 + 能登录」，不含任何错误路径。

### 一、批 1 侦查（已完成）

6 个前端均可从宿主浏览器打开并登录：

| 系统 | 入口 | 口令 |
|---|---|---|
| contract-check | `http://localhost:8088/` | `123456` |
| smart-procurement | `http://localhost:18082/admin` | `123456` |
| good-question | `http://localhost:8089/` | `123456` |
| customer-service | `https://localhost:8443/chat`（8081 → 301 → 8443，自签证书） | `123456` |
| online | `http://localhost:18080/` | **`12345678`** |
| offline | `http://localhost:8180/` | 见 offline 仓 |

⚠️ `18082` 是**本机 `.env` 改 `WEB_PORT` 后**的值（该文件未入库）。**换机器会回到无宿主端口状态。**

### 二、批 2a–2d 造错：**结论 = 浏览器造不出可回流的错**（已结案）

原定判据「浏览器操作 → 产出端 `error_cluster` +1」**不可达**。三条路均实测定性：

| 路 | 实测 | 为何不聚簇 |
|---|---|---|
| cc 上传非法文件 | `POST /api/files/upload` → **400** `{"detail":"仅支持 PDF / DOCX 文件"}` | `HTTP_400` ∉ 回流值域 |
| gq 超长输入 | `POST /api/chat/1341` → **422** `String should have at most 4000 characters` | `HTTP_422` ∉ 回流值域 |
| LLM 层错误 | 需 LLM 真故障；实测 cc 的 LLM **可达**（`/models` 返 401 = 网络通） | 浏览器不可达 |

**根因（合规格，非缺陷）**：回流值域 = `backend/app/analyzer/classify.py` 的
`LLM_ERR_TYPES`（7 类）∪ `L2_ERR_TYPES`（4 类），**全部是 agent 侧 LLM / 依赖故障**；
客户端 4xx 属「用户输入错」，按设计**不回流**。

**决定性证据**：`trace_judge_state` id=**19017**（cc 那次）的 `judgement_json` =
`{"layer": "none", "root": {"status": "error", "error_type": "HTTP_400"}, "candidate_error_sets": []}`，
且 `judged=1 processed=1` ⇒ **判定确实跑完**，不是等待不足。

### 三、UI 验收（online **8 页全验**；offline 内容页 5 页 + 登录，**已全验**）

#### 3.1 总览页 —— ✅ 无偏差（差异属设计，非缺陷）

UI `cards.total=354`，同刻 `trace_judge_state` 直查 = **349**。

**不是缺陷**：`backend/app/api/metrics.py` 注释明写「计数/error/timeout/序列 = 实时整窗（**准确超集**）」
—— UI 读**原始事件 index(ES)**，判定表是派生态，两者本就不该相等。
逐小时差仅落 4 个小时，且可解释：09-13 那 3 条源于「**09-13 全天全平台零判定行**」
（判定流水线 09-14 02:30 才起步）。

#### 3.2 异常页 —— ✅ 逐列精确匹配，且该行**由浏览器操作产生**

| 来源 | agent | trace_id | 接口 | 状态 | 错误 |
|---|---|---|---|---|---|
| 库 `trace_judge_state` 19031 | good-question | `aa3052dc19d1d6b438a0be42cd2bd8da` | `POST /api/chat/{id}` | error | HTTP_422 |
| UI 异常页首行 | good-question | `aa3052dc19d1d6b438a0be42cd2bd8da` | `POST /api/chat/{id}` | error | HTTP_422 |

（接口被正确归一为动态段 `{id}`。）

#### 3.3 回流看板 —— ✅ 逐项全等

被验项 = 端点 `/api/v1/backflow/overview` 的**全部字段**（口径见 `backend/app/api/backflow.py:447-484`，
响应形状钉死为 `{clusters, links, to_fix, by_agent[]}`）：

未处置 **11** / 复核中 **10** / 已修复 **14**；link passed **14** / pending **20** / failed 0；
待修复集 **10**；分 agent：cc 9·0、cs 1·1、gq 1·5、c2-push 0·3、unknown 0·1 —— **与库内逐项相等**。

> 全部数字用**端点自己的谓词**在库内重算后比对，不是拿别的口径凑。产出命令见 §四末条。
> ⚠️ 复现时手写 SQL 必须抄端点的 `group by` 与过滤条件；分 agent 计数若换了分组维度会得到另一组数
> （本次该端点走的是 `backflow.py:477` 的 `agent_rows` 分组）。

#### 3.4 跨端对账：4 个 agent × 15 条回流用例，**两端 UI 逐字符相等** —— ✅

> **判据（2026-09-17 用户改写）**：不是「UI 值 == 本端库值」，而是**同一批 agent 产生的数据，
> 在 online 与 offline 两端要对得上**。本节按后者验。

**关联键 = `payload_id`** —— 三处都有：online `error_case_link` / offline `error_backflow_inbox` /
offline `test_case`。两库同实例，可跨 schema 直接 join「`dev.obs` ↔ `ai_evaluation`」。

**① 总量链（全平台，不止 4 家）**

```
error_case_link 34 = active 24 + invalidated 10
   ├─ 25 已推 offline（15 active/acked + 10 rejected/acked）
   └─  9 active 尚未推
error_backflow_inbox 25 = 15 active + 10 rejected ；inbox_only = 0
```

**② 状态互不串门**（混淆矩阵无例外）：inbox `active` 15 条**全部**来自 active link；
`rejected` 10 条**全部**来自 invalidated link；`invalidated, 不在 inbox` = 0。

**③ 4 家逐条对穿**（online 簇详情页 ↔ offline 套件页，「回查状态」两值都出现过）

| agent | 簇 | payload 前缀 | 库 verify | online 页 | offline 用例 | offline 套件页 |
|---|---|---|---|---|---|---|
| gq | 3840 / 3841 / 3859 / 3860 / 3880 | `7e8a241a` `7cdf6182` `e63bb7eb` `4217d889` `d0e4e3c8` | passed ×5 | 回归通过 | 3618 / 3619 / 4073 / 4074 / 4083 | ✅ |
| gq | 3856 | `4b1801ce` | pending | 待回归 | 4072 | ✅ |
| cs | 3865 | `4bf40a77` | passed | 回归通过 | 4076 | ✅ |
| cs | 3861 | `d309f8a3` | pending | 待回归 | 4075 | ✅ |
| cc | 3870 | `385e8beb` | passed | 回归通过 | 4077 | ✅ |
| cc | 3871–3875 | `6b71654c` `8e1c6fa4` `85745bff` `bfcec2eb` `42dc4782` | pending ×5 | 待回归 | 4078–4082 | ✅ |
| sp | 3881 | `7345301f` | passed | 回归通过 | 4084 | ✅ |

**④ 双向零孤儿**：回填用例里找不到对应 active payload 的 = **0**；active payload 找不到对应用例的 = **0**。
**⑤ 状态映射双向 1:1**：`passed ↔ 回归通过` 8 条、`pending ↔ 待回归` 7 条，8+7=15，
与库内 4 家 active link 数（gq 5+1 / cs 1+1 / cc 1+5 / sp 1）逐家相等。
**⑥ 每条 payload_id 在两端字面出现**：offline 侧嵌在用例名（`backflow:<uuid>`），
online 侧在 link 行与「组装 D19 信封」时间线里。

##### ⚠️ 本节两个易被后人读错之处（勿复用错误读法）

1. **`links.invalidated = 0` 是对的，不是缺陷。** 回流看板 `links` 五个桶取 `ErrorCaseLink.verify_status`
   （`backend/app/api/backflow.py:459`），**不是 `offline_status`**。库内 `verify_status` 只有
   `pending`/`passed` ⇒ 该桶恒 0 正确。把 `offline_status='invalidated'` 的 10 条拿来比它 = 拿错列。
2. **`version_drift` 在库里有 1 行，但「死分支」结论仍成立。** 该行是
   `backend/tests/integration/backflow_reject_seed.py:14` **种进去的**（`DRIFT_SCHEMA="9.9"`，
   直接 `UPDATE payload_json`）。它**恰因绕开 pull 层直写库**才触发得到 —— 与
   `revision-design-register.md` 「`version_drift` 被 online pull 层上游挡死」是同一件事的两面。
   收件时刻（09-14 09:48）晚于该结论（09-11），**不构成反例**。

**⑦ 已知缺口（与 `revision-design-register.md` 「区分信息不跨端」一致，非本轮新缺陷）**：
offline `reject_code` 回传 online 时**部分塌缩** —— `offline_cap_gap` 1:1 保留（4 条），
但 `version_drift`(1) 与 `content_gap`(1) 在 online 侧均被塌成 `online_content_gap`。

#### 3.5 offline 四页验收（配置中心 / Agent 管理 / 用户管理 / 看板）—— ✅ 3 绿 1 缺陷（缺陷已处置，见 §3.7）

| 页面 | 比对结果 |
|---|---|
| 配置中心 | 3 个 tab 键集**全等**（运行期 16 / 进程级 20 / 注册期 2 = 38 项）；`is_hot`（热生效列）、`updated_at` 逐行相符。**但 3 项只读数值显示错**（见下） |
| Agent 管理 | **59/59 行**；启用开关 59/59 全开 = 库 `enabled` 59/59；契约版本 `2.0` 恰 4 家、凭证「已配置」恰 4 家，与库内同一批；`owner_id` 全 NULL ⇒ 全「未指派」；4 家真实 agent 的 `base_url` 逐字符相符 |
| 用户管理 | 5 行，`id` / 用户名 / 角色 / 启用状态全等（`542`、`521` 库内 `enabled=0`，UI 开关恰为关） |
| 看板 | 门禁墙 6 张有分卡逐值相符（含新验 `probe-c3-auto` 60·1/1、`probe-c4a-pool` 60·5/5）；评测记录 200 条 + 「超 200 条仅展示最新」横幅（库内 `eval_run` 实为 **347**）✓；最新 5 行 `3713–3717` 逐字段相符 |

**缺陷（有两侧机制，非猜测）**：配置中心对**无 `CONFIG_META` 契约的 number 型配置项**以 0 位小数渲染：

| key | 库值 | UI 显示 |
|---|---|---|
| `judge_review_confidence` | 0.7 | **1** |
| `alarm.error_ratio` | 0.5 | **1** |
| `judge_drift_consistency_threshold` | 0.8 | **1** |

根因两侧均已落实：`frontend/src/views/Config.vue:37` 写 `:precision="row._meta?.precision ?? 0"`，
而 `frontend/src/constants/configMeta.js` 里**这三个 key 确实不存在**。对照组 =
`judge_na_threshold` 有 `precision: 2`，UI 就正确显示 `0.30`。
三项均只读（`editable` 为 false）⇒ 影响面 = **展示了与库不符的只读数值**，用户改不了数。
**状态：已修并真机复验，见 §3.7**（下表为修复前现场，保留原样）。

**两处观察（不判为缺陷，仅登记）**：

1. 用户管理里**已禁用**用户的操作列仍写「禁用」（`Users.vue:46` 标签写死，无「启用」反向操作）。**本次未处置。**
2. 配置中心**非 `text` 型**项会**多渲染一个空 JSON 文本域** —— `Config.vue:40` 的单位后缀 `<span>` 用
   `v-if` 另起了一条链，链尾 `v-else` 对所有非 `text` 项为真。**⚠️ 原登记写的是「无契约 number 项」，
   已订正为「非 text 项」——`bool` 行也中招（见 §3.7）。已修。**

**⚠️ 探针坑（差点写成缺陷）**：`el-switch` 的 `<input>.value` 恒为 `"on"`，**不反映开关状态**。
首版取 `value` 得出「`alarm.enabled` 库内 `false`、UI 显示 on」的假差异；
改用 `is-checked` / `checked` 后证实开关是关的，与库一致。
**凡 switch / checkbox，一律读 `checked` 类属性，绝不读 `value`。**

#### 3.6 online 余下 5 页验收（接口 / LLM 失败 / 链路查询 / 系统管理·配置 / 系统管理·账号）—— ✅ 全绿

> 筛选态：`obs.metricFilter` = `{window:"7d", agent:"good-question"}`（模块级单例 + localStorage 持久化）。
> **信源分两类**：接口 / LLM 失败 / 链路查询读 **ES**（`dev.obs-event-*`，链路查询另含 `dev.obs-log-*`），
> **不是 MySQL** —— 拿库去比会得出全错的结论。系统管理两页才读 MySQL（`dev.obs`）。

| 页面 | 信源 | 结果 |
|---|---|---|
| 接口 | ES | **16 请求级行逐值全等**（请求数/错误/超时/P50/P95/P99 全中，含排序）；LLM 级 **1 行** 118 调用 / 23 失败 = **19.49%** 全等；下钻 **2 个模型**全等（`deepseek-chat` 97·3·pt=121088·ct=17419，`deepseek-v3` 21·20·pt=210·ct=0） |
| LLM 失败 | ES | **23/23 逐行全等**（时间 / agent / trace_id / 接口 / 请求状态 / LLM 节点 / 模型 / 错误类型），ES `total` 亦为 23 |
| 链路查询 | ES（event+log） | **全 10 页 × 20 = 200 行逐行、按序全等**（时间 / agent / trace_id / 接口 / **最近节点** / 状态 / 错误）。页脚「共 800 条 trace（检索深度上限 200）」**已独立复现**（见下） |
| 系统管理·配置 | MySQL | **13 行逐值全等**（`dev.obs.dict_config` 中 `agent_id IS NULL` 的 12 行 + `claim_ttl_days`）；version / updated_by=`seed` / 毫秒时间戳全等 |
| 系统管理·账号 | MySQL | **3/3 全等**（`admin`=admin、`clm-probe-admin`=admin、`clm-viewer`=viewer；状态全 `启用` = `status=1`；两个 probe 号 `display_name` 为 NULL ⇒ UI 显示 `—`） |

**两个「看着像不一致、实为正确」的点（先写死，防后人误判）**：

1. 配置页 `claim_ttl_days` 的 version 列显示「**0（seed 默认，库内无行）**」—— 它**确实**没有库行
   （`dict_config` 该键无 `agent_id IS NULL` 的行），UI 是在显式标注「这是默认值、不是库值」。
   **不是缺行，是把缺行如实画了出来。**
2. `dict_config` 另有 **13 行 `agent_id` 非空**（per-agent 的 `fallback_utterance`），本页**不显示** ——
   页面自己的副标题写的就是「v1 生效键（**全局**）」。**不是漏显示。**

**⚠️ 探针坑（本次两条，都会产生假结论）**：

1. **下拉框的选项文本会混进 `innerText`**：`el-select` / 原生 `<select>` 的 `<option>` 都在 DOM 里，
   按 `td.innerText` 取值会得到「viewer\nadmin」这种**两值并列**的假值。本次差点据此报「三个账号
   角色都是 viewer/admin」。**读法：原生 `<select>` 读 `.value`；`el-select` 读其选中态节点。**
   与 §3.5 的 `el-switch` 坑同族 —— **表单控件的 `innerText` 一律不可信**。
2. **转录 id 少一个字符会造出「ES 里查不到」的假缺失**：链路查询第 1 页有一条
   `9f9ab18509df511**9**b359f9d8627a2b7d`，我抄成 `…511b359…`（漏一个 `9`）后 ES 返 0 命中，
   一度判为「UI 显示了库里没有的 trace」。**报「查不到」之前，先把 id 从页面上重新取一次，别用手抄的。**

**链路查询：页脚「共 800 条」与「检索深度上限 200」两数字的关系（本次独立复现）**

原登记只说「第 1 页 20/20 全等、800 未复现」。本次补齐，两条都要记住 —— **800 与 200 不矛盾，是两个口径**：

| 数字 | 口径 | 取证 |
|---|---|---|
| **800** | `cardinality(trace_key)` **去重后的 trace 条数** | 独立脚本照抄 `es.py:42 build_trace_list_body` 直查 ES：`cardinality = 800` |
| **200** | **列表可分页取到的上限**（后端硬闸） | `trace.py:114` `offset ≥ MAX_LIST_RESULTS(200)` → 400 `ERR_TRACE_0002`；`es.py:22` 常量 |
| （2240） | hits.total，**折叠前**的文档数 | 同一脚本回读：`hits.total = {value: 2240}` |

即：**「共 800 条」说的是「7d 窗口内有 800 个不同 trace」，不是「页面能翻出 800 行」**；
页脚那句「检索深度上限 200」是页面自己如实标出了硬闸。**折叠不改 `hits.total`**（它仍是折叠前文档数），
故 `total` 必须以 `cardinality` 聚合为准 —— `es.py:157-160` 正是这么写的，本次回读证实。

**全 10 页比对（UI ↔ ES 逐条）**：UI 侧 `traces-ui.json` 采 10 页 × 20 = 200 行（页号 1→10 正确推进，
200 个 trace_id **全唯一、零重复零遗漏**）；ES 侧用同一 body 取折叠后 200 行。两侧**按序逐位比对**：

```
UI=200  ES=200      顺序敏感全等: True     集合相等: True
UI 独有=0  ES 独有=0     agent 列不符条数: 0
```

**顺序敏感全等**是本次最强的判据 —— 它同时证了「集合相同」与「`ts desc` 排序一致」，
只比集合会把排序缺陷漏过去。

> ⚠️ 窗口边界：我的 `now_ms` 与页面请求时刻不同（窗口整体平移几分钟）。本次**未出现**首尾差异，
> 但这不证明「永不出现」—— 若下次比对出现 1–2 条首尾差，**先查是否落在窗口边界**，别急着判缺陷。

#### 3.7 处置 §3.5 缺陷（配置中心数值失真 + 多渲染文本域）—— ✅ 已修并真机复验

**改了什么（offline 仓 `frontend/src/views/Config.vue`，2 处）**：

1. `:precision="row._meta?.precision ?? 0"` → 新增 `numPrecision(row)`：有 `_meta.precision` 用契约值；
   无契约项**按值推断**小数位（整数 0 位，小数取实际位数）。
   **已知不覆盖**：`String(1e-7)` 是 `"1e-7"`、不含小数点 ⇒ 推成 0 位、显示成 `0`。
   *（第一版曾加「科学计数法给 6 位兜底」分支，复核时发现它**达不到目的**——precision=6 下
   `el-input-number` 渲染成 `0.000000`，同样是错值，只是多一条不起作用的代码，已删除，
   并在代码注释里如实标为已知限制。）*
2. 单位后缀 `<span>` 从**链中间**移到整条 `v-if/v-else-if/v-else` 链**之后**。

**第 2 条订正了 §3.5 观察 2 的定级与范围** —— 登记时写的是「无契约 number 项多渲染一个空 JSON 文本域」，
**实际更宽**：`Config.vue:40` 那个 `<span>` 用 `v-if` 另起了**第二条链**（40 → 41 → 47），
而 `:27`/`:32` 是第一条链。于是链尾 `v-else` 对所有**非 `text`** 项都为真 ⇒
**`bool` 行也在开关旁边多挂一个空文本域**（如 `judge_cache_enabled`）。**遍历 3 个 tab 逐行数控件数**才看出来。

**真机复验（重建镜像后，逐值）**：

| 项 | 库值 | 修前 UI | 修后 UI |
|---|---|---|---|
| `judge_review_confidence`（run） | 0.7 | 1 | **0.7** ✓ |
| `alarm.error_ratio`（global） | 0.5 | 1 | **0.5** ✓ |
| `judge_drift_consistency_threshold`（global） | 0.8 | 1 | **0.8** ✓ |
| `judge_na_threshold`（有契约，对照组） | 0.30 | 0.30 | **0.30** ✓（未受波及） |
| `alarm.enabled`（bool） | false | switch + **空文本域** | switch，**文本域 0 个** ✓ |

行数未变（运行期 16 / 进程级 20 / 注册期 2 = 38）。修后**仅存的两个 textarea** 是 `run_timeout`（库值 null）
与 `llm_allowlist`（空 list），**本就该走 JSON 分支**（placeholder「null（使用默认）」），非残留。

**回归测试**（`frontend/src/views/Config.test.js`，挂载式，对齐仓内 `views/*.test.js` 惯例）：
6 例全绿，全量 11 文件 / 59 例全绿。
**判别力已单独验证**：把 `Config.vue` 回退到修前版本后重跑，**2 red** ——
`expected '1' to be '0.7'`（精度）与 `expected [...] to have a length of +0 but got 1`（多余文本域），
即红的两条正是缺陷本体。**另 4 条在修前修后都绿，是「防修过头」的守卫，不具判别力**，勿当成验证力。

**⚠️ 验证路径坑（本条会让人误判「改了没生效」）**：offline `frontend` 容器**无任何 volume 挂载**
（`docker-compose.yml:76 build: ./frontend`），是 Dockerfile **烤入 nginx 的静态包** ⇒
改源码不重建镜像，容器里就不是这份代码。且 `nginx.conf:50` 只给 `js|css|…` 发 `expires 7d`，
`location /` 未给 `index.html` 显式 `no-cache` ⇒ **重建后浏览器仍可能加载旧入口 chunk**。
本次实测：容器内已是 `Config-DfCe6P81.js`，页面加载的却还是 `Config-BJmgMw97.js`，
`judge_review_confidence` 照旧显示 `1` —— **必须硬刷（reload + ignoreCache）并核对
`performance.getEntriesByType('resource')` 里的 chunk 名**，才算验到新包。

**未处置 / 新登记**：

- §3.5 观察 1（用户管理对已禁用用户仍显示「禁用」，`Users.vue:46` 标签写死）**本次未动**。
- **已订正的一处登记（原框架写反了，2026-09-17 当日取证后重述）**：
  原先我在此登记「`solution_detail.md:889` 说 `judge_review_confidence` 热生效=是，
  而 `configMeta.js` 无此键 ⇒ UI 置灰 = **规格↔前端契约分歧**」，
  并暗示 §3.5 里「补 `CONFIG_META` 条目」那条备选修法可能才是对的。

  **取证结论：UI 置灰是对的，分歧在文档侧。** 链条如下（每节都可复核）：

  1. `backend/app/api/config.py:35-50` `put_global_config` 的准入门 = 该 key 在 `system_config`
     表有行 + `is_hot` 为真 + `validate_sysconfig_value(...)` 通过；**没有独立白名单**。
  2. `backend/app/core/sysconfig_schema.py:15-16`：**meta 缺失 → 直接拒绝**（「缺少配置契约（meta），拒绝热改」）。
  3. 传入的 meta 取自 `DEFAULT_SYSTEM_CONFIG.get(key, {}).get("meta")`；而
     `judge_review_confidence` 在 `backend/` 下 **grep 零命中**（`seed.py` 计数为 0）
     ⇒ meta 为 None ⇒ **PUT 必 400**。故前端「无契约即置灰」的代理**判断正确**，
     且**有测试守着**：`backend/tests/test_frontend_meta_sync.py` 断言
     `configMeta.js` 与 `DEFAULT_SYSTEM_CONFIG` 的 key 集合**双向严格相等**（实跑 1 passed）。
  4. 那些 DB 行 `is_hot=1` 是**历史残留**（seed 里已无此 key），与 `Config.vue:111-113`
     注释所称「无契约残留项（`alarm.*`/`smtp.*` 等）」完全吻合。

  **由此暴露的真问题（新登记，未处置）**：`solution_detail.md` §七 配置项清单表与实现**成片不同步**，
  不是孤例 —— 规格表 **31 项**、`seed.py` **24 项**、**交集仅 20**：

  | 方向 | 数量 | keys |
  |---|---|---|
  | 规格有 / 实现无 | **11** | `assertion_penalty`、`breaker_half_open_probe`、`contract_check_timeout`、`error_rate_block`、`human_review_timeout`、`judge_review_confidence`、`overfit_threshold`、`retry_backoff_max`、`review_llm.base_url`、`review_llm.model_name`、`sse_idle_timeout` |
  | 实现有 / 规格无 | **4** | `judge_cache_enabled`、`judge_cache_ttl_seconds`、`max_active_runs_per_agent`、`scoring_timeout` |

  **⚠️ 不要把「实现里没有」读成「实现漏了 11 个功能」**：这 11 项可能是有意裁剪（设计稿≠订单），
  也可能是真缺口（`error_rate_block` / `assertion_penalty` 听上去像评分侧硬门禁）。
  **本次没有取证，故不下结论**；判定它需要逐项回查处置（属另一批）。

#### 3.8 批 1：cc 真实操作 → 跨端验收（**本批第一次「在 agent 自己的 UI 上操作」**）—— ✅ 验收完成，**带出 1 个真实可复现缺陷 F1（已修，见 §3.9）**

> **背景**：§3.1–3.7 全部是**「验收」**半边（把 UI 显示的值与库里/ES 里的值对上），
> **「操作」半边一次都没做** —— `cc`/`sp`/`gq`/`cs` 四个 agent 自己的前端，本批之前**一个都没打开过**。
> 用户原话「在浏览器端，对 4 个 agent 进行页面功能操作」指的正是这半边。§3.8 起补。

**操作（全部在 `localhost:8088` cc 自己的页面上、由人点击完成）**：

| # | 输入 | 结果 |
|---|---|---|
| 1 | `a5_conflict.pdf`（160 KB，`char_count=28091`） | 任务 **#660 FAILED** @40% |
| 2 | 同上（重跑，验可复现性） | 任务 **#661 FAILED** @40%（**2/2 可复现**） |
| 3 | `good.pdf`（1.7 KB，单段） | 任务 **#662 WAITING_REVIEW** @100% ✓（判别实验，见下） |

**缺陷 F1（真实、可复现、非我注入）** —— 修复与复验见 **§3.9**：

```
error_type : INTERNAL_ERROR
error_msg  : cannot enter context: <_contextvars.Context object at 0x7ebdf781e940> is already entered
interface  : GET /api/tasks/{id}/result      node: request      duration_ms: 7262
```

- **根因（已回读代码 + 判别实验坐实）**：`contract-check/backend/app/llm/extractor.py:532-533`
  ```python
  ctx = contextvars.copy_context()
  results = list(ex.map(lambda s: ctx.run(_single, s, partial_model, schema), segments))
  ```
  **同一个 `ctx` 被 `ThreadPoolExecutor` 的多个 worker 并发 `run()`** —— `Context.run()` 并发进入会抛
  「already entered」。`max_workers = min(len(segments), MAX_PARALLEL=8)`（`:528`）。
- **判别实验（不是推测，是跑到才写的）**：`SINGLE_SEGMENT_CHAR_LIMIT=20000`（`:26`）⇒
  `char_count=28091` 被切成 ≈9 段、8 线程并发 ⇒ 必撞；`good.pdf` 极小 ⇒ 单段 ⇒ 无并发 ⇒ **不报错**。
  **实测与预测逐条吻合**（662 跑到 100%）。
- **为什么一直没被发现**：验收样本集里唯一的「正常件」`good.pdf` 只有 1.7 KB，
  **正好绕开了并行路径** —— 样本集**不含多段用例**。
- ⚠️ **归属已验**：这是 cc 仓自身的缺陷，**不是**平台（online/offline）的问题。

**缺陷 F2（同一次操作里暴露）**：错误信息把 **Python 原始异常串连同内存地址
`0x7ebdf781e940`** 直接显示给终端用户（cc 页面「任务 #660 FAILED 40% cannot enter context…」）。

**观察 O1（不判缺陷，仅登记）**：任务 FAILED 后**上传按钮保持禁用**，刷新页面才恢复。
可能是「一次只允许一个任务」的有意设计，本次未取证，不判。

**跨端结论（用户判据：「同一份 agent 产生的数据在两端对得上」）**：

| 端 | 结果 |
|---|---|
| **online** | ✅ **逐字对得上**。链路查询详情页 `/traces/contract-check/task-660` 显示 `2/2 事件`：seq0 `request` `error` + 完整 `error_msg`、seq2 `llm_call` `ok`（`deepseek-chat`，prompt 3050 · completion 2398 · total 5448）。与 ES 原始事件、与 cc 页面上的报错**三处逐字一致** |
| **offline** | **零新增**（`eval_run` 仍 24 行 / max id 3708；`test_case` 仍 149）。**这不是缺陷** —— 成功流量本就不进离线；失败两次的错误又被值域挡（见下） |

**🔴 关于「真实流量走七环」这条，本次拿到了一个比原先更精确的结论**：

原来的记载是「无一条**真实用户流量**走完七环」。本次**真实流量到了、也产生了真实 error**，
但它**进不了七环** —— 被**回流值域**挡在门外：

- 值域 = `backend/app/analyzer/classify.py:38-51`，**恰好 11 词**
  （L1 七类 `llm_*` + L2 四类 `llm_interface_business`/`external_non_llm`/`db_error`/`redis_error`）。
- `INTERNAL_ERROR` **不在其中** ⇒ 不建簇。**实测佐证**：`dev.obs.error_cluster` 最新仍是 **3881**
  （sp，2026-09-17），本批**未新增任何簇**。
- 故本批**仍未能让真实流量走完七环** —— 但成因从「没有真实流量」**订正为**
  「**真实流量来了，其错误类型不在回流值域内**」。这两句不是同一回事，后者可查、可复现。

> ⚠️ **本文写的是「值域不含 INTERNAL_ERROR」这个事实**，**不是**「值域该不该含它」的裁决 ——
> 那属于设计决策，本次不下结论。

**复核命令**：

```bash
# ① 本批三次操作在 ES 的新增事件（基线 = 操作前 max ts）
#    48 条 request 事件 + 3 个 task trace；F1 的两条可按下式直接取
#    见 §3.6 末的 ES 查询模板，filter: agent=contract-check, ts>操作前基线, must_not node=heartbeat
# ② 回流值域（11 词）
sed -n '37,51p' backend/app/analyzer/classify.py
# ③ 根因（并发复用同一 Context）
sed -n '528,534p' ../contract-check/backend/app/llm/extractor.py
sed -n '26,31p' ../contract-check/backend/app/llm/extractor.py   # 20000 / 3500 / 8 三个常量
# ④ 未新增簇（最新仍应是 3881）
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -t -e \
  "select id,agent,error_type,status,first_trace_id from \`dev.obs\`.error_cluster order by id desc limit 3;"'
# ⑤ offline 零新增
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -t -e \
  "select count(*) cnt,max(id) from ai_evaluation.eval_run where agent_id=2299; select count(*) from ai_evaluation.test_case;"'
```

**本批证不了什么（勿外推）**：

1. **证不了「真实用户用了系统」** —— 操作是我在浏览器里点的，仍**不是真实用户**。
2. **证不了七环** —— F1 的错误进不了值域；`good.pdf` 那条是成功流量，本就不回流。**七环的 error 分支仍无真实流量**。
3. **证不了 `sp`/`gq`/`cs`** —— 本批只做了 cc 一家（批 2/3/4 未开工）。
4. **F1 的修复未做** —— 本批只取证、未改 cc 代码（改 cc 属另一仓另一批）。→ 已于 §3.9 修复并复验。

#### 3.9 F1 修复 + 真机复验（**批 1 的补章**）

**改动**：`../contract-check/backend/app/llm/extractor.py:528-539`（cc 仓，1 处）：

```python
# 前：ctx 在循环外取一次，被 min(len(segments), 8) 个 worker 并发 run() ⇒ 并发 enter 同一 Context
ctx = contextvars.copy_context()
results = list(ex.map(lambda s: ctx.run(_single, s, partial_model, schema), segments))
# 后：每段各拿一份副本
parent_ctx = contextvars.copy_context()
results = list(ex.map(lambda s: parent_ctx.copy().run(_single, s, partial_model, schema), segments))
```

**修法上有个陷阱（已实测排除）**：**不能**把 `copy_context()` 挪进 lambda —— 那拷的是 **worker 线程自己的空上下文**，会丢掉提交方的 task span，**修好并发却弄坏 `record_llm` 的观测锚点**。实测 `parent_ctx.copy().run()` 在 4 个 worker 里读到的仍是提交方设的值 ✓。

**实验室判别实验**（容器内 Python 3.11.16，临界区 `time.sleep(0.3)` 拉长）：

| 写法 | 8 线程结果 | 耗时 |
|---|---|---|
| 共享同一 ctx（原） | **7/8 报错**，串与生产逐字同形 | 0.30s |
| 各自 copy（新） | **0/8 报错** | 0.30s |

⇒ 修复有效，且**并行性未损**（耗时相同）。⚠️ 注意：若不拉长临界区，两种写法**都报无错** —— 该实验本身若不设争用就无判别力。

**🔴 为什么既有 58 个绿单测没抓住它（已定位到具体那一行）**：`cc/backend/tests/test_defensive_paths.py:276-284`
`test_segmented_llm_error_clean_failed` **确实构造了多段输入**（`SINGLE_SEGMENT_CHAR_LIMIT // 12 + 100` 行 ≈ **21,000 字符 > 20,000**）⇒ **确实开了 8 线程**。
但它用 `patch.object(extractor, "call_json", side_effect=LLMError(...))` —— 替身**瞬间抛异常、临界区长度为零** ⇒ 8 个线程**永远不重叠** ⇒ **撞不上**。
**故 F1 活了这么久的成因不是「缺一条覆盖多段的测试」，而是「那条测试里没有争用」**（memory `concurrency-test-needs-contention-proof` 的教科书式实例：**跑在并行路径上 ≠ 并发真的发生**）。
⇒ 本次**未新增回归测试**（按拍板口径只修不扩）：**该缺陷目前仍无任何测试守护**，后人改回共享 ctx 不会变红。要补须让替身带 `time.sleep` 制造重叠，**属另一批**。

**真机复验**（cc UI 重传同一份 `a5_conflict.pdf` → 任务 **#663**）：

| 口径 | 修前（#660/#661） | 修后（#663） |
|---|---|---|
| 任务终态 | FAILED @40% ×2 | **WAITING_REVIEW @100%** |
| 抽取质量 | — | **COMPLETE** |
| `request` 事件 | `error` / `INTERNAL_ERROR` | **`ok` / error_type=None** |
| `llm_call` 事件 | — | **8 条全 `ok`**（+3 条后段），零 INTERNAL_ERROR |
| 耗时 | 7262ms（中途炸） | 12468ms（跑完） |

**并发争用证据**（不是「跑绿就算过」）：8 条 `llm_call` 启动时刻 `…427861 / 427953 / 428132 / 428140 / 428156 / 428331 / 428511`，**彼此仅隔 8~200ms**，而各自 duration 1167~1827ms ⇒ **时间窗高度重叠**，确属并发。这也解释了 cc 页面上出现的「**跨段字段冲突**（已标低置信）」——多段并行真的发生了。

**跨端核（修后同样是三处一致）**：
- **online UI** `/traces/contract-check/task-663` = **12/12 事件**，seq / 时间 / 耗时 / usage 与 ES 原始事件**逐字全等**（如 seq=18：`prompt 3050 · completion 2398 · total 5448`）。
- **offline 零新增**：本批（09-18 08:13）在 `eval_run` **无新行** —— 以 `id > 3705` 实查，3709~3717 全部是 09-16/09-17 的历史行（**这不是「本批没新增」的间接推断，是逐行看时间戳**）。成功流量不进离线，失败那条进不了值域，两侧都符合设计。
- **回流零新增簇**：最新仍 **3881**（09-17 05:34）。

**失败证据保留**：`task-660`/`task-661` 两条 `INTERNAL_ERROR` 事件**仍在 ES**（`error_msg` 含 `cannot enter context: <_contextvars.Context object at 0x7ebdf781e940>`）—— 修复**没有覆盖**失败现场，两批证据并存成对照。

**🔴 本批订正我一处错报**：批 1 时我报「offline `eval_run` max=3708」，**该数字是错的**（真实 3717）。结论（本批零新增）不变，但当时那个数字不是当次实查所得，已作废。

**复核命令（§3.9 增补）**：

```bash
# ① 容器内确认跑的是新代码（cc 无源码 bind mount ⇒ 必须重建镜像，只重启无效）
docker exec contract-check-backend sh -c 'grep -n "parent_ctx" /app/app/llm/extractor.py'
# ② 修后任务的 ES 事件（应全 ok、零 INTERNAL_ERROR）
curl -s "http://localhost:39200/dev.obs-event-*/_search" -H 'Content-Type: application/json' \
  -d '{"size":50,"sort":[{"ts":"asc"}],"query":{"bool":{"filter":[{"term":{"trace_id":"task-663"}}]}}}'
# ③ 失败证据未丢（应仍是 2 条 INTERNAL_ERROR）
#    同上查询，trace_id 换 terms:["task-660","task-661"]，filter 加 {"term":{"status":"error"}}
# ④ offline 本批零新增（逐行看时间戳，勿只看 max）
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -t -e \
  "select id,agent_id,started_at from ai_evaluation.eval_run where id > 3705 order by id;"'
```

**§3.9 证不了什么**：① 仍**不是真实用户**（我在浏览器点的）；② cc 仓的改动**未提交**（是否提交由人定）；③ 一次成功**不能证明**该并发缺陷在全部分段规模下都不再出现（只在 ≈9 段这一档复验过）。

#### 3.10 批 1 补章：cc 四个视图补全 + 复核提交走通（**带出 3 条新发现**）

> **由来**：用户质问「cc 彻底验证完了吗」—— **答：没有**。§3.8/3.9 只覆盖了 cc 前端 4 个视图里的 `Workbench` 的上传半边；
> `History` / `Rules` **一次都没打开**，`Login` 只走过「401 被迫重登」，且主链路的**最后一步「提交审核」从未点过**。
> 本节即补这一轮。视图全集取自 `frontend/src/App.vue:9-22`（cc **无 router 文件**，菜单即视图切换）。

**① 复核提交走通（主链路最后一段）**

`#662` 1 条异常、`#663` 2 条异常，逐条选完后方可提交（未选满时「提交审核」禁用、提示「请为全部异常选择…」，**这是页面级硬闸，已实测**）。

| 任务 | 我的选择 | 落库 `violation.status` |
|---|---|---|
| #662 | 确认问题 | `CONFIRMED` |
| #663 | 确认问题 | `CONFIRMED` |
| #663 | **误报** | `FALSE_POSITIVE` |

⇒ **两个分支都取到真值**。提交后任务 `WAITING_REVIEW` → **`FAILED`**（有确认的问题即判失败，实测一致）。

**接口是 `POST /api/tasks/{id}/resume`（`frontend/src/api.js:38`），不是 `PATCH /violations/{id}/status`。** 三处对得上：
ES 事件 `POST /api/tasks/{id}/resume` `ok` `duration_ms=124` `ts=1789690822772` ↔ 库 `check_task 662.update_time = 00:20:23` ↔ 页面状态跳转。

**② 四个视图补全**

| 视图 | 本轮结果 |
|---|---|
| Workbench | 上传 + **复核提交**（上表） |
| History | **首次打开**：`Total 539`，行内可看 `#660~#664`、状态、抽取质量、创建时间，操作列（PDF/Excel/删除） |
| Rules | **首次打开**：`Total 34`、2 页；行含类型/级别/来源/聚合/状态/操作（编辑·试跑·启用·失效·删除） |
| Login | 退出登录 → 重新登录成功（token 重建） |

**③「Rules 页 Total 34 vs 库 56」不是缺陷（已论证，勿再登记）**

`check_rule` 按 `ontology_version_id` 分组 = **NULL 9 条（手写规则）+ v2 22 条 + v3 25 条**；
**34 = 9 + 25** ⇒ 页面显示的是**当前本体版本 + 手写规则**，排除 v2 的 22 条历史规则。
`ontology_version` 最新行 = `id=3`（`loaded_time 2026-08-11`）⇒ **v3 即当前版本，页面口径正确**。

**④ 三条新发现**

**F3 —— 真缺陷（数据正确性，sha256 级证据）**：`check_task_service.py:722-723`
```python
cf = db.query(ContractFile).filter(ContractFile.sha256 == sha).first()
if cf is None:
    ...
    cf = ContractFile(file_name=_sanitize_filename(original_name), ...)   # ← 只有首次创建才写名字
```
**sha256 去重命中时直接复用旧行，本次上传的 `original_name` 被丢弃** ⇒「同一份内容，第一次叫什么、以后永远叫什么」。

| 实测 | 我实际传的 | 落库 `file_name` | 内容真身（sha256 / size） |
|---|---|---|---|
| #664 | `f3probe_918a.pdf` | `data/acceptance/good.pdf` | good.pdf ✓（`58c7f413…` / 1695） |
| #660 / #661 / #663 | `a5_conflict.pdf` | **`good.pdf`** | **a5_conflict.pdf**（`23ccb494…` / **160295**） |

⇒ **名字与内容可以完全不符，且在 `History` 页直接展示给用户**。这正是本批判据（两端数据对得上）的反面 —— **连 cc 自己一端的 UI 与库都对不上**。
附带：名字里还会存进**相对路径**（`data/acceptance/good.pdf`），`_sanitize_filename` 未剥路径。
**未修**（属 A 级、改 cc 核心代码，须先出方案）。

**F4 —— 复核提交的观测无法归因（覆盖缺口）**：该事件 `extra` 为空、`extra` 侧无 task id；
`app/api/files.py:19` 注释明写「本路由（upload）是 cc **唯一**携带业务入参的 HTTP 入口」⇒
**从 ES 看不出某次复核审的是哪个任务、选了什么**。另：后端存在 `PATCH /violations/{id}/status` 路由，**全时段 0 次调用**（前端不走它）。

**F5 —— 人工复核无审计**：`violation.confirm_user` 列存在、`Workbench` 审核表有「确认人」列，
但**全表 559 行非空 = 0**（其中 **11 行已被复核过**）⇒ **无任何写入方**。典型 [[existence-is-not-reachability]]。

**⑤ 本轮我自己的两处失误（如实记）**

1. **又猜列名一次**：查 `check_rule` 时写了 `status='DISABLED'`，真列名是 `enabled`。**这次 `SHOW COLUMNS` 跑在前**，所以只废掉后续两条查询、未产生错结论。
2. **说错一句话并当场订正**：我先断言「复核提交没有任何观测事件」，随后查到 `POST /api/tasks/{id}/resume` 就是它、且事件存在 ⇒ **该句作废**。教训 = 认接口名不能只看 `grep` 的一个方向，要回前端 `api.js` 取调用点。

**复核命令（§3.10 增补）**：

```bash
# ① 复核提交的三处一致（ES 事件 / 库 update_time / violation 状态）
curl -s "http://localhost:39200/dev.obs-event-*/_search" -H 'Content-Type: application/json' \
  -d '{"size":5,"query":{"bool":{"filter":[{"term":{"interface":"POST /api/tasks/{id}/resume"}},{"range":{"ts":{"gt":1789690803835}}}]}}}'
docker exec contract-check-backend sh -c 'python -c "
import os,pymysql
c=pymysql.connect(host=os.environ[\"MYSQL_HOST\"],port=int(os.environ[\"MYSQL_PORT\"]),user=os.environ[\"MYSQL_USER\"],password=os.environ[\"MYSQL_PASSWORD\"],database=os.environ[\"MYSQL_DATABASE\"])
cur=c.cursor()
cur.execute(\"SELECT id,task_id,status,confirm_user FROM violation WHERE task_id IN (662,663)\")
print(cur.fetchall())
cur.execute(\"SELECT COUNT(*) total,COUNT(confirm_user) with_user FROM violation\")
print(\"F5: confirm_user 非空 =\", cur.fetchone())
"'
# ② F3：文件名与内容 sha256 不符（决定性）
#    同一脚本内改为 SELECT id,file_name,file_size,sha256 FROM contract_file WHERE id IN (91,94)
#    再与本仓样本比对：sha256sum backend/data/acceptance/{good.pdf,a5_conflict.pdf}
# ③ Rules 页 34 的论证
#    SELECT ontology_version_id, COUNT(*) FROM check_rule GROUP BY ontology_version_id;   -- 9 / 22 / 25
```

**§3.10 证不了什么**：① 仍**不是真实用户**；② `Rules` 页只读了列表，**写操作（新建/编辑/试跑/启用/失效/删除）一个都没点**；③ `History` 页的删除、导出 PDF/Excel **未点**；④ F3/F4/F5 **均未修**。

#### 3.11 处置 F3（上传文件名归属「本次上传」而非「这份内容」）—— ✅ 已修并真机复验

**缺陷 F3（真实、可复现、非注入）**：`contract_file` 按 sha256 去重，同一行被多个 task 引用；
而文件名存在 `contract_file.file_name` 上 ⇒ **同一份内容被第二次上传时，历史记录显示的是首次的名字**。
实测 #664 传 `f3probe_918a.pdf`（1695B，`good.pdf` 副本），落库显示 `data/acceptance/good.pdf`；
`contract_file` id=91 同时被 #662/#664 引用，id=94 同时被 #660/661/663 引用。

**为什么不能就地改 `contract_file.file_name`**：会波及引用同一行的**历史** task（列表/导出名一起变）。
**为什么不能改成「每次新建 contract_file 行」**：`contract_file.sha256` **有唯一索引**（见 `models.py:25`），
建不了第二行。⇒ 名字必须落到 task 侧，新增 `check_task.original_name`。

**改动（6 处，全在 cc 仓，⚠️ 未提交）**：

| # | 文件:行 | 改动 |
|---|---|---|
| 1 | `db/models.py:54` | `CheckTask` 新增 `original_name`（`VARCHAR(255) NOT NULL DEFAULT ''`） |
| 2 | `main.py:243` | `_ensure_column(engine, "check_task", "original_name", ...)` 幂等迁移 |
| 3 | `service/check_task_service.py:434` | `_sanitize_filename` **先剥路径再判长度**（`\` 与 `/` 都取末段） |
| 4 | `service/check_task_service.py:770` | 建 task 时写 `original_name=_sanitize_filename(original_name)` |
| 5 | `service/check_task_service.py:673/681` | `list_tasks` 展示与筛选走**同一表达式** `coalesce(nullif(original_name,''), contract_file.file_name)` |
| 6 | `report/report_data.py:123` | 导出名同口径 `task.original_name or cf.file_name` |

**前端（`History.vue` / `Rules.vue`）零改动** —— 两处都经 `listTasks` 取数（`api.js:37`），
改在 service 层即全覆盖；改前先 grep 确认过，不是省事。

**单测（新增 `tests/test_upload_name.py` 11 条 + `test_report.py` 补 1 条）**：
覆盖「剥路径 5 条 / 去重命中仍记本次名 3 条 / 存量行回退 3 条 / 导出名同口径 1 条」。
全量 `429 passed`（改前 428）。

**判别性验证（这一步是重点，不是走过场）**：把上述 4 个后端文件**回退到 `HEAD` 版本**再跑同一份新单测
⇒ **7 failed, 4 passed**，红的正是 F3 相关断言（`good.pdf` != `f3probe_919b.pdf` 等），
绿的是本就与修复无关的 4 条。**证明这些断言在修前会红，不是「怎么写都绿」**。

**真机复验**（重建镜像 `docker compose build backend && up -d` → 迁移自动建列）：

| 判据 | 结果 |
|---|---|
| 库里新列 | `check_task.original_name` `varchar(255) NOT NULL` ✅ |
| **回归（最重要）** | #655–664 **10 行展示名与修复前基线逐字相同**（655-659 `b1_missing_date.pdf`；660/661/663 `good.pdf`；662/664 `data/acceptance/good.pdf`）✅ **修法没波及历史** |
| 新上传 #665（传 `f3probe_919b.pdf`，sha 命中 id=91） | `original_name=f3probe_919b.pdf`，`status=WAITING_REVIEW@100%` ✅ |
| **同一 `contract_file` 行两个名字** | #664 与 #665 **同引 cf id=91**，分别显示 `data/acceptance/good.pdf` / `f3probe_919b.pdf` ✅ **这才是 F3 的判据** |
| `contract_file` 未被就地改 | id=91 仍是 `data/acceptance/good.pdf` ✅ |
| UI 列表 | `f3probe_919b.pdf`（#665 行）✅ |
| UI 筛选（有区分度） | 搜 `good.pdf` **不含 #665**（修前会含）；搜 `f3probe` 命中 #665 ✅ |
| 导出名同口径 | `Content-Disposition` = `合同校验报告_f3probe_919b.pdf_665.{pdf,xlsx}` ✅（修前是 `…data/acceptance/good.pdf…`，还带 `/`） |

**跨端核对（#665）**：ES `trace_key="contract-check#task-665"` 恰 **3 条**，与 online UI「3 / 3 事件」
（seq 0 request / 2 llm_call / 4 llm_call，model/status/耗时/时间逐项）**全等**；
offline `eval_run` max **仍 3717**、online `error_cluster` max **仍 3881** —— **两处零新增**。
（**注意别复用「cc 白名单设计上关闭」这句**：§六 已核库内 cc `backflow_allow=1`、`backflow_enabled=true`，
零回流的真因是 §3.8 订正的「`INTERNAL_ERROR` 不在回流值域 11 词内」。）

**§3.11 证不了什么**：① 只验了「名字归属」这一条，**没验并发上传同 sha 时 `original_name` 的竞态**
（走的是同一分支，理论上同形，但未实测）；② 导出只读了 `Content-Disposition`，
**未开文件核对内容**；③ F4/F5 **仍未处置**；④ cc 两处代码改动 **仍未提交**。

**复核命令（§3.11）**：

```bash
# ① 回归：展示名表达式对存量行的取值（须与修复前基线逐字相同）
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -t -e \
 "SELECT t.id,t.original_name,COALESCE(NULLIF(t.original_name,\"\"),cf.file_name) AS display_name,cf.id AS cfid \
  FROM check_task t LEFT JOIN contract_file cf ON cf.id=t.contract_file_id WHERE t.id>=655 ORDER BY t.id" contract_check'
# ② 判别性：4 个后端文件回退 HEAD 后重跑 tests/test_upload_name.py，期望 7 failed / 4 passed
# ③ 同 sha 命中行：SELECT id,file_name,file_size,sha256 FROM contract_file WHERE id IN (91,94)
# ④ 导出名：页面 fetch /api/tasks/{id}/report?format=pdf 后读 content-disposition
```

#### 3.12 cc Rules 写操作面全量走查 —— ✅ 走通，**带出并修复 F6**

**范围**：cc「规则管理」页六个写操作（新建 / 编辑 / 试跑 / 启用 / 失效 / 删除）+ 本体规则的只读边界。
全部经**真实鼠标点击**（el-radio-button 的 JS `.click()` 不生效，须用 MCP 点击 uid），每个动作**逐条对库取证**。

| 写操作 | 真机结果（库侧回读） |
|---|---|
| 新建 | #63 落库，UI `Total 34→35`，行显示「失效」+ 启用/删除按钮（`MANUAL` 分支正确）✅ |
| 编辑 | 级别 `MEDIUM→HIGH` **落库**；**改名未落库** ❌ ← 见 F6 |
| 试跑 | 返回 `FAIL / LOW / token=6749` + reason；回查 `rule_id=63` 的 `rule_check_result` 与 `violation` **均 0 行** ⇒ 规格「试跑不落库」属实 ✅ |
| 启用 | `enabled 0→1`，`update_time` 变更 ✅ |
| 失效 | `enabled 1→0`，`update_time` 变更 ✅ |
| 删除 | 物理删除；回到基线 **56 行 / 54 启用 / max_id=62**，零残留 ✅ |
| 本体规则只读 | UI 层：无「删除」按钮、失效按钮 `disabled`；**API 层守卫未实测**（见「证不了什么」）✅ |

**剔除的假缺陷**：新建抽屉无「类型」选择器 —— 与 API `CreateBody.type: Literal["SEMANTIC"]` 一致
（确定性规则由本体生成），**不是缺陷**，勿登记。

#### F6（真实缺陷，已修）：规则改名经 `PUT /api/rules/{id}` 静默失效

- **现象**：编辑规则改名 → 弹「保存成功」→ **名字不变**；**同一请求里的 severity 却落库**
  （即「部分字段生效」——正是这个不对称让它看起来像前端缓存问题，实为服务端死键）。
- **根因（不是推断，是唯一调用点对比）**：`api/rules.py:52` 传 `UpdateBody.model_dump(exclude_none=True)`，
  键为 **`name`**；而 `service/rule_service.py:205` 遍历的元组里写的是 **`"rule_name"`**
  ⇒ `"rule_name" in data` **恒 False**，是条**死分支**。全仓 `update_rule` 仅此一个调用点，
  没有任何路径能发出 `rule_name` 键。
- **同文件内自证**：`create_rule` 第 182 行用的是 `data["name"]` —— **同一模块两种口径**，
  这是「建/改同一字段应同名」的最直接铁证。
- **为何长期未暴露**：`tests/test_rule_service.py` 对 `update_rule` **零覆盖**（只有 `rule_name`
  作为 ORM 构造参数出现）；UI 走 `name`（与 API 契约一致）⇒ **服务层单侧缺陷，前端无过错**。
- **修法（用户 2026-09-18 拍板「改 service 认 name 键」）**：`update_rule` 里显式映射
  `name → rule_name`，从遍历元组中摘掉 `"rule_name"`；**不动 API 契约、零前端改动**。
  取舍：触及服务层（A 级，已先出方案）；换来建/改同名自洽。

**单测**：新增 `TestUpdateRule`（4 条）/ 全量 **433 passed**（改前 429 + 4，既有用例零调整）。

**判别性验证**：4 个后端文件回退 HEAD 后重跑同一份新测试 → **1 failed / 19 passed**，
红的恰是 `test_rename_takes_effect`，断言 `AssertionError: '旧名' != '新名'`。
⚠️ **另 3 条修前也是绿的**（「不改名时别丢名字」「本体规则别越权」「404 返回 None」锁的是
**别改坏**的边界，修前本就不违反）⇒ **判别性的只有 1 条，不是 4 条**，勿把 4 条都算作判据。

**真机复验（连跑两遍，符合探针可重复性要求）**：

| 组 | 操作 | 库侧结果 |
|---|---|---|
| A | 新建 #64「F6复验A-原名」→ 改名 + 同级改 severity | `rule_name=F6复验A-新名-20260918`、`severity=HIGH` **两项均落库** ✅ |
| B | 新建 #65「F6复验B-原名」→ **纯改名**（不碰 severity） | `rule_name=F6复验B-新名-20260918`、`severity` **仍 MEDIUM**（未被误改）✅ |

两组 UI 列表均同步显示新名；删除确认弹窗文案也用的是**新名**（改名已传播到 UI 各消费点）。
镜像重建后**在容器内**读 `/app/app/service/rule_service.py` 复核，确认跑的是修后版本
（cc 无源码 bind mount，改后端必须 `docker compose build backend`）。

**跨端核对**：900 秒窗口内 cc 写操作事件 = `POST /api/rules` **2** + `PUT /api/rules/{id}` **2**
+ `DELETE /api/rules/{id}` **2** = **6 条，全部 `ok`** —— 与本轮实际操作次数（2 建 / 2 改 / 2 删）
**精确相等**（既证「事件齐全」，也证「无多计」）。offline `eval_run` max **仍 3717**、
online `error_cluster` max **仍 3881**，两处零新增（规则 CRUD 属管理面，不产生 agent 故障回流）。

**订正上一轮的一处误记**：我此前把「改名后 `rule_iri` 与 `rule_name` 不一致」写成 F6 的副作用 ——
**错**。`_gen_rule_iri` 仅在 `create_rule` 调用，update 从不重算 iri，**这是有意设计**
（iri 是创建后稳定的技术标识）。修前之所以看不出不一致，只是因为**改名根本没生效**。

#### F7（只读观察，**未真机实证**，勿当已验缺陷）

`Rules.vue` 对 `ONTOLOGY_GENERATED` 规则也开放「编辑」入口，且抽屉内 名称 / 表达式 / 描述
输入框**均未禁用**，而 `update_rule` 的本体分支**只认 `enabled` / `severity`，其余静默忽略**。
仅由静态读码得出；我试图实测（改 #55 表达式后保存）**被权限拦截，我未绕过**，
遂取消抽屉未保存，并回查确认 #55 未被改动（`update_time` 仍 `2026-08-11 07:43:59`、总数仍 56）。
⇒ 登记为**观察**，不是结论。

**§3.12 证不了什么**：① **「删除被引用规则应被拒」分支未验** —— 拟用 #23 实测时被权限拦截，
未绕过（`delete_rule` 的 refs 检查 + FK RESTRICT 仅静态读码，未跑真机）；② 本体规则的
**API 层**写守卫未实测（只验了 UI 层按钮态）；③ 试跑只验了「不落库」，**未核对 LLM 判定质量**；
④ F4/F5 **仍未处置**；⑤ cc 侧 F1/F3/F6 三处代码改动与 online 台账**均未提交**。

**复核命令（§3.12）**：

```bash
# ① 规则表基线与残留（期望恒为 56 / 54 / 62 / 0）
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -t -e \
 "select count(*) total,sum(enabled) enabled_cnt,max(id) max_id,sum(id>62) probe_left from contract_check.check_rule"'
# ② 改名落库（对任一 MANUAL 规则经 UI 改名后回读）
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 -t -e \
 "select id,rule_name,rule_iri,severity,update_time from contract_check.check_rule where id=:id"'
#   ↑ rule_iri 不随改名变 = 设计（_gen_rule_iri 仅 create 调用），不是缺陷
# ③ 判别性：rule_service.py 回退 HEAD 后重跑 tests/test_rule_service.py，期望 1 failed / 19 passed
# ④ 容器内代码版本（cc 无 bind mount，改后必须重建镜像才生效）
docker exec contract-check-backend sh -c 'sed -n "199,214p" /app/app/service/rule_service.py'
# ⑤ 本轮写操作事件（相对窗口，勿用过窄的绝对时间窗 —— 会静默排掉边界外事件）
SINCE=$(( ($(date +%s) - 900) * 1000 ))
curl -s "http://localhost:39200/dev.obs-event-*/_search" -H "Content-Type: application/json" \
 -d "{\"size\":0,\"query\":{\"bool\":{\"filter\":[{\"term\":{\"agent\":\"contract-check\"}},{\"range\":{\"ts\":{\"gte\":$SINCE}}}]}},\"aggs\":{\"by_if\":{\"terms\":{\"field\":\"interface\",\"size\":30}}}}"
```

### 四、复核命令（**结论数字必须连同产出命令一起引用**，勿只搬数字）

```bash
# 造错前基线 / 任意时刻水位（容器内展开 root 口令，不外泄）
docker exec -i shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N' <<'SQL'
select agent, status, count(*) from `dev.obs`.error_cluster group by agent, status order by 1,2;
select offline_status, verify_status, count(*) from `dev.obs`.error_case_link group by 1,2;
SQL

# 批 2 的决定性证据（layer=none 合规格）
docker exec -i shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N' \
  -e "select judgement_json from \`dev.obs\`.trace_judge_state where id=19017"

# 批 3.2 的两条浏览器 trace
docker exec -i shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N' \
  -e "select id,agent,trace_id,interface,root_status,root_error_type from \`dev.obs\`.trace_judge_state where trace_id in ('aa3052dc19d1d6b438a0be42cd2bd8da','47b4ad0671eed4bccc69836df71bf802')"

# 批 2 造错前基线（2026-09-17，逐处取）
#   conversion_record 125 / error_case_link 34 / error_cluster 35 /
#   needs_review_batch 0 / trace_judge_state 780 / verify_run_record 47

# §3.4 跨端对账（payload_id 三处关联）
docker exec -i shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N' <<'SQL'
# ① 总量链 + inbox 双向孤儿
select l.offline_status, (i.payload_id is not null) as in_inbox, count(*)
from `dev.obs`.error_case_link l
left join ai_evaluation.error_backflow_inbox i on i.payload_id=l.payload_id
group by 1,2;
# ③ 4 家 15 条三元组（簇 / payload / verify / 用例 id）
select c.agent, l.cluster_id, l.payload_id, l.verify_status, tc.id
from ai_evaluation.error_backflow_inbox i
join `dev.obs`.error_case_link l on l.payload_id=i.payload_id
join `dev.obs`.error_cluster c on c.id=l.cluster_id
join ai_evaluation.test_case tc on tc.payload_id=l.payload_id
where i.status='active'
  and c.agent in ('good-question','customer-service','contract-check','smart-procurement')
order by c.agent, tc.id;
# ④ 双向零孤儿（两条都应返回 0）
select count(*) from ai_evaluation.test_case tc
join ai_evaluation.test_suite s on s.id=tc.suite_id
where s.is_error_suite=1 and s.agent_id in (2297,2298,2299,2300)
  and not exists (select 1 from ai_evaluation.error_backflow_inbox i
                  where i.payload_id=tc.payload_id and i.status='active');
SQL

# §3.3 回流看板逐值复核（在 obs-frontend:18080 控制台内执行，token 取 localStorage['obs_access']；
#   返回体即 overview 全字段，照 §3.3 所列逐项比对）
fetch('/api/v1/backflow/overview',{headers:{Authorization:'Bearer '+localStorage['obs_access']}}).then(r=>r.json()).then(console.log)

# §3.5 批 4 四页的库侧底数（offline 前端 = ai-eval-frontend:8180）
docker exec -i shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N' <<'SQL'
# 配置中心：38 项，scope 三分；key 是保留字，必须反引号
select scope, `key`, is_hot, json_unquote(value), updated_at
from ai_evaluation.system_config order by scope, `key`;
# Agent 管理：59 行 / 启用 59 / 有凭证 4 / 契约 2.0 恰 4
select count(*) as total, sum(enabled=1) as en, sum(auth_config is not null) as cred,
       sum(contract_version='2.0') as cv2 from ai_evaluation.agent;
# 用户管理：5 行
select id, username, role, enabled from ai_evaluation.user order by id desc;
# 看板：总 run 数（UI 只展示最新 200）；最新 5 行
select count(*) from ai_evaluation.eval_run;
select r.id, a.name, r.version, r.status, r.agent_score, r.total_case, r.pass_case, r.started_at
from ai_evaluation.eval_run r join ai_evaluation.agent a on a.id=r.agent_id
order by r.id desc limit 5;
SQL

# 注：`system_config.value` 是 json 列；`json_unquote` 后小数直接可比。
# 注：探针读 el-switch 必须读 is-checked/checked，读 value 恒得 "on"（见 §3.5 探针坑）。

# §3.6 接口 / LLM 失败 的信源是 ES，不是 MySQL（容器 shared-elasticsearch，宿主 39200）
# 三页的等价 ES 查询（agent=good-question，window=7d）。注意链路查询要多带 log index。
NOW=$(date +%s%3N); S=$((NOW - 7*86400*1000))
# 接口页：请求级 16 行 + LLM 级 1 行（body 同 backend/app/store/es.py:260 build_metrics_interfaces_body）
curl -s "http://localhost:39200/dev.obs-event-*/_search" -H 'Content-Type: application/json' -d \
  "{\"size\":0,\"query\":{\"bool\":{\"filter\":[{\"range\":{\"ts\":{\"gte\":$S,\"lte\":$NOW}}},{\"term\":{\"agent\":\"good-question\"}}],\"must_not\":[{\"term\":{\"node\":\"heartbeat\"}}]}},\"aggs\":{\"req\":{\"filter\":{\"term\":{\"node\":\"request\"}},\"aggs\":{\"by_iface\":{\"terms\":{\"field\":\"interface\",\"size\":50},\"aggs\":{\"pct\":{\"percentiles\":{\"field\":\"duration_ms\",\"percents\":[50,95,99]}},\"err\":{\"filter\":{\"term\":{\"status\":\"error\"}}},\"to\":{\"filter\":{\"term\":{\"status\":\"timeout\"}}}}}}},\"llm\":{\"filter\":{\"term\":{\"node\":\"llm_call\"}},\"aggs\":{\"by_iface\":{\"terms\":{\"field\":\"interface\",\"size\":50},\"aggs\":{\"fail\":{\"filter\":{\"bool\":{\"should\":[{\"term\":{\"status\":\"error\"}},{\"term\":{\"status\":\"timeout\"}}]}}}}}}}}}"
# LLM 失败页：命中数必须 = 23，且逐条 (ts,trace_id,model,error_type) 与页面 23 行一一对应
curl -s "http://localhost:39200/dev.obs-event-*/_search" -H 'Content-Type: application/json' -d \
  "{\"size\":30,\"sort\":[{\"ts\":\"desc\"}],\"query\":{\"bool\":{\"filter\":[{\"range\":{\"ts\":{\"gte\":$S,\"lte\":$NOW}}},{\"term\":{\"agent\":\"good-question\"}},{\"term\":{\"node\":\"llm_call\"}},{\"bool\":{\"should\":[{\"term\":{\"status\":\"error\"}},{\"term\":{\"status\":\"timeout\"}}]}}],\"must_not\":[{\"term\":{\"node\":\"heartbeat\"}}]}}}"
# 链路查询页：**必须同时带 log index**（只查 event 会漏掉「最近节点=log」的 trace）
curl -s "http://localhost:39200/dev.obs-event-*,dev.obs-log-*/_search" -H 'Content-Type: application/json' -d \
  '{"size":5,"sort":[{"ts":"asc"}],"query":{"term":{"trace_id":"<从页面重新取的 trace_id>"}}}'

# §3.6 系统管理两页（MySQL）
docker exec -i shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N' <<'SQL'
select config_key, json_unquote(config_value), version, updated_by, updated_ts
from `dev.obs`.dict_config where agent_id is null order by config_key;   -- 12 行；缺的 claim_ttl_days 即「库内无行」
select count(*) from `dev.obs`.dict_config where agent_id is not null;   -- 13：per-agent，本页不显示
select id, username, role, status from `dev.obs`.user order by id;       -- 3 行
SQL
```

### 五、本批**未做**（勿读成已验）

- ~~online 未验页~~ **已全验**（接口 / LLM 失败 / 链路查询 / 系统管理·配置 / 系统管理·账号，见 §3.6）。
  ~~链路查询只读了第 1 页~~ **已补全：10 页 × 20 = 200 行与 ES 按序逐位全等；「共 800 条」= `cardinality(trace_key)`
  已独立复现**（见 §3.6 末「两个数字的关系」）。**该页整页验完。**
- ~~online `/change-password` 页~~ **不属本批范围**：online 路由表里本就没有该页（它在 offline 仓），
  与 offline 侧「唯一未验页」是同一件事，勿重复登记。
- ~~offline 未验页~~ **已全部验完**：看板（§3.3 跨端对账 + §3.5 门禁墙/评测记录）、用例管理
  （suite 内 2 条 / 标注待办 149 条，与库内 `test_case` 逐值相等）、配置中心 / Agent 管理 / 用户管理（§3.5）。
  **唯一未验页 = 修改密码**（未列入本批范围）。
- **§3.5 登记的 1 处缺陷 + 观察 2 已处置**（配置中心只读数值失真、非 text 项多渲染文本域，
  见 §3.7 已修并真机复验）；**观察 1（用户管理禁用按钮标签）仍未处置**。
- ~~「浏览器造错 → 新簇」这段链路本次始终没被真跑过~~ **§3.8 已把这段推进到底并给出确切成因**：
  真实流量**到了**、**也产生了真实 error**（`INTERNAL_ERROR`，2/2 可复现），
  **但该 error_type 不在回流值域 11 词内 ⇒ 不建簇**（实测未新增簇，最新仍是 3881）。
  **七环的 error 分支仍无真实流量，但成因已从「没有真实流量」订正为「真流量来了、类型不在值域内」**（见 §3.8）。
- ~~F1 未修（改 cc 属另一仓另一批）~~ **已于 §3.9 修复并真机复验**：`extractor.py` 改为每 worker 各持一份
  `parent_ctx.copy()`，重跑 `a5_conflict.pdf` 从 `FAILED@40%` → `WAITING_REVIEW@100%`，
  8 条 `llm_call` **并发重叠且全 `ok`**，online UI 12/12 与 ES 逐字全等，offline 零新增。
  ⚠️ cc 仓该改动**未提交**（是否提交由人定）。
- ~~F3 未修~~ **已于 §3.11 修复并真机复验**（`check_task.original_name` + 展示/筛选/导出三处同口径），
  7 项判据全过（含「回归：存量 10 行显示名逐字不变」与「同一 `contract_file` 行两个名字」）。
  ⚠️ cc 仓该 6 处改动**未提交**（是否提交由人定）。
- **F4（复核提交事件 `extra` 为空、不带 task id；`PATCH /violations/{id}/status` 全时段 0 次调用）仍未处置**。
- **F5（`violation.confirm_user` 全表 559 行非空 = 0，UI 有「确认人」列但无写入方）仍未处置**；
  §3.11 又新增一例佐证：复核提交后 #665 的 violation 789 `confirm_user` 仍为 `NULL`。
- **「对 4 个 agent 进行页面功能操作」这半边**：**本批此前只做过验收半边**；
  §3.8 已补 **cc 一家**（批 1）。**批 2/3/4（gq / cs / sp）未开工** —— 四家里的三家 agent 前端仍未打开过。
- ~~cc 的写操作面仍只走了一部分~~：§3.10 走了复核提交、§3.11 走了**导出 PDF/Excel**、
  **§3.12 已把 `Rules` 页六项写操作（新建/编辑/试跑/启用/失效/删除）全部走通**并带出修复 **F6**。
  **仍未点**：`History` 页的删除；另 §3.12 另有两条未验（`删除被引用规则应被拒` 分支、本体规则
  的 **API 层**写入守卫）—— 均因权限拦截未绕过，已在 §3.12「证不了什么」逐条登记。
- 批 2（造错）中 cc / gq 之外的两家（cs / sp）**未单独跑**，结论由分类器同构外推；
  但 **§3.4 的跨端对账覆盖了 4 家全量**（cs 2 条 / sp 1 条），那一段不是外推。

### 六、本批顺手发现的两处文档滞后（**未改**，留待处置）

1. `backend/app/core/seed.py:42` 与 `backend/app/analyzer/classify.py:8` 仍写「cc `backflow_allow=0`／
   cc 双保险」，但库内实测 cc `backflow_allow=1`、`backflow_enabled=true`。
   **这是既定变更**（`backend/tests/integration/backflow_allow_probe.py:10` 自述
   「cc 七环开通后该值已 0→1」），**是代码注释未跟改，不是闸门失效**。
2. 同探针自述「探针**结构性恒红**」—— 属已知长期红，处置口径见 chronic-noise（长期固定红 ⇒ 疲劳化）。

---

## 批 2｜gq（good-question）家浏览器 UI 验收（2026-09-18）

> 承接「## 浏览器端 UI 验收（2026-09-17）」的批 2。用户指令：**一家一家做，把每家做扎实，再推进下一家**。
> 本批为**第一家 gq**（`native_rag` schema，前端 `http://localhost:8089/`，ES agent 名 `good-question`）。

### 1. 页面功能操作（真实鼠标/键盘）

| 步 | 操作 | 结果 |
|---|---|---|
| 1 | 仪表盘 | 显示「7 文档库 / 17 文档 / 490 片段」，与 DB 逐字相符 |
| 2 | 文档库页 | 7 个库列表 |
| 3 | 聊天问答 → 选「演示知识库」→ ＋新会话 | 新建会话 **#1342**（`library_id=9`） |
| 4 | 提问「请事假需要提前几个工作日提交申请？由谁审批？」 | 流式答案 + 引用来源 **3** 条 |

答案内容可判：答「**事假：须提前 3 个工作日提出申请**」，与库内文档一致；并主动声明「文档中未明确指定事假的具体审批人」，**未编造**。

### 2. online 侧三方对账（UI ↔ DB ↔ ES），逐字段

| 面 | 值 |
|---|---|
| UI | `/chat/1342` 列表项 title = 我的问题；聊天区「2 条消息」 |
| DB | `chat_sessions` 1342：`title`=问题原文、`library_id=9`、`message_count=2`；`chat_messages` 2811(user)/2812(assistant)，assistant 220 字，`sources_json` 长度 **3** |
| ES | `trace_key=good-question#2c960568e4f6878ee29a21a0b4e2319b`，**total=4** |
| UI trace 页 | `/traces/good-question/2c960568…` 显示 **`4 / 4 事件`** |

**逐条相等**：UI 4 条 seq = {0, 2, 9, 13} = ES 4 条 seq，**集合全等**。逐字段：`node`(request/llm_call)、`model`(deepseek-chat)、`status`(全 ok)、`duration_ms`(17928 / 1311 / 1456 / 2197)、`usage`(`{1020,79,1099}` / `{1604,154,1758}` / `{2270,238,2508}`)、`ts` 毫秒尾(`.074`)。

### 3. 写操作面（本轮补做）—— 4 次写操作 = 4 条写事件

| UI 操作 | DB 核验 | ES 事件 |
|---|---|---|
| 删除会话 #1342（含二次确认框） | `sess_total 1171→1170`、`lib9 23→22`、`s1342=0`、`m1342=0`（**2 条消息级联删除**） | `DELETE /api/sessions/{id}` ×1 ok |
| 新建文档库 `wop-verify-20260918` | 新增 `id=15`，name/description/`created_at` 全对，`libs 7→8` | `POST /api/libraries` ×1 ok |
| 删除文档库 `id=15` | `libs 8→7`、`l15=0`、`max_id` 回 14 | `DELETE /api/libraries/{id}` ×1 ok（740ms） |
| （提问） | — | `POST /api/chat/{id}` ×4 |

近 25 分钟 ES 聚合：**25 条事件全 `ok`**，写事件次数与操作次数**精确相等**。

### 4. offline 侧

- **已注册**：`ai_evaluation.agent` id=**2300** `good-question`，`enabled=1`（四家 2297–2300 齐）
- **闭环史**：**27 条 `eval_run`**，模式规整 —— `manual`（suite 2161，22 用例）→ `error_regression`（suite 2593，6 用例），后者 `trigger_signal_id` **精确指向前一条 manual run**（3711→3712、3709→3710、3660→3661）
- **今日零新增**：`error_backflow_inbox` 最后一条停在 2026-09-17 05:35 —— **预期行为，不是缺陷**。本轮 4 条事件全 `ok`，而回流值域 11 词全是 agent 侧故障（详见「二、批 2a–2d 造错」），客户端正常流量结构性不产生回流。

### 5. 跨端对账（历史链，焊点已锁定）

online `error_cluster` **id=3880** ⇄ offline `test_case` **id=4083**，其 `backflow_envelope` 逐字含：

```
"agent": "good-question", "cluster_id": 3880,
"trace_id": "gqaccept2-ec9de3b906aa", "interface": "POST /api/chat/{id}",
"trigger_version": "0.1.0"
```

五项与 online 侧**逐字相等**；`payload_id`(`d0e4e3c8-…`) 两端一致；时延链：cluster `first_ts` 2026-09-17 00:49:58 → inbox `received_at` 00:50:59（**61 秒**回流）→ `test_case.created_at` 00:50:59。

### 6. 两处观察项（**未判为缺陷**，勿当已定性）

1. **会话列表项不实时刷新**：发问后列表项仍显示「新会话 / 0 条消息」，手动刷新后才显示正确 title 与条数。数据本身正确（刷新后 UI↔DB 全等）⇒ 是呈现层刷新时机问题。
2. **文档库删除无二次确认**：删除会话有确认框（且提示「所有聊天记录将被删除」），删除文档库**直接生效**。二者同为不可逆操作，口径不一致 —— 是否有意设计**未核规格**，故只记观察。

### 7. 本批证不了什么（显式声明，勿外推）

1. **第 5 节的跨端链起点是注入的** —— envelope 内 `"content": "注入验收 278b4ae0：请回答一个全新问题以避开缓存？"`。它证「**跨端管道打通**」，**不证「有真实用户流量走完七环」**。
2. **今日 gq 真实操作流量无 offline 对账面** —— 正常问答全 `ok`，不产生回流。第 3 节的跨端对账是 **online 侧**（UI↔DB↔ES），**offline 侧今日零参与**。
3. 文档库页的**文档上传/删除**未点；仪表盘仅看未操作。
4. 本节所有数字**未跨机器复现**，仅在本机当日环境成立。

### 8. 复核命令

```bash
# online 侧：该 trace 的 ES 全量（应 total=4）
curl -s "http://localhost:39200/dev.obs-event-*/_search" -H "Content-Type: application/json" -d '{"size":0,"query":{"term":{"trace_key":"good-question#2c960568e4f6878ee29a21a0b4e2319b"}},"aggs":{"by_seq":{"terms":{"field":"seq","size":10}}}}'

# online 侧：近 25 分钟 gq 事件按 interface 聚合（写事件应各 ×1）
T=$(( ($(date +%s) - 1500) * 1000 )); curl -s "http://localhost:39200/dev.obs-event-*/_search" -H "Content-Type: application/json" -d "{\"size\":0,\"query\":{\"bool\":{\"must\":[{\"term\":{\"agent\":\"good-question\"}},{\"range\":{\"ts\":{\"gte\":$T}}}]}},\"aggs\":{\"by_iface\":{\"terms\":{\"field\":\"interface\",\"size\":20}}}}"

# offline 侧：gq 注册与闭环史
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 -t -e "select id,name,enabled from ai_evaluation.agent where id=2300; select id,trigger_type,trigger_signal_id,total_case,pass_case,fail_case,finished_at from ai_evaluation.eval_run where agent_id=2300 order by id desc limit 6"'

# 跨端焊点：test_case 4083 的回流载荷（应含 cluster_id=3880 与 trace_id=gqaccept2-ec9de3b906aa）
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 -N -e "select left(backflow_envelope,600) from ai_evaluation.test_case where id=4083"'
```

> **复核注意（防腐）**：会话 #1342 与文档库 `id=15` 已在第 3 节**删除**，故 DB 侧复现需重走第 1 节操作；**ES 事件不随业务删除而消失**，故 trace 查询与写事件聚合仍可复现（受 ES 保留期约束）。
> 「今日零新增」这类断言**只在本机当日成立**，引用时须连日期一起带。

---

## 批 2｜sp（smart-procurement）家浏览器 UI 验收（2026-09-18，**上篇**）

> 前端 `http://localhost:18082/`（**根路径自动跳 `/admin`**）；schema `smart_procurement`；ES agent 名 `smart-procurement`。

### 1. 🔴 结构性发现：sp 前端是**管理员后台**，**无评标业务页**

菜单 = 工作台 / 用户管理 / 专家管理 / 供应商管理 / 工商信息 / 系统配置。而 sp 七环的流量出口是 **`POST /api/v1/reviews/{id}/chat`** —— **该链路在 UI 上无入口**。
⇒ **「用 sp 的页面操作造出走七环的流量」这条路结构性不存在**，与 gq（问答页即业务页）不同。

### 2. 登录与一条**真实**的 error

- 登录页明示演示账号：`admin` / `123456`（另 `pm1` 项目经理、`expert_01` 评审专家、`supplier_01` 供应商）。
- **实测异常**：以 admin 登录后能看工作台，但点「用户管理」**直接跳 `/login`** ⇒ 页面重渲染后鉴权失效。ES 侧留下一条**真实**（非注入）error：

| 字段 | 值 |
|---|---|
| `trace_key` | `smart-procurement#0c7e7d61e8b7e5f4924c5440ef32b9c4` |
| `node` / `interface` | `request` / `GET /api/v1/users` |
| `error_type` | **`HTTP_401`** |
| `status` / `duration_ms` | `error` / 16 |

### 3. 写操作：新建用户（走通 + 三方对账）

| 面 | 值 |
|---|---|
| UI 行（首行） | `wop_probe_20260918` / `写面验证` / `评审专家` / `wop@example.com` / `13800000000` / `启用` / `2026-09-18 01:32:34` |
| DB `users` | `user_id=U-1053F56F9FA3`、`username`、`display_name`、`role=REVIEW_EXPERT`、`email`、`phone`、`is_active=1`、`created_at` —— **七项逐字相等** |
| ES | `POST /api/v1/users` ×1 **ok** |

**⚠️ `user_id` 是字符串业务主键**（`U-<hex>` / `VFY-<姓名>`），`max(user_id)` 返回 `VFY-石秀云` 是**字典序**、无意义 —— 排序/取最新必须用 `created_at`。

### 4. 🔴 本批最有价值的实测：**真实 4xx error 不回流**（首次有实测证据）

近 15 分钟 sp 的 ES：`request` ×4（`GET /api/v1/users` 2 ok + **1 error=HTTP_401**、`POST /api/v1/users` 1 ok）+ `heartbeat` ×15（无 `interface`/`status`，故 `terms` 聚合不含）。

**online `error_cluster` 里 sp 仍只有 1 行**（id=3881，`first_ts` 2026-09-17 05:34:02，即昨日那条注入的），**今日零新增**。

⇒ 「客户端 4xx 客户端错误永不回流」此前是**从回流值域 11 词推导**的结论，**本轮首次由真实操作产生的真实 401 实测印证**：它出现在 ES（`status=error`），但不建簇、不回流。

### 5. 本批**未做**（勿读成已验）

- 用户管理页：**改角色**未点；**切换启用/禁用**尝试 2 次均失败（`switch` 报 `did not become interactive`，两次超时后**不再重试**，原因未查）；**「删除用户」在 UI 上不存在** —— 操作列只有 `switch` + 角色 `combobox`，**无删除按钮** ⇒ 探针用户 `wop_probe_20260918` **无法从 UI 清除**（**未擅自改库**，留待处置）。
- **专家管理 / 供应商管理 / 工商信息 / 系统配置** 四页**一次都没打开**。
- 未取 **offline 侧** sp 的对账面（`agent` id=2297 已注册为已知事实，但本批未查其 `eval_run` / 回流）。
- 「点用户管理跳登录」**未定性**：是 token 过期还是路由鉴权不一致，**未查规格**，只记现象。

### 6. 复核命令

```bash
# ES：sp 近 15 分钟按 node 聚合（应见 request ×4 含 1 条 HTTP_401 + heartbeat ×15）
T=$(( ($(date +%s) - 900) * 1000 )); curl -s "http://localhost:39200/dev.obs-event-*/_search" -H "Content-Type: application/json" -d "{\"size\":0,\"query\":{\"bool\":{\"must\":[{\"term\":{\"agent\":\"smart-procurement\"}},{\"range\":{\"ts\":{\"gte\":$T}}}]}},\"aggs\":{\"by_node\":{\"terms\":{\"field\":\"node\",\"size\":20},\"aggs\":{\"st\":{\"terms\":{\"field\":\"status\"}}}}}}"

# online：sp 的簇（今日应零新增，仍只有 3881）
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 -t -e "select id,interface,error_type,status,first_ts from \`dev.obs\`.error_cluster where agent=\"smart-procurement\" order by id desc limit 5"'

# DB：新建用户落库
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 -t -e "select user_id,username,role,display_name,email,phone,is_active,created_at from smart_procurement.users where username=\"wop_probe_20260918\""'
```

> **清理待办**：`wop_probe_20260918`（`user_id=U-1053F56F9FA3`）**仍留在库中未删** —— 写操作面还没走到「删除用户」。
> **防腐**：「今日零新增」类断言只在本机当日成立，引用须连日期一起带。

---

## 批 2｜sp 续做：六页走完 + 撞出并修复一个真缺陷（2026-09-18）

> 承上篇。上篇的「未做」清单（专家/供应商/工商/系统配置四页未打开）**本篇已补完**；
> 「点用户管理跳登录」**本篇给出归因**（见 §3）。

### 1. 页面面 6/6 与三方对账

| 页面 | 路由 | 写操作 | UI ↔ DB ↔ ES |
|---|---|---|---|
| 用户管理 | `/admin/users` | 新建用户（上篇） | 七项逐字；`POST /api/v1/users` ok |
| 专家管理 | `/admin/experts` | **Excel 批量导入 2 条** | `expert 30→32`、`users 55→57`、`expert_specialization 65→67`；**1 写 ↔ 1 条 `POST /api/v1/experts/import`**（ok 1476ms，`trace_key=smart-procurement#715e496d…`）；UI 刷新后「专家管理（32）」 |
| 供应商管理 | `/admin/suppliers` | **拉黑 → 解除 往返 ×2 轮** | `blacklisted 1→0`（黑名单总数回基线 1）；**4 写 ↔ 4 条 `PUT /api/v1/suppliers/SUP-011/status`**（当日实测口径，见 §8 订正） |
| 工商信息 | **`/admin/conflicts`** | **CSV 导入 ×2 次** | `pending_conflict` 落 1 行；UI 刷新后「冷数据(1) / 待处理」↔ DB `PENDING` 逐字；**2 次导入 ↔ 2 条 `POST /api/v1/conflicts/import`**（第 1 次 0 命中未落库，但 HTTP 仍是 ok —— 见 §8） |
| 系统配置 | `/admin/config` | **只读**（写面经用户拍板跳过） | **UI 显示 11 项但 DB 只 1 行**（`llm.temperature`），其余 10 项走代码默认值 |

专家导入的**跨表焊点**：`expert.user_id` 与 `users.user_id` 逐字相等（`EXP-A60986913112 ↔ U-64310996705E`）；
自动建号规则 `expert_31` / `expert_32`、`role=REVIEW_EXPERT`、`must_change_password` 由导入路径置位。

### 2. 🔴 真缺陷：解除拉黑不恢复登录账号（已修复 + 三层验证）

**症状**：拉黑供应商后其登录账号被禁用；**解除拉黑后账号仍是禁用**（`supplier` 表已回 ACTIVE ⇒ 两表不一致）。

**根因**（`app/services/supplier_service.py` 的 `update_status`）—— 只实现了禁用，未实现启用：

```python
# 旧（缺陷）：单向
if new_status == SupplierStatus.INACTIVE:
    ...
    user.is_active = False
```

`SupplierStatus` 只有 ACTIVE / INACTIVE 二元；解除拉黑时 `new_status = ACTIVE` ⇒ **进不了该 if**。

**判为缺陷（非有意设计）的依据**：同仓 `expert_service.py:242-246` 做同一件事是**双向**的 ——
`user.is_active = new_status == ExpertStatus.ACTIVE`；且旧注释写着「同步禁用/**启用**」（**注释承诺了启用，实现没做**）。

**真机取证（修复前）**：20 个供应商账号全表 —— `supplier.status=ACTIVE` 却 `is_active=0` 的**只有 `supplier_11`**
（本次拉黑又解除的那个），其 `updated_at` 精确等于**拉黑**时刻 ⇒ 解除那一步在 `users` 表**零痕迹**；
对照 `supplier_05`（真 INACTIVE，`updated_at=NULL`）、其余 18 个 ACTIVE 账号 `is_active` 全为 1 ⇒ **排除「本来就是 0」**。

**修复**：`user.is_active = new_status == SupplierStatus.ACTIVE`（代价 = 每次状态变更多查一次 user）。

**验证三层**：
1. sp 全量单测 **380 passed**；
2. **判别性验证**：回退该行后 **1 failed / 14 passed** —— ⚠️ 新增 2 条里**只有 1 条判别**
   （`test_update_status_unblacklist_enables_login_account` 变红；`..._blacklist_disables_login_account` 回退后**仍绿 ⇒ 它不判别**）；
3. **真机复验**（`docker restart sp-app` 后 —— `./app` 是 bind mount 但**无 `--reload`**，不重启进程仍是旧模块）：
   拉黑 → `is_active=0`；解除 → **`is_active=1`**（修复前会停在 0）。

**我造成的副作用已撤销**：`supplier_11` 的 `is_active` 已恢复为 1。

**未处置、仅登记的隐患**：供应商账号靠 `User.display_name == supplier.name` 关联（**无外键**），
**同名供应商会互相误伤**；原注释误写成「按 username 前缀约定关联」。本篇**只修单向→双向，未动关联方式**。

### 3. 订正：sp 前端无 404 兜底 —— 「跳登录」有两种机制

- 菜单「工商信息」的实际路由是 **`/admin/conflicts`**（不是 `/admin/business`）；「系统配置」是 `/admin/config`。
- **未匹配路由 → 静默跳 `/login`，且零请求、零 ES 事件**（实测 `/admin/zzz-not-exist`、`/admin/business` 均如此）。
- 而上篇那条「点用户管理跳登录」时，ES 里有**真实**的 `GET /api/v1/users → HTTP_401`
  ⇒ **两次跳登录机制不同**：前者是纯前端路由兜底（无 404 页），后者是真实鉴权失败。
  **归因必须区分**，否则会把「路由写错」误判成「鉴权坏了」。

### 4. 工商信息页的隐含前提（文案没写）

文案只说「未匹配到**系统的企业**计入待办（冷数据）」。实测：
**人和企业都不匹配 → 「命中 0 条，待确认 0 条」、DB 零写入**；
改成**人匹配（`高伟` → 自动解析 `expert_id=EXP-016`）、企业不匹配 → 「待确认 1 条」**并落 `pending_conflict`
⇒ **人必须先匹配到系统内专家**，否则整行被静默丢弃。

### 5. 观察项（**未判为缺陷**）

- 工商信息页**写成功后列表不刷新**（仍显「冷数据(0)」，reload 后正确）—— 与 gq 会话列表同族，**第 2 次**出现。
- 用户页**搜索框**输入后仍显全量 57 条（大概率防抖未生效，**未复验 ⇒ 标为未验**）。

### 6. 未处置残留（A 级，未擅自动库）

`wop_probe_20260918`（UI 无删除入口）、导入专家 ×2（`EXP-A60986913112` / `EXP-17717E7DCC68` + 账号 `expert_31/32` + 标签 2 条）、
冷数据 `pending_conflict` id=1。

### 7. 复核命令

```bash
# 1) 专家导入落库（应 2 行；user_id 与 expert.user_id 逐字相等）
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 -t -e "select expert_id,user_id,name,organization,region,experience,status from smart_procurement.expert where name like \"导入探针%\""'

# 2) 三表行数（导入后应 32 / 57 / 67）
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 -t -e "select (select count(*) from smart_procurement.expert) expert,(select count(*) from smart_procurement.users) users,(select count(*) from smart_procurement.expert_specialization) spec"'

# 3) 缺陷判据：status=ACTIVE 却 is_active=0 的供应商账号，应为 0 行
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 -t -e "select u.username,u.is_active,s.status,s.blacklisted from smart_procurement.users u join smart_procurement.supplier s on s.name=u.display_name where u.role=\"SUPPLIER\" and s.status=\"ACTIVE\" and u.is_active=0"'

# 4) 冷数据
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 -t -e "select id,person_name,company_name,credit_code,expert_id,status,created_at from smart_procurement.pending_conflict"'

# 5) ES：sp 近 10 分钟的写事件
curl -s 'http://localhost:39200/dev.obs-event-*/_search' -H 'Content-Type: application/json' -d '{"size":20,"_source":["interface","status","duration_ms","ts"],"query":{"bool":{"filter":[{"term":{"agent":"smart-procurement"}},{"range":{"ts":{"gte":"now-10m"}}},{"exists":{"field":"interface"}}]}},"sort":[{"ts":"asc"}]}'
```

> **防腐**：「三表行数 32/57/67」只在本机当日成立（此后任何写入都会改它），引用须连**当日**与**产出命令**一起带。

### 8. offline 侧两端对账 —— 并订正本篇两处数字

判据（用户原话）：「**同一份 agent 产生的数据，在 online 和 offline 两端必须对得上**」。
**切分口径 = 按当日 00:00 起，不是 24h 滚动窗口**（滚动窗口会把 09-17 的流量混进来，正是它让本篇两处数字失真）。

| 观测面 | **09-17 基线** | **09-18 新增** |
|---|---|---|
| online ES `dev.obs-event-*`（agent=`smart-procurement`） | 635 条 | **23 条**（截至 10:15 已增至 **25** —— 见 §10） |
| online 簇 `` `dev.obs`.error_cluster `` | **1 个**（id=3881，`llm_connection`，`fixed`，05:34:02） | **0** |
| offline `error_backflow_inbox`（envelope 含 sp） | **1 条**（`payload_id=7345301f…`，case_id=**4084**，05:35:09） | **0** |
| offline `eval_run`（`agent_id=2297`） | **19 条**（manual 14 + error_regression 5，max id=3717，05:39:11） | **0** |

**09-18 那 23 条的构成**（9 类 interface，**逐条可归因到我的浏览器操作**）：
`GET /api/v1/suppliers` 6 ok ｜ `GET /api/v1/users` **3 ok + 1 error** ｜
`PUT /api/v1/suppliers/SUP-011/status` 4 ok ｜ `GET /api/v1/experts` 2 ok ｜ `GET /api/v1/{id}` 2 ok ｜
`POST /api/v1/conflicts/import` 2 ok ｜ `GET /api/v1/config` 1 ok ｜ `POST /api/v1/experts/import` 1 ok ｜
`POST /api/v1/users` 1 ok。**唯一那条 error = 上篇那条真实 `HTTP_401`。**

**这不是空绿**（防 [[shape-mismatch-yields-silent-zero]]）：先证「今天 sp 确实有流量进了 online」= **23 条非空**，
才能把「offline 两侧零新增」读成**结构性的零**，而不是**没流量的零**。

**归因**：今天我做的全是**管理后台 CRUD**（`/admin/*`：用户 / 专家 / 供应商 / 工商 / 配置）。
offline 的两条入口 —— `error_backflow_inbox` 收的是**回流**、`eval_run` 由 `error_regression` 触发 ——
**都不吃 CRUD 流量**。故「零新增」是**符合设计**，不是缺陷。
那条 401 不回流同属设计：回流值域 11 词全是 agent 侧 LLM/依赖故障，**客户端 4xx 永不回流**
（见 memory `browser-ops-cannot-produce-backflow-errors`）。

**09-17 那条链在时间上严丝合缝**（昨天的七环是活的，但是**注入**的 —— 见第四十二笔）：
簇 3881 建于 05:34:02 → inbox 05:35:09 收下 case_id=**4084** → `error_regression` eval_run 3713–3717 于 **05:35:11–05:39:11** 逐条产出。
`trigger_signal_id` = {2480, 2487, 2506, 3027, 3666}，**逐个非空**。

**🔧 两处数字订正（本篇 §1 表格已同步改）** —— 两处都是**「当时正确、被我后续动作改掉」**，
正是 [[memory-status-markers-rot]] 说的「**验收数字不随存产出命令即不可复核**」：

| 断言 | 当时的数 | **当日实测** | 差异来源 |
|---|---|---|---|
| `PUT /api/v1/suppliers/SUP-011/status` | 2 条 | **4 条** | 我做了**两轮往返**：修复前 1 轮 + **修复后真机复验 1 轮**；「2 条」是第一轮当时快照 |
| `POST /api/v1/conflicts/import` | 1 条 | **2 条** | 我导了**两次** CSV；第 1 次「命中 0 条」业务上零落库，**但 HTTP 仍是 `ok`** ⇒ ES 照记 |

### 9. 复核命令（两端对账）

```bash
# A) offline：sp 基线 + 当日新增（两值都必须是 0 才算「今日零新增」）
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 -t -e "select count(*) sp_runs,max(id) max_run_id,max(started_at) last_run_at from ai_evaluation.eval_run where agent_id=2297; select count(*) sp_inbox,max(received_at) last_inbox_at from ai_evaluation.error_backflow_inbox where envelope_json like \"%smart-procurement%\"; select count(*) run_0918 from ai_evaluation.eval_run where started_at>=\"2026-09-18 00:00:00\"; select count(*) inbox_0918 from ai_evaluation.error_backflow_inbox where received_at>=\"2026-09-18 00:00:00\";"'

# B) online：sp 的簇基线 + 当日新增（当日应为 0）
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 -t -e "select count(*) sp_clusters,max(id) max_id,max(created_at) last_at from \`dev.obs\`.error_cluster where agent=\"smart-procurement\"; select count(*) clusters_0918 from \`dev.obs\`.error_cluster where agent=\"smart-procurement\" and created_at>=\"2026-09-18 00:00:00\";"'

# C) ES：按【当日】切分（改 T0 可换日；勿用 now-1d —— 滚动窗口会混入前一日，本篇两处数字就是这么错的）
T0=$(( $(date -d "2026-09-18 00:00:00" +%s) * 1000 ))
curl -s 'http://localhost:39200/dev.obs-event-*/_search' -H 'Content-Type: application/json' -d "{\"size\":0,\"query\":{\"bool\":{\"filter\":[{\"term\":{\"agent\":\"smart-procurement\"}},{\"range\":{\"ts\":{\"gte\":$T0}}}]}},\"aggs\":{\"by_iface\":{\"terms\":{\"field\":\"interface\",\"size\":30},\"aggs\":{\"st\":{\"terms\":{\"field\":\"status\",\"size\":5}}}}}}"
```

> **防腐**：「09-18 新增 23 条 / 基线 635 条」只在本机当日成立，引用须连**当日**与**产出命令**一起带。
> **口径警告**：同一批数据用「近 24h」和「当日 00:00 起」会得出**不同**的桶计数 —— 本篇 §1 的 2 条 vs 4 条即此。

### 10. 用户页「改角色」往返 —— 判为**规格空白**，非缺陷

**操作对象**：`expert_31`（`导入探针甲`）—— **特意选它**，因为它在 `expert` 表**有实体** `EXP-A60986913112`，
而另一个探针 `wop_probe_20260918` 只存在于 `users` 表（新建用户页不建实体）。**只有前者能暴露「改角色是否联动实体」**。
操作：评审专家 → 供应商 → 评审专家（往返）。

| 观测面 | 结果 |
|---|---|
| **UI** | 角色列与操作列下拉同步变；**无二次确认弹窗**（容器/弹窗均为空） |
| **DB** | `users.role` 同步变 + `updated_at` 跟变；角色分布往返回到 `ADMIN 1 / PM 2 / REVIEW_EXPERT 34 / SUPPLIER 20` |
| **ES** | **2 次写 ↔ 2 条** `PUT /api/v1/users/U-64310996705E/status`（ok **51ms** / **9ms**） |
| **`expert` 表** | 🔴 **纹丝不动** —— 全程 `ACTIVE`，`updated_at` **停在导入时刻**（01:38:55），`expert_specialization`「软件开发」也在 |

⇒ 账号已非专家角色，**专家档案仍 ACTIVE** ⇒ **悬空专家**。

**判为「规格空白」而非缺陷**（**与 §2 那个真缺陷的判法形成对照**）：
- 回读规格 `solution.md:2216`：「创建、编辑、启停用、**分配角色**」—— 只说分配角色，**没有一句承诺级联实体**；
- **找不到兄弟实现**：`expert_service` / `supplier_service` **都没有**「改角色时联动实体」的代码；
- 而 §2 那个缺陷之所以成立，是因为**有背书**：同仓 `expert_service:242-246` 是**双向**的 + 旧注释写着「同步禁用/**启用**」。
⇒ **找不到兄弟实现 + 规格没写 = 不判缺陷**（[[implementation-odd-is-not-defect]] 的正面用法）。

**但它是真实的功能断点，须登记**：`expert.status=ACTIVE` 的专家会进评标抽取池，
若其登录账号已被改成非专家角色，**该专家会被抽中却登不进去**。
本篇**不擅自改代码** —— 规格未要求，加了就是「无消费方的实现」（[[no-over-engineering]]）。

**⚠️ 数字再次被后续动作改掉 —— §8 那个口径警告**当场**应验**：
本条操作又给当日加了 **3 条**（`GET /api/v1/users` 新增 **1 条真实 401**（会话过期所致）+ `PUT /api/v1/users/{id}/status` ×2）
⇒ **09-18 当日总数从 23 变 25**。**当日数字天然是滚动值**，引用必须连**时点**一起带（本条截止 **10:15**）。

---

## 批 3｜cs（customer-service）家浏览器 UI 验收（2026-09-18，**进行中**）

### 0. 环境

| 项 | 值 |
|---|---|
| 入口 | **`https://localhost:8443`**（自签证书，浏览器未拦）；HTTP 8081 全量 301 到 HTTPS |
| 容器 | `customer-service-nginx`（8081/8443）、`customer-service-backend-1`（8000） |
| 登录 | `admin` / `123456` —— `.env` 的 `ADMIN_DEFAULT_PASSWORD` 经 **sha256 前缀比对**确认就是公开演示口令（`8d969eef…`，len=6），**非秘密** |
| 前端路由 | **只有 4 条**：`/login` `/register` `/chat` `/admin`（`/admin` 需 `requiresAdmin`） |
| 标识 | ES `agent=customer-service`；offline `ai_evaluation.agent` id=**2298** |

### 1. 🔴 cs 上首次实到「真实用户流量走完七环」（**推翻第四十二笔的既有结论**）

此前结论：「**两家七环的红全是我注入的，无一条真实用户流量走完七环**」（第四十二笔）。**cs 上不成立** ——
存在完整、逐字可核、**非注入**的真实流量链。

| 环 | 载体 | 逐字证据 |
|---|---|---|
| ① 观测 | ES 事件 | 真实 uuid trace `fd75aa346d004723b0053b940df88eac`；`trigger_version=**0.1.0**`（注入簇 3842 是 `2026.09.09-r1`）；node=`request`/`llm_call` **成对**出现 |
| ② 聚类 | 簇 **3861**（`llm_timeout`，`POST /api/v1/sessions/{id}/messages`） | `first_trace_id` = **同一 uuid**；`input_snapshot` = `{"content":"我不太确定你们的售后流程具体是怎么走的？"}`；**`count=6` 恰等于 request 层事件数 6**（09:53:08 / 10:10:57 / 10:23:04 / 10:24:04 / 10:25:04 / 10:26:04） |
| ③ 组装→回流 | inbox **id=12** | `source.cluster_id=**3861**` + `source.trace_id`=**同一 uuid** + `evidence.input.content`=**同一文本** —— **三重逐字相等** |
| ④ 判定 | case **4075** | 由该回流建立 |
| ⑤ 回归回推 | eval_run **3662–3665** | `error_regression`，02:23–02:26（inbox +22 分钟） |

**对照组**：inbox **id=16** ⇄ 簇 **3865**（`llm_connection`，trace `d1994368f80044b89ce1fd0c69206a93`，
输入 `"你好，请介绍一下你自己"`）同样**三重逐字**。

**🔻 必须同时标注的边界（不夸大）**：
- 只走到「**回归回推**」，**第七环「收口」未观测到** —— 簇 3861 `status` 至今仍是 **`open`**（自 09-16 已两天）；
- 三簇三态：3842 `claim`（**注入**）/ 3861 `open`（真实）/ 3865 `fixed`（真实）；
- 这是 **09-16 的历史流量**，**不是**本次浏览器操作造出来的。

**结构性差异（为什么 cs 行、gq/sp 不行）**：gq/sp 前端是管理后台、无评标/问答业务页 ⇒ 页面操作造不出 agent 流量；
**cs 的 `/chat` 本身就是 agent 主链路** —— 真实用户在页面上提问即生产 agent 事件。

### 2. 一条 `rejected` 回流：`content_gap`

inbox **id=3**（属**注入**的簇 3842）：`status=rejected`、`reject_code=**content_gap**`、
`reject_detail=no_fallback_config.words 为空或非数组（fail-closed：空词表不判 pass）`、**`case_id=NULL`**
⇒ 该 error **永远拿不到 case**。**fail-closed 是有意设计**，本批**只登记不处置**（与 `backflow-fallback-absorption-gap` 同族）。

### 3. 一次自我纠错（口径）

中途我怀疑「ES 与 MySQL 差 8 小时 = 时区偏移」。**实测证伪**：Git Bash `date -d` 与 python `fromtimestamp`
**同为 +0800、一致**。真因是**我的查询没过滤 interface 且 `size:20` 按 ts 升序**，被 `HTTP_404` 挤满 ⇒ 只返回最早 20 条。
簇比首条事件晚 **6 分 47 秒**（两次恒等）= **真实处理延迟**，不是口径错。
⇒ `error_cluster` / `error_backflow_inbox` 的时间列存 **UTC**，ES `ts` 是 **epoch ms**，**比较前一律统一到 epoch**。

### 4. cs 观测面基线（ES，7 天）

`POST /api/v1/sessions/{id}/messages` **161**（145 ok / **16 error** —— error 全是 `llm_timeout`×14 + `llm_connection`×2，
**全部 node 成对且全在回流值域内**）｜`POST /api/v1/sessions` 58 ok ｜`POST /api/auth/login` 70（67 ok / 3 error）｜
`GET /healthz` 26 ok ｜`POST /api/v1/auth/login` **21 全 error**（**已查清，见 §6**）｜其余零星。

> ⚠️ **本表的计数口径**：以上是**按 interface 分组**的桶，**不含 SDK 心跳**。
> cs 每 **60 秒**落一条 `{"node":"heartbeat","source":"sdk"}`（**无 `interface` / 无 `status`**），
> 当日实测 **156/162 条是心跳**。**任何「今日 cs 有多少事件」的统计不排除 heartbeat 都是错的**
> （另：`hits.total` 是**总事件数**，**不是 error 数** —— 本批我一度把它读成 error 计数，见 §7）。

### 5. 复核命令

```bash
# cs 三簇（3861 open / 3865 fixed = 真实；3842 claim = 注入）
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 -t -e "select id,interface,error_type,status,count,first_ts,latest_ts,first_trace_id from \`dev.obs\`.error_cluster where agent=\"customer-service\" order by id"'

# 三重逐字：inbox.source.cluster_id ←→ 簇 id；inbox.source.trace_id ←→ 簇 first_trace_id
docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 -t -e "select id, json_extract(envelope_json,\"\$.source\") src, json_extract(envelope_json,\"\$.evidence.input\") inp from ai_evaluation.error_backflow_inbox where id in (12,16)"'

# cs 的 agent 侧错误事件（**必须先排除 HTTP_\*，否则被客户端 4xx 挤满 —— 本批踩过**）
T=$(( ($(date +%s) - 604800) * 1000 )); curl -s 'http://localhost:39200/dev.obs-event-*/_search' -H 'Content-Type: application/json' -d "{\"size\":40,\"_source\":[\"interface\",\"node\",\"error_type\",\"trace_id\",\"ts\"],\"query\":{\"bool\":{\"must_not\":[{\"prefix\":{\"error_type\":\"HTTP_\"}}],\"filter\":[{\"term\":{\"agent\":\"customer-service\"}},{\"term\":{\"status\":\"error\"}},{\"range\":{\"ts\":{\"gte\":$T}}}]}},\"sort\":[{\"ts\":\"asc\"}]}"
```

> **防腐**：「3861 count=6」「161/16」等只在本机当日成立，引用须连**当日**与**产出命令**一起带。
> **口径**：本批时间一律**统一到 epoch** 再比（DB 存 UTC、ES 存 epoch，**直接对字符串必错**）。

### 6. 「`POST /api/v1/auth/login` 21 条全 error」的结论：**旧 dist 残留，非缺陷**

- 现象：21 条**全 `HTTP_404`**、`duration_ms` **0~1ms** ⇒ **路由层直接拒**，未进业务
- 真实路径：`backend/app/api/auth.py:17` = `APIRouter(prefix="/auth")` ⇒ 实际是 **`/api/auth/login`**
- 前端调的是**正确**路径：`frontend/src/api/authApi.ts:9` → `authClient.post('/auth/login', …)`
- **决定性证据 = 仓内已归档同一现象**（`README.md:196`）：
  > 改过 `frontend/src/` 后必须重新 `npm run build` —— dist 挂载 nginx volume，旧构建不生效
  > （**T15 实测：`/api/auth/login` 路由统一后旧 dist 仍请求 `/api/v1/auth/login` → 登录 404**）
- **当日实证**：09-18 当日 cs 的 `HTTP_404` 命中 **0 条** ⇒ 已随 dist 重建修复
- 21 条时间形态 = **每组 3 条、间隔 60~90ms**（09:05:35×3 / 09:06:50×3 / 09:06:53×3 / 09:07:09×3 / 09:07:13×4 / 09:51:13×3 / 10:20:33 / 10:20:41）
- **顺带发现两处陈旧文档**（与旧 dist 同源、均不影响运行，按「不碰无关代码」**只登记**）：
  - `customer-service/backend/app/api/auth.py:4` 的 docstring 写 `POST /api/v1/auth/login`
  - `customer-service/docs/API.md:17` 的 curl 示例写 `http://localhost:8000/api/v1/auth/login`

⇒ 判为**非新缺陷、已归档**。

### 7. admin 写操作面走查（8 个写操作 ↔ 8 条写事件）

**先声明这批能证明什么**：offline `agent_interface`（agent_id=2298）**只有 1 行** `POST /api/v1/sessions/{sid}/messages`
⇒ **admin 页面的全部 CRUD 都不在 offline 观测面上**。故本批的绿只证明 **UI ↔ DB ↔ ES 三侧在 online 内自洽**，
**证不了「两端对账」**（这条面 offline 根本不认，**不是「没数据」**）。

基线（走查前）：`knowledge_docs` 4 行（id 1-4、`sync_status=ok`、`updated_by=system`）；
`orders` 5 行（`max_id=117`；DELIVERED 2 / SHIPPED 1 / PAID 1 / CANCELLED 1）；`order_items` 8 行。

| # | 操作 | UI | DB | ES |
|---|---|---|---|---|
| 1 | 上传知识库 | 新行插首位 | `id=16`、`updated_by=admin`、`updated_at=02:36:42` | `POST /api/v1/admin/knowledge` ×1 |
| 2 | 编辑知识库 | 更新时间逐字更新 | `content` len 80→**92**、md5 前 8 位 `7d65fc45`→**`9208b205`** | `PUT …/knowledge/probe_cs_20260918` ×1 |
| 3 | 同步知识库 | 全「已同步」 | `sync_status` 全 ok、`updated_at` **不变** | `POST …/knowledge/sync` ×1 |
| 4 | 删除知识库 | 行消失 | 行消失、**回基线 4 行** | `DELETE …/knowledge/probe_cs_20260918` ×1 |
| 5 | 新建订单 | 首行 `PROBE-20260918-0001｜1｜已付款｜12.34｜02:42:27｜探针商品×1(正常)` | `orders id=485` PAID/12.34；`order_items id=189` returnable=1 | `POST /api/v1/admin/orders` ×1 |
| 6 | 改状态 | 「已付款」→「已发货」 | `status` PAID→**SHIPPED** | `PUT /api/v1/admin/orders/{id}` ×1 |
| 7 | 删除订单 | 行消失 | `orders 485` 消失 **且 `order_items order_id=485` 一并消失（级联 ✓）**；总数回 5/8 | `DELETE /api/v1/admin/orders/{id}` ×1 |
| 8 | 重置测试数据 | 二次确认弹窗文案与后端实现逐字一致 → 回 5 条种子订单 | 见下 | `POST /api/v1/admin/reset-demo` ×1 |

**决定性核对**：当日 cs **非 GET** 事件按 interface 聚合 = 上表 **8 条，每条恰好 ×1**
（另有 `POST /api/auth/login` ×1 = 我登录，**非走查操作**）⇒ **8 写 ↔ 8 条写事件，精确相等且一一对应**。

**第 8 项「重置测试数据」的精确影响**（读 `customer-service/backend/app/api/routes.py:515-545` + 实测）：

- 实现 = 事务内 `DELETE return_orders, refund_orders, complaint_tickets, order_items, orders`，**只重建** `_SEED_ORDERS` + `_SEED_ITEMS`
- **⚠️ 不可逆**：被删的 `complaint_tickets` **16 行**、`refund_orders` 1 行、`return_orders` 1 行 **不重建**
- **执行前已全量备份** 18 行 → `.tmp-probe/cs-reset-backup-20260918.sql`
  （`--no-create-info --complete-insert --skip-extended-insert`；文件内 INSERT **18 条 = 库内计数** ✓）
- 实测 diff：`orders.id` 113-117 → **486-490**（重建换新自增 id）；`ORD-20240801-001` 商品 **已退货×2 → 正常×2**；
  三表 1/1/16 → **0/0/0**；`conversation_history` 553 / `tool_call_log` 352 **不动**
- ⇒ 与 docstring 用途**逐字吻合**（「退货后 SKU 变 RETURNED…测试前调用恢复到初始状态」）⇒ **符合设计，非缺陷**
- **回灌命令**（如需恢复那 18 行，**须你确认后再执行**）：
  `docker exec -i shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" customer_service' < .tmp-probe/cs-reset-backup-20260918.sql`
  （注意 `complaint_tickets.idempotency_key` 是唯一键，期间若产生同键行会撞）

### 8. 本批自我纠错 ×2（同一病根：**取证选择器**）

1. **把 `hits.total` 读成 error 计数** ——「今日 cs 有 159 条 **error 事件**」是**错的**，159 是**含心跳的总事件数**。
   （「今日零 404」那条结论是从 `404s` 桶读的，**未受影响**。）
2. **选择器没排除隐藏/无关节点**，连环两次误报：
   - 「上传后 UI 表格没有新行」→ 实为 `slice(0,8)` 被订单表挤占 + 页面用了 **4 个 `<table>`（表头/表体分离）**，新行在 `table[1]` 首位
   - 「保存后模态框未关闭 / 取消点不动」→ 实为 `[role=dialog]` 命中了 **`parentDisplay:none`、`rect` 全 0 的隐藏残节点**；
     模态框**正常关闭**，只是 DOM 节点未卸载 ⇒ **两条观察项均已撤回**

⇒ 教训：**取「可见元素」必须过滤 `getBoundingClientRect().width > 0`**，否则隐藏残节点会让界面**看起来坏了**。
（同族：[[unreachable-assertion-vs-false-red]] —— 判 FAIL 的两种相反成因。）

### 9. 本批未处置 / 未验

- **未验：无**。admin 页面上的写操作按钮**已全量走完**（知识库 4 + 订单 4）。
- **登记未处置**：知识库「同步」的结果在 UI 上**无独立呈现**（无「上次同步时间」栏），只体现为列表刷新。
- **cs 仍未做：无**。`/chat` 当日真流量已做（见 §11）。

### 10. 收口环（第七环）缺口 —— **已定性：不是缺陷，是「没人认领」**（用户拍板「不认领，就此结项」）

**先订正我自己的半截话**：我此前记的「cs 第七环未观测到」**不准确**。

`dev.obs`.`error_case_link` 三簇对照：

| link | 簇 | case | trace | trigger_version | verify_status | 时间 |
|---|---|---|---|---|---|---|
| 2223 | 3842（注入） | NULL | `clm-customer-service-1` | `2026.09.09-r1` | pending | 09-14 |
| **2243** | **3861（真实）** | 4075 | `fd75aa34…`（真 uuid） | `0.1.0` | **`pending`（至今）** | 组装 09-16 02:22:05 |
| **2244** | **3865（真实）** | 4076 | `d1994368…`（真 uuid） | `0.1.0` | **`passed`** | 组装 08:16:54 → 08:46:43 |

⇒ **3865 = 真实 uuid → case 4076 → link `passed` → 簇 `fixed`**：**第七环在 cs 上是真走通过一次的**，
「真实用户流量走完七环」这句话**成立**。

**3861 停在 `open` 的根因链（三条证据咬合）**：

1. **`open→claim` 没有后台作业**：worker 六个 job（`judge_scan`/`cluster`/`assemble`/`claim_ttl`/`rejudge`/`rollup`）
   **无一做此事**；它是**人工端点** `POST /clusters/{id}/claim`（`backend/app/api/backflow.py:630`）。
2. `backend/app/worker/rejudge_job.py` 的 docstring **逐字写了这个现场**：「**claim 晚于推送**……
   此时 cluster 仍是 `open` ⇒ **推送端点被 `cluster.status=='claim'` 守卫挡下**」。
3. **实测吻合**：3861 的 link 组装于 `02:22:05`，offline 的 `error_regression` run 在 `02:23–02:26` 跑完
   ⇒ 结果到达时簇仍 `open` ⇒ 被挡 ⇒ link **至今 `pending`**；
   而 **3865 被认领后 52 秒**（≈ 一个 `rejudge_job` 周期）link 转 `passed` ⇒ 簇 `fixed`。

⇒ **3861 缺的唯一一样东西 = 一次人工认领**；认领后 `rejudge_job` 会自动重放已落库结果，**无需重跑离线**。
**这是设计（收口由人工发起），不是缺陷** ⇒ 用户拍板**不认领，就此结项**。

> **可移植读法**：判「某簇为何没收口」，先看 `claimed_by`。**`claimed_by` 为 NULL 的簇永远停在 `open`，
> 且不会有任何报错或日志** —— 它**看起来像机制故障，其实是「没人按按钮」**。

> **复核命令**：
> ```bash
> docker exec shared-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 -t -e "select id,cluster_id,case_id,source_trace_id,trigger_version,verify_status,assembled_ts,updated_at from \`dev.obs\`.error_case_link where cluster_id in (3861,3865) order by id"'
> ```

### 11. cs `/chat` 当日真流量 —— liveness 取证（**结论：链路今日仍活；不构成七环证据**）

**做法**：浏览器在 `https://localhost:8443/chat`（已登录 `cs_token`）发一条真实提问
「商品到货后发现外包装破损、里面也有磕碰，我想退货，运费谁承担？」（2026-09-18 03:07:21Z）。

**取到的证据（三条，均逐字）**：

| 面 | 结果 |
|---|---|
| ① ES（排除心跳） | 本次新增 **2 条**，全 `ok`：`POST /api/v1/sessions/{id}/messages`（68ms，trace `28e7ca83…`）+ `GET /api/v1/sessions`（3ms） |
| ② online `dev.obs` | 当日 `error_cluster` **0 行**；按 `first_trace_id=28e7ca83…` 查 **0 行** |
| ③ offline `ai_evaluation` | cs(2298) 最新 run 仍 **3702 / 2026-09-16 08:46:28** ⇒ **零新增** |

**跨端对账（顺带取得，非本次动作产生）**：online 看板 cs 卡片 `c1-signal-20260916-2 / 96.74 / 96% / 16-17 用例`
↔ offline `eval_run` id=3701 `agent_score=96.74 / total_case=17 / pass_case=16` —— **逐字相等**。

**⚠️ 本次提问的真实成分（不许夸大）**：响应是 SSE（`text/event-stream`），但**全程约 68ms**，
且 `usage` 事件 `prompt_tokens=0 / completion_tokens=0`；`done` 带 `intent=RETURN_REQUEST`，
回复文案「请提供您的订单号」由 **`order_query` 阶段短路产出**。
⇒ **本次根本没有调用 LLM**，是规则路径。因此这条流量：

- **能证明**：`/chat` 真链路今日仍活；真实提问确实进了 agent 主链路并被观测面记到（2 条 `ok`）；
  当日真实 trace 在 online 侧**确无簇**，与「正常消息不回流」一致；两端计数零漂移。
- **不能证明**：七环。**它连 L1 判定面都没进**（无 LLM 调用、无 `error`、无簇）。
  七环的真实流量证据仍是 09-16 那组（簇 3865 → link 2244 `passed`，见 §10）。

- **登记未处置（观察项，未判缺陷）**：`GET /api/v1/sessions` 当日有 1 条 `HTTP_401`
  （我未登录时碰的，客户端 4xx）⇒ **与「4xx 永不回流」一致，未建簇**，是既有判据的又一次独立复现。

### 12. 四家页面面收口 —— 提交与残留清点（2026-09-18）

**已提交（用户拍板「只 commit，不 push」）**：

- sp `df28261` `fix(supplier): 解除拉黑同步恢复登录账号（修「只禁不启」）`
  —— **本批唯一一处真代码修复未落地，现已落地**。提交前实跑 `tests/unit/test_supplier_service.py` = **15 passed**（含新增 2 条）；
  仓内 pre-commit 钩子实跑 **380 passed / 覆盖率 70.64%（阈值 45%）**。
  ⚠️ **与 [[local-precommit-hook-gap]] 的一处对照**：该 memory 记「覆盖率门禁对 `backend/` 布局的仓是死代码」——
  sp 是 `app/` 布局，**本例中门禁确实生效并打印了覆盖率**。两条不冲突，但**判「钩子管不管用」必须先看仓的布局**。
- online `b52d193` `docs(task): 批 3 cs 收尾 ……`（`task.md` +553/−0 纯新增）。
- **未 push 合计 11 笔**：online 5 · offline 2 · contract-check 3 · smart-procurement 1。

**残留清点（我只列出，不删）**：

| 位置 | 体积 | 性质 | 处置 |
|---|---|---|---|
| `contract-check/.tmp-revert/` | **1.2 GB / 34,727 文件**（真身 = 拷贝出的 `.venv` 1.1 G + `data` 74 M + `fonts` 17 M） | F3 判别性回退用的整仓拷贝，**无 `.git`、可重建** | **用户拍板清除**（命令见下） |
| `agent-evaluation-online/.tmp-probe/` | 529 KB / 53 文件 | 各批真机探针取证快照（`gq-*`/`sp-*`/`f6-*`/`rules-*`/`cs-*-snap` 等），**被本台账 §6~§11 多处引作复核依据** | **留** |
| `customer-service/.tmp-probe/` | 8 KB / 2 文件 | cs 探针脚本 | **留** |
| `smart-procurement/.env.c1bak` · `contract-check/backend/.env.c1bak` · `contract-check/.tmp-revert/.env.c1bak` | — | 凭据备份 | **一律保留，不读不删** |

**🔴 本次新登记的隐患（只登记，未处置）**：`contract-check` 仓的 **`backend/.env.c1bak` 与 `.tmp-revert/.env.c1bak` 均未被 `.gitignore` 覆盖**
⇒ 任何人一次 `git add -A` 就会把**明文凭据**收进暂存区。
对照（说明这是可修的）：同目录 `.tmp-revert/.env` **被忽略**（`.gitignore:3` 的 `.env` 规则任何层级都匹配）；`smart-procurement/.env.c1bak` **也被忽略**。
⇒ 补忽略规则属**改配置 = A 级**，须另开一条先出方案，**不在本批顺手做**。

**⚠️ 一条不得连坐的耦合**：`online/.tmp-probe/cs-reset-backup-20260918.sql` 是「重置测试数据」执行前 18 行的**唯一备份**
（16 工单 + 1 退款 + 1 退货）⇒ **清 `.tmp-probe` 时必须先单独救出它**，否则那三张表永久不可恢复。

**清理命令（我未执行 —— 按全局规约 `rm -rf` 必须由用户自己跑）**：

```bash
# 1) 先确认对象（应打印 1.2G）
! du -sh /d/study/aiprojcet/contract-check/.tmp-revert
# 2) 再删
! rm -rf /d/study/aiprojcet/contract-check/.tmp-revert
# 3) 删后复核：应只剩 ?? backend/.env.c1bak
! git -C /d/study/aiprojcet/contract-check status --short
```
