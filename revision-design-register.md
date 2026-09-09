# Task#4 error 回流修订设计台账（登记 → 设计 → 评审 → 落字）

> **性质**：工作台账，**非权威方案**。权威口径仍以 solution.md / solution_detail.md / offline error-backflow-phase1.md / error-backflow-phase2.md 为准。
> **来源**：2026-09-07 双端数据流整链推演（online→offline 打点→聚类→D19→pull→激活→error_regression run→回查→auto-fixed/needs_review→K-TTL 收敛）产出的硬伤 H1-H6 及衍生项。
> **状态机**：`recorded`(已登记) → `designed`(已出设计) → `reviewed`(已评审≥1轮) → `approved`(用户拍板) → `landed`(已落字) → `cross-checked`(多文档交叉核对)。
> **当前**：R-1~R-12 全部 `landed`——**R-1/R-2/R-12**（2026-09-07 首批：detail v1.5 + solution v3.5.5 + phase2 v0.6.2）；**R-3~R-10 修订包二批 + R-11**（2026-09-07：detail **v1.6** + solution **v3.5.6** + phase2 **v0.7**，落字详情见登记表各行；R-11 = 随各 R 落字并入的环 2 用例，不独立占版本）。**R-18/R-19**（C 类高危 2 条，2026-09-07 评审 v0.1 → 用户拍板方案 A → 已落字：detail **v1.7** + solution **v3.5.7** + phase2 **v0.7.1**；offline 零机制，落点见评审记录区）。**R-13~R-17**（B 类 5 条，2026-09-07 评审 v0.1 → 用户逐条拍板 → **landed（2026-09-07：detail v1.8 + solution v3.5.8）**：R-13 判定位窗口化 / R-14 unclean_run 口径归一 + 挂起标注派生 / R-15 input_truncated 优先 / R-16 excluded 自动消费 / R-17 K 序列锚 versions 读面，方向详见登记表、落点见评审记录区 R-13~R-17 节；offline 零机制——R-16/R-17 读面字段落位 + R-13 同簇刷新复制机制代码留 Phase B 实现核对）。**R-20~R-24**（C/低危 5 条，2026-09-07 评审 v0.1 → 用户逐条拍板 → **landed（2026-09-07：detail v1.9 + solution v3.5.9 + phase2 v0.7.2）**：R-20 pre-scan 门禁立项 + 空答 fail 语义定性 / R-21 root-late 补判通道 + root_late_complement / R-22 收尾回填 na 钉死 scheduler_unexecuted / R-23 timeout 三层语义分界 / R-24 requeue guard 状态域精确化，方向详见登记表 R-20~R-24 行、落点见评审记录区 R-20~R-24 节；R-20 code = Phase B pre-scan 实施门禁、R-21/R-24 = online 实现清单）。双端已完成提交（2026-09-07：online main 0b4662f + e016c45 / offline dev dcf4680 + e85fa2e）；R-3~R-10、R-18/R-19、R-13~R-17、R-20~R-24 已全部落字并 commit 收口。**Phase B**（offline error-backflow-code_detail.md，含 R-3 差集对账/R-8 cap_gap 节流/R-4-5 只读面/R-12 text.py 等 offline 机制代码单独立项 + **R-20 pre-scan 实施门禁**）：code_detail v0.3 已定稿（2026-09-07）并升格为权威详设 `error-backflow-solution_detail.md`（**现行 v1.1**：2026-09-07 登记层增补 §12.6 集成异常/边界用例 X-1~X-11）+ 拆 `error-backflow-task.md`（引详设 v1.1），代码实施中。** 集成用例登记层收口（2026-09-07，非 R 修订）：online detail **v1.10**（§14.5 X-1~X-13 = task 阶段 4 T-4.13/T-4.14 编号化）+ offline 详设 **v1.1**（§12.6 X-1~X-11 = error-backflow-task 阶段 D/F 编号化）——纯登记层无语义变更：solution v3.5.9 / phase1 v0.2.2 / phase2 v0.7.2 语义基线不动，全部 R 落点历史行版本号保留。
> **H7 批（2026-09-07 第二轮双端整链推演，R-1~R-12 全部 landed 的新基线上复推）**：A 类 7 条 wire/consistency 缺陷（H7-1~H7-7）+ 1 条残留（H7-20）按用户裁决「**A 类先修，B/C 立项评审**」已四文档直接修补落地、**不升版本**（detail v1.6 / solution v3.5.6 / phase2 v0.7 / phase1 v0.2.1 现行版内修补，落点见评审记录区「A 类修复记录」）；B 类 5 条（H7-8~H7-12 已拍板机制联动 gap）+ C 类 4 条（H7-13~H7-16 新设计 gap）+ 低危 3 条（H7-17~H7-19）登记为 **R-13~R-24**——其中 **R-18/R-19**（C 类高危 2 条）已评审 v0.1 → 用户拍板方案 A → **landed**（detail v1.7 / solution v3.5.7 / phase2 v0.7.1，见评审记录区各节）；**R-13~R-17**（B 类 5 条）已评审 v0.1 → 2026-09-07 用户逐条拍板 → **landed（detail v1.8 / solution v3.5.8，见评审记录区 R-13~R-17 节；offline 零机制，R-13 同簇刷新复制机制 + R-16 excluded 字段落位为 Phase B 实现核对项）**；**R-20~R-24**（C/低危 5 条）已评审 v0.1 → 2026-09-07 用户逐条拍板 → **landed（2026-09-07：detail v1.9 + solution v3.5.9 + phase2 v0.7.2，方案 = 登记表 R-20~R-24 行「已拍板方向」列，落点见评审记录区 R-20~R-24 节）**。

## 基线 / 目标版本

- 基线：solution.md **v3.5.4** / solution_detail.md **v1.4** / task.md（环 0~3）/ offline error-backflow-phase1.md **v0.2.1** + error-backflow-phase2.md **v0.6.1**。
- 每项 approved 后落字目标（未拍板不动版号）：detail → **v1.5**、solution → **v3.5.5**、phase2 → **v0.6.2**；phase1 仅当某项触及批 1 机制才动。
- **本行记录首批（R-1/R-2/R-12）落字目标，为历史标注**；后续批次落字目标逐批滚动（修订包二批 = v1.6/v3.5.6/v0.7；R-18/R-19 = v1.7/v3.5.7/v0.7.1），现行状态以 header「当前」句与登记表各行「landed」落点为准，勿以本行数字回推。
- 原则：online 侧语义修订以 detail 为落点、solution 做权威同步；offline 侧尽量零机制改动（纯消费语义/注记同步），R-3/R-4/R-7/R-8 若需机制改动须单独立项评估范围。

## 已拍板方向（AskUserQuestion 2026-09-07）

- H1 → **A1**：K 改 claim 级参数（cluster 固化 `claim_k`，默认取全局默认=2，claim 可降 1；顺带补 K 配置键缺口）。
- H2 → **B1**：纯净判据下钻到 claimed case 自身行 + 按 na error_type 分流（仅环境/调度级 na 触发 unclean_run，case 级技术 na 不牵连他 cluster）。
- H3-H6 → **本次一并起草修订**（逐项设计评审，不落字先行）。
- 本批推演结论 → **记入 memory**（已执行）。

## 登记表

| ID | 标题 | 定位锚点（会话核对，落字前复读原文） | 影响端 | 已拍板方向 | 状态 |
|---|---|---|---|---|---|
| R-1 | auto-fixed 依赖发版节奏：修复即收工/版本不递增时 K=2 永不可达，重 claim 同 fix_version 每 14d 原地转圈 | detail §7.6（K 稳定序列，K=2 默认 dict_config 可配）、§10.1（claim TTL 两时钟）；phase2 §5.2（completed 守卫 return，同版本不重建） | online（detail/solution），phase2 仅注记 | **A1：claim 级 claim_k**（评审①K=1 显式逃生门/②零推进可降推进后锁死/③动态提示依赖 R-5） | approved → **landed**（2026-09-07，detail v1.5 §7.6 + solution v3.5.5 + phase2 v0.6.2 注记） |
| R-2 | R5"纯净 run = run 级 na_case==0"粒度过粗：打包 run（多 cluster 一 run）内无关 case 的技术 na 误伤他 cluster 真实 pass → unclean_run | detail §7.6（纯净可判、unclean_run）；phase2 §6.4（na 五源）、§9.3（na 行带 error_type，只读面够用、不加字段） | online 消费语义（offline 零机制） | **B1：case 级 + 环境级 na 分流**（评审①B1 成立由实现核对支撑/②离线标注影响域列+无标注从严/③na 退 batch 改单点、撞键裁定收窄） | approved → **landed**（2026-09-07，detail v1.5 §7.6 + solution v3.5.5 + phase2 v0.6.2 §6.4 标注列） |
| R-3 | 洪峰并发丢版本无重试锚：同 agent 至多 1 活跃 error run，多版本连发被丢的中间版本永不建 run → online 回查空 → TTL | phase2 §5.2（洪峰收敛）、§5.3（补偿对账仅补首建缺口、锚被吸收态拦截） | offline 机制 + online 语义 | 已拍板（方案 C：对账版本差集补齐） | approved → **landed**（2026-09-07：phase2 v0.7 §5.3 差集补齐 spec + §11.2 场景 17；online 语义零改动 = detail v1.6 修订注 + solution v3.5.6 同步） |
| R-4 | cap 截断 newest-active-first 饿死最老 case：高错误率 agent 下队尾 case 永不进 run，其 cluster 永等不到终值 | phase2 §6.1 注1（cap 估算、newest-active-first、case_truncated 仅诚实标记） | online 语义/可见性 + offline 只读面透出 | 已拍板（方案 1：online 可见性 + 人工收敛） | approved → **landed**（2026-09-07：detail v1.6 §7.6 缺行成因诊断 + §9.3 excluded-case 只读面；solution v3.5.6；phase2 v0.7 §9.3 溢出透出 + §11.2 场景 18；不跨端保窗口维持） |
| R-5 | fix_version 三方字符串相等无硬校验：claim 填未发布/错版本 → offline 无该 version run → 空轮询满 14d | detail §8.4（claim 端点）、§7.5（版本字面量域 B-5）；phase2 风险 17（双向 mismatch） | online 交互/告警 + offline 只读面（数据源） | 已拍板（软校验 + agent 已见版本新读面） | approved → **landed**（2026-09-07：detail v1.6 §8.7 agent 已见版本读面 + §9.3 claim 表单软校验告警；solution v3.5.6 §10.4；phase2 v0.7 §9.3 读面数据源） |
| R-6 | L2 子节点 error_type 原值还原精度：err_summary_json 未钉 schema，若存分类非原值 → §6.2 原值去重粒度漂移 | detail §5.1⑩（err_summary 聚合字段）、§6.2（error_type 原值去重） | online schema 钉死 + 环2 用例 | 已拍板（钉死原值域） | approved（实现前钉死点） → **landed**（2026-09-07：随 detail v1.6 §4.3/§5.1 err_summary_json DDL schema 钉死落字，不独立占版本；solution/phase2 零改动） |
| R-7 | online_content_gap（含**空词表**）无批量自愈：配置补齐后需 admin 逐个 requeue | detail §7.4（requeue、reason 码 online_content_gap）；phase1 §6.3/§6.5 | online（批量工具） | 已拍板（批量端点 + 可愈性标注） | approved → **landed**（2026-09-07：detail v1.6 §7.4/§8.4/§9.3 批量 requeue + 可愈性标注；solution v3.5.6 §10.3；online 环 2 场景 → detail v1.6 §14；phase2 零改动） |
| R-8 | cap_gap 每小时自愈对**已 acked 闭环** rejected 行也重扫：映射持续缺时每小时重发无效 invalidated ack（online 200 幂等兜底，纯噪音） | phase1 §6.5（cap_gap 自愈未限定 ack_status） | offline 节流 | 已拍板（探测态节流） | approved → **landed**（2026-09-07：phase2 v0.7 §6.5 节流修正注记 + §11.2 场景 20 + phase1 §6.5 引用修订；offline 机制代码单独立项 code_detail；online 零改动 = detail v1.6 依据注 + solution v3.5.6） |
| R-9 | needs_review_batch 整批 resolve 与 TTL job 并发 CAS 冲突：引用 cluster 处置瞬间被回退 open → 整批事务回滚，重试语义未定义 | detail §7.6（batch resolve 前提"引用 cluster 保持 claim"）、§8.4 | online 并发语义 | 已拍板（语义化跳过非 claim） | approved → **landed**（2026-09-07：detail v1.6 §7.6 处置语义 + §8.4 per-cluster 结果 + 整批单事务/批级 CAS；solution v3.5.6 §10.4；phase2 零改动） |
| R-10 | 复现 input 截断/归一保真：evidence.input ≤8K 截断代表事件，长输入尾部依赖型错误可能复现假 pass → 假 fixed | detail §5.1④（input_snapshot ≤8K vs input_hash normalize 4096）；phase1 §2.1/§6.3（超长判定未定义） | online 语义 + offline 边界 | 已拍板（截断标记 + 禁用 + 新 reason input_truncated） | approved → **landed**（2026-09-07：detail v1.6 §5.1 input_truncated 列 + §7.6/§8.4/§9.3 + reason 值域 3→4 + input_hash normalize 4096→8192；solution v3.5.6 §10.2/§10.4；phase2 v0.7 注记 + §11.2 场景 21） |
| R-11 | 环 2 应补用例集（随各 R 落字时并入对应场景）：无关 case na 隔离 / input 截断边界 / claim_k=1 快路径 / 重 claim 同 fix_version 提示 / 洪峰丢版本 / cap 最老饿死 | phase2 §11.2 场景 14/15/16（R5/R6/R7）为现行基线 | 双端环 2 | 登记项（不独立机制设计） | recorded → **landed**（2026-09-07 随 R-3~R-10 落字并入：offline 场景 17-22 → phase2 §11.2；online-only → detail v1.6 §14；不独立占版本） |
| R-12 | verifier 空串/纯空白应答 pass 缺口（核对 offline 实现 text.py 发现）：`KeywordNotContainsOp` 对 answer="" / 纯空白返回 pass（与 run 有无 na 正交，executor 跑通 + agent 空话术即中招） | offline `backend/app/assertions/ops/text.py` run() L46-62；phase2 §7.2/§7.4 单测矩阵无空串行 | **offline 机制微改（共享算子，影响普通 run 断言）+ online 消费语义** | 修共享 op：strip 后空串/纯空白 → fail（同 path 缺失/非文本层）；先扫现网断言空字段依赖确认纯收紧；单测矩阵补行 + 回归金丝雀 | approved（评审：修共享 op + 先扫副作用；突破 offline 零机制承诺、单独立项） | approved → **landed**（2026-09-07，phase2 v0.6.2 §7.2 决策注 + §11.1 单测行；text.py 代码变更单独立项） |
| R-13 | input_truncated 标记无清理/更新机制：一次截断 → claim 永久不计 K、escape 不可达（B，H7-8） | detail v1.6 §5.1 input_truncated 列 + §7.6 判据（标记只置不清） | online 语义 | **判定位窗口化（复用 input_truncated 列刷新、单 trace 即刷）**：列语义 = 该 cluster 当前判定态——消费 step4 同键新 trace 开簇/回填复制时以新判定态刷新（≤8K 清 0、>8K 置 1），已 closed cluster 不刷新（终态只读不翻案）；同簇回填补一次复制（online 机制代码、记 Phase B）；截断历史留 needs_review(input_truncated) 产物 + 详情警示不抹（2026-09-07 用户逐条拍板） | recorded → approved → **landed**（2026-09-07：detail v1.8 + solution v3.5.8，落点见评审记录区 R-13~R-17 节；同簇刷新复制机制代码 = Phase B 核对项、offline 零机制） |
| R-14 | unclean_run 载体状态模型双写：batch link_refs（引 pass case 保持 claim）vs state-machine 表 needs_review 行归属口径未统一（B，H7-9） | detail v1.6 §7.6 needs_review_batch + state-machine 表 | online | **A' 口径归一 + 挂起标注派生**：状态机表 reason 列 unclean_run 收窄 =「经 batch 载体处置、cluster 不入 needs_review 态」（unclean_run = 存疑非否定，批引 cluster 保持 claim 正确）；cluster 详情/列表实时派生「被未决 unclean_run 批 Bx 挂起」标注（join 未 resolved 批 link_refs、免加列）；**TTL 不豁免沿用兜底**（批引用 = 不纯净中断观察，TTL 到期自然回退 open、批 resolve 时 R-9 skipped_already_open 幂等覆盖）（2026-09-07 用户逐条拍板） | recorded → approved → **landed**（2026-09-07：detail v1.8 + solution v3.5.8，落点见评审记录区 R-13~R-17 节；offline 零机制） |
| R-15 | input_truncated × unclean_run 双通道无优先级/互斥：同 run 双条件时 reason 取哪个、批/单点归属排他未定义（B，H7-10） | detail v1.6 §7.6 reason 聚合归属 | online | **input_truncated 优先（纵向个案治本 > 横向批量归因）**：双条件同现时该 cluster 走 input_truncated 单条通道（cluster 级 needs-review-resolve）、**不并入** unclean_run 批（批聚合 link_refs 排除自身 input_truncated=1 的 cluster）；同 run 其余无截断 pass cluster 照常走批；reason=input_truncated + note 附「同版 run 含环境级 na」（2026-09-07 用户逐条拍板） | recorded → approved → **landed**（2026-09-07：detail v1.8 + solution v3.5.8，落点见评审记录区 R-13~R-17 节；offline 零机制） |
| R-16 | R-4 excluded_case_ids 无自动 fetch path：附着于 case_id-query 不可达的 run，核对路径断裂（B，H7-11） | detail v1.6 §9.3 excluded 只读面 + 查询键 | online + offline 读面 | **缺行诊断自动消费 excluded 读面**：detail §7.6 v1.6 ① 从「UI 引导人工 offline 核对」升级为自动——recheck 判 claimed case 在 bound_version run 缺行 → 自动 GET runs?agent=&version= → 判 case_id ∈ excluded_case_ids：∈ 自动标「窗口外欠测（cap 挤出、非修复失败）」沿用现语义（不自动 reopen/不进 needs_review）、∉ 维持人工兜底；excluded_case_ids 落 runs list 每行或 detail 位置留 Phase B 实现核对；offline 零新机制（R-4 字段已在）（2026-09-07 用户逐条拍板） | recorded → approved → **landed**（2026-09-07：detail v1.8 + solution v3.5.8，落点见评审记录区 R-13~R-17 节；excluded_case_ids 落 runs list/detail 字段位置 = Phase B 实现核对项、offline 零机制） |
| R-17 | R-3 差集迟到补建 × K sequence continuity：某版 run 于 K 观察窗内迟到补建，补建结果是否计入/重排既有 K 序列 → false-fixed window（B，H7-12） | phase2 v0.7 §5.3 R-3 差集块 + detail v1.6 §7.6 K 序列 | offline + online 消费语义 | **K 序列版本锚 = R-5 versions 读面（agent 发版拓扑权威）**：detail §7.6 补「候选版本序列定义」——recheck 以 GET versions（window_days 覆盖 claim TTL 14d）取 ≥ fix_version 全版本序逐版：versions 有该版且 error run 有终值 → 判 K；versions 有该版但无 error run → **缺行中断**（下一可见 error run 不续缺环，v1(pass)+v3(pass) 不假连续）；迟到补建终态到达后补判推进。根因 = 版本连续性缺权威锚，非迟到补建计入问题；versions 端点用途从「claim 表单提示」升级「K 判据序列源」（recheck 每轮多一次 RPC）；offline 零新机制（versions 读面 R-5 已在）（2026-09-07 用户逐条拍板） | recorded → approved → **landed**（2026-09-07：detail v1.8 + solution v3.5.8，落点见评审记录区 R-13~R-17 节；versions 端点用途升级为 K 判据序列源随 v1.8 §8.7 落、offline 零机制） |
| R-18 | input 明文无 persistence carrier：消费 step4 仅存 root_input_hash，cluster 快照/截断判定的原始 input 来源缺定义（C，H7-13，高危） | detail v1.6 §6.2/§7.6 root_input_hash + 组装链路取数点 | online | **方案 A（判定 worker 落明文快照列 carrier，聚类/组装引用，§6.2 取数从判定态列）**（2026-09-07 用户拍板） | recorded → reviewed → approved → **landed**（2026-09-07：detail v1.7 §5.1 DDL 增列 input_snapshot_clean/input_truncated + §4.1 step4/§4.3 root 到达落点 + §6.2 复制 + solution v3.5.7 §7.2；offline 零机制） |
| R-19 | error_type 长短名字面量不一致：executor 常量 `connect_error/sse_parse_error/http_error/http_client_error/pool_error` vs 文档短名 → 分类 key miss → unclean 风暴（C，H7-14，高危，executor.py L1-40 实证） | offline backend executor.py L1-40 + detail §6.2 error_type 原值域 | online + offline | **方案 A 全量（字面量对齐 executor 真值 + no_usage/contract_error 补入归 case 级 + code 一致性单测护栏）**（2026-09-07 用户拍板） | recorded → reviewed → approved → **landed**（2026-09-07：detail v1.7 §7.6 + phase2 v0.7.1 §6.4/§11.1 + solution v3.5.7 §10.5；code 一致性单测护栏入环 0 静态核对项） |
| R-20 | R-12 shared-op 收紧缺 pre-scan owner；普通 run 空答 fail 与 leakage-recurrence（空话术复现）判定混淆（C，H7-15） | phase2 v0.7 §7.2 R-12 注 + offline ops/text.py | offline 机制（code 走 Phase B） | **A：pre-scan 门禁立项 + 空答语义定性**——R-12 core（空答 fail）不动；① pre-scan 显式立项为 Phase B code_detail 实施门禁（owner = offline 实施、产物 = pre-scan 报告：扫现网 keyword_* 断言空字段依赖 + 合法空答清单，发现合法空答 → 收紧带豁免白名单上线）；② 复现 run 空答 fail 语义定性 = leakage 空话术复发证据（agent 无有效产出），与词表命中 fail 同属未修复、证据形态不同；「空答不落 na、落 verifier fail」保持（2026-09-07 拍板） | recorded → designed → reviewed → approved → **landed**（2026-09-07：phase2 v0.7.2 §7.2 R-20 注 + §11.1 补注 + §10 blockquote + §13 行；pre-scan 实施门禁入 task 环 0，code 走 Phase B code_detail） |
| R-21 | 残 trace 且 root 迟到漏分类：L2 归因/聚类对残 trace + root-late 分支缺定义（C，H7-16） | detail L2 归因/聚类（error_cluster 组装） | online | **A：root-late 补判通道**——step4 root 到达发现 judged=1 且 root 此前未参与判定（root_ok 0→1）且 root_status∈{error,timeout} → 不重跑整 trace、仅对 root 级产出补一次候选（root_error_type 走 §6.1 L1/L2 值域筛，命中才补）→ 复用 §6.2 聚类：同键已有 cluster → count+1/补快照（open 且缺 input 实文 → 现 root input 已落可补组装）；异键 → 开新 cluster；同键已 closed（fixed/inactive）→ 跳过不翻案；幂等 = root 到达事务内置 root_late_complement 标记 CAS 防重（2026-09-07 拍板） | recorded → designed → reviewed → approved → **landed**（2026-09-07：detail v1.9 §4.3④/§4.4/§5.1⑩/§6.1/§6.2/§14 E-28 + solution v3.5.9 §6.1/§7.2/§10.2；root_late_complement 列 + step4 补判 code 项 = online 实现清单，offline 零机制） |
| R-22 | non-scanner 来源 na 行回填 error_type 未定义：na 载体聚合键 run_id+error_type 断链（低危，H7-17） | detail v1.6 §7.6 na 行聚合 | online + phase2 注 | **A：收尾回填 na 统一钉死 scheduler_unexecuted**——scanner 回收 + orchestrator cancel + run 级超时收尾三路径回填 na 同源 scheduler_unexecuted（调度级原因、非 case 交互失败）；「na case 必带 error_type」不变量全覆盖收尾路径；timeout 不作收尾回填原因（只作 case 级 na 源 + run 终态，与 R-23 一处对齐）；实现期单测护栏断言收尾回填 na error_type 非空（2026-09-07 拍板） | recorded → designed → reviewed → approved → **landed**（2026-09-07：phase2 v0.7.2 §6.3 R-22 注 + §6.4 源行三路径 + §11.1 护栏断言 + detail v1.9 §7.6 ①/§8.7 + solution v3.5.9；实现按三路径统一 error_type 落 scheduler_unexecuted） |
| R-23 | run-timeout 文案/语义张力：§6.4 源矩阵 vs §7.6 reason 聚合边界表述不一致风险（低危，H7-18） | detail v1.6 §6.4 + §7.6 | online + phase2 注 | **A：timeout 三层语义分界 + 兜底边界闭合注**——① case 级 na 源（executor 交互超时，na 行 → reason=na、case 级不牵连）；② run 终态 timeout = 半途中断、不直接触发 needs_review（兜底 = claim TTL 回退 open，B-3）；③ run 级 timeout 收尾产生的回填 na（error_type=scheduler_unexecuted，环境级）→ 该 run 非纯净 → 关联 pass case 入 unclean_run 批（R-2 环境级牵连）——「run 超时非源」排除的是 timeout 事件直接驱动 cluster 状态、不排除环境级回填污染的间接作用（2026-09-07 拍板） | recorded → designed → reviewed → approved → **landed**（2026-09-07：detail v1.9 §7.6 ② v1.9 blockquote（三层分界 + B-3/B-4 兜底引用）+ solution v3.5.9 + phase2 v0.7.2 §2.3 注③/§6.4） |
| R-24 | requeue-guard 不交叉 claim lifecycle：guard 不感知 claim 推进，rescan/requeue 与 claim 处置并发缺交叉语义（低危，H7-19） | detail v1.6 §7.4/§7.6 | online | **A：requeue guard 状态域精确化 + 锚点保护**——requeue 复位条件从「cluster 非 inactive」精确到 `cluster.status ∈ {open, claim, needs_review}`（fixed/inactive 已 closed → 禁 requeue、需重测走 superseded+reopen 重建）；claim/needs_review 态允许（供 claim 回归 run / needs-review-resolve 补充证据拉取复位）+ 显式声明 requeue **不动 cluster 锚点**（fix_version/claim_k/TTL 保留，run 回查仍以现 claim 锚定）；verify 兜底 = 仅 verify_status=pending 的 invalidated link 走此路（已推进状态不在此路，2026-09-07 拍板） | recorded → designed → reviewed → approved → **landed**（2026-09-07：detail v1.9 §7.4 requeue guard 状态域改写 + §9.4 门控行 + §14 E-29；online-only，requeue guard code = online 实现清单） |

## 备注

- **R-1 关联**：K 配置键缺 detail §10.1 生效键清单（既有缺口）→ 随 A1 一并解决（claim_k 固化 + 默认键 `claim_k_default` 入清单）。
- **R-3/R-4 属 offline 机制层**（admission/重试锚），一旦改动即突破"offline 零机制改动"承诺，评审时需单独界定影响范围与环 2 覆盖面。
- 锚点均来自本会话双端文档事实抽取，落字前逐条复读原文核对。

---

## 评审记录区（逐项追加）

### R-1（H1 → A1：claim 级 K）— 设计 v0.1（2026-09-07）

**目标**：auto-fixed 的 K 从"全局 dict_config 单一值"改为"每次 claim 时固化 `claim_k`"，使 claim 人对低频发版/修复即收工 agent 可选 K=1 当场收敛、活跃 agent 保留 K=2 跨版本复证；消除"版本不递增/修复后不再发版 → K 差 1 永不达 → 每 14d 原地转圈"的结构性死路；顺带把 K 匿名 dict_config 键补进 §10.1 生效键清单。

**机制**：
1. **载体**：`error_cluster` 增列 `claim_k TINYINT UNSIGNED NOT NULL DEFAULT 2`，随 claim CAS 同批写入（claimed_at/claimed_by/claim_due_ts/fix_version 一并）。TTL 回退 open 后重 claim 可改值；每次 claim 重新固化，TTL 自新认领起算（与 R6 一致）。
2. **claim API**（detail §8.4）：入参新增可选 `k`（域 {1,2}，超域 400；缺省 = 全局默认 2）→ 写 cluster.claim_k。
3. **dict_config**：§10.1 生效键清单补 `auto_fixed_k_default`（默认 2），供 claim 表单预填与缺省取值；§7.6 匿名"可配 dict_config"表述收敛为该键。
4. **判定读取**（§7.6 / verify_run_record 消费）：verify passed = "自 claim fix_version 起连续 **claim_k** 个纯净可判版本 run 均无 fail"。K 只读 claim 时固化值、**不实时读全局键**（防观察期改全局键造成已攒序列语义漂移）。verify_run_record 行补记 claim_k 快照（审计，弱可选）。
5. **不可变**：claim 生命周期内 claim_k 不可改（防序列语义中途漂移）；要改需 TTL 回退 open 后重 claim。
6. **收敛终点**（§10.1）：不变——K 满 → fixed（TTL 停钟）/ claim TTL 先到 → 回退 open。claim_k=1 = fix_version 版纯净可判 pass 即 fixed（等价 v1.3 单版判，但判据仍含纯净 run/判定产物体系，比 v1.3 严）。
7. **重 claim 提示**（产品 guard，非硬校验）：TTL 回退后重 claim 若 fix_version 与上次相同，表单提示"该版本 error run 已存在/可能已 pass，auto-fixed 将等第 {claim_k} 个不同版本；agent 不再发版请改填更高版本、选 k=1、或走 admin_review"。offline run 状态 claim 时不可见 → 只提示不强判。
8. R7/reentry 门控、needs_review reason 值域、needs_review_batch 聚合：不受影响。

**边界**：claim_k 白名单 v1 只放开 {1,2}（域 1..5 预留）；"观察期 agent 突然活跃想升 K" 只能等 TTL 回退重 claim（见待评审②）。

**落点清单**：detail §5.1④ DDL 加列 + §7.6（判据改读 claim_k + 不可变声明）+ §8.4（claim 入参 k、重 claim 提示）+ §10.1（补 auto_fixed_k_default 键）+ §5.1⑧/§7.6 verify_run_record（可选 claim_k 快照）；solution §10.4（claim 行 + auto_fixed 判据措辞）+ §10.5（K 判据块）+ 修订记录 v3.5.5；phase2 §2.3①/§10 B-11 注记同步（"online 消费侧以 claim_k 为准，offline 零机制改动"）；环 2 补用例（并入 R-11）。版本：detail v1.5 / solution v3.5.5 / phase2 v0.6.2。

**评审记录（2026-09-07 用户拍板）**：
- ① **接受 K=1 为显式逃生门**：默认 K=2 不变，claim 人显式降 1；论据 = K=2 防不住复现失真/verifier 缺陷类单版误判（那部分由 R-10/R-12/reentry 兜），K=1 仅对低频 agent 开放。
- ② **改 K 窗口 = 零推进可降、推进后锁死**：K 序列尚无纯净 pass 时允许降 K（无历史包袱）；一旦首版 pass 入账即锁死至 claim 结束，防已攒序列验收标准被重释。
- ③ **动态提示 + 与 R-5 合并落**：表单不预填推荐值，按 agent 近期版本活跃度动态提示（"未观测到近期发版可考虑 K=1"）；数据源探测 = R-5 的版本活跃度查询，两者合并为同一基础设施（R-1 表单依赖登记入 R-5 范围）。
- R-1 待落字规格更新：§6 收敛终点、§5 不可变 → 改"零推进可降、推进后锁死"；claim 表单交互纳入 R-5 依赖。

### R-2（H2 → B1：纯净判据下钻 claimed case + 环境级 na 分流）— 设计 v0.1（2026-09-07）

**问题回顾**：error_regression run 按 agent 打包全部 active error case（多 cluster 一 run）。现行 R5"纯净可判 = 终态 ∧ `na_case==0`"（detail §7.6）是 **run 级一刀切**：任一 case 的技术 na 把整 run 标不纯净 → run 内**其它 cluster 的真实 pass** 也被转 needs_review(unclean_run)。na 本为 case 级信号，跨 cluster 污染成立。

**设计原则**：把"复现环境可靠吗"与"claimed case 自己有可判证据吗"分开。recheck 判据锚点从 run 改为 **claimed cluster 对应 case 在该 run 的行**；na 对 pass 的"污染力"按其 error_type 归为**环境级 vs case 级**两类（error_type 值域权威源 = phase2 §6.4 na 五源；na 行必带 error_type，只读面已够，offline 零机制）。

**na error_type → 可靠性影响域映射**（消费侧规格，落 detail §7.6；语义权威留在 phase2 §6.4，本表仅消费归类）：

| error_type（na 源） | 归类 | 对同 run 其它 case pass 的影响 |
|---|---|---|
| circuit_open / interface_disabled / scheduler_unexecuted（调度层未执行/回收） | **环境级** | 整 run 复现会话不可靠 → 他 case pass 存疑 → 触发 unclean_run |
| http_client_error / pool_error（出站连接/执行池） | 环境级（从严） | 同上（executor 到被测 agent 通道层失败，疑似 agent/环境整体） |
| timeout / connect / sse_parse / http / no_done / body_too_large（该 case 与 agent 的交互失败） | **case 级** | 只说明该 case 无证据，**不牵连**他 cluster 已跑通的 pass |
| missing_assertion / assertion_shape（判定素材缺失） | case 级 | 主路径已被 load 过滤前置，运行期仅防御；同左 |

**判定映射（claimed cluster X，在 run R）**：
1. X 行 = fail → reopen + K 清零（强证据，不变）。
2. X 行 = pass 且 R 无**环境级** na（不论有无 case 级 na）→ 计 K。
3. X 行 = pass 且 R 存在**环境级** na → 不 verify passed、转 needs_review(unclean_run)；不计 K 不清零（中断观察）。
4. X 行 = na（case 自身，任意 error_type）→ needs_review(reason=na)；不计 K 不清零。
5. X 缺行 → 无终值，轮询至 claim TTL（缺行≠na，不变）。

**与 R-1 正交**：claim_k 决定"连续几版"（R-1），本判据决定"每版何谓纯净可判"（R-2）——落字时同入 §7.6 auto-fixed 判据块。

**对既有裁定/载体的影响**：
- reason 值域 {na, unclean_run, reentry_same_version} 不变，但 **unclean_run 触发条件窄化**：从"na_case>0 的 run 内 pass 行"→"存在环境级 na 的 run 内 pass 行"。
- `needs_review_batch` 撞键裁定扩展：同 (run,error_type) 下若 cluster X 产 na 批、cluster Y 产 unclean_run 批 → 按原裁定并入**单条 unclean_run 批**（link_refs 引两 cluster，resolve 整批同动作）。语义上 X 的 na 并入 Y 的批是否可接受 → 待评审③。
- 运行级 `na_case` 读面保留（展示/审计/告警），不再直接作判据。

**评审记录（2026-09-07 用户拍板，① 由实现核对支撑）**：
- ① **B1 成立**（核对 offline 实现 text.py `KeywordNotContainsOp` + phase2 §7.1）：结构异常态（answer 缺失/None/非文本）全保守 fail → "环境降级误 pass"被挡；残留空串/纯空白 pass 缺口与 na 牵连正交 → 交 R-12 单列。
- ② **离线标注 + 无标注从严**：phase2 §6.4 矩阵加"影响域（环境/case）"列为离线权威标注；online 消费侧按标注走，无标注的新 error_type 默认从严（unclean）+ 告警。从严仅兜底非常态。
- ③ **na 退 batch 改单点**：unclean_run 批纯粹化 = 只承载"环境级 na 污染下 pass 行 cluster"；纯 na cluster 退 batch 走 cluster 级单点处置（reopen_cluster / escalated，或保持 claim 等下轮 error run 自然补判）。撞键裁定收窄（v1.4 撞键并入语义仅适用于多 unclean cluster，na 不再并入被无辜批量 reopen）。

**核对补记（2026-09-07 已核 offline 实现，回应待评审① verifier 空应答前提）**：
- **executor 成功语义**（phase2 §7.1 L349）：`error_type is None` → 成功 → 进 verifier；na 五源矩阵无"空输出"源 → 空应答落在 verifier 判。
- **verifier 实现**（`offline backend/app/assertions/ops/text.py` `KeywordNotContainsOp.run` + `path.py resolve`）：answer 键缺失 → KeyError → **fail（保守）**；answer 存在但 `None`/dict/list/数字等非 str → resolve 返回非 str → **fail（保守）**；answer 为 `str` 且空串/纯空白 → `hits` 空 → **pass（不保守）**。
- **结论**：① 的核心担忧场景——"同 run 他 case 环境降级 → 本 case 应答也是异常结构 → 被误判 pass"——**在结构层已被保守 fail 挡住**（缺失/None/非文本全 fail）；② 但残留一个真实缺口 = **空串/纯空白应答判 pass**，且它与"na 是否牵连"正交（即使 run 无任何 na，该 case 自身 executor 跑通 + 应答为空照样 pass）。该缺口是 **verifier 层独立缺陷**，不属于 R-2 case 级判据能力范围。
- **衍生修补建议（待评审，可能单列 R-12）**：`KeywordNotContainsOp` 对 strip 后空串/纯空白**保守 fail**（与 path 缺失/非文本 fail 同层，phase2 D2 分层守卫语义一致："输出结构异常谈不上修复生效"）→ 不新增 error_type、不改 executor 成功语义。**影响面：这是 offline 机制微改 + 共享算子**（普通 run 断言亦走该 op）→ 突破本批"offline 零机制改动"承诺、需单独界定，且需回归既有 keyword_contains/keyword_not_contains 金丝雀断言与 §11.1 单测矩阵（补"空串应答 fail"行）。若采纳：落 phase2 §7.2/§11.1 + offline 实现，不属纯 online 消费语义。

**落点清单**：detail §7.6（判定映射 + na error_type 归类表 + reason 触发窄化 + 撞键扩展）、§1.4/§12.1（unclean_run 触发描述同步）、§7.2/§5.1⑦b（batch 撞键注）；solution §10.5（判据块）+ §10.4；phase2 §2.3①/§6.4 注记（"na error_type 语义为权威源，消费侧按 claimed case+环境级归类判定，offline 零机制"）；环 2 场景（并入 R-11：无关 case 技术 na 隔离用例 + 环境级 na unclean 用例）。版本：detail v1.5 / solution v3.5.5 / phase2 v0.6.2。

### R-3（洪峰并发丢版本无重试锚）— 设计 v0.1（2026-09-07）

**问题回顾（核 phase2 §5.2/§5.3/§6.1 确认成立）**：洪峰收敛 = 内部创建器取 agent 行锁后查「该 agent 活跃（pending/running）error run ≥ 1 → 拒建」（v0.5.2 落点）。丢版本路径：v1 信号建 R1（running）期间 agent 发 v2/v3 并各自到终态 → 各自触发 maybe_auto_schedule → §5.2 per-(agent,version) 查 latest 均为 None → 进创建器 → **活跃闸拒建、fire-and-forget 无重试**。§5.3 补偿对账**只以「最新到达终态的 manual run」为锚**调一次 maybe_auto_schedule → 只查最新版本（v3）→ v3 由对账补建，**中间版本 v2 永久丢**（其版本号从未建 run，对账差集无此维度）。后果：claim fix_version=v2 → 回查空 → 静默 14d TTL reopen；且 **R-1 claim_k 跨版本序列依赖"每个 fix_version 版本都有 run"，丢版本直接使该判据空转**（不是缺行中断观察，是整版无 run 无判）。

**设计选项**：
- **方案 C（推荐）：活跃闸=1 保留，补偿对账从「单最新锚」升级为「版本差集补齐」**。对账按 agent 列出「已到终态的 manual/held_out distinct version」−「已有 error run 的 version」差集 → 对缺失版本**逐个补建**（每个缺版以该版最近终态 manual run 为锚记 trigger_signal_id，遵守活跃闸，一周期补 1 个，后续周期继续）。效果 = 丢的版本不再永久丢，延迟到对账周期逐步补齐（执行仍串行，总耗时与排队等价）；改动面小（§5.3 对账逻辑 + §5.2 措辞），执行并发闸/§6.2 槽池全不动。
- **方案 A'：解除建单活跃闸**（建单与执行解耦）——每 (agent,version) 独立建 run 全部入队，执行由 §6.2 per-agent 共享槽池串行；防无界积压设 per-agent 未终态 run 上限，超限丢最老未执行（诚实登记）。改动面大（§5.2 skip 规则 + 创建器闸 + 槽池交互），积压深度无自然上界需新上限。

**影响界定**：offline 机制改动（§5.3 对账），突破"offline 零机制"承诺 → 落 phase2（§5.2/§5.3/§10/修订记录）+ 环 2 补「洪峰 3 版连发 → 3 run 最终全建出、中间版 claim 可回查」用例。online 语义零改动（回查 B-1(b) 选取序已覆盖多 run）。若评审选 A' 则另补槽池积压上限语义。

**评审记录（2026-09-07 用户拍板）**：
- ① **采纳对账版本差集补齐（方案 C）**：保留活跃闸=1 与执行语义不动；补偿对账从「单最新锚」升级为「agent 已发版终态 manual distinct version − 已有 error run version」差集逐版本补建（遵守活跃闸，一周期补 1，缺版以该版最近终态 manual run 为锚记 trigger_signal_id）。中间版本从永久丢 → 延迟补齐。**落字前提（实施核对）**：对账差集查询须区分 manual/held_out 与 error_regression（后者不作信号），并显式排除 §5.2 已吸收（trigger_signal_id 命中）与坏终态重建范围（timeout/cancelled 版本号视为有 run，靠新信号重建逻辑），防差集与重建双路径冲突。
- ② 环 2 补「洪峰 3 版连发」用例（并入 R-11）；online 语义零改动确认。

### R-4（cap newest-active-first 饿死最老 case）— 设计 v0.1（2026-09-07）

**问题回顾（核 detail §6.2 L801-805 + phase2 §6.1 注1 + v0.6 注 L111）**：窗口（7d）内同键复发只 count+1、**不重生成 link** → 一个 cluster 的 case 在窗口期内保持同一 case；claim 后 user 等回归观察。高错误率 agent 持续激活**其它新错误**的 case（newest-active-first）→ 该 claimed 老 case 被挤出 cap 窗口 → 之后**每个 fix_version 版本 run 都不含该 case** → recheck 缺行 ≠ na → 轮询至 claim TTL → 回退 open → 用户重 claim → 又缺 → **每 14d 原地转圈**。此场景与 R-1（有 run 但 K 不够）正交：**case 根本不在 run 里，claim_k=1 也救不了**。v0.6 注 L111「R6 边界声明」已对"单次截断中断 K"拍板接受退化；R-4 是"高错误率下**永久**挤出"，超出该边界声明覆盖的退化成度。

**核心矛盾**：offline 侧无法感知 online 的 claim（回流单向拉 ack），**admission 保窗口无消费者**——register 登记归属"offline admission 兜底"在机制上不可行（无法区分哪个老 case 被 claim 盯）。真症结在 online 侧**欠测不可见**：case_truncated 只有溢出**计数**，online 不知道"缺行的 claimed case 是因 cap 溢出欠测、还是该版本就不该含它"。

**设计选项**：
- **方案 1（推荐，归属修订为 online 语义/可见性）**：offline platform 只读面把溢出**具体 case 列表**透出（case_truncated 从计数升级为 per-case 标记或 `excluded_case_ids`）；online 回查发现 claimed case 在 fix_version 版 run 中缺行且 ∈ 溢出列表 → 判「该版本窗口外欠测」→ claim 详情给可诊断状态「该 case 连续 N 版未纳入回归（cap 窗口外），非修复失败」→ 前端引导（admin 复核走人工 fixed，或提示该 agent 错误量需治理）。**不引入跨端保窗口**（尊重 v0.6 L111 拍板）。offline 只加只读面字段。
- **方案 2**：维持现状——视为已被 v0.6 注 L111「接受退化」覆盖，仅环 2 补用例，R-4 关闭为"已覆盖"。风险 = 高错误率 agent 的 claim 永远无法 auto-fixed，用户每 14d 手动重 claim 转圈仍静默。
- **方案 3（不推荐）**：打破跨端边界引入 claim case 保窗口（新消息通道，成本高，与 v0.6 L111 明示否决相悖）。

**评审记录（2026-09-07 用户拍板）**：
- ① **采纳方案 1 = 归属修订为 online 可见性 + 人工收敛**：offline 只读面把溢出具体 case 透出（case_truncated 计数 → per-case 标记或 excluded_case_ids）；online 回查发现 claimed case 缺行且 ∈ 溢出列表 → 判「该版本窗口外欠测」非修复失败 → claim 详情可诊断状态 + 前端引导（admin 人工 fixed / agent 错误量治理提示）。不引入跨端保窗口（尊重 v0.6 L111）。
- ② **落地拆分确认**：offline 改动 = platform 只读面加溢出 case 列表字段（新增只读、不改 run 语义）；online 改动 = §7.6/§8.7 回查欠测判定 + §9.3 UI 诊断文案 + §7.5 版本门控提示。环 2 用例随 R-11。
- ③ register 登记表归属列 R-4 由「offline admission 兜底」修订为「online 语义/可见性 + offline 只读面透出」。

### R-5（fix_version 三方相等无硬校验）— 设计 v0.1（2026-09-07）

**问题回顾**：claim fix_version 自由文本、共享版本字面量域只约束"非空 ≤64 无空白/控制字符"（detail §8.4/phase2 §2.4）——人手输入 ≠ agent 自报（大小写/v 前缀/尾随空格/`r47`vs`47`）在字面量域内合法但不等值 → offline 该版本永不建 run → 空回查静默 14d TTL。B-5 已落"表单候选提示/归一化"文本但无数据源；detail v1.5 §9.3 已挂「版本活跃度动态提示（数据源 R-5）」指针（R-1 评审③ 合并落地）。数据源缺口 = offline manual/held_out run 的版本清单 online 侧**当前不可读**（D19 pull/回查均为 error-run 维度）。

**设计**：
1. **数据源（新只读读面）**：offline 补「agent 已见版本列表」读面（manual/held_out runs distinct version + 最近终态时间），只读不改 run 语义 → online claim 表单实时/缓存查询。
2. **归一化（提交前）**：trim + 大小写/v 前缀提示（不改存储值语义，共享域仍字符串相等判定）。
3. **软校验（推荐，非硬拦）**：claim 提交时若 fix_version ∉ 该 agent 已见版本 → **告警确认**（「未观测到该 agent 该版本评测 run——可能未发版或字面量不匹配，已见版本：…」），确认后才提交——不硬拦因合法场景存在（修复版本 = 正在跑尚未终态的首版 / 对账周期滞后）。
4. **版本活跃度提示**：按该 agent 90d 版本数/发版间隔动态提示 K 建议与「近期无发版考虑 K=1」（R-1③ 数据源复用）。
5. claim 后 recheck 无 run 期前端持续显示「待 <version> 回归 run」+ 版本活跃度（避免静默）。

**影响界定**：offline 新增只读 API（机制新增但不改 run/判定语义）；online detail §8.4/§7.5/§9.3 + solution §10.4 交互层。硬校验（fix_version ∉ 已见 → 400）作为更严备选——需豁免机制防误拦首版。

**评审记录（2026-09-07 用户拍板）**：
- ① **采纳「软校验+新读面」**：offline 新增只读读面 = agent 已见版本列表（manual/held_out runs distinct version + 最近终态时间，只读不改 run 语义）；claim 提交前 trim + 大小写/v 前缀归一提示；fix_version ∉ 已见版本 → **告警确认**（展示已见版本，确认后才提交，非硬拦——豁免首版修复尚未终态/对账周期滞后合法场景）；claim 后 recheck 空窗期前端持续显示「待 <version> 回归 run」+ 版本活跃度。
- ② **与 R-1③ 合并**：版本活跃度动态 K 提示数据源 = 本读面同一基础设施（detail §9.3 指针兑现），表单不预填推荐值。
- ③ **落字范围**：offline 只读 API（机制新增、不改 run/判定语义）；online detail §8.4（claim 告警交互）/§7.5/§9.3 + solution §10.4 交互层。环 2 用例并入 R-11。状态登记表归属列维持「online 交互/告警」，补「offline 只读面（数据源）」。

### R-6（err_summary_json 未钉 error_type 原值 schema）— 设计 v0.1（2026-09-07）

### R-6（err_summary_json 未钉 error_type 原值 schema）— 设计 v0.1（2026-09-07）

**问题回顾（核 detail §4.3 L440 + DDL L681）**：err_summary_json 字段注释 =「子节点 error 汇总（error_type 分类计数、error_msg 脱敏、agent_version）」——措辞"error_type 分类"未钉死**存原值还是 L1/L2 分类键**。§6.2 去重与 §7.5 reentry 观察键 = error_type **原值**（L794 实现约定"按原值去重，不跨类合并"）→ 若 err_summary 内子节点 error_type 误存分类键（或未来消费 err_summary 做聚合/原值还原），与去重键粒度漂移 → 聚类键不一致的静默错。

**设计（纯 schema 钉死，实现前钉死点）**：
1. **err_summary_json 字段级 schema 钉死**（detail §4.3/§5.1⑩ DDL 注释）：条目数组，每条 = `{error_type: <原值枚举，与 §5.1⑤ error_cluster.error_type 同值域，禁 L1/L2 分类键>, error_msg: <脱敏 ≤512>, count}` + 顶层 agent_version；L2 判定/聚合消费 err_summary 一律按原值分组还原。
2. **一致性登记**：err_summary 的 error_type 原值与 §6.2/§7.5 去重键、phase2 §6.4 na 影响域标注同域（R-2 权威源引用）。
3. **环 2 用例**：子节点 error_type 原值经 err_summary → 聚类/影响域归类按原值命中（防分类键污染回归用例）。

**影响界定**：online detail 文档修订（schema 规格 + 注释）+ 环 2；offline 零机制改动（err_summary 为 online 消费侧字段）。

**评审记录（2026-09-07 用户拍板）**：
- ① **采纳「钉死 schema 原值域」**：err_summary_json 条目钉死 = `{error_type: <原值枚举，与 §5.1⑤ error_cluster.error_type 同值域，禁 L1/L2 分类键>, error_msg: <脱敏 ≤512>, count}`，顶层 agent_version。L2 判定/聚合消费一律按原值分组，禁以 err_summary 做聚类去重源（去重/观察键 = 根级 error_type 原值，§6.2 L794 口径）。
- ② **落字范围与时点**：detail §4.3/§5.1⑩/DDL L681 注释修订 + 环 2 原值还原用例；offline 零机制。属「实现前钉死点」——拍板后不独立占版本，随后续 detail 修订批次一并落字。
- ③ 一致性登记：err_summary error_type 原值域与 §6.2/§7.5 去重键、phase2 §6.4 na 影响域标注同域（引用 R-2 权威源）。

### R-7（online_content_gap 无批量自愈）— 设计 v0.1（2026-09-07）

**问题回顾**：payload 因 online 现场内容缺被驳回 invalidated（reason=online_content_gap、detail 指明缺项，detail §7.4 L904）后归 online admin 重推恢复（detail §7.4 L900-902 单条 requeue）。admin 修正现场（补字段/补词表 `no_fallback_config`）后需逐 link 手工 requeue——高错误率 agent 成批 invalidated 时无批量入口；且「requeue 不愈」类（phase1 §6.3 L320-323 版本不识别）无标注会误导 admin 反复重推；空词表类（phase1 L317-319 空词表 fail-closed → content_gap）补齐即愈，但工具不区分可愈性。

**设计（online 批量工具）**：
1. **批量 requeue**：回流聚类 invalidated 视图筛选 `offline_status=invalidated + invalidate_reason=online_content_gap`（可按 agent/缺项过滤）→ admin 勾选 → 批量 requeue（每行复用 §7.4 守卫：cluster 非 inactive；防抖 ≤N/min）→ 逐行结果（requeued / skipped+原因）。
2. **可愈性标注**：按 reject_detail 缺项区分「补齐+重推可愈」（字段缺/词表空）vs「requeue 不愈」（版本不识别，phase1 §6.3 L322）→ 批量列表列示，不愈行默认不可勾选（强制确认才放行），防无效反复重推。
3. **前端/审计**：invalidated 列表「批量重推」动作 + 结果回显；conversion_record 记批量操作（actor、筛选条件、逐行结果）。

**影响界定**：online 改动（detail §7.4/§8.4 + §9.3 UI + solution §10.4/§12.1）；offline 零机制（§6.5 L359 重处理逐 payload 天然支持批量重拉）。环 2 补「批量 requeue → 逐行重拉建 case」用例（随 R-11）。备选 B = 仅批量端点不加可愈性标注（更轻但留误推入口）；备选 C = 定时自动 requeue job（配置补齐后自愈）——自动重推时机不可控（未补齐即重推 → 再 invalidated 循环），不推荐。

**评审记录（2026-09-07 用户拍板）**：
- ① **采纳批量端点 + 可愈性标注**。落字范围：detail §7.4（批量 requeue + 逐行 §7.4 守卫复用 + 防抖）、§8.4（新批量端点返回 per-row 结果）、§9.3（invalidated 筛选/批量重推/结果回显 UI）；solution §10.4/§12.1 权威同步。
- ② 可愈性标注数据源 = `invalidate_reason/reject_detail` 缺项：空词表/字段缺 → 可愈可勾；「版本不识别」→ 不愈行默认禁勾、强确认才放行（复用 phase1 §6.3 L322 区分语义，避免误导 admin 反复重推）。
- ③ 环 2 补「批量 requeue → 逐行重拉重处理建 case」用例（随 R-11）；offline 零机制确认。

### R-8（cap_gap 自愈对已 acked 闭环行重发无效 invalidated ack）— 设计 v0.1（2026-09-07）

**问题回顾**：phase1 §6.5 L355 cap_gap 自愈每小时扫 `status='rejected'+reject_code='offline_cap_gap'` 行 → 先复位 ack_status='none' → 重跑自检+映射；判据 L359「status='rejected'（ack_status 任意，含已 acked 的 invalidated 闭环）→ 重处理」→ **已 acked 闭环**（远端已收 invalidated）的行在映射持续缺期间每小时重复：复位 → 重跑仍缺 → 再发 invalidated ack → online 幂等 200 → 纯噪音出站 + 无意义日志。不能简单「跳过已 acked」——L355「agent 接入补齐后自动恢复」恰恰依赖这些行持续被探测。

**设计（offline 节流；语义 = invalidated ack 只通知一次 + 本地探测补齐）**：
1. cap_gap 行首次 reject ack 成功后进入**「等待接入」探测态**：每小时自愈只做本地重跑（inbox 留档 envelope 重自检+映射，先不落库不 ack）；**补齐（通过）→ 建 case + 发 ack active**（复用 payload_id，契约 R2 `invalidated(offline_cap_gap)→active`）；**仍缺 → 静默等下轮：不复位 ack_status、不重发 invalidated**。
2. **收窄 §6.5 L359 判据**：「status='rejected' → 重处理」仅适用于 ack_status ∈ {none, pending}（首次/对账未闭环需重发）或收到 requeue/内容刷新（online_content_gap 重拉覆盖 envelope）的行；已 acked 的 cap_gap 行走上探测路径。
3. manual_invalidate（§6.5 L363）与 requeue 重处理语义不变（它们各自有新的 ack 要发）。

**影响界定**：offline 机制微改（§6.5 自愈流程 + §6.4 对账范围注记），online 契约零改动（幂等已兜底）；环 2 补「映射缺期间无重复 invalidated 出站、补齐后单次 active」断言用例（随 R-11）。**属现稿行为修正（削无效重发）→ 与 R-3/R-12 同类，需 register 机制改动单独立项。** 备选 B = 维持现稿每轮重发（online 幂等兜底、零改动）——接受无效出站噪音，R-8 降级为登记观察项；备选 C = 改事件触发（agent 接入补齐时人工/注册事件触发重扫、去每小时探测）——丢失 L355「无 online 干预自动恢复」，不推荐。

**评审记录（2026-09-07 用户拍板）**：
- ① **采纳探测态节流**：cap_gap 行 invalidated ack 只发一次（首次 reject 闭环到远端）；成功后进「等待接入」探测态——每小时仅本地重跑 envelope 自检+映射，补齐（通过）→ 建 case + 发 ack active（复用 payload_id，契约 R2）；仍缺 → 静默等轮（不复位 ack_status、不重发 invalidated）。收窄 §6.5 L359「status='rejected' → 重处理」适用范围至 ack_status ∈ {none, pending}（首次/对账未闭环）或收到 requeue/内容刷新（online_content_gap 覆盖 envelope）；已 acked 的 cap_gap 行走探测路径。manual_invalidate 与 requeue 重处理语义不变。
- ② **register 机制改动单独立项**：R-8 = offline 现稿行为修正（削无效重发）→ 与 R-3（对账差集）/R-12（共享算子）同类，代码变更单独立项，本稿仅决策登记。
- ③ 落字范围：offline phase1 §6.4/§6.5 判据与自愈流程注记；online 契约零改动（幂等已兜底）；环 2 补「映射缺期间无重复 invalidated 出站、补齐后单次 active」断言用例（随 R-11）。

### R-9（needs_review_batch 整批 resolve 与 TTL/状态漂移并发 CAS）— 设计 v0.1（2026-09-07）

**问题回顾**：batch resolve 语义 = 整批同动作单事务，`reopen_cluster` 对引用各 cluster CAS `claim→open`，处置**前提 = 引用各 cluster 保持 claim**（§7.6 L946/L1024）。但 claim 生命周期有并发漂移源：claim_ttl_job 超窗自动回退 open（§1.3 10min 周期，L922/L1167）、回归 failed 回退 open（L969）。batch 自聚合生成到 admin resolve 天然跨 ≥10min → 期间任一引用 cluster 被 TTL/回归 failed 回退 open → 事务内 CAS claim→open 条件不满足 → **整批回滚**，resolve 无果；重试时引用集合状态继续漂移 → 重试语义未定义（反复回滚死循环风险；或与「整批原子」语义矛盾——漂移 cluster 其实已自然达成 open 目标）。

**设计（online 并发语义修订；目标 = 消除非 claim 引用 cluster 导致整批失败）**：
1. **语义化跳过非 claim 引用 cluster**：resolve(reopen_cluster) 事务内逐引用 cluster CAS `claim→open`；CAS 失败 → 读当前 status 分流：已 open（TTL/回归 failed 自然回退）→ **目标态已达成，计 `skipped_already_open` 幂等跳过**（非部分处置——处置目标「该错不再被 claim 锁死」已达成）；fixed（极端：K 满 auto-fixed 提前收敛）→ 计 `skipped_fixed`（错误确已修，不再 reopen）；其余不可预期态 → 该 cluster 不处置、返回明细待人工复核。批整体仍置 resolved，conversion_record 记逐 cluster 结果。
2. **重试语义**：幂等安全（已处置 cluster 重放幂等/批已 resolved 409）；前端结果面板展示 skipped 明细，供人工核实「自然回退是否需再 claim」。
3. **保留整批同动作、单事务提交 + 批级 CAS**（status open→resolved 防双 admin 并发处置，后到者 409）；仅放宽「引用 cluster 必须保持 claim」硬前提为「到达 open 即计成功」。

**影响界定**：online 语义修订（detail §7.6 处置语义 blockquote + §8.4 端点响应/重试说明 + §9.3 前端结果展示 + 环 2 并发用例：batch 聚合后 TTL 先回退 → resolve 返回 skipped、不整批失败）；offline 零机制。备选 B = 维持整批强原子（任一引用非 claim → 整批回滚 + 提示刷新重试）——并发窗口仍在、admin 需撞运重试，不推荐。

**评审记录（2026-09-07 用户拍板）**：
- ① **采纳语义化跳过非 claim 引用 cluster**：resolve(reopen_cluster) 事务内逐引用 cluster CAS `claim→open`；CAS 失败读当前态分流——已 open（TTL/回归 failed 自然回退）→ `skipped_already_open`（目标态已达成，幂等跳过，非部分处置）；fixed（K 满提前收敛）→ `skipped_fixed`（错误确已修不再 reopen）；其余不可预期态 → 不处置返回明细待人工。批整体单事务置 resolved；conversion_record 记逐 cluster 结果（reopened / skipped_already_open / skipped_fixed / manual_review）。
- ② **重试与并发**：幂等安全（已处置 cluster 重放幂等、批已 resolved → 409）；批级 CAS（open→resolved）保留防双 admin 并发；§8.4 端点返回 per-cluster 明细供前端结果面板展示，skipped 项供人工核实「自然回退是否需再 claim」。
- ③ 落字范围：detail §7.6 处置语义 blockquote（前提「引用 cluster 保持 claim」放宽为「到达 open 即计成功」）+ §8.4 端点响应/重试 + §9.3 前端 + solution §10.x 权威同步；环 2 并发用例（batch 聚合后 TTL 先回退 → resolve 返回 skipped、不整批失败）随 R-11；offline 零机制确认。

### R-10（复现 input 截断/归一保真）— 设计 v0.1（2026-09-07）

**问题回顾**：error_cluster.input_snapshot = 代表 input 实文**脱敏+截断 ≤8K**（detail §5.1 L552），组装复现输入取 input_snapshot（L814）；input_hash = sha256(normalize)，normalize = strip+折叠空白+**截断 4096**（L551）→ 去重/观察键粒度 4K < 复现输入上限 8K。保真缺口：① 原始 input >8K → 复现输入截断 → **尾段依赖型错误**（触发依赖 8K 之后内容）复现 run 无错 → verifier pass → 纯净 run + K 攒满 → **假 auto-fixed**；② hash 归一截断 4096 → 「4096 前缀相同、尾部不同」的长输入 hash 碰撞并入同 cluster → 代表快照错配。phase1 无超长 fail 分支（§2.1 evidence.input ≤8K 必填；L574 仅登记超长单测）→ offline 拿到的 input 即截断后实文、无原始长度感知。

**设计（online 消费降级为主 + offline 边界行为确认）**：
1. **截断感知**：组装/落库时判 `len(原始 input) > 8K` → link/payload 显式标 `input_truncated`（【实现前钉死点】DDL；不用 input_snapshot 实长 8K 逼近——恰好 8192 未截断边界不可靠）；error run 复现输入源随带截断标记。
2. **auto-fixed 判据禁用截断证据**：claimed case 关联 run 带截断标记 → 该版 run 结果**不计 K 不置 verify passed**（复现输入 ≠ 真错误输入 → 终值不可信）→ 转 needs_review（**reason 值域 {na, unclean_run, reentry_same_version} 3→4 增 `input_truncated`**，claim 级单条走 cluster 级单点 needs-review-resolve、不产批，同 reentry_same_version 通道）→ claim 详情 UI 提示「input 超长截断、复现证据不完整：建议人工复核或让 agent 出小输入版本后重 claim」；后续小输入纯净版本仍可正常攒 K auto-fixed。
3. **hash 归一上限对齐**：normalize 截断 4096 → 对齐复现输入截断上限（≥8K 或全量 hash），消除去重粒度 < 复现粒度的键/快照漂移。
4. **环 2 边界行为确认**（phase2 注记）：error run 对截断输入复现 pass = verifier **如实判 pass**（na 语义不符——na 是 infra 判不了，此处判定能且如实）；「截断 → 假 auto-fixed」防护在 online 消费侧（上 2）。phase1 §2.1 增注：evidence.input ≤8K 为 envelope 约定、截断由 online 源头执行并带标记，offline 不截断不改写。

**影响界定**：online 语义 + reason 值域扩展 + 组装/DDL 标记（实现前钉死点）；offline 零机制（仅 phase1/phase2 边界注记 + 环 2 用例随 R-11）。备选 B = 截断证据照常计入 auto-fixed（风险接受靠人工复看）——假 fixed 风险留给 K-TTL 收敛后 reopen，不推荐；备选 C = input_snapshot 全量存不截断（扩大字段）——违背 ≤8K 设计、payload 膨胀，不推荐。

**评审记录（2026-09-07 用户拍板）**：
- ① **采纳标记 + 判据禁用 + 新 reason `input_truncated`**：组装/落库判 `len(原始 input)>8K` → link/payload 显式标 `input_truncated`（【实现前钉死点】DDL 加列，不用实长 8K 逼近）；claimed case 关联 run 带截断标记 → 该版结果不计 K 不置 verify passed → 转 needs_review(reason=`input_truncated`，claim 级单条、不产批、走 cluster 级单点同 reentry 通道) + UI 提示「input 超长截断、复现证据不完整：建议人工复核或 agent 出小输入版本后重 claim」；后续小输入纯净版正常攒 K。
- ② **reason 值域 3→4 扩展**：{na, unclean_run, reentry_same_version} + `input_truncated`（v1.5 R-2 钉死值域的有意扩展，随 R-10 落字同步 §5.1⑦/§7.6 reason 注与 phase2 §6.4/§11 对应口径）。
- ③ **hash 归一上限对齐**：normalize 截断 4096 → 对齐复现输入截断上限（≥8K 或全量 sha256），消除去重粒度 < 复现粒度的键/快照漂移（detail §5.1 DDL input_hash 注释 + §6.2 去重键口径）。
- ④ 落字范围：online detail（§5.1④ input_snapshot/input_hash 注 + DDL + §7.6 判据 blockquote + §9.3 UI + §8.4 needs-review）+ solution §10.x 同步；offline 仅 phase1 §2.1 / phase2 §11.2 边界注记（error run 对截断输入复现 pass = verifier 如实判 pass，na 语义不符；防护在 online 消费侧）；环 2 用例（长输入尾依赖错误 → 复现 pass 带标 → 不 auto-fixed 转 needs_review）随 R-11。offline 零机制确认。

---

### A 类修复记录（H7-1~H7-7 + H7-20：第二轮推演 wire/consistency 缺陷，2026-09-07 已落地、不升版本）

> 用户裁决「**A 类先修，B/C 立项评审**」。A 类 = 已拍板机制（R-1~R-12 落字稿）内的表述矛盾/载体缺口，不改变已拍板语义，四文档现行版内直接修补共 **13 edits**（detail v1.6 7 处 + solution v3.5.6 2 处 + phase2 v0.7 2 处 + phase1 v0.2.1 2 处）。

| ID | 缺陷 | 修补落点 |
|---|---|---|
| H7-1 | input_truncated 判定时点矛盾：组装点仅见 ≤8K 截断快照，判不了原始 `len(input)>8K` | detail v1.6 §5.1④ error_cluster 列注 + §6.2 注「判定时点 = cluster 首现落快照/窗口内回填时判打点原始 input，勿在组装判」；solution v3.5.6 §7.2 同句联动修正 |
| H7-2 | §7.6 state-machine 表未接入 input_truncated（reason 4 值新条目缺迁移/聚合口径） | detail v1.6 §7.6 claim-row → needs_review transition 注 + needs_review row reason 值域注（四类含 input_truncated、claim 级单条不产批） |
| H7-3 | §6.2 normalize 截断残留 4096（R-10 已 4096→8192，此处漏改） | detail v1.6 §6.2 normalize 截断注对齐 8192 |
| H7-4 | error_case_link / D19 envelope 缺 input_truncated carrier（仅 cluster 列有标记，link/payload 无透传） | detail v1.6 §5.1④ error_case_link DDL 增列（置 fix_version 后）+ §7.1 envelope 表增字段行（组装自 cluster 列复制随 link 透传；offline 只读上下文、判定仍如实）；solution v3.5.6 §7.2 联动 |
| H7-5 | detail §8.7 vs phase2 §9.3 read-face 字段清单不一致（case_truncated_count + window_days 缺） | phase2 v0.7 §9.3 R-5 读面补 `case_truncated_count` 聚合 + `window_days` 入参，对齐 detail v1.6 §8.7 |
| H7-6 | trace_judge_state.root_input_hash 注释为孤儿 HMAC 标注（与 error_cluster.input_hash 同算法事实不符） | detail v1.6 L682 注释改「判重键 = sha256(normalize(input))，与 error_cluster.input_hash 同算法」 |
| H7-7 | 双规范残留：phase2 §5.3 正文单锚语义未被 R-3 差集取代；phase1 §6.5 old-loop 判据未收窄（R-8 修订仅 phase2 注记，phase1 正文仍旧语义） | phase2 v0.7 §5.3 标注「历史基线、实施以 R-3 差集块为准」；phase1 §6.5 判据行 + §5.2 复位规则加 R-8 inline 修订注（判据收窄 `ack_status∈{none,pending}`、已 acked invalidated 不复位/不重发、进探测态）；phase1 正文 = v0.2.1 历史语义不动、code 随单独立项落 |
| H7-20 | solution §10.2「会话上下文摘要归一」残留（v1 不采集该摘要，v3.4 时代残留） | solution v3.5.6 §10.2 该句改为「v1 无会话上下文摘要，摘要归一属二期」（归入本轮直接修补） |

### R-13~R-24（第二轮推演 B/C + 低危项，recorded 待评审，2026-09-07）

> 来源：R-1~R-12 全部 landed 的新基线上第二轮双端整链推演。其中 **R-18/R-19**（C 类高危 2 条）已评审 v0.1 → 用户拍板方案 A → 落字 landed（见下两节）；**R-13~R-17**（B 类 5 条）已评审 v0.1 → 用户逐条拍板 → **landed**（2026-09-07：detail v1.8 + solution v3.5.8，落点见评审记录区 R-13~R-17 节）；**R-20~R-24**（C/低危 5 条）已评审 v0.1 → 2026-09-07 用户逐条拍板 → **approved**（方向见登记表 R-20~R-24 行「已拍板方向」列；R-20 pre-scan 门禁立项 / R-21 root-late 补判通道 / R-22 收尾回填 na 钉死 / R-23 timeout 三层分界 / R-24 requeue guard 精确化），落字目标 detail v1.9 + solution v3.5.9 + phase2 v0.7.2（待批）。

- **R-13（B，H7-8）** input_truncated 无清理/更新机制：标记只置不清，一次截断（agent 该时输入超 8K）→ claimed case 关联 run 永久不计 K、escape 提示不可达，后续同 case 小输入纯净版本也走不出死区。待评审：标记可否随「后续小输入纯净证据」解除/覆盖（cluster 首现截断 vs claim 观察窗内逐 run 判定分层）。
- **R-14（B，H7-9）** unclean_run 载体状态模型双写：needs_review_batch link_refs 引 pass case（保持 claim、不落 needs_review 态）vs state-machine 表 needs_review 行——claim 与批引 case 同体时两处状态口径未统一。
- **R-15（B，H7-10）** input_truncated × unclean_run 双通道无优先级/互斥：同 run 同时带截断证据 + 环境级 na → reason 取哪个、走批还是 claim 级单点，排他规则未定义。
- **R-16（B，H7-11）** R-4 窗口外欠测核对无自动 fetch path：excluded_case_ids 附着于 offline run（case_id-query 不可达——查询按 claims 建索引），核对断链。待评审：读面查询键扩展 or 结果落独立诊断表。
- **R-17（B，H7-12）** R-3 差集迟到补建 × K sequence continuity：某版本 run 在 K 观察窗内**迟到补建**（差集对账后补，K 已攒至该版本号）——补建结果是否计入/重排既有 K 序列 → false-fixed window。待评审：版本连续性对迟到补建 run 的计入规则。
- **R-18（C，H7-13，高危）** input 明文无 persistence carrier：消费 step4 只落 root_input_hash，error_cluster 快照与截断判定的**原始 input 取数点缺定义**（组装链路来源悬空）。
- **R-19（C，H7-14，高危）** error_type 长短名字面量不一致：offline executor 常量长名 `connect_error/sse_parse_error/http_error/http_client_error/pool_error`（已读 executor.py L1-40 实证）vs 文档/领域短名 `connect/sse_parse/http/...` → 消费侧分类 key miss → 误判路径 / unclean 风暴。
- **R-20（C，H7-15）** R-12 shared-op 收紧（strip 后空串→fail）缺 pre-scan owner：现网既有空字段断言依赖未扫；且普通 run 空答 fail 与 leakage-recurrence（agent 空话术）判定混淆风险。
- **R-21（C，H7-16）** 残 trace 且 root 迟到：trace 不完整 + root error 晚到时 L2 归因/聚类分支漏分类（现 L2 假设 trace 完整）。
- **R-22（低危，H7-17）** non-scanner 来源 na 行回填 error_type 未定义：na 载体聚合键 `run_id+error_type` 对非 scanner 判定来源（如 executor 直标）断链。
- **R-23（低危，H7-18）** run-timeout 文案/语义张力：timeout 在 §6.4 源矩阵 vs §7.6 reason 聚合间的边界表述不一致风险（技术 na 不牵连 vs 超时中止整体语义）。
- **R-24（低危，H7-19）** requeue-guard 不交叉 claim lifecycle：guard（幂等/并发守卫）不感知 claim 推进状态，rescan/requeue 与 claim 处置并发时缺交叉语义。

---

### R-13~R-17（H7-8~H7-12 B 类 5 条）— 评审 v0.1 → 落字（2026-09-07）

**逐条评审 → 用户拍板（2026-09-07，方案详见登记表 R-13~R-17 行「已拍板方向」列）**：
- **R-13 → 判定位窗口化（复用 `input_truncated` 列、单 trace 即刷）**：列语义从「cluster 首现截断一次置位」改「**当前判定态**」——消费 step4 同键新 trace 开簇/回填复制时以新判定态刷新（≤8K 清 0、>8K 置 1），已 closed cluster 不刷新（终态只读不翻案）；截断历史留 needs_review(input_truncated) 产物 + 详情警示不抹。子决策 = 单 trace 即刷（不攒批、不待同簇回填）。
- **R-14 → A' 口径归一 + 挂起标注派生**：unclean_run = 存疑非否定——只经 batch 载体处置、**cluster 不入 needs_review 态**（状态机表 claim 迁移 reason 剔除 unclean_run、needs_review 态 reason 注「本态不驻」）；批引 cluster 保持 claim、cluster 详情/列表实时派生「被未决批 Bx 挂起」标注（join 未 resolved 批 link_refs、免加列）；**TTL 不豁免**沿用既有兜底（批引用 = 不纯净中断观察、到期自然回退 open、批 resolve 时 R-9 skipped_already_open 幂等覆盖）。
- **R-15 → input_truncated 优先（纵向个案治本 > 横向批量归因）**：同 run 双条件（截断 + 环境级 na）同现 → 该 cluster 走截断单条通道、**不并入 unclean_run 批**（批 link_refs 排除自身 input_truncated=1 的 cluster）；同 run 其余无截断 pass cluster 照常走批；reason=input_truncated + note 附「同版 run 含环境级 na」。
- **R-16 → 缺行诊断自动消费 excluded 读面**：detail §7.6 v1.6①「UI 引导人工离线核对」升级自动——recheck 判缺行 → 自动 GET runs?agent=&version= → case_id ∈ excluded_case_ids → 自动标「窗口外欠测（cap 挤出、非修复失败）」沿用现语义（不自动 reopen/不进 needs_review）；∉ 维持人工兜底引导；excluded_case_ids 落 runs list 每行 / detail 位置 = **Phase B 实现核对项**。
- **R-17 → K 序列版本锚 = R-5 versions 读面（agent 发版拓扑权威）**：候选版本序列定义——recheck 以 GET versions（window_days 覆盖 claim TTL 14d）取 ≥ fix_version 全版本序逐版：versions 有该版且 error run 有终值 → 判 K；versions 有该版但无 error run → **缺行中断**（下一可见 error run 不续缺环，杜绝 v1+v3 丢中间版假连续 false-fixed）；迟到补建终态到达后补判推进。根因 = 版本连续性缺权威锚（非迟到补建计入）；versions 端点用途从「claim 表单提示」升级「**K 判据序列源**」（recheck 每轮多一次 RPC）；offline 零新机制（versions 读面 R-5 已在）。

**落字（2026-09-07）**：detail **v1.8**（header + 修订记录 + §5.1④ error_cluster.input_truncated 列语义注「当前判定态、单 trace 即刷、closed 不刷新」+ §6.2 窗口行刷新语义 + §7.6 状态机表 claim 迁移 reason 剔除 unclean_run + §7.6 判定语义 v1.8 blockquote 五条 ①~⑤ + §5.1⑦b needs_review_batch 注（挂起派生 + link_refs 排除截断 cluster）+ §9.3 聚类详情 input_truncated 当前判定态警示 + 被未决批挂起徽标 + §8.7 runs 行 excluded_case_ids 响应 / versions 行用途升级 + §14 E-23~E-27 用例）+ solution **v3.5.8**（header + 修订记录 + §10.4 needs_review 段 R-14/R-15 句 + 状态机表 claim 迁移行 reason 剔除 + needs_review 行 reason 注 + §10.5 缺行 bullet R-16 / K 判据 R-17 versions 锚 / input 截断行 R-13+R-15）。**offline 零机制**——phase2 保持 **v0.7.1** 不动。**Phase B 实现核对项**：R-13 §6.2 同簇回填刷新复制（online 机制代码）、R-16 excluded_case_ids 落 runs list 每行/detail 字段位置。**状态：recorded → designed → reviewed → approved → landed（detail v1.8 + solution v3.5.8）。**

---

### R-18（H7-13 → input 明文载体真空）— 评审 v0.1（2026-09-07）

**问题回顾（原文实证，严重度比登记升一级：不是「诊断信息缺源」，是「组装主链路明文载体真空」）**：
- `trace_judge_state` DDL（detail §5.1⑩，L674-694）逐列核对：判定态只持久 `root_input_hash`（sha256(normalize(input))，L683）、`err_summary_json`（子节点 error 汇总，非明文）、`judgement_json`（layer/candidate/input_hash，非明文）——**无任何 input 明文列**。
- 明文消费流 = §4.3 消费 worker 累积 trace（内存持原始 input → 算 hash 落库）→ judge_scan_job（§6.1，判定）→ cluster_job（§6.2，聚类）→ assemble_job（§6.3，组装）。**判定态之后明文已失**：聚类开 cluster 需「该 trace request.input」落代表快照（§6.2 L804）、窗口回填需明文（L805）、组装取 `error_cluster.input_snapshot`（§6.3 L817，注释「组装取数源，不依赖 ES 回读」v3.5.1）——明文跨 job 交接点 = trace_judge_state 表，但该表无明文。
- 链路同时多声明「**不依赖 ES 回读**」（§6 intro L774 + L553 列注）→ 现实收尾二选一：a) input_snapshot 恒 NULL → §6.3「快照缺 input 实文 → 只计数不组装」→ **error 回流闭环整体不产 D19、offline 无回归，链路静默死**；b) 实现违规回读 ES（背 v3.5.1 承诺、ES ILM 30d/重读）。
- **与 H7-1 判定点矛盾**：H7-1 落字「判定时点 = cluster 首现落快照/窗口内回填时判打点原始 input>8K」——但原始 input 明文在聚类（cluster 首现方）不存在，其仅见判定态；原始 `len(input)>8K` 的判定能力**只在判定 worker 消费原始事件的进程内存**。根因 = 明文持久载体缺列 + input_truncated 判定点落错 job。

**设计（方案 A：判定 worker 单点落明文快照 carrier，聚类/组装引用，全链无 ES）**：
1. `trace_judge_state` 增列 `input_snapshot_clean MEDIUMTEXT NULL`（root request.input 脱敏截断 ≤8K 明文快照）+ `input_truncated TINYINT NOT NULL DEFAULT 0`（原始 len>8192 置 1）——由 **§4.1 consumer 流水线 step4（root 到达更新累积态、算 `root_input_hash` 同刻，唯一见原始 input 明文处）** 落库（§4.3 L442「root 到达 → 记 request ts/interface/status/input_hash」步骤扩展）；judge_scan_job 判定后置、仅见表行不见明文，非落点（自审修正：初稿误写 judge_scan_job，消费 step4 才算 hash 才是明文持有点）。H7-1 判定点同步精确化为「**消费 step4 root 到达判截断落明文快照**」（聚类开 cluster 仅复制判定态列不再判——本轮 H7-1 落字「cluster 首现判」仍见不到原始明文，措辞随 R-18 落字时再下钻到 step4）。
2. §6.2 开 cluster / 窗口回填：`error_cluster.input_snapshot` 与 `input_truncated` 自该 trace 判定态列**复制**（同源 → 与 H7-4 link 透传口径天然一致）；判定态列 NULL（残 trace 无 request 根）→ 保持「只计数不组装」。
3. §6.3 组装不变（仍取 cluster.input_snapshot）；D19 evidence.input 来源不变。整链无 ES 回读、无第二 topic。
4. 落字边界：online 机制改动（判定态新列 + **消费 step4** 快照/截断逻辑 + 聚类取数改自判定态列）→ detail 版本推进 + 实现前钉死点照落；offline **零改动**（offline 只消费 D19，不感知来源变更）。

**评审**：① 载体收敛到判定态单列、判定点收敛到唯一见原始明文 job，H7-1/H7-4 与本节自洽闭环；② 备选 B = 聚类回读 ES 违背 v3.5.1 承诺不取；③ 边界确认 = 多 error 同 trace 仍取 root request.input（判定 root=request 根，与现 §6.2 语义一致），残 trace 缺 root → 列 NULL → 不组装现状保持。

**落字（2026-09-07 用户拍板采纳方案 A）**：detail v1.7 —— `trace_judge_state` DDL 增列 `input_snapshot_clean MEDIUMTEXT NULL` + `input_truncated TINYINT NOT NULL DEFAULT 0`；落点 = §4.1 consumer 流水线 step4（root 到达、算 root_input_hash 同刻）扩展写快照/判截断 + §4.3 root 到达行注（消费 step4 = **唯一见原始 input 明文处**）+ §6.2 开 cluster/窗口回填自判定态列复制 input_snapshot_clean/input_truncated（聚类/组装不再判、组装仍取 cluster.input_snapshot）+ H7-1 判定时点措辞下钻到「消费 step4 root 到达判截断落明文快照」（聚类仅复制）→ detail §5.1④/§6.2/§6.3 联动。solution v3.5.7 §7.2 判定点同句同步。offline 零机制（offline 只消费 D19，不感知来源变更）。**状态：design v0.1 → approved → landed（detail v1.7 + solution v3.5.7）。**

### R-19（H7-14 → error_type 字面量错位 + 值域漏项）— 评审 v0.1（2026-09-07）

**问题回顾（executor.py 原文 + phase2 §6.4 + detail §7.6 三方对表）**：
- **executor.py L22-38 真实产出值（10 个）**：`no_done / no_usage / timeout / pool_error / http_error / http_client_error / connect_error / sse_parse_error / body_too_large / contract_error`；`RETRYABLE_ERRORS = {timeout, connect_error, sse_parse_error, http_error, no_done}`（L38）。
- **phase2 §6.4 na 五源矩阵（online 判据的权威标注源，L326-332）与 detail §7.6 影响域清单（L966-971）** 在 case 级列 `timeout / connect / sse_parse / http / no_done / body_too_large`——**短名**。
- **对表 = 5 处不一致**：① `connect_error`（executor 真值）文档写 `connect`；② `sse_parse_error` 写 `sse_parse`；③ `http_error` 写 `http`——三处恰是 R-2 语义归 **case 级** 的技术失败（该 case 与 agent 交互失败）；④ `no_usage`（未收 usage 契约违反）、⑤ `contract_error`（prepare 配置/模板/解析/未知兜底）executor 会产出，但**两值未入任何判据矩阵**。pool_error/http_client_error/body_too_large/circuit_open/interface_disabled/scheduler_unexecuted/missing_assertion/assertion_shape 字面量两侧一致 ✓。
- **后果链**：online 判据对 na 行 error_type 归类（§7.6 ④）——三错位值 + 两漏项值全部落入「**无标注的新 error_type 默认从严 = 环境级 → unclean_run + 告警**」（detail §7.6 L964 兜底）→ 本属 case 级（不牵连他 cluster 已跑通 pass）的技术 na 系统性升格环境级 → **整 run 假 unclean_run + 同 run 他 cluster 真实 pass 被误伤（转 needs_review/不计 K）+ 持续告警噪音**。connect/sse_parse/http_error 在复现 run 每个 case 都可能触发（被测 agent 偶发 5xx/断连/SSE 畸形即中），风暴频度高。no_usage/contract_error 成片时（agent 契约整体不合）放大。

**设计（方案 A：字面量对齐 executor 真值 + 补漏项归 case 级 + code 一致性单测护栏）**：
1. 判据权威清单改列**真实产出值**：
   - **case 级** = `timeout / connect_error / sse_parse_error / http_error / no_done / body_too_large / no_usage / contract_error / missing_assertion / assertion_shape`
   - **环境级** = `circuit_open / interface_disabled / scheduler_unexecuted / http_client_error / pool_error`
   - `no_usage` / `contract_error` 归 **case 级**：均为该 case 与 agent 交互的契约/配置级失败（无证据、不牵连他 cluster 已跑通 pass）；成片时（凭证/契约错）同 run 无 pass 可牵连 → 不构成 unclean 污染；与 timeout/no_done/body_too_large 同类。`contract_error` 若实现期发现「prepare 凭证错成片且与他 case pass 混存」再复审环境级。
2. 落点：phase2 §6.4 行 1 触发列 + L334 影响域 case 级清单 + RETRYABLE 短名注释 → 真值；detail §7.6 L966-971 影响域矩阵 case 级行 + L964 值域权威注；solution 同步（如有内联 error_type 清单需全仓核对，环 0 补一致性项）。
3. **单一权威源 + 防回归护栏（本评审认为比一次性改字面量更重要）**：executor error_type 常量保持 executor.py L22-31 唯一产出源（值不动）；新增 **code 一致性单测**断言「executor 常量全集 ⊆ §6.4 标注清单 ∪ 已知调度/assertion 值域」——未来加 error_type 忘标注即红，杜绝「名字漂移 → 静默风暴」复发；环 0 增静态核对项。
4. 备选 B（结构性根治，本期不取、观察登记）：na 行透传结构化影响域（`impact_domain: environment/case`）替代 online 字面量归类 → 改 offline 结果 schema、破 R6 载体承诺，成本高；作为独立候选项留档。

**评审**：① executor.py 常量**名**（ERROR_CONNECT 等）与**值**（"connect_error"）分离——运行时只以值为准，本次不一致全在「文档字面量 vs 代码值」，改文档不改代码，风险低；② 兜底从严（未知 error_type → 环境级）保留为护栏没错，但**名字错位让它从「兜底」变「常态」**——改字面量后从严回归真兜底；③ no_usage/contract_error 归类是唯一语义新决策，已给 case 级推荐与复审触发条件。

**落字（2026-09-07 用户拍板采纳方案 A 全量）**：判据权威清单改列 executor.py L22-31 真值——**case 级** = `timeout / connect_error / sse_parse_error / http_error / no_done / body_too_large / no_usage / contract_error`（+ missing_assertion/assertion_shape 独立 case 级行）；**环境级** = `circuit_open / interface_disabled / scheduler_unexecuted / http_client_error / pool_error`；`no_usage/contract_error` 补入归 case 级（该 case 与 agent 交互契约/配置级失败，不牵连他 cluster pass）。落点：detail v1.7 §7.6 影响域矩阵 + 值域权威注；phase2 v0.7.1 §6.4 矩阵行 1/行 2（RETRYABLE_ERRORS = `{timeout, connect_error, sse_parse_error, http_error, no_done}`，L38 真值）+ §6.4 影响域 case 级清单 + §11.1 na 判定矩阵镜像；solution v3.5.7 §10.5 判据块。**落字后全表清点追改一处遗漏（2026-09-07）**：phase2 §2.3 v0.6.2 注② 内嵌 case 级清单同为现行判据正文、落字时漏改（仍短名 + 漏二项），已改真值 + 补漏项（同版收口，见 phase2 v0.7.1 §2.3 注①/§13 修订行）。code 一致性单测护栏（executor 常量全集 ⊆ 标注清单 ∪ 已知调度/assertion 值域）登记环 0 静态核对项、实现随 code 落地。备选 B（`impact_domain` 结构化透传）留档不取（破 R6 载体承诺）。**拍板补记（2026-09-07 清点后用户确认）**：挑战点「`no_usage` 是否应拉出做重试观察（防 agent 偶发漏发 usage 被误归永久 case 级失败）」——**维持现状，`no_usage` 不进 RETRYABLE**（直接 na 不重试；与 executor.py L38 真值一致，其瞬时缺漏的代价 = 该 case 当版 na、不牵连他 cluster，下版重测收敛，无需重试）。**状态：design v0.1 → approved → landed（detail v1.7 + phase2 v0.7.1 + solution v3.5.7）。**

### R-20~R-24（H7-15~H7-19 C/低危 5 条）— 评审 v0.1 → 拍板 approved（2026-09-07，方案详见登记表 R-20~R-24 行「已拍板方向」列）

- **R-20（C，offline 机制 code 走 Phase B）→ A：pre-scan 门禁立项 + 空答语义定性**——R-12 core（空答 fail）不动；pre-scan 显式立项为 Phase B code_detail 实施门禁（owner = offline 实施、产物 = pre-scan 报告：现网 keyword_* 断言空字段依赖 + 合法空答清单，合法空答 → 收紧带豁免白名单）；复现 run 空答 fail 语义定性 = leakage 空话术复发证据（agent 无有效产出、与词表命中 fail 同属未修复、证据形态不同）；「空答不落 na、落 verifier fail」保持。落字 = phase2 语义注 + §11.1 补注 + §10 B 项登记 + task 环 0 门禁。
- **R-21（C，online 机制）→ A：root-late 补判通道**——step4 root 到达发现 judged=1 且 root 此前未参与判定（root_ok 0→1）且 root_status∈{error,timeout} → 不重跑整 trace、仅 root 级补候选（root_error_type 走 L1/L2 值域筛）→ 复用 §6.2 聚类：同键 count+1/补快照（open 且缺 input 实文 → 补组装）；异键开新簇；同键已 closed 跳过；幂等 = root 到达事务置 root_late_complement CAS。落字 = detail §4.3/§4.4/§6.1/§6.2/§14 + solution §7.2/§10.2 同步。offline 零机制。
- **R-22（低危）→ A：收尾回填 na 统一钉死 `scheduler_unexecuted`**——scanner 回收 + orchestrator cancel + run 级超时收尾三路径回填 na 同源；「na case 必带 error_type」不变量全覆盖收尾路径；timeout 不作收尾回填原因；单测护栏断言非空。落字 = phase2 §6.3/§6.4 + detail §8.7/§7.6 注。
- **R-23（低危）→ A：timeout 三层语义分界 + 兜底边界闭合注**——① case 级 na 源（na 行→reason=na）；② run 终态 timeout 不直接触发 needs_review（兜底 = claim TTL 回退 open）；③ run 超时收尾回填 na（scheduler_unexecuted 环境级）→ 关联 pass case 入 unclean_run 批（R-2）——「超时非源」排除直接驱动、不排除环境级回填污染。落字 = detail §7.6 + §10 B-3/B-4 + phase2 §2.3/§6.4。
- **R-24（低危）→ A：requeue guard 状态域精确化 + 锚点保护**——复位条件 = `cluster.status ∈ {open, claim, needs_review}`（fixed/inactive closed 禁、需重测走 superseded+reopen）；requeue 不动 cluster 锚点（fix_version/claim_k/TTL 保留）；verify 兜底 = 仅 pending invalidated link。落字 = detail §7.4 + §9.4 + §14 用例。online-only。

**落字（2026-09-07 逐问拍板批，本批全 landed）**：detail **v1.9**（header + 修订记录行 + §4.1 step4 表行 root-late 例外 + §4.3④ root-late 补判 + §4.4/§5.1⑩ `root_late_complement` 幂等列 + §6.1 补候选 bullet + §6.2 root-late 补候选聚类段 + §7.4 requeue guard 状态域改写（R-24）+ §7.6 v1.9 blockquote（R-22 收尾回填统一 / R-23 timeout 三层分界 / R-21 幂等标记）+ §8.7 runs 行 R-22 收尾注 + §9.4 requeue 门控行 + §14 E-28/E-29）+ solution **v3.5.9**（header + 变更行 + 修订记录表补 v3.5.8/v3.5.9 两行 + §6.1 step4 root-late 例外句 + §7.2 trace_judge_state 行 `root_late_complement` + §10.2 root-late 补判聚类段）+ phase2 **v0.7.2**（header + 契约引用行 v1.9 + §2.3 v0.7.2 注①R-22 ②R-20 ③R-23 三层分界 + §6.3 R-22 收尾统一注 + §6.4 源行三路径 + §7.2 R-20 注 + §11.1 收尾 error_type 护栏 + §10 v0.7.2 blockquote + §13 v0.7.2 行）。**R-21/R-24 = online 机制/语义（root_late_complement 列 + 消费 step4 补判 / requeue guard 状态域）= online 实现清单；R-20 code（pre-scan 报告）= Phase B code_detail 实施门禁；R-22 收尾单测护栏入实施清单。**（此前「待落字（未拍板不动版号）」句为拍板时历史标注，本批已落字。）**状态：recorded → designed → reviewed → approved → landed（detail v1.9 + solution v3.5.9 + phase2 v0.7.2）。**

---

## 附录 A：非 R 批次登记区（P0 平台轨实现收口等，非 Task #4 error 回流修订）

> 本区登记**不属于 Task #4 error 回流修订**、但与同一批 online 权威文档（solution / solution_detail / task）联动的实现收口批次。
> 单独成区以免污染上方 Task #4 台账的语义边界；性质同 header——工作台账、**非权威方案**，权威口径仍在 solution / solution_detail / task。
> 状态机沿用 header：`recorded` → `designed` → `reviewed` → `approved` → `landed`。

| 批次 | 内容（实现/裁定要点） | 落点 | 状态 |
|---|---|---|---|
| P0-1 | **online 阶段 1 尾项实现收口**：T-1.3（ES index template/ILM，`es-template/` 提交物 + infra `es-init` 落建，ik_max_word 中文分词 + ILM 30d）；T-1.4（trace 查询三端点护栏全开）；T-1.6（前端 **Vue3 + Vite** 三页 + nginx 反代）；**auth 最小闭环**（= T-1.6 登录页数据源 §8.1 隐式前置） | detail **v1.11** 修订记录（栈裁定 / auth 边界 / 四实测发现）+ §9 全章 React→Vue + §9.1 登录落点 /traces 注；solution 六处 React→Vue **就地修补不升版**（H7 A 类先例）+ L3 版本行联动；task.md 阶段 1 收口 bullet + L3 权威引用升 v1.11；ci.yml 注释 Vue 同步 | **landed（2026-09-08）**：S-1 浏览器级 + S-5 curl 级验证全绿、backend 152 单测过 |
| P0-2 | **阶段 1 全量验证复验 + 三笔提交推送收口**：online main `76611d2`（47 files，含 sdk 修复 3 笔 + T-1.2 共 5 笔随行快进 `0d404a8..76611d2` 全推）+ infra dev `ce29141`（api-gateway timing 事件 Schema，offline 埋点批独立提）+ `ecdb694`（es-init）；两仓工作区干净、均落远端 | 落点 = git 历史 + progress memory；本 register 无权威语义改动（P0-1 已 landed，本轮复验零缺陷） | **landed（2026-09-08）**：S-1 浏览器 e2e（登录/列表/详情树/红显/正文保护/懒加载/中文检索/守卫）+ S-5 curl 级（auth 全端点/鉴权/分页/过滤/正文开关/ik 分词）复验全绿，前端 console 零报错 |
| P1-1 | **阶段 2 平台轨 T-2.1~T-2.4 收口 + 指标链路实现钉定**：L1/L2 判定（`analyzer/classify.py` 纯函数）+ judge_scan_job 落**独立 worker 进程 asyncio 自管循环**（1min + rollup 整点，非 APScheduler）+ R-21 root-late 补判接线（消费 step4 同事务 CAS，`root_late={status,error_type,layer,hit,at}`）+ metrics 四端点（/overview|interfaces|anomalies|llm-failures，窗口路由）+ **O-1 = 进程内无锁缓存** key=`endpoint|agent('*')|window` TTL 60s + agg 超时 3000 + `ERR_METRICS_0001` 复数前缀确认 + 7d rollup（`{env}.obs-metrics-rollup` 单 index + doc_type group/meta + 确定性 `_id` 覆写幂等 + `rollup-meta|{hour}` 廉价迟到探测）+ **O-4 裁定变更 = 自研纯 Python t-digest**（PyPI `tdigest` 在无 MSVC Windows 源码编译失败 → 用户确认自研）+ **7d mixed 读取口径拍板**（卡片分位仅并覆盖小时 sketch、计数/序列实时整窗、interfaces 行级分位实时、rollup 缺失降级实时）+ dashboard 前端（/dashboard + 手写 SVG 折线 + 7d mixed 横幅） | detail **v1.12**（修订记录 + §5.3 rollup mapping/读取口径 + §8.3 metrics 四端点响应形状 + §12.2 O-4）；solution.md rollup 调度措辞「APScheduler 同族」**就地修补不升版**（H7 A 类先例）；task.md 阶段 2 平台轨收口注（T-2.5 真实 agent 联调 defer agent 整改轨）；git 历史 | **landed（2026-09-08）**：backend 单测 **237 passed** + lint 零告警；S-5 curl + S-1 浏览器 e2e 全绿；demo 数据 + rollup 写侧 one-shot 重建 6 已完成小时（group 计数对齐 meta source_count）；真实 rollup data 上 7d mixed 分位 vs ES 实时重算偏差 p50 0.35% / p95 0.04% / p99 0.17%（<1% 达标） |
| P1-2 | **阶段 2 平台轨前端 IA 重构 + metrics agents 端点**（T-2.4 dashboard 单页四 tab 拆一级菜单的细节整容 + 动态 agent 下拉数据源，多菜单化拍板落地）：① **`GET /metrics/agents`**（纯实测 7d 去重 agent 列表，freq desc、size≤100、非白名单/字典合成——实测可见 cc/demo-agent；O-1 缓存 key=`agents|*|7d` 同套 TTL 60s；ViewerUser）；② 前端**五一级菜单 1:1 落页**（总览 `/dashboard`（**60s 自动刷新对齐后端 60s 缓存**，Q7）/ 接口 `/interfaces`（双 tab）/ 异常 `/anomalies` / LLM 失败 `/llm-failures`，链路查询 `/traces` 独立接壳），每页只拉自身端点；③ **共享 MetricFilterBar**（agent 动态下拉 = 全站 + agents 实测列表、window 1h/24h/7d、默认 24h/全站、localStorage `obs.metricFilter` 持久化跨页，Q3）+ 动态下拉同源复用链路查询表单（Q6）；④ 空态语义分页归位（接口双 tab 空 = no_traffic；异常/LLM 失败空列表 = 「窗口内无异常/无失败现场」有效空态、section 自带文案，Q1）；⑤ 细节整容（App.vue 吸顶双行壳 + CSS 变量圆角层级/轻阴影/斑马纹，无引图表库，Q2） | detail **v1.13**（修订记录 + §8.3 agents 端点行/缓存注/响应形状 + §9.1 菜单结构与空态归位 + §9.2 页表五菜单行）；task.md 阶段 2 平台轨收口注追加行；git 历史 | **landed（2026-09-08）**：backend 单测 **243 passed**（agents +5）+ 本窗口后端 diff ruff 零新增（es.py:199 基线遗留容忍）；前端 vue-tsc + vite build 绿；S-1 浏览器 e2e 全绿（五菜单导航/高亮（trace-detail 映射链路查询）/ 总览 24h 实时 + **7d rollup 状态** + 60s 自动刷新 tick 渲染完好 / 双 tab / 异常·LLM 失败真实行 + 下钻 / 链路页动态下拉过滤（good-question→314）与无命中空态 / 跨页 filter 继承（good-question+7d）/ console 零 error/warn） |
| P1-3 | **两批 commit 挑战点收敛（展示诚实化 + 缺陷修补 + 判定固化语义裁定注记）**：① **1.1 判定固化 gate 语义（用户拍板接受现状，仅注记）**——gate 关闭窗内判 `none` trace 因 `judged=1` 不重判 = 有意语义（"关闭即暂停该 agent 回流"，配置回摆不回填），归因看 `judgement_json.gate` 快照（detail §4.3 判定固化注）；② **1.2 7d 分位 vs 计数不同样本 → UI 字段级标注**——`MetricsOverview` 增 `covered_hours`（7d 已 rollup 小时数，1h/24h 恒 0），总览 7d rollup/mixed 渲染分位口径注（detail §8.3/§9.2/§9.3）；③ **1.3 series 边界桶 QPS 按实际覆盖宽折算**——`_overview_series` 逐桶 `covered_ms = min(ts+桶宽,end) − max(ts,start)`（首桶左越窗/尾桶进行中小时右越窗不再虚低爬坡；error/timeout_rate 分母仍桶内 count）；④ **2.1 agent 幽灵选择修复**——`/agents` 增 `{total, truncated}`（`distinct` cardinality agg 真实去重总数）+ MetricFilterBar 幽灵 warn/「清除为全站」+ top100 截断提示 + 前台可见性刷新（>60s 陈旧才重拉，非轮询）；⑤ **2.2 总览自动刷新 60s→45s + 可见性门**（45<后端 60s TTL 非整约 → 命中缓存存活期；后台暂停、回前台 >15s 陈旧补一轮）；⑥ **2.3 异常/LLM 失败列表 total/truncated 提示**（anomalies body `track_total_hits: True`；llm-failures 折叠 total 走 `cardinality(trace_key)` agg——collapse 不改 hits.total） | detail **v1.14**（修订记录 + §4.3 判定固化 gate 语义注 + §8.3 响应形状四行 + §9.1 MetricFilterBar 增强 + §9.2 三页功能点行 + §9.3 四文案行）；task.md 追加行；git 历史 | **landed（2026-09-08）**：backend 单测 **249 passed**（基线 243 + 新增 6：partial 桶折算 2 / anomalies 截断 1 / llm cardinality 1 / agents truncated·fallback 2）；本窗口新增后端 diff ruff 零新增（es.py:199 基线遗留容忍行不碰）；前端 vue-tsc + vite build 绿；**已 commit 已 push origin**（本批代码 + detail v1.14 落字 = main `4707577`，`main==origin/main` 工作区干净） |
| P2-1 | **阶段 3 P2 回流第一批 error 聚类归并写侧**（= T-3.1 前半，detail v1.15）：① 新 `analyzer/cluster.py` **共享归并内核**（cluster_job 与 consumer root-late 同用）——去重键 `agent+interface+error_type 原值+input_hash`（§2.5 原值不跨类合并）；生命周期纯函数 `pick_merge_target`（count / skip / open，`reopen_after_terminal` 区分正常候选 vs root-late）；`_apply_count` = count+1 + latest_ts 刷新 + input_truncated 单 trace 即刷（R-13）+ 快照缺回填（R-18）；**E-12 吸收** = 新簇插入 `begin_nested()` savepoint + IntegrityError 回退重查转 count；② 新 `worker/cluster_job.py`——judged=1∧processed=0 扫批（batch=200、批循环收敛），行级 `begin_nested`「逐候选 merge_candidate（正常候选 reopen_after_terminal=True）+ processed CAS=1」原子，CAS rowcount!=1 → `_RowRaced` 行改动回退不双计，IntegrityError 保 processed=0 下轮重试转 count；**Fork A（用户拍板）** = root_input_hash NULL 行（残 trace 无 input 现场）候选不建簇只置 processed=1（错误由 R-21 迟到 root 补判兜底）；不消费 `judgement_json.root_late`（Fork B consumer 内联防双计）；③ worker/main 新增 `_cluster_loop`（`CLUSTER_INTERVAL_S=15`，run→sleep 串行不重叠、异常自愈同 judge）；④ **Fork B（用户拍板）** = consumer/state.root_late_complement 尾部同事务内联归并（补判 hit ∧ hash 齐备 → `merge_candidate(reopen_after_terminal=False)`，closed 不翻案 §4.3④/E-28）；⑤ **§6.2 R-21 句语义修正**（实现核对发现与 §4.3④/E-28 不一致）：root-late 同键 closed（fixed/inactive）→ 跳过不翻案、仅从未出现开新簇 gen=1；「closed 后复发新开 gen+1」限正常候选 | detail **v1.15**（修订记录 + §6.2 R-21 句改写）；task.md T-3.1 推进注；git 历史 | **landed（2026-09-09）**：backend 单测 **269 passed**（基线 249 + 新增 20：pick_merge_target 6 / error_msg_for 4 / build_cluster_row 2 / candidate 拆解 2 / cluster_loop 2 / consumer root-late wiring 4）；本窗口新增后端 diff ruff 零新增；**cluster_probe 集成探针容器内真库 6/6 全绿**（开簇字段/CAS / 同键 count+1 + R-13 回填 / fixed 复发 gen+1 + root-late skip / Fork A / gate 关停 / uk_cluster_dedup 唯一约束）；真数据观察 70 行 pending 全 clean trace → 0 簇正确；**已 commit 已 push origin**（代码 + detail v1.15 + register 本行 + task T-3.1 = main `00ad3b8`，`main==origin/main` 工作区干净） |
| P2-2 | **阶段 3 P2 回流第二批 D19 信封组装**（= T-3.2，detail v1.16）：① **触发形态（用户拍板）** = 纯 `assemble_job` 周期补偿扫描（`ASSEMBLE_INTERVAL_S=60`）——不做 cluster 首现即时内联（cluster_job 与 consumer root-late 两处产 open 由同一扫描幂等覆盖、单一写路径；新开簇至出 link ≤60s，offline 分钟级轮询可接受）；② 新 `converter/no_fallback_cfg.py`——`resolve_fallback_wordlist` 读 **per-agent** `dict_config(agent_id←Agent.id by name, key='fallback_utterance')` → `(words, version)`（`fallback_utterance` 为 per-agent 键、GLOBAL_DEFAULTS 无全局回退概念），命中返 config_value list + config.version、配置行缺/agent 缺 → `([],0)` fail-closed；③ 新 `converter/envelope.py`——`build_envelope` 按 §7.1 sample 逐键产 D19 信封（schema_version=1.0 / case_type=regression_error / payload_id=uuid4 / source{agent,interface,trace_id←first_trace_id,cluster_id,generation} / versions{trigger_version, fix_version=cluster 即时值（claim 前 null、永不回写）} / evidence{input=快照 json.loads 成功嵌还原值失败嵌原文, output·session_snapshot·retrieve_hit=null} / assert{no_fallback:{rule:wordlist,config_ref:{wordlist_version}}} 与 no_fallback_config{words,wordlist_version} 同刻同源）；`assemble_cluster` = 事务内 resolve→build→写 `error_case_link`(assembled+pending、source_trace_id/trigger_version/fix_version/input_truncated 自簇复制、payload_json=ensure_ascii=False) + `conversion_record(action=assemble)`（**input_truncated 不进 JSON、随 link 列透传**）；**空词表照建信封**（words==[] fail-closed 载体 → offline 结构自检 content_gap）；④ 新 `worker/assemble_job.py`——扫批判据 open ∧ input_snapshot 非空（E-13 快照缺跳过、R-18 回填后下轮扫到）∧ **无 `verify_status='pending'` link**（§6.3 窗口抑制，invalidated 仍 pending 占位不重组装），order by id limit 200 批循环收敛、每候选 `begin_nested` savepoint + IntegrityError（uk_link_current/uk_link_payload 并发双 worker）吸收跳过（E-12 先例）、每批一次 commit；⑤ worker/main 新增 `_assemble_loop`（60s run→sleep 串行不重叠、单轮异常 logger.exception 下轮自愈同 judge/cluster）、start 健康日志补 assemble_interval_s | detail **v1.16**（修订记录 + §6.3 触发句追加「纯周期扫描实现形态」注记）；task.md T-3.2 推进注；git 历史 | **landed（2026-09-09）**：backend 单测 **287 passed**（基线 269 + 新增 18：parse_snapshot_input 4 / build_envelope 4 / resolve_fallback_wordlist+parse_words 4 / assemble_cluster 4 / assemble_loop 2）；本窗口新增后端 diff ruff 零新增（E501 两处已修）；**assemble_probe 集成探针容器内真库 8/8 全绿**（A-1 首现组装 link+conv+envelope 逐字段含中文 ensure_ascii 可回读 / A-2 窗口抑制 / A-3 快照 NULL 只计数不组装 / A-4 空词表 words==[] / A-5 uk_link_current 二次组装 IntegrityError / A-6 fix_version 组装即时值带出 / A-7 fixed 排除 / W-1 resolve 真库读三态）；**代码未 commit 未 push、worker 未重启（等授权）**——重启后 `_assemble_loop` 生效，库内真实 open cluster 将被组装（当前 per-agent 词表为空 → fail-closed words==[] 信封，属预期） |

> **P0-1 实测发现（detail v1.11 修订记录，防复踩）**：① ES collapse 不改 hits.total（= 折叠前文档数）→ 去重 trace 总数须独立 `cardinality(trace_key)` agg，折叠键须 concrete keyword（不支持 runtime 字段，实测 400）；② 详情排序须 **seq asc**（SDK request 事件在中间件 finally 才 emit、ts 恒为全 trace 最大 → ts asc 会让根锚点沉底）；③ nginx 反代目标用 container_name `obs-backend`（共享 external network 上 `backend` alias 被 5 仓轮询占用 → /api 404）；④ `backend/.env` 会被 docker compose 按运行 CWD 加载并覆盖仓根 `.env`（DB_PASSWORD 错源 → Access denied），容器 env 变更须 `--force-recreate`。
> **P1-1 实测发现 / 实现钉定（detail v1.12 修订记录，防复踩）**：① **O-4 裁定变更** = 原拍板 PyPI `tdigest` 的 C 依赖（accumulation-tree）在无 MSVC Windows 只能源码编译、pip 实测失败、索引无纯 Python 替包 → 自研纯 Python t-digest（用户确认；只喂去重带权样本 + 超 K 单遍压缩，极端离群独立成簇保住右尾 p95/p99；确定性同输入同输出）；② **7d mixed 读取口径** = 卡片分位仅并 rollup 覆盖小时 request-node sketch（跨源分位不可精确合成）；total/error/timeout 计数与 series 保持实时整窗（精确超集，不与 rollup 计数掺）；interfaces 行级分位保持实时 agg（覆盖样本不足支撑行级近似）；rollup index 缺失/ES 异常降级整窗实时；`source∈{rollup,realtime,mixed}` + `fallback_hours`（窗内未覆盖整点小时），7d mixed 前端横幅「部分时段回退实时口径」；③ rollup 迟到探测 = 廉价 `count(size:0)` 比对 `rollup-meta|{hour}` 源计数、仅差异小时全量重算（确定性 `_id` 覆写），避免每轮重扫 6h 窗；④ 周期调度 = worker 进程内 **asyncio 自管循环**（judge_scan 1min + rollup 整点对齐，非 APScheduler）；`judgement_json` / `root_late` 形状钉死，T-3.6 聚类直接消费不改；⑤ O-1 缓存 = 进程内无锁 dict（仿 dict_config 60s 模式），key=`endpoint|agent('*' 全站)|window`；错误码为 `ERR_METRICS_0001`（复数前缀，§8.9 权威）。
