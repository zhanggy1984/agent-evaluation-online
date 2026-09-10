# agent-evaluation-online 线上观测平台 — 开发前详细设计（solution_detail）

> 基线：`solution.md` **v3.5.9**（error-only 一期定稿；含 v3.5.2 部署边界 + v3.5.3 B 包 needs_review 源 = error-run na 与 reentry 版本门控语义 + v3.5.4 R5-R7 auto-fixed 判据重构权威同步 + v3.5.5 R-1 claim_k / R-2 case 级纯净判据权威同步 + v3.5.6 R-3~R-10 修订包语义同步 + v3.5.7 R-18/R-19 高危 2 条语义同步 + v3.5.8 R-13~R-17 B 类 5 条语义同步 + v3.5.9 R-20~R-24 C/低危 5 条语义同步）。
> 本文件把 v3.5.9 方案落到「可直接指导开发」的粒度：**字段级 schema、DDL、API 契约、状态机矩阵、时序、页面功能点、接入与验收用例**。
> 文档关系：**`solution.md` 是权威（定标准、定边界、定口径）；本文件是实现基线（定字段、定接口、定实现顺序）**。两者冲突时以 `solution.md` 为准，并把冲突点记录到 solution.md §17 / 本文件 §12.2。
> 修订记录：2026-09-03 **v1.1（六方向独立评审修入）**——判定执行方裁定（judge_scan_job）、现行 link 唯一键语义（cur_key 生成列）、公共 infra 故障降级与 `{env}.` 租户命名、平台间 ack 前置矩阵与 requeue 游标、全站实时护栏默认值（O-1 裁定）、引用清理；其余见 §12.2 与文内标注。
> 修订记录：2026-09-03 **v1.2（契约修订包 R1~R3，Task #4-① 环 0 拍板）**——R1：`pull/payloads` 响应每条 payload 附顶层 `assembled_ts`（online 组装/requeue 时刻，offline 增量锚唯一来源，§7.2/§8.7）；R2：ack 前置矩阵补 `invalidated(offline_cap_gap)→active` 自愈回写例外（§7.3「激活」行本支持，v1.1 矩阵文本修订遗漏）；R3：ack 前置不符 400（`ERR_CLUSTER_0003`）响应带当前 `offline_status`+`invalidate_reason`（offline manual-invalidate 竞态对账，§8.7/§8.9）。字段/状态机语义未再变更；offline 配套方案 `error-backflow-phase1.md` v0.2 按其语义实现。
> 修订记录：2026-09-03 **v1.3（契约修订 B 包，Task #4-② 对接核查拍板）**——B-1：recheck 判定源限定 error_regression run 终态 + per-case 值域映射（pass/fail/na/缺行）+ 同 (agent,version) 多 run 选取序 + §8.7 `status` 取值集 + case_pass/run_status 语义修正（§5.1⑥）；B-3：needs_review 源 = error-run `na` 结果行，§1.4/§7.6/§12.1 三处口径同步，run 超时非源（兜底 = claim TTL 超窗回退 open）；B-4：na 批量聚合载体 `needs_review_batch`（§7.6/§8.4，v1.3 补 §5.1 ⑦b DDL + 批量 resolve 端点/整批原子）；B-5：fix_version/agent_version 版本字面量域 + reentry 门控 = 等值+日期前缀门控（§7.5/§8.4，v1.3 补同日不等值 count+1 可见性提示）；B-6：回归 run 归档保留语义（§7.3）。v1.3 排查补正（2026-09-03）：needs_review_batch DDL + 处置动作集/整批原子 + 门控可见性提示。对应 offline `error-backflow-phase2.md` v0.5.1 按其语义实现（待用户终审，未 commit）。
> 修订记录：2026-09-07 **v1.4（R5-R7 落字 + 消费语义终审补定义 + 一致性修订，Task #4-②）**——auto-fixed 判据重构落地 = **纯净 run 前提 + 跨版本稳定序列 K**（§7.6 判定语义 blockquote：K=2 默认可配 / fail 即时 reopen 清零 / 缺行不计数不终止 / reentry 同版本禁 auto-fixed）；reason 值域扩展 {`na`, `unclean_run`, `reentry_same_version`} 与聚合归属（needs_review_batch 同 (run,error_type) 单条、unclean_run 批承载不纯净 run 的 na+pass 行、reentry_same_version claim 级单条不产批）——§1.4/§7.6/§12.1 三处登记 + §5.1 ⑦b/verify_run_record 注释 + §7.5 门控联动 + §8.4 claim/review 端点联动；K-TTL 收敛终点（§7.6/§10.1 `claim_ttl_days`：两时钟先到者、K 观察不延长 TTL）；一致性修订：905 门控正文同步等值+日期前缀、§8.7 读面契约补 run 级 `na_case` + per-na-case `error_type`、verify_run_record 消费注、引用清理（§12.4→§10.1、§8.5.1→§8.5、solution §10.4/§10.5 前缀标注）。依据 offline `error-backflow-phase2.md` v0.6.1（2026-09-07 终审通过）按其语义实现；对 solution.md v3.5.4。双端均未 commit。
> 修订记录：2026-09-07 **v1.5（R-1 claim_k + R-2 case/环境级纯净判据落字，Task #4-③ 整链推演硬伤修订，2026-09-07 逐问评审拍板）**——① R-1：auto-fixed 的 K 由全局单一值改 **claim 级固化 `claim_k`**（`error_cluster` 增列 DEFAULT 2、claim CAS 同批写；claim API 入参可选 `k∈{1,2}`、缺省取 dict_config 新键 `auto_fixed_k_default`=2；K 只读固化值、不实时读全局键；claim 生命周期内**零推进可降、推进后锁死**；claim_k=1 = fix_version 纯净可判 pass 即 verify passed；TTL 回退 open 后重 claim 可改值、TTL 自新认领起算）；② R-2：纯净判据由「run 级 `na_case==0`」下钻 **claimed case 行 + na error_type 影响域分流**（环境级 circuit_open/interface_disabled/scheduler_unexecuted/http_client_error/pool_error → 触发 `unclean_run`；case 级 timeout/connect/sse_parse/http/no_done/body_too_large/missing_assertion/assertion_shape → 不牵连他 cluster pass）——`unclean_run` 触发窄化 + `needs_review_batch` **纯化 = 仅 unclean_run 批** + **纯 na cluster 退批改 cluster 级单点** + 撞键裁定收窄（na 不再被并入批）。落点 §5.1 ④/⑥/⑦b、§7.6、§8.4、§8.7、§10.1、§1.4/§12.1；对 solution.md v3.5.5；依据 offline `error-backflow-phase2.md` v0.6.2 注记（offline 零机制）。双端均未 commit。
> 修订记录：2026-09-07 **v1.6（R-3~R-10 逐项设计评审拍板落字，Task #4-③ 修订包二批）**——R-3 洪峰对账版本差集补齐（offline §5.2/§5.3；online 语义零改动，多 run 回查选取序已覆盖）；R-4 缺行成因诊断 = cap 截断挤出 → 人工核对 offline `excluded-cases` 只读面、「窗口外欠测」非修复失败（§7.6/§9.3，不跨端保窗口）；R-5 claim 软校验非硬拦 + offline **agent 已见版本只读面**数据源（§8.7 新增读面 + §9.3 claim 表单告警，版本活跃度 K 提示 v1.5 指针兑现）；R-6 `err_summary_json` schema 钉死原值域（§4.3/§5.1 DDL，禁 L1/L2 分类键）；R-7 批量 requeue + 可愈性标注（§7.4/§8.4/§9.3）；R-8 cap_gap 探测态节流（offline phase1 §6.5 引用修订：invalidated ack 只发一次 + 本地探测补齐，online 零改动）；R-9 batch resolve 语义化跳过非 claim 引用 cluster（§7.6 处置语义/§8.4 per-cluster 结果）；R-10 复现输入截断证据降级 + `input_truncated` 标记列 + **reason 值域 3→4**（§5.1 DDL/§7.6/§8.4/§9.3）+ input_hash normalize 截断上限 4096→8192 对齐复现截断。**reason 值域 = {`na`, `unclean_run`, `reentry_same_version`, `input_truncated`}**。对 solution.md v3.5.6；依据 offline `error-backflow-phase2.md` v0.7 注记。双端均未 commit。
> 修订记录：2026-09-07 **v1.7（R-18 input 明文载体 + R-19 error_type 字面量对齐，Task #4-③ H7 批高危 2 条评审拍板落字）**——**R-18**：修复 `trace_judge_state` 只持久 `root_input_hash`、明文无载体的组装主链路断点——判定态增列 `input_snapshot_clean`（root request.input 脱敏截断≤8K 明文快照）+ `input_truncated`，**消费 step4 root 到达同刻落库**（§4.1 step4/§4.3，唯一见原始明文处）；§6.2 开 cluster/回填取数源改自判定态列复制；`error_cluster.input_truncated`/`error_case_link.input_truncated` 来源链 = 消费 step4 → cluster → link（**H7-1 判定点从「cluster 首现」下钻到「消费 step4」**，聚类/组装仅见 ≤8K 截断快照不可判）。**R-19**：error_type 判据字面量对齐 executor 真值 + 补漏项——case 级 `timeout / connect_error / sse_parse_error / http_error / no_done / body_too_large / no_usage / contract_error`（§7.6 影响域矩阵），消除「名字错位 → 未知从严 → 假 unclean_run」系统性误伤；权威标注随 offline `error-backflow-phase2.md` v0.7.1 §6.4。对 solution.md v3.5.7。双端均未 commit。
> 修订记录：2026-09-07 **v1.8（R-13~R-17 H7 批 B 类 5 条逐条评审拍板落字，Task #4-③）**——R-13 input_truncated 判定位窗口化：`input_truncated` 列语义 = **当前判定态**（同键窗口内新现 trace 判定态到达开簇/回填时刷新、单 trace 即刷 ≤8K 清 0；已 closed cluster 不刷新不翻案，§5.1④/§6.2/§7.6 v1.8 ①），截断历史留已产出 needs_review 产物 + 详情警示不抹；R-14 unclean_run 载体口径归一 + 挂起标注：状态机 claim 迁移 reason 列收窄剔除 unclean_run =「只经 batch 载体处置、cluster 不入 needs_review 态」，批引 claim cluster 详情/列表**实时派生「被未决 unclean_run 批 Bx 挂起」标注**（join link_refs 免加列），TTL 不豁免沿用既有兜底（§7.6 状态机表/§7.6 v1.8 ②/§9.x）；R-15 双通道优先级 = **input_truncated 优先**：同 run 双条件 cluster 走截断单条、不并入 unclean_run 批（批 link_refs 排除截断 cluster），reason=input_truncated + note 附环境级 na（§7.6 v1.8 ③/§5.1⑦b）；R-16 缺行诊断**自动消费 excluded 读面**：recheck 判缺行自动 GET runs 比 case_id ∈ excluded_case_ids → 自动标「窗口外欠测」，∉ 维持人工兜底（§7.6 v1.6 ① v1.8 ④/§8.7；offline 零新机制，字段位置 Phase B 核对）；R-17 K 序列**版本锚 = versions 读面**：候选版本序列 = GET versions ≥ fix_version 全版本序（window_days 覆盖 TTL 14d），versions 有版无 error run → 缺行中断（杜绝中间版丢 run 时 v1+v3 假连续 false-fixed），迟到补建终态到达补判推进（§7.6 v1.8 ⑤/§8.7 versions 用途升级 = K 判据序列源）。Phase B 立项：R-13 §6.2 同簇刷新复制、R-16 excluded_case_ids 字段位置核对。对 solution.md v3.5.8。双端均未 commit。
> 修订记录：2026-09-07 **v1.9（R-20~R-24 H7 批 C/低危 5 条逐条评审拍板落字，Task #4-③）**——**R-20**（offline，本稿仅语义注 + 立项登记）：R-12 core 空答 fail 不动；pre-scan 显式立项为 Phase B code_detail 实施门禁（owner = offline 实施，产物 = pre-scan 报告），复现 run 空答 fail 语义定性 = **leakage 空话术复发证据**（agent 无有效产出、与词表命中 fail 同属未修复、证据形态不同），「空答不落 na、落 verifier fail」保持。**R-21** root-late 补判通道（§4.3④/§4.4/§5.1⑩/§6.1/§6.2）：judged=1 后 root 迟到（root_ok 0→1）且 root_status∈{error,timeout} → 不重跑整 trace、step4 仅补一次 root 级候选（root_error_type 走 L1/L2 值域筛）+ `root_late_complement` 幂等 CAS 标记（§4.4/§5.1⑩）。**R-22** 收尾回填 na 统一 error_type=`scheduler_unexecuted`（scanner 回收/orchestrator cancel/run 级超时收尾三路径同源；「na case 必带 error_type」不变量全覆盖收尾路径；§7.6 v1.9 ①/§8.7）。**R-23** timeout 三层语义分界 + 兜底边界闭合注（case 级 na 源 / run 终态非直接源 = B-3 claim TTL 兜底 / 收尾回填环境级污染→unclean_run 批；§7.6 v1.9 ②）。**R-24** requeue guard 状态域精确化 = `cluster.status ∈ {open, claim, needs_review}` + 锚点保护（不动 fix_version/claim_k/TTL）+ verify 兜底 = 仅 pending invalidated link（§7.4/§9.4/§14 E-29）。对 solution.md v3.5.9；依据 offline `error-backflow-phase2.md` v0.7.2。R-20/R-21 code 变更单独立项 Phase B/实现清单。双端已 commit，收口见下「commit 收口」行。
> 修订记录：2026-09-07 **commit 收口（双端基线确认）**——online main 0b4662f + e016c45 / offline dev dcf4680 + e85fa2e：solution/solution_detail/task + error-backflow-phase1/phase2/code_detail + 平台本体 docs 各就各位。v1.1~v1.8 历史行「双端均未 commit」为各版当时实态（历史快照保留）；后续修订以本行为 commit 基线。
> 修订记录：2026-09-07 **v1.10（集成异常与边界用例登记层增补）**——§14 新增 §14.5「集成异常与边界用例（task.md 阶段 4 T-4.13/T-4.14 编号化，X 系列）」X-1~X-13：把 `task.md` T-4.13（异常 6 组）/ T-4.14（边界 7 组）追加场景编号化为验收用例（埋点前提/检索注入转义/平台间契约/大对象/时间/窗口/时序/数量级/并发词表/保留期边界死角），销 task.md L124/L160「须回填 detail §14」待办，验收以 X 编号为权威口径。纯用例登记层增补、无语义变更：solution v3.5.9 / offline phase1 v0.2.2 / phase2 v0.7.2 语义基线不动。
> 修订记录：2026-09-08 **v1.11（阶段 1 尾项实现收口 + 前端栈裁定落字 + 查询实测修正，= task.md 阶段 1 T-1.3/T-1.4/T-1.6 + auth 隐式前置）**——本批实现约定与 S-1/S-5 验证发现：① **前端栈裁定 Vue3 + Vite**（本版 §9 全章 React 措辞随改；solution.md 六处同步就地修补、不升版——H7 A 类「直接修补不升版本」先例，语义基线不动）；② **Authorization 承载与 token 存储落定**（原文档缺口）：`Authorization: Bearer` 头 + access/refresh 双 token 存 localStorage（`obs_access`/`obs_refresh`），401 single-flight refresh-on-401；**登录成功落点先指 `/traces`**（§9.1 注，dashboard 属阶段 2 就位后改回）；③ **auth 最小闭环边界显式化**：5 次/15min 失败锁定 = 进程内计数（uvicorn `--workers 1` 单实例，重启清零可接受），**无 token-version 列迁移**——user_version 即时吊销属 §8.6 阶段 3 面，UserSession revoked + status 检查 + access 15min 短效已覆盖最小面；④ **trace 列表去重总数 = `cardinality(trace_key)` agg**（S-5 实测：ES collapse 不改 hits.total = 折叠前文档数，去重口径须独立 agg；折叠键须 concrete keyword 字段——collapse 不支持 runtime 字段，实测 400，见 es.py `build_trace_list_body`）；⑤ **详情排序 = seq asc 结构序**（S-1 实测：SDK 在中间件 finally 才 emit request 事件、其 ts 恒为全 trace 最大 → ts asc 让根锚点沉底子树散乱，改 seq 创建序即拓扑序，见 es.py `build_trace_events_body`）；⑥ **正文保护维持**（body_search=false 置空 input/output/log_message、检索面收窄 error_msg/error_type，前端零渲染兜底两层）；红显 = status∈{error,timeout}、llm_call 高亮 = node=="llm_call" 语义不变（CSS 顺序修正：red 定义于 llm 之后保证重叠时红胜）；⑦ **部署实测两坑**：nginx 反代目标须 container_name `obs-backend`（dev 共享 external network 上 `backend` alias 被 5 仓轮询占用 → 实测 /api 404）；`backend/.env` 会被 docker compose 按运行 CWD 加载并覆盖仓根 `.env`（DB_PASSWORD 错源 → Access denied），容器重建须 `--force-recreate` 才吃新 env。solution v3.5.9 / offline phase1 v0.2.2 / phase2 v0.7.2 语义基线不动。
> 修订记录：2026-09-08 **v1.12（阶段 2 平台轨 T-2.1~T-2.4 收口 + 指标链路实现钉定，= task.md 阶段 2 平台轨子集）**——本批实现约定与验证发现：① **L1/L2 分层判定落地**（§6.1 `analyzer/classify.py` 纯函数：白名单门 + llm_fact_ok 重算（列==1 或 entries 有 error_type∈LLM_ERR_TYPES）+ L1/L2/OR 门控 + 残 trace 子节点照判 + `root_late_decision` 单事件值域筛）；judge_scan_job 落独立 worker 进程 **asyncio 自管循环**（judge_scan 1min + rollup 整点对齐，仿 consumer `_heartbeat_loop`，非 APScheduler）；`judgement_json` 落库形状钉死 `{version,decided_at,layer,gate,llm_fact_ok,root,candidate_error_sets,root_late}`、`root_late` = `{status,error_type,layer,hit,at}`（R-21 root-late 补判通道输出 = 消费 step4 同事务 CAS 落库，judged 不推翻；§4.3④，T-3.6 直接消费不改）；残 trace 子节点分支 interface 回填（state.py 非 root 分支，§4.3，残 trace 首个 error 子节点回填支撑 L2 字典查询）；② **metrics 四端点落地**（§8.3 `app/api/metrics.py`，响应字段形状本版 §8.3 增补钉定）——overview/interfaces/anomalies/llm-failures 全 ViewerUser，window∈{1h,24h,7d}，1h/24h 实时 date_histogram、7d 走 §5.3 混合路由；参数非法 / agg 超时 / ES 不可用 → `ERR_METRICS_0001`(400)（**复数前缀确认**，§8.9）；**O-1 护栏落地 = 进程内无锁缓存** key=`endpoint|agent('*' 全站)|window`、TTL=`metric_agg_cache_ttl_s`=60、agg request_timeout=`metric_agg_timeout_ms`=3000，缓存命中跳过 ES（§8.3/§12.2 O-1 行）；③ **7d 小时级 rollup 落地**（§5.3）——单 index `{env}.obs-metrics-rollup`（非周滚动）+ mapping dynamic:false + **doc_type group/meta 分列**（meta doc 记源计数）+ 确定性 `_id = sha256("rollup|agent|interface|node|model|hour")` 整小时重算覆写幂等 + `rollup-meta|{hour}` 廉价迟到探测（下轮 count(size:0) 比对 meta、仅差异小时重算，避免每轮重扫 6h）+ sketch 序列化 JSON-base64；④ **O-4 裁定变更：PyPI `tdigest` → 自研纯 Python t-digest**（`app/store/tdigest.py`——PyPI 包 C 依赖在无 MSVC Windows 源码编译失败、本环境索引无纯 Python 替包，用户确认自研；只喂去重带权样本 + 超 K 单遍压缩 + 确定性，跨小时合并误差实证 <1%，§12.2 O-4 行更新）；⑤ **7d mixed 读取口径实现钉定（用户拍板，§5.3 回填）**：卡片 p50/p95/p99 = **仅 merge rollup 已覆盖整点小时** request-node sketch（跨源分位不可精确合成）；**total/error/timeout 计数与 series 保持实时整窗**（精确超集、不与 rollup 计数掺——rollup 计数与源一致由 meta 探测保证）；interfaces 行级分位保持实时 agg（覆盖小时样本不足支撑行级 covered-only 近似）；rollup index 缺失 / ES 查询异常 → 降级整窗实时（covered=[] → source=realtime）；响应 `source∈{rollup,realtime,mixed}` + `fallback_hours`（窗内未覆盖整点小时），7d mixed 时前端横幅「部分时段回退实时口径（N 个整点小时无 rollup 覆盖）」；⑥ **T-2.4 dashboard 前端落地**（Vue3 `/dashboard` + 手写 SVG `TimeSeriesChart` 折线（不引图表库）+ 空态 4 型 + 概览卡/接口双 tab/异常聚焦/LLM 调用失败下钻 → trace 详情）；登录落点 `/traces` → `/dashboard`（§9.1 v1.11 注兑现）；⑦ 验证：backend 单测 **237 passed** + lint 零告警；demo 数据（gen_metrics_demo.py）+ rollup 写侧 one-shot 重建 6 已完成小时、group 计数与 meta source_count 对齐；**真实 rollup data 上 7d mixed 分位 vs ES 实时重算偏差 p50 0.35% / p95 0.04% / p99 0.17%（<1% 达标）**；S-5 curl 四端点 × 1h/24h/7d + agent/interfaces 过滤 + window 非法 400 全绿；S-1 浏览器 e2e（dashboard 空态/卡片数值/7d mixed 横幅/interfaces 双 tab/异常下钻 trace 详情）全绿。solution v3.5.9 / offline phase1 v0.2.2 / phase2 v0.7.2 语义基线不动；task.md 阶段 2 平台轨子集出口达成（收口注随落，T-2.5 真实 agent 联调 defer agent 整改轨，平台侧条件已就绪）。**实现修订（挑战 3 双缺陷修复，2026-09-08 追加本版行）**：⑦（原⑤）7d 覆盖基准改 = **rollup 小时级 meta doc**（新 store 助手 `fetch_rollup_covered_hours`；rollup_job 对处理过小时恒写 meta、含零流量 → 空小时算已覆盖、非缺口，不再被当缺口永久实时回补）；`fallback_hours` 只列**已闭合**小时缺口——当前进行中小时由 rollup 设计上不预聚合、实时回补，**不计缺口** → 全部已闭合小时覆盖时 `source="rollup"` 可达（三态落实非死码）、无任何覆盖 = `source="realtime"` 且 `fallback_hours=[]`（§5.3 读取口径块已按此改写）。对应单测：metrics 19→21 passed + backend 全量 **238 passed**。
> 修订记录：2026-09-08 **v1.13（阶段 2 平台轨前端 IA 重构 + metrics agents 端点，= T-2.4 dashboard 单页拆一级菜单的细节整容 + 动态 agent 下拉数据源）**——本批实现约定与验证发现：① **metrics 新增 `GET /metrics/agents`**（§8.3 补行）：返回近 7d **纯实测去重 agent 列表**（`agent` terms agg freq desc、size 上限 100 = `_LIST_LIMIT`，**非白名单/非字典合成**——实测可见 cc/demo-agent，Q5 语义）；只读原始事件 index（request 锚 + 心跳 must_not 复用心跳排除）；响应 `{agents:[name,...]}`；O-1 进程内缓存 key=`agents|*|7d` 同套（TTL 60s，缓存命中跳 ES）；ViewerUser 鉴权（未登录 401 `ERR_AUTH_0002`）；② **前端 IA 重构（Q1 拍板）**：单页 dashboard 内四段（概览/接口/异常/LLM 失败）拆**五个一级菜单 1:1 落页**——总览 `/dashboard`（概览卡 + QPS/失败率-超时率双图，**Q7：60s 自动刷新对齐后端 O-1 60s 缓存**，仅总览自动刷新其余手动）/ 接口 `/interfaces`（请求级/LLM 级双 tab）/ 异常 `/anomalies`（request 错误/超时倒序列表）/ LLM 失败 `/llm-failures` / 链路查询 `/traces`；**每页只拉自身端点**（§9.2 行级拆分）；③ **共享指标过滤条 `MetricFilterBar`（Q3）**：agent 下拉（全站 + `/metrics/agents` 动态实测列表）+ window 1h/24h/7d 三段；**默认 24h/全站**；filter 持久化 localStorage（`obs.metricFilter`）**跨四个 metric 页共享**（module 级单例，路由切换不重置，实测 good-question+7d 从总览继承到接口页）；agent 动态下拉**同源复用**于链路查询表单（Q6：文本框→下拉）；`useAgents` single-flight 加载 + 401 静默（登录态由广播处理）；④ **空态语义分页归位**：总览 no_traffic/no_rollup（沿 §9.1）、接口双 tab 均空 = no_traffic（有桶才出明细）、**异常/LLM 失败空列表 = 「窗口内无异常/无失败现场」有效空态**（不误用 no_traffic，各自 section 自带准确空文案，payload 未就绪不渲染该文案以免误导）；⑤ **细节整容（Q2 轻量）**：布局壳 App.vue 吸顶双行（品牌/用户行 + 一级菜单行，登出态整壳隐藏）+ 内容域 max-width；style.css 引入 CSS 变量统一圆角层级（大面板 8px/小控件 4px）+ 轻阴影 + 表格斑马纹基调（scoped 组件继承不重复声明）；延续无图表库（沿用手写 SVG `TimeSeriesChart`）。⑥ 验证：backend 单测 **243 passed**（agents 新增 5 = TestAgentsEndpoint 4 + body 锚 1）；本窗口新增后端 diff **ruff 零新增**（es.py:199 为基线历史遗留容忍行，不碰无关代码）；前端 vue-tsc + vite build 绿；S-1 浏览器 e2e 全绿（五菜单导航与高亮正确（trace-detail 映射「链路查询」）/ 总览 24h 实时 + **7d rollup 状态（source=小时聚合，P50 726/P95 2552/P99 4133、1,263 请求、无缺口横幅）+ 60s 自动刷新 tick 后渲染完好** / 接口双 tab 真实行 / 异常 + LLM 失败真实行 + 异常行下钻 trace 详情 / 链路页动态下拉过滤（good-question→314）与无命中空态 / 跨页共享 filter 继承 / console 零 error/warn）。solution v3.5.9 / offline phase1 v0.2.2 / phase2 v0.7.2 语义基线不动。
> 修订记录：2026-09-08 **v1.14（两批 commit 挑战点收敛：展示诚实化 + 缺陷修补 + 判定固化语义裁定注记）**——① **1.1 判定固化 gate 语义（用户拍板：接受现状，仅注记不动判定代码）**：gate 关闭窗口内判 `none` 的 trace 因 `judged=1` 不重判 = **有意语义**（判定 CAS 单行幂等固化；"关闭即暂停该 agent 回流"，配置回摆不回填、gate-close 行也按 judged=1 处理）；归因以 `judgement_json.gate` 快照为准（§4.3/§6.1）。② **1.2 7d 分位 vs 计数不同样本 → UI 字段级标注（挑战点 1.2 落字）**：`MetricsOverview` 增 `covered_hours`（= 7d 窗已 rollup 小时数，meta 判别含"处理过零流量"小时；1h/24h 恒 0）；总览页 7d 且 `source∈{rollup,mixed}` 渲染分位口径注「分位基于 N 个已完成小时聚合（截至上一整点，迟到流量不计入分位）；总数/失败率/序列为实时全窗」。③ **1.3 序列边界桶 QPS 折算（缺陷）**：`_overview_series` 逐桶按 `covered_ms = min(ts+桶宽, end) − max(ts, start)` 折算样本时长（ES date_histogram 对齐整边界 → 首桶左越 window_start、尾桶=进行中小时右越 window_end；原按满桶宽除虚低、曲线右端呈持续爬坡假象；尾桶折算后 = 真实"已过秒数"口径），error/timeout_rate 分母仍桶内 count；covered_ms≤0 守卫 → qps None。④ **2.1 agent 幽灵选择修复 + top100 截断提示**：`/agents` 响应增 `{total, truncated}`（`total` = `distinct` cardinality(agent) agg 真实去重数，非 terms top100 桶数；缺 agg 回退 len）；MetricFilterBar 检测**幽灵 agent**（localStorage 持久化值掉出活跃列表 → `<select>` 空显但 filter 仍指向 → warn +「清除为全站」）+ **top100 截断提示**「近 7d 共 N 个 agent，下拉仅显示最活跃 M 个」+ **前台可见性刷新**（切回前台且列表 >60s 陈旧才 `loadAgents(true)`，会话中新上线 agent ~1min 可见，不引轮询）；⑤ **2.2 总览自动刷新 60s→45s + 可见性门**：`AUTO_REFRESH_MS=45_000`（< 后端 O-1 60s TTL 且非其整约 → 每 tick 命中缓存存活期、后端实查约减半；运维若置 TTL=0 禁缓存则接受每分钟实查）；interval 回调跳过后台（`document.hidden`）与在飞请求；`visibilitychange` 回前台且 >15s 陈旧立即补一轮；底部 caption 中性化（不再耦合"每 60s"数值）。⑥ **2.3 异常 / LLM 失败列表静默截断 → total/truncated 提示（缺陷）**：`MetricsAnomalies`/`MetricsLlmFailures` 各增 `{total, truncated}`——anomalies body `track_total_hits: True`（真实 total）；llm-failures 折叠列表 total 走 `cardinality(trace_key)` agg（**collapse 不改 hits.total**，去重失败 trace 数须独立 agg）；前端两列表页 truncated 时渲染「窗口内共 N 条（失败现场），仅显示最新 M 条」。⑦ 验证：backend 单测 **249 passed**（基线 243 + 新增 6：partial 桶折算 2 / anomalies 截断 1 / llm cardinality 1 / agents truncated 2）；ruff 限本次 diff 零新增（es.py:199 基线遗留容忍行不碰）；前端 vue-tsc + vite build 绿。solution v3.5.9 / offline phase1 v0.2.2 / phase2 v0.7.2 语义基线不动。
> 修订记录：2026-09-09 **v1.15（阶段 3 P2 回流第一批 error 聚类归并写侧落地 + §6.2 R-21 句语义修正，= T-3.1 前半 / register 附录 A P2-1）**——本批实现约定与验证发现：① **共享归并内核 `analyzer/cluster.py`**（cluster_job 与 consumer root-late 同用，detail 引用 §6.2）：去重键 = `agent+interface+error_type 原值+input_hash`（§2.5 原值不跨类合并，与 §7.5 reentry 观察键同源）；生命周期纯函数 `pick_merge_target`（单测面）= 同键 ∃ 非终态簇（open/claim/needs_review）→ count / 同键 closed 且 `reopen_after_terminal=False`（root-late）→ skip / 否则 open（generation = 历史 max+1；`uk_cluster_dedup` 含 generation）；count 动作 = count+1 + 刷新 latest_ts + `input_truncated` 单 trace 即刷（R-13）+ 快照缺回填（R-18，open 且缺 input 实文时补齐）；**E-12 吸收** = 新簇插入包在 `begin_nested()` savepoint，IntegrityError → savepoint 自动回退重查转 count；twin 未提交不可见 → 上抛，外层行级 CAS 保 processed=0 下轮重试转 count。② **新 `worker/cluster_job.py`**（judged=1∧processed=0 扫批 `CLUSTER_BATCH=200`、order by id 批循环到空批收敛；每行 `begin_nested()` 内「逐候选 `merge_candidate`（`reopen_after_terminal=True` = 正常候选：closed 后复发新开代数）+ 尾部 `UPDATE … processed=1 WHERE … AND processed=0` 行级原子」——CAS rowcount!=1 → `_RowRaced` 本行归并改动随 savepoint 回退不双计；IntegrityError → 保 processed=0 下轮重试转 count；**Fork A（用户拍板）**：`root_input_hash` NULL 行（残 trace 无 input 现场）候选不建簇只置 processed=1，该 trace 错误由 R-21 迟到 root 补判走正规聚类兜底；**不消费 `judgement_json.root_late`**——root-late 由 consumer 补判事务内联归并（Fork B），重扫会双计）。③ **worker/main 新增 `_cluster_loop`**：`CLUSTER_INTERVAL_S=15`（判定到期即应尽快归并进 error_cluster，T-3.1；run→sleep 串行不重叠、异常退避自愈、stop 干净取消，同 judge_scan 装配）。④ **Fork B（用户拍板）consumer 内联归并**：`consumer/state.py root_late_complement` 尾部——补判 hit ∧ row.root_input_hash ∧ row.interface → 同事务 `merge_candidate(reopen_after_terminal=False)`（§4.3④/E-28：同键 closed 跳过不翻案；仅该键从未出现才开新簇 gen=1；代表字段用到达 root 事件自身：error_msg = event.error_msg、trigger_version = event.agent_version）。⑤ **文档修正（实现核对发现 §6.2 R-21 句与 §4.3④/E-28 不一致，本行定音）**：§6.2 原句「同键无现行非终态 cluster（含已 inactive/已 fixed 后）→ 新开 cluster（generation 按终态代数推进）」把正常候选的「closed 后复发新开」错套到 root-late 上——**root-late 归并权威语义 = 同键已 closed（fixed/inactive）→ 跳过不翻案（E-28/§4.3④），仅该键从未出现才开新簇 generation=1；「closed 后复发新开 generation+1」仅限正常候选（cluster_job `reopen_after_terminal=True`）**，§6.2 R-21 句已按此修正。⑥ 验证：backend 单测 **269 passed**（基线 249 + 新增 20：pick_merge_target 6 / error_msg_for 4 / build_cluster_row 2 / candidate 拆解 2 / cluster_loop 2 / consumer root-late 内联 wiring 4）；本窗口新增后端 diff **ruff 零新增**；**cluster_probe 集成探针容器内真库 6/6 全绿**（S-1 开簇字段逐项 + processed CAS / S-2 同键 count+1 不重建不改代 + R-13 快照回填与 input_truncated 刷新 / S-3 fixed 后正常复发 gen+1 + root-late 同键 closed skip / S-4 Fork A / S-5 gate 关停空候选 / S-6 uk_cluster_dedup 同键同代重复插 IntegrityError）；真数据观察：dev 现存 70 行 pending（judged=1∧processed=0）经 `run_cluster_merge` 消费 → 0 簇全置 processed = **正确**（70 行全 clean trace：root_input_hash NULL / layer:none / candidate_error_sets 空 → Fork A skip）；obs-worker 仍跑启动前代码，_cluster_loop 待重启拾取（未授权未重启）。P2-1 = T-3.1 前半（聚类归并写侧）；link 组装落库（assemble_job，P2-2）另批。未 commit 未 push（等授权）。solution v3.5.9 / offline phase1 v0.2.2 / phase2 v0.7.2 语义基线不动。
> 修订记录：2026-09-09 **v1.16（阶段 3 P2 回流第二批 D19 信封组装落库，= T-3.2 / register 附录 A P2-2）**——① **触发形态（用户拍板）**：`assemble_job` **纯周期补偿扫描**（`ASSEMBLE_INTERVAL_S=60`，§6.3「每分钟扫 open 且无现行 link 的 cluster」）统一组装——**不做 cluster 首现即时内联**（cluster_job created 与 consumer root-late 内联两处产 open 若分两套触发点会漏/耦合；单一写路径幂等全覆盖，新开簇至出 link ≤60s，offline 拉取分钟级轮询可接受）；**扫描判据** = `status='open'` ∧ input_snapshot 非空（快照缺 input 实文 = E-13 只计数不组装，R-18 补齐快照后下轮扫到）∧ 无 `verify_status='pending'` link（pending 即 cur_key 占位；invalidated 仍 pending 占位 → 不重组装，§6.3 窗口抑制）。② **converter 两模块**（§6.3 step3 文件布局照落）：`converter/no_fallback_cfg.py` `resolve_fallback_wordlist`（组装瞬间读 per-agent `dict_config(agent_id,'fallback_utterance')` → words=config_value + wordlist_version=config.version；`fallback_utterance` 是 per-agent 键——seed GLOBAL_DEFAULTS 无此项，无全局回退概念；agent/配置行缺 → `([],0)` 防御，空表信封照建 = fail-closed 载体 words==[]）；`converter/envelope.py` `build_envelope`（§7.1 sample 逐键：schema_version=1.0 / case_type=regression_error / payload_id=uuid4 / source{agent,interface,trace_id←cluster.first_trace_id,cluster_id,generation} / versions{trigger_version, fix_version=cluster.fix_version 组装即时值，claim 前 null、永不回写} / evidence{input=快照 `json.loads` 成功嵌 parse 值否则嵌原文, output/session_snapshot/retrieve_hit=null} / assert.no_fallback.config_ref.wordlist_version === no_fallback_config.wordlist_version 同刻同源；**evidence JSON 内不含 input_truncated——随 error_case_link.input_truncated 透传，§7.1 行/sample 证实**）+ `assemble_cluster` 单簇编排（写 link assembled+pending + conv action=assemble 一步事务，IntegrityError 上抛调用方 savepoint 吸收）。③ **worker 新增 `assemble_job.py` + main 挂 `_assemble_loop`**：`ASSEMBLE_BATCH=200` 批循环到空批收敛、每候选 `begin_nested()` savepoint（link+conv 原子同进退）、`uk_link_current`/`uk_link_payload` IntegrityError → savepoint 自动回退跳过计数（双 worker 竞态 E-12 吸收面）；DB 异常上抛 worker loop 退避自愈。④ 验证：backend 单测 **287 passed**（基线 269 + 新增 18：snapshot parse 4 / envelope 逐键+即时值+空词表+null input 4 / resolve 三态+parse_words 4 / assemble_cluster 产物 4 / assemble_loop 生命周期 2）；本窗口新增后端 diff **ruff 零新增**；**assemble_probe 集成探针容器内真库 8/8 全绿**（A-1 首现组装 link+conv+envelope 逐字段+中文直存 / A-2 窗口抑制：已有 pending link 不进扫描候选 / A-3 快照缺 E-13 跳过不组装 / A-4 空词表 fail-closed 信封照建 / A-5 uk_link_current 二次组装 IntegrityError / A-6 fix_version 组装即时值带出 / A-7 non-open（fixed）不进候选 / W-1 resolve 真库读命中+agent 缺两态）；**探针不全局跑 run_assemble**（防把库内真实 open cluster 无差别组装出 link——真 open 组装属启用行为，待重启后自然发生），扫描候选语义经 `_scan_candidates` 判据核验。obs-worker 仍跑 P2-1 代码，_assemble_loop 待重启拾取（未授权未重启）。P2-2 = T-3.2；pull/ack（P2-3）另批。未 commit 未 push（等授权）。solution v3.5.9 / offline phase1 v0.2.2 / phase2 v0.7.2 语义基线不动。
> 修订记录：2026-09-09 **v1.17（阶段 3 P2 回流第三批平台间契约 pull-API + ack 回写 + admin invalidate/requeue 落库，= T-3.3 / register 附录 A P2-3）**——本批实现约定与验证发现：① **鉴权面落地**（§8.8/§8.9）：`/pull/*` = **预共享静态 secret**（env `EVALUATOR_SERVICE_SECRET`，`require_evaluator` Bearer `secrets.compare_digest` 比对、未配置 fail-closed 全 401 `ERR_PULL_0001`，不接平台 JWT——offline 只持 service secret）；backflow 人工面三端点 = 平台 **admin** JWT（deps.py 新增 `require_admin`，viewer → `ERR_AUTH_0002` 403）。② **新 `app/backflow/` 域包**（纯逻辑 + DB 编排，镜像 converter/worker 风格）：`ack.py`——纯 `ack_decide` 打 §7.3 矩阵（draft/active/invalidated 前置 + **R2 例外 gate link 现行 invalidate_reason=offline_cap_gap → active、仍须 case_id** + 当前==目标幂等 noop E-15）+ `pull_payloads`（join error_cluster 按 agent 过滤、(assembled_ts,id) keyset 升序、assembled_ts≥since_ts、limit+1 截断产 base64url 游标）+ `apply_ack` **CAS UPDATE … WHERE offline_status=前置**（并发双 offline 交错 rowcount=0 → 重读：==目标幂等 200 / 否则 `ERR_CLUSTER_0003` **R3 响应带当前 offline_status+invalidate_reason**；target∈{draft,active} 清失效标注）；`requeue.py`——纯 `requeue_guard_errors`（R-24：仅 invalidated∧verify=pending∧cluster.status∈{open,claim,needs_review}∧**防抖 ≥5min、锚 = assembled_ts**）+ `requeue_link`/`requeue_batch`/`invalidate_link`（复位复用 payload_id + `resolve_fallback_wordlist` 现词表 → `build_envelope(payload_id=…)` **重填 payload_json + 刷新 assembled_ts=now + 清 invalidate_reason/invalidated_by + 不动 cluster 锚点**（fix_version/claim_k/TTL）+ conv(action=requeue/invalidate)；batch 逐行 savepoint 隔离、汇总 conv、**≤20/min 语义 v1 落逐行 ≥5min 防抖**；invalidate 仅 assembled/draft，active 后走 superseded+reopen）。③ **API**：`app/api/pull.py`（POST /pull/payloads——schema_version≠1.0→`ERR_PULL_0002`、case_type∉白名单→200 空集不触 DB（§12 加固/X-5）、坏 since_ts/next_token 400；响应每元素 = 信封全文 + 顶层 `assembled_ts` ISO（契约 R1）；POST /pull/ack——未知 payload→`ERR_PULL_0003`(404)、缺 action 422）+ `app/api/backflow.py`（links/{id}/invalidate、links/requeue-batch **静态段先于 /links/{id} 声明**、links/{id}/requeue）；`AppError` 加可选 `extra`（R3 进响应体、纯增量不影响既有形状）；`converter/envelope.build_envelope` 加可选 `payload_id`（None → 原 uuid4 行为不变）。④ **零 DDL 零新 worker job**：error_case_link 既有列（case_id/invalidate_reason/invalidated_by/offline_status/verify_status/payload_json/assembled_ts）+ conversion_record.action 自由串；pull/ack/requeue/invalidate 全请求驱动（§7.2 online 不设拉取时钟），obs-worker 无新 job 无需重启。⑤ 验证：backend 单测 **307 passed**（基线 287 + 新增 20 test_backflow：ack 矩阵全分支 / requeue 守卫 + 防抖 5min 边界 / cursor roundtrip / HTTP 鉴权负例 ERR_PULL_0001/0002/0003、R3 extra、viewer 403）；本窗口新增后端 diff **ruff 零新增**；**pull_probe 集成探针容器内真库 HTTP 级 13/13 全绿**（P-1~P-13：分页 keyset 升序无重漏 + agent 过滤 / since_ts 增量边界 / draft·active·invalidated 全矩阵 + R2 例外 + R3 带态 / E-15 幂等重放 + 双 ack 交错 / E-22 requeue 后 since 旧水位重拉可见 / admin invalidate·requeue·批量 + viewer 403 / 未知 payload 404）。E-5/E-6/E-15/E-22 环 1 验（fake-offline HTTP 客户端走通状态机；E-6/E-22 集成复验在阶段 4 T-4.3）。P2-3 = T-3.3；claim/回查（P2-4）另批。**未 commit 未 push（等授权）**。solution v3.5.9 / offline phase1 v0.2.2 / phase2 v0.7.2 语义基线不动。
> 修订记录：2026-09-09 **v1.18（阶段 3 P2 回流第四批 人工处置状态机 + 回查 verify 收口，= T-3.4 / register 附录 A P2-4）**——本批实现约定与验证发现：① **人工处置状态机写面落地**（§7.6 状态机矩阵 / §8.4，新 `app/backflow/claim.py`）——claim / ignore / reopen / needs-review-resolve / fixed-review 五端点全 **CAS `WHERE status=期望旧值`** + 同批 conversion_record 审计：**claim**（open→claim，**fix_version 必填 + trim 归一**（Task #4-② 防人手 ≠ agent 自报；比较 lower 归一、存储保 trim 原串）；**claim_k 固化**值域 {1,2}、缺省 dict_config `auto_fixed_k_default`=2 写死固化（K 只读固化值、不实时读全局键）；TTL = dict_config `claim_ttl_days` 默认 14d 起算；claim_due_ts 落库；conv detail JSON 含 note/k）/**ignore**（open→inactive，现行 pending link 先 superseded 停回查）/**reopen**（fixed/inactive/needs_review→open 复发/误判反悔，note 留痕）/**needs-review-resolve**（单条源 = pure na / reentry_same_version / input_truncated：reopen_cluster→open / escalated §16 通道 v1 只记录不迁移，conv detail 带 reason）/ **fixed-review（admin）**（approve:true → claim→fixed(closed_by=admin_review) + 现行 link verify passed / false → claim→open + link failed；**viewer 调 → `ERR_AUTH_0002` 403——viewer 不单方 closed**）；**ERR_CLUSTER_0002(409 带当前状态) 本批首用激活**（error_flow 域既空号场景码经 AppError 首用补位，CAS 竞态/重复处置 → 409，detail §8.9 语义已定、无结构改）；非法迁移/当前状态不符/值域/参数 → `ERR_CLUSTER_0003`(400)、不存在 → `ERR_CLUSTER_0001`(404)。② **回查 verify 判定内核**（§7.6 v1.5 R-2 纯净判据 / R-19 字面量 / R-10 / R-15 / R-16 / R-17，新 `app/backflow/verify.py`）——error_type 影响域归类常量表（**环境级 5** = circuit_open / interface_disabled / scheduler_unexecuted / http_client_error / pool_error；**case 级 10** = timeout / connect_error / sse_parse_error / http_error / no_done / body_too_large / no_usage / contract_error / missing_assertion / assertion_shape；**无标注新 error_type 默认从严 = 环境级**，R-19 宁慢勿假 fixed，`classify_error_type`）+ 纯函数 `route_verdict`（fail→reopen K 清零 / na→needs_review(reason=na) **cluster 级单点不牵连批** / pass∧input_truncated→needs_review(input_truncated) 单条（**R-15 双通道截断优先**，不入 unclean 批）/ pass∧run 环境级 na→unclean_run 走批不计 K 不清零 / pass∧纯净→count_k）+ `decide_k`（**相邻纯净 pass 才 seq+1**，R-17 防跨缺版假连续；unclean/missing 断链不清零、seq 保留；seq≥claim_k→terminal passed）+ 集成 `judge_link`（versions 读面取 ≥ fix_version 全版本序逐版判；fv 未发版/读面未收录 → no_progress「待发版」不推进；缺版无终值 run 无历史行 → **gap 缺行中断**（不得 v1(pass)+v3(pass) 假连续）；同 (agent,version) 多 run 取序优先 completed、绝不含 running/pending；`uk_verify_run`(link_id,run_id) 幂等逐版留档判定、终态只读不覆写；R-16 缺行 case ∈ excluded_case_ids → excluded_hit 标注「窗口外欠测」维持人工兜底轮询至 TTL、∉ 同）；K 满 → 现行 link passed + cluster fixed(closed_by=auto_regression)（**E-7**）/ fail → link failed + 即时 reopen（K 清零）；recheck 每轮逐行 commit/rollback，offline 读异常上抛 → 「回查失败待人工」（§16）幂等可重试。③ **unclean_run 批载体**（v1.8 R-14 / R-9，新 `app/backflow/batches.py`）——`ensure_unclean_batch`（`uk_batch_agg`(run_id,agent,bound_version,error_type) **全状态唯一幂等单条**——resolve 后同 key 复发（unclean 未愈，re-claim 同 fv + 新 link 再遇同 run）→ **复用同批重开**（status=open 清 resolve 审计 + 挂新 ref，不插第二条防 uk IntegrityError 卡死）、open 批 cluster 按 id 去重追加、**批引 cluster 保持 claim 不入 needs_review 态**）+ `resolve_batch`（**整批同动作单事务，动作集 {reopen_cluster, escalated}**：CAS batch open→resolved 抢占（冲突 ERR_CLUSTER_0002 409、未 commit 全回滚、**resolved_ts/resolved_by/resolve_action 落审计**）+ reopen_cluster = 逐引用 cluster CAS claim→open + 现行 pending link **superseded 释放 cur_key**（assemble_job 重建新 link）+ **每结果都落 conv(action=needs_review_resolve) 审计（note 截断 ≤1024）**，逐 cluster R-9 语义化 reopened / skipped_already_open / skipped_fixed（K 满先收敛极端）/ manual_review；escalated = §16 批升级：批置 resolved 不迁移 cluster，引用 cluster 由人工后续处置）。④ **读面 3 GET**（§8.4，viewer，`app/api/backflow.py`）——**响应形状响应模型字段级钉死（metrics 风格），P2-6 前端逐字段消费**：overview `{clusters(5 status 计数), links(5 verify_status 计数), to_fix, by_agent[]}`（to_fix = link `offline_status=active ∧ verify_status∈{pending,failed}` 计数，**本地镜像近似——offline 权威集不对账**；by_agent 仅 open/claim 两态按 agent 分布）；clusters 列表 `{items[], total, page, page_size}` 筛选 agent / interface / layer / status(5 值) / watch（= 现行 pending link 的 offline 拉取/确认态），items 字段见 `_cluster_item`（cluster 元数据 + claim 字段 + 现行 link 摘要 payload_id/case_id/offline_status/verify_status）；clusters/{id} 详情 `{…item, links[], verify_runs[], conversions[], waiting_days}`（verify_runs = verify_run_record 版本×case_pass 时间线含 excluded_hit；conversions = conversion_record 审计全链；waiting_days 锚 = claim 态 claimed_at 否则 first_ts）。⑤ **offline 回查读面 client + config 新键**（§8.7 / §13.5）——新 `app/core/offline_client.py` OfflineClient(base_url, secret=evaluator_service_secret、httpx.AsyncClient trust_env=False、**MockTransport 测试可注入**)：list_runs `GET /api/v1/runs`（status 终态白名单 + excluded_case_ids）/ run_results `GET /api/v1/runs/{run_id}/results?case_id=` / agent_versions `GET /api/v1/agents/{agent}/versions?window_days=`，HTTP≥400 → OfflineReadError + 3x 指数退避重试；config 新键 **`offline_base_url: str = ""`——空 = recheck_job 停轮**（offline 配套轨未启动前安全默认，日志 debug 注明，不进 _validate_secrets 强校验）。⑥ **新 worker job ×2**（worker/main 挂 loop，均 60s 周期 run→sleep 串行 + 异常退避自愈，同 assemble 装配）：`claim_ttl_job.py`（`run_claim_ttl` 扫 `status='claim' ∧ claim_due_ts<now`，每行 begin_nested savepoint + CAS claim→open 清 claimed_by/claimed_at/claim_due_ts、claim_k 复位默认、**fix_version 保留溯源**、conv action=claim_ttl_expire detail 含 TTL，**E-8**）；`recheck_job.py`（扫 status='claim' 且现行 pending link 承载 → judge_link 逐行事务收口；offline_base_url 空 = 本轮跳过 debug）。⑦ 验证：backend 单测 **342 passed**（基线 307 + 新增 35 test_backflow_claim：claim/ignore/reopen/fixed-review/needs-review-resolve 迁移守卫各分支 + claim k 值域 {1,2} 超域 / needs-review-resolve escalated §16 只记录保留状态 / batch resolve action 值域（超域 ERR_CLUSTER_0003）/ recheck_job offline_base_url 空停轮（engine 未触达即返回 0）/ route_verdict·decide_k·classify_error_type 纯函数全分支（含 R-15/R-17/R-19 护栏字面量）/ HTTP 鉴权负例（viewer→fixed-review ERR_AUTH_0002 403、无 token 401、ERR_CLUSTER_0001））+ 本窗口新增后端 diff **ruff 零新增**；**claim_probe 集成探针容器内真库 HTTP 级 13/13 全绿**（C-1 claim 固化 + due≈now+14d + conv / C-2 ignore·reopen·fixed-review(approve±) + viewer 403 / **C-3 E-7** 假 offline 两版纯净 pass → verify_run_record×2 + verify passed + fixed(closed_by=auto_regression) / **C-13 recheck_job 编排**：驱动真 worker `_run_recheck_cycle` 扫 claim+pending 逐簇收口 → fixed_auto / C-4 回归 fail → link failed + cluster 回退 open / C-5 环境级 na run 内 case pass → unclean 批建(uk_batch_agg) + cluster 保持 claim / C-6 同批双 ref resolve → 整批 reopened + 批 resolved(含 resolved_ts) + link superseded 释放 cur_key；escalate 子校验：批 resolved 不迁移 cluster（保持 claim/link pending）/ C-7 单 case na → needs_review(reason=na) + link superseded + resolve reopen / **C-8 E-8** claim_due_ts 超窗 → claim_ttl_job 回退 open + fix_version 溯源 + conv(claim_ttl_expire) / C-9 gen>1 claim 软提示（offline 未配 = warning None 放行；硬闸 P2-5）/ C-10 CAS 竞态：双 session 同读 open → 先手 200 / 后到者 ERR_CLUSTER_0002(409) / C-11 读面 3 GET shape + 筛选分页 / C-12 excluded_case_ids 命中 → record excluded_hit + case_pass NULL + 不自动迁移）；**batches.py 真 bug 修复**（`ensure_unclean_batch` create 分支误引用先前 `select().first()` 的 None 批对象取 `.id` → AttributeError，探针 C-5 捕获——单测面未覆盖 create 路径，DB 语义集成探针补位回归）。E-7/E-8 环 1 验（真机端到端留阶段 4 T-4.4 环 2）；C-3/C-4 之外的单错级「同 run 他错仍红」在环 2 复验。**obs-worker 运维态：仍跑 P2-3 代码，claim_ttl/recheck 两新 loop 待重启拾取**（未授权未重启；offline_base_url 空 → recheck 即便拾取也停轮）。P2-4 = T-3.4；reentry 哨兵 job / 复发提示（T-3.5 P2-5）、前端回流页（T-3.7 P2-6）另批。**未 commit 未 push（等授权）**。solution v3.5.9 / offline phase1 v0.2.2 / phase2 v0.7.2 语义基线不动。
> 修订记录：2026-09-09 **v1.19（阶段 3 P2 回流第五批 §7.5 reentry 版本门控 + 终态只读显式守卫，= T-3.5 / register 附录 A P2-5）**——① **reentry 载体 = 内联 cluster_job（用户拍板，非独立 reentry_job）**：所有 judged 事件已被 trace_judge_state processed CAS 唯一消费（cluster_job 主链 + consumer root-late 内联走同 `analyzer/cluster.py` 内核），独立哨兵 job 会双消费冲突——T-3.6 的 reentry_job 条目就地注「并入 cluster_job」，不落文件。② **§7.5 版本门控编码**（B-5 等值+日期前缀序，纯函数 `reentry_gate_allows(agent_version, fix_version)`）：两侧各截前 10 位日期前缀（YYYY.MM.DD）且均命中 → 前缀相等仅**完全等值**放行（同日不等值按"修复上线中/未上线"不过，防 `r100`<`r47` 类字典序乱序把同日已上线误判为未上线）；前缀不等按日期前缀字符串序（新现日期晚于 fix 放行、早于 fix 不过，构建标签不参与跨日比较）；任一侧非该形态（含 None/空）→ 整体不透明字面量仅等值；**candidate 版本 None → False**（无版本证据不开 reentry，人工 reopen 兜底）。**门控只在最高代终态簇 = fixed 且 fix_version 非空（claim 产物）时咨询**——inactive 终态 / fixed 无 fix_version（UPDATE 造数无 claim 语义）→ 无门控基础维持 P2-1 无条件开（**S-3 / test_worker_cluster 既有 fixed 夹具零破坏**，fixed 恒带 fix_version 仅生产 claim 路径成立）。**门控不过 → merge 返新动作 "blocked"、DB 零落**（不建簇不 count 不 conv；judged 行仍被 processed CAS=1 消费掉，detail v1.3 口径；「同键新版本复发 N 次」可见性 = P2-6 前端实时派生 ES，不新增存储列）；两调用方 cluster_job·state.py 均忽略 merge 返回值 → blocked 零 break。③ **conv(action="reentry") 同事务落新建 reentry 簇**（随簇插入同处 `begin_nested()` savepoint，E-12 twin 吸收回退时 conv 一并回退不孤儿；actor_user_id=None；detail = §7.5 L951 原文提示「同键线上再现…线上仍复发，claim 或回归失守，请核对 fix_version 是否覆盖线上路径」；原 fixed 簇终态不改写不追加审计）。④ **E-10 终态只读显式守卫**（P2-4 已天然成立：recheck 只扫 claim∧pending、uk_verify_run 幂等、_decision_from_row 只读）补显式层：`judge_link` 入口 fv/case_id 校验后 `if link.verify_status != "pending" → no_progress("link 非 pending（终态只读，迟到 run 不覆写）")`——pending 是唯一可判定态，passed/failed/invalidated/superseded 均不可覆写（迟到 run 不追加不改写，重开另起新 link），把"终态只读"固化为 judge_link 局部不变量防未来调用方误触。⑤ 测试与验证：单测 **352 passed**（基线 342 + 10 = `reentry_gate_allows` 全分支 matrix：同日等值放行 / 同日不等值 r48·r100 挡 / 跨日早晚 / 裸日期等值 / 非日期字面量等值 / 单侧非日期 / None 空串 / strip）；本窗口新增后端 diff **ruff 零新增**（cluster_probe S-1/S-3 两行 E501 为 HEAD 存量未编辑区，不碰无关代码）；**cluster_probe 容器内真库 10/10 全绿**（S-7 E-9：fixed+fix_version 后同键跨日再现 → gen2 + conv(reentry) actor_user_id=None + 提示原文，原 fixed 簇不动 / S-8 同日不等值 → blocked 零落 / S-9 早于 fix → blocked 零落 / S-10 回归护栏：fixed 无 fix_version 与 inactive 终态复发照开 gen2 不写 conv）；**claim_probe 容器内真库 14/14 全绿**（新增 C-14 = S-11 归属：K 满 passed→fixed 终态后复调 judge_link → no_progress + 迟到同 bound_version 失败 run 不追加 + cluster 保持 fixed——E-10 探针因需 claim→verify 全程基建，落 claim_probe 侧同构 C-3 处，cluster_probe 无 claim/verify 基建不重复脚手架）。⑥ obs-worker 运维态：**仍跑 P2-4 代码，_cluster_loop 的 §7.5 门控 + judge_link 终态守卫待重启拾取**（未授权未重启）。P2-5 = T-3.5（E-9/E-10 环 1 验；真机端到端留阶段 4 环 2）；claim 详情「同键新版本复发 N 次」阻断可见性、前端回流页（P2-6）另批。**未 commit 未 push（等授权）**。solution v3.5.9 / offline phase1 v0.2.2 / phase2 v0.7.2 语义基线不动。
> 修订记录：2026-09-10 **v1.20（阶段 3 P2 回流第六批前端回流页 + blocked 复发读面实现形态修正，= T-3.7 / register 附录 A P2-6）**——本批实现约定与验证发现：① **前端回流页落地**（§9.1/§9.2/§9.3/§9.4）：「回流看板」为**第六个一级菜单** `/backflow`（现五菜单之后，detail §9.1 v1.13 五菜单未含回流页 → 本版登记第 6 项；**viewer/admin 均可见，无菜单级 gating**）；两页**独立路由**（先例 = TraceDetail 独立壳，非抽屉）——`/backflow` 列表（overview 卡：cluster 状态分布 / link verify 分布 / 待修复集本地近似 + 标注 / by_agent 分布；筛选 agent·interface·layer·status·watch + 分页；cluster 表含状态 pill·error_type·input_hash·**代表 trace（`first_trace_id`，可跳 trace 详情）**·count·generation·first/latest ts·fix_version）与 `/backflow/clusters/:clusterId` 详情（元数据 + links 表 + verify_runs 版本×pass/fail 时间线 + conversions 审计时间线 + 人工操作区 + claim 复核窗倒计时 + **reentry_observe caption** + **open_batches「处置整批」**）；admin-only 动作（fixed-review / link invalidate / requeue）按 `role==='admin'` 前端隐藏 + 后端 require_admin 二次鉴权；**二期入口（弃留墙/quality）整条隐藏不渲染**。② **blocked 复发读面实现形态修正（用户拍板，推翻 v1.3/v1.19 的「前端 ES 派生」）**：前端只能经 backend API 取数（nginx `/api/` → 后端，**无 ES 通道**），且 ES 只存原始 trace 事件（两节点 event/log，**无 judged / root_input_hash / candidate_error_sets 语义**，root_input_hash 是判定侧归一哈希无法从 ES 还原）→「前端实时派生（查 ES）」**不可行**；改为**后端读 MySQL `trace_judge_state` 现算**（judge 保留窗内，见 §7.5 派生口径），**仍不新增存储列**（无 DDL/无新列/无新 job）。③ **后端最小增量（全响应加法）**：新 `app/backflow/recurrence.py`（纯函数过滤核 `recurrence_rows_py` + `cluster_reentry_observe`，复用 `analyzer/cluster.reentry_gate_allows`）；`GET /backflow/clusters/{id}` 响应追加 `reentry_observe`（claim/fixed 态计算值否则 null）+ `open_batches`（`NeedsReviewBatch.status=open` 且 `link_refs` JSON 含该 cluster_id）；`_cluster_item` 补 `first_trace_id`（ErrorCluster 既有列，无新列）；**claim 端点 R-5 版本预检做全**（offline 配置时 best-effort 查 `agent_versions` 读面，fix_version 未见于已见版本 → 行内告警，非硬拦；offline 未配 → None 沿用 generation>1 软提示）。④ 验证：backend 单测 **385 passed**（基线 352 + 新增 33 `test_backflow_recurrence`：`recurrence_rows_py` fixed/claim 全分支矩阵 + 锚边界 + latest_version 取序 + fix_version 空 → None + error_type 命中集合 / `_cluster_item`·detail 字段级断言 / claim 版本预检 fake transport 三分支）；本窗口新增后端 diff **ruff 零新增**；前端 `vue-tsc --noEmit` + `vite build` 绿；前端文案集中于 `src/backflowLabels.ts`（offline_status / verify_status / needs_review reason 逐字 + cluster 状态中文 + conversion action 中文 + reentryCaption）。**环 1**（假 offline/online 数据）；真机浏览器 e2e 留阶段 4。P2-6 = T-3.7。**阶段 3 剩余 = T-3.9 online 侧 P2 门（验收门，非实现批）+ T-3.8 offline 判定语义改造（offline 仓，另一条腿）；P2 编号止于 P2-6**（P2-1~P2-6 = T-3.1~T-3.7 回流实现批，一一对位）——**本行原写「P2-7 gate 门 / offline 配套轨另批」系自编号误引，已撤销**（「gate 门」出处 = solution §11 #5「judge 放行开关」，属**二期、v1 不实装**，最易被误读成一期待办）。solution v3.5.9 / offline phase1 v0.2.2 / phase2 v0.7.2 语义基线不动。

---

## 0. 范围与一致性规约

### 0.1 本次开发范围（锁定，来自 v3.5.1）

| 面 | 范围 | 落点 |
|---|---|---|
| online 平台 | FastAPI backend + Vue3 frontend 完整实现细节 | 本文件全章 |
| agent 接入 | 4 个存量 agent（gq/cs/sp/cc）的 obs-sdk 埋点/接入契约 | 本文件 §11 |
| offline 依赖边界 | D19/D20 信封 + pull 传输 + 回写/回查的 **online 侧**实现 | §7 + §8.7 |
| offline 内部 | 只到「依赖契约 + 期望行为」；实现归 **Task #4**（独立方案、独立评审） | §7.3「offline 期望行为」 |

**回流一期 = error-only**：只回流 L1/L2 error（`case_type=regression_error` 一种），回流 agent 白名单 = {gq, cs, sp}（cc 不回流，D18）。
**二期机制一律不实现**：L3 quality（fallback / low_confidence / 弃留墙 / judge）、会话 N 轮上下文摘要、session_state 快照、`regression_quality` case_type、needs_review 常态触发。受影响的 schema 字段、ES 字段、config 键、UI 入口**只留位不打洞、不索引、不采集、不渲染**（见 §0.4 打标规约）。

### 0.2 打标规约（全文档统一）

- `【二期】` = 该处字段/机制二期才启用；一期**保留占位但不填充、不索引、不展示、不触发**。
- `【方案约定】` = 直接来自 solution.md，改动需回到方案层评审。
- `【实现约定】` = 方案未强制、本文件补充的实现默认值；可自由调整但记录在案。
- `【待 Task #4】` = offline 侧行为，由 offline 方案定稿，本文件只写 online 侧依赖契约。
- 引用规约：无前缀 `§x.y` = 本文件内部章节；引用 `solution.md` 一律显式写「solution §x.y」。本文件不使用三级编号 `§x.y.z`——任何历史遗留的三级引用按最近一级章节语义修正读（v1.1 已清理）；正文遗留裸 `§15/§16/§17`（本文件无对应大章）指 solution.md 的阶段验收/风险/open 章简写，保留不改。

### 0.3 读者与章节地图

| 读者 | 章节 |
|---|---|
| backend 全栈 | §1 布局 → §2 事件契约 → §4 消费/处理 → §5 DDL/ES → §6/§7 回流 → §8 API 全集 |
| 前端 | §1 → §8 → §9 页面规格 |
| agent 整改负责人 | §11 |
| offline 对接（Task #4） | §6.3 + §8.7 + §11.4 词表通道 |
| 平台运维/admin | §10 配置 → §13 安全 → §14 冒烟/验收 |

### 0.4 术语速查

| 词 | 含义 |
|---|---|
| 事件 event | SDK 上报的最小单位，一个 trace 由 N 个事件组成（§3） |
| trace | 一次请求的全链路（request 根节点 + 子节点），跨 Kafka 批次累积（§4.3） |
| error_type 分类 | L1/L2/L3 分层判定的输入（§3.3） |
| cluster | error 聚类最小单元（§6），代表「一个错误 + 一个现场」 |
| error_case_link | cluster → case 的生成记录（§5/§6），offline_status/verify_status 挂在它身上 |
| payload | D19 统一信封，组装后供 offline pull（§9） |
| fallback_utterance | dict_config 内 per-agent 兜底话术词表（no_fallback 断言用，组装快照固化 §7.1/配置 §10） |

---

## 1. 总体实现结构与模块职责

### 1.1 技术栈与组件（[§3/§14]【方案约定】）

| 组件 | 选型 | 说明 |
|---|---|---|
| backend | FastAPI + SQLAlchemy 2.x + Alembic + pydantic v2 | 独立容器，经公共 API 网关暴露（域名/TLS infra 域） |
| DB | MySQL 8，库名 `obs` | 只放平台元数据 + 回流状态，**不落事件本体** |
| 事件存储 | Elasticsearch 8.x 单节点 | 事件 index + 日志 index 分列，ILM 30 天，周滚动（§5.2） |
| MQ | Kafka（KRaft 单 broker），SASL/TLS + topic 级 ACL | 每 agent 一 topic，partition=1 |
| 前端 | Vue3（SPA，只经 backend API） | 无直连 ES/MySQL |
| SDK | Python：`kafka-python` + 标准库 + structlog 可选 | 见 §11 |

**部署边界【实现约定】（2026-09-03 补充）**：online 仅以 Docker 交付 **backend + frontend 两个服务**；MySQL/ES/Kafka 与网关/域名/TLS 一律使用**公共基础设施（公共 infra + 公共 API 网关）**，不自建、不随 compose 打包。上表 DB/事件存储/MQ 行「自管单实例」等运行时形态仅为平台侧视图，实际拓扑与凭证以公共 infra 为准——本平台以**租户**身份接入（infra 分配 endpoint + 最小权限账号 + topic/index/ACL 白名单，落点 §13.2/§13.3）。对外访问统一经公共 API 网关（浏览器→前端、前端→backend API 均过网关）。**网关默认拓扑（v1.1，§12.2 O-6）**：网关终止 TLS + 域名，平台内部仍自持 JWT（§13.1）；平台间端点（§8.7）不走公网网关，走 infra 内网/服务凭证直连（§13.5）。网关若做统一认证/限流前置属 infra 域，平台内角色模型（§13.1 JWT）保持不变；**若网关已吞认证，需与 infra 约定身份透传头防双认证打架——P0 前确认**。

### 1.2 仓库目录（实现约定，可在首 commit 内调整）

```
agent-evaluation-online/
├── backend/
│   ├── pyproject.toml            # fastapi / sqlalchemy / alembic / aiokafka|kafka-python(仅测试) / elasticsearch
│   ├── alembic/                  # migrations（初始建表含全部索引）
│   ├── app/
│   │   ├── main.py               # FastAPI 装配：CORS、JWT 中间件、路由注册、startup 拉起 worker
│   │   ├── core/
│   │   │   ├── config.py         # pydantic-settings；所有配置项（清单 §10）
│   │   │   ├── auth.py           # JWT 签发/校验/refresh/吊销（admin 与 viewer 角色，§13.1）
│   │   │   ├── deps.py           # 依赖注入：CurrentViewer / CurrentAdmin / DB session / ES client
│   │   │   ├── errors.py         # 统一错误码 + 异常→HTTP 映射（§8.9）
│   │   │   ├── http.py           # httpx 客户端（平台间 pull/回写用，§8.7）
│   │   │   ├── log.py            # structlog/logger 统一（入参出参 debug，CLAUDE 规范）
│   │   │   └── audit.py          # config 变更 / 人工操作审计写盘（§13.5）
│   │   ├── models/               # SQLAlchemy ORM（§5.1，与 DDL 一一对应）
│   │   ├── schemas/              # pydantic：事件接收、API request/response、D19 信封
│   │   ├── consumer/
│   │   │   ├── main.py           # 每 agent 一消费协程组；批量拉取→处理→提交
│   │   │   ├── validate.py       # 事件契约强校验（§4.1）
│   │   │   ├── mask.py           # 脱敏复核（SDK 掩码核对，仅校验不还原，§13.4）
│   │   │   └── es_dispatch.py    # 事件→ES ingest（事件/日志分 index、_id 幂等）
│   │   ├── analyzer/
│   │   │   ├── trace_state.py    # 判定态持久化（§4.3 累积态表）
│   │   │   ├── classify.py       # L1/L2 分层判定 + L2 OR 门控（§6.1）
│   │   │   ├── cluster.py        # 归一化、去重、聚类窗口（§6.2）
│   │   │   └── metrics.py        # 实时 agg 计算辅助（看板查询侧在 api）
│   │   ├── converter/
│   │   │   ├── envelope.py       # D19 信封构造（schema_version / evidence / assert 区，§6.3）
│   │   │   ├── no_fallback_cfg.py# 组装时固化 fallback_utterance 词表快照（§6.3 step3/§7.1）
│   │   │   └── backflow.py       # pull-API 服务端 + 激活/驳回/回查 回写处理（§8.7）
│   │   ├── worker/
│   │   │   ├── judge_scan_job.py # 判定执行方：扫 judged=0 ∧ ttl_until≤now → classify → judged=1（§4.3/§6.1）；顺带清理过期判定行（§4.3/§10.1 purge）
│   │   │   ├── cluster_job.py    # 周期聚类扫描：judged=1 ∧ processed=0 进聚类（§6.2）
│   │   │   ├── assemble_job.py   # cluster→payload 组装（§6.3）
│   │   │   ├── requeue_job.py    # invalidated→assembled 复位（admin 触发；刷新 assembled_ts，§7.4）
│   │   │   ├── claim_ttl_job.py  # claim 复核窗超窗回退 open（§7.6）
│   │   │   ├── recheck_job.py    # claim 后按 fix_version 轮询 offline run → 单错级回查（§7.6/§8.7）
│   │   │   ├── rollup_job.py     # 7d 小时级指标 rollup（§5.3）
│   │   │   └── reentry_job.py    # 观察哨位复发反馈（版本门控，§7.5）
│   │   └── api/                  # 路由（§8 全集）；无 HTTP ingest——上报只走 Kafka（§3.3）
│   │       ├── auth.py  ├── trace.py  ├── metrics.py  ├── clusters.py
│   │       ├── cases.py ├── agents.py ├── config.py   └── offline.py   # 平台间 pull/回写（受信凭证）
│   ├── tests/                    # 单测 + 冒烟（§14）
│   └── docker/                   # Dockerfile
├── sdk/
│   ├── pyproject.toml
│   └── obs_sdk/                  # 见 §11.1
├── frontend/                     # Vue3：页面与路由规格见 §9.2（菜单/数据源）
├── docker-compose.yml            # 仅编排 backend+frontend（交付）；中间件用公共 infra，连接串经 .env 注入（§1.1 部署边界）
├── docs/                         # 观测契约规范 + agent 接入文档（与 §3/§11 同步维护）
└── solution.md / solution_detail.md
```

### 1.3 端到端数据流（一条链看懂）

> 时间驱动 job 周期（均【实现约定】，单飞见 §5.3/§7.6）：judge_scan/cluster/assemble 1min；claim_ttl 10min；recheck 1~5min（轮询 offline run）；rollup 每小时对齐整点；reentry 1~5min；requeue 仅 admin/offline 触发，不设周期。多实例部署时 job 需分布式锁/CAS 抢单飞，防 rollup/recheck/聚类双写。
```
agent 业务 → obs_sdk 打点(内存有界队列) → Kafka obs.agent.<name>
   → consumer(校验/脱敏复核) ──┬──→ ES 事件+日志 index（_id 幂等, ILM30d）
                               └──→ MySQL 判定态 trace_state(累积) → analyzer L1/L2 判定
   → 命中回流 → cluster 聚类去重(7d窗口, error 去重键) → error_cluster(+error_case_link 待生成)
   → assemble_job 组装 D19 信封(快照取 input 实文, no_fallback_config 固化) 
       → error_case_link offline_status=assembled (payload_id 幂等)
   → offline pull-API 拉取 assembled → 建 draft
   → offline 结构自检 → 回写 active/invalidated(rejected)
   → offline 回归 run → run_results 回查 → verify_status passed/failed 单错级
   → passed 触发线上 claim/fixed 流转（§7.6）
```

### 1.4 一期/二期边界在实现层的落地位置（勿误建二期物）

| 二期物 | 一期处理（实现层） |
|---|---|
| 事件字段 `quality` / `retrieve_hit` / session 摘要 | schema 声明但**恒缺省/不采集**；ES mapping **dynamic:false + 显式禁用该字段**（§3.1/§5.2） |
| 信封字段 `session_snapshot` / `retrieve_hit` / assert 区二期项 | schema 占位类型，**组装器不填、恒 null 或缺省**（§9.2） |
| dict_config 键（会话轮数、θ、弃留墙阈值等） | 键不存在于 v1 dict_config 表（不建配置项，清单 §10.2）；UI 分「v1 生效 / 二期规划（灰置）」两组（§9.1/§9.2 配置页） |
| UI：quality 出口、弃留墙、L3 质量 tab、trace quality 过滤 | **整条隐藏不可达**（不做空 tab）；仅原始事件 JSON 展示不可避免暴露 `quality:null` 时附行内提示（§10） |
| `error_cluster` L3 判据、证据签名去重 | 不实现；v1 去重只用 error 去重键（§6.2） |
| needs_review | v1 源 = claim 回归 error run 结果行的判定产物，reason 值域 = {`na`（na 结果行；**cluster 级单点、退批 v1.5**）、`unclean_run`（含**环境级** na run 内 pass 行，v1.5 窄化；批聚合 = 仅 unclean_run 批）、`reentry_same_version`（reentry 产物同版本 claim 的旧 run pass 行，claim 级单条）、`input_truncated`（复现输入截断证据不可信，claim 级单条，v1.6 R-10）}；聚合归属/流转见 §7.6 判定语义 v1.5/v1.6；判分 na/会话快照不足等其它常态触发源仍二期/D18 不回流 |

### 1.5 命名与口径约定（实现约定，写入项目 .editorconfig / CONTRIBUTING）

- DB/字段：`snake_case`；表前缀见 §5.1；时间列 `DATETIME(3)` 存 **UTC**；展示层本地化。
- 事件字段：`snake_case`；`@timestamp`（ES）为毫秒 epoch。
- API：REST，`/api/v1/...`；分页统一 `page/page_size`，返回 `{items, total, page, page_size}`。
- 错误码：`ERR_模块_序号` 见 §8.9。
- 时间窗口统一口径：错误聚类窗口 7 天、【实现约定】以「error_cluster 首现时间」滚动；config 键见 §10.1。
- 标识符一律英文；注释/文档中文（项目规范）。

### 1.6 开发环境与本地跑通（P0 首日目标）

1. 主 `docker-compose up` 只编排 **backend + frontend**（不内置任何中间件）；本地端口映射直连不经网关。MySQL/ES/Kafka 连**公共 infra 的 dev/test 实例**：endpoint/账号/凭证经 `.env` 注入（不入镜像、不入仓库）；infra 暂无 dev 实例时，本地另起 `compose.infra.dev.yml`（**非交付物**，仅个人开发辅助，不进主 compose、不进 CI）。
2. `alembic upgrade head`；`seed.py` 建首 admin（`init_admin`，§13.1）与 4 个 agent 行 + 空 interface 字典。
3. 冒烟：`tests/smoke` 里手工 Kafka producer 投一条合法 request+llm_call 事件 → trace 可查、看板出现计数 → 完成 P0 验收（§14.1）。
4. backend 依赖：`httpx` 用于平台间；consumer 建议 `aiokafka`（【实现约定】异步消费组），测试用 `kafka-python` 直连亦可——**若 aiokafka 与本环境冲突，回退同步 `kafka-python` + 线程池，不影响其余设计**。

### 1.7 模块实现顺序依赖（指导排期，细化见 §14 验收）

```
P0(骨架): models+migrate → consumer(校验/脱敏/ES分派) → ES 索引 → api/trace 查询 → sdk 雏形 → 链路冒烟
P1(两维): analyzer 判定态+ES 实时 agg+metrics API → 看板+全站纵览前端 → gq/cs/sp 接 SDK（cc 仅 HTTP 层）
P2(回流): analyzer 聚类/去重 → converter 信封+落库 → offline pull-API/回写/回查 → 前端回流页
          → worker(jobs) → 端到端回归闭环验收 + 兜底吸收基础可见性验收
```

各 worker job 依赖其数据表先建（§5.1）与判定逻辑先落地（§6），job 与 API 可并行。

---

---

## 2. 统一事件契约（字段级规格）

> 依据：solution.md §4.1~§4.6。**契约即标准**：schema 由 backend `schemas/event.py` 定义并强校验；SDK 序列化必须与本文一致，禁止 agent 自定义覆盖标准字段。下表「校验」列 = 消费侧强校验（§4.2）与 SDK 侧自校验共用同一份规则。

### 2.1 顶层字段规格

| 字段 | 类型 | 必填 | 含义与规则 |
|---|---|---|---|
| `schema_version` | str `"1.0"` | ✅ | 事件 schema 版本。消费侧不认版本丢弃并计数（§4.2） |
| `event_kind` | enum | ✅ | `event`（节点事件）/ `log`（日志行）。决定落哪个 ES index（§5.2） |
| `trace_id` | str ≤64 | ✅ | 网关 `X-Request-ID`；无网关由 SDK 兜底生成 UUID。trace 内唯一 |
| `agent` | str | ✅ | agent 标识，见 §10 agent 表。与 Kafka topic 归属必须一致（§3.3 校验） |
| `agent_version` | str? | 否 | agent 部署版本，SDK init 从环境注入（R5 回查版本锚定源，§7.3）；可空但 gq/cs/sp 建议必填 |
| `interface` | str ≤256 | ✅ | 归一化接口：`METHOD /path`。动态段归一化为 `{id}`（见 2.6） |
| `node` | enum | ✅ | `request/llm_call/tool_call/retrieve/db/redis/log`（2.3） |
| `seq` | int ≥0 | ✅ | trace 内全局单调自增；根 request=0；log 行也占 seq 槽位（2.4） |
| `branch` | int ≥0 | 否 | 并行分支标注（纯文本标记，不入幂等键与引用） |
| `parent` | int? | ✅(非根) | 父节点 seq；request=null。引用始终按 seq（无歧义） |
| `ts` | int ms UTC | ✅ | 事件时间。消费侧迟到判定依据（§4.3 水位） |
| `duration_ms` | int | request/llm_call ✅ | 该节点耗时；其余节点可空 |
| `status` | enum | ✅ | `ok/error/timeout` 三态互斥；timeout 由 SDK 按接入约定阈值打标（§10.1 `timeout_ms` 键），平台不二次判 |
| `error_type` | enum? | status=error 时 ✅ | §2.5 错误分类全集 |
| `error_msg` | str ≤512 | 否 | 脱敏错误摘要（键级掩码后截断） |
| `input` | obj/str? | 否 | 入参，序列化前**键级掩码**；取数接口传查询词脱敏。展示/检索受 §2.7 控制 |
| `output` | obj/str? | 否 | 出参/答复摘要（脱敏）。仅 request 节点建议带；正文展示面控制同 input |
| `usage` | obj | llm_call ✅ | `{prompt_tokens, completion_tokens, total_tokens}`，非负 int |
| `model` | str? | llm_call ✅ | 模型名（如 `deepseek-v3`） |
| `quality` | obj? | 否 | **【二期】** `{level, reason}`；v1 不采集、恒缺省，SDK 不得填充（2.8） |
| `retrieve_hit` | obj? | 否 | **【二期】** `{hit_count, top_score, query_hash}`；v1 不采集、恒缺省（2.8） |
| `log_level` | enum? | log ✅ | `DEBUG/INFO/WARNING/ERROR` |
| `log_message` | str ≤8K | log ✅ | 日志正文（键级掩码 + 截断） |
| `extra` | obj | 否 | agent 自定义扩展，仅允许白名单键（见 2.9） |

### 2.2 样例（三份，供 SDK 单测与消费侧契约测试直接使用）

**① request 根节点（error 透传，L1 现场）**
```json
{
  "schema_version": "1.0", "event_kind": "event",
  "trace_id": "tr-9f2c1a", "agent": "good-question",
  "agent_version": "2026.08.31-r47",
  "interface": "POST /api/chat/{id}", "node": "request",
  "seq": 0, "branch": 0, "parent": null,
  "ts": 1785897600000, "duration_ms": 3200,
  "status": "error", "error_type": "llm_timeout", "error_msg": "provider timeout after 3000ms (masked)",
  "input": {"session_id": "{id}", "question": "帮我查一下XX政策"}, "output": null,
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
  "model": null, "quality": null, "retrieve_hit": null,
  "log_level": null, "log_message": null, "extra": {}
}
```

**② llm_call 子节点（最终失败，request ok——兜底劣化现场；埋点前提见 2.3.2）**
```json
{
  "schema_version": "1.0", "event_kind": "event",
  "trace_id": "tr-9f2c1a", "agent": "good-question", "agent_version": "2026.08.31-r47",
  "interface": "POST /api/chat/{id}", "node": "llm_call",
  "seq": 1, "branch": 0, "parent": 0,
  "ts": 1785897600000, "duration_ms": 3000,
  "status": "error", "error_type": "llm_interface_business", "error_msg": "upstream 502 (masked)",
  "input": null, "output": null,
  "usage": {"prompt_tokens": 812, "completion_tokens": 0, "total_tokens": 812},
  "model": "deepseek-v3", "quality": null, "retrieve_hit": null,
  "log_level": null, "log_message": null, "extra": {}
}
```

**③ 日志行（同 trace，占 seq 槽位）**
```json
{
  "schema_version": "1.0", "event_kind": "log",
  "trace_id": "tr-9f2c1a", "agent": "good-question", "agent_version": "2026.08.31-r47",
  "interface": "POST /api/chat/{id}", "node": "log",
  "seq": 2, "branch": 0, "parent": null,
  "ts": 1785897600500, "duration_ms": null,
  "status": "ok", "error_type": null, "error_msg": null,
  "input": null, "output": null, "usage": null, "model": null,
  "quality": null, "retrieve_hit": null,
  "log_level": "WARNING", "log_message": "retry attempt=2 will retry in 800ms",
  "extra": {}
}
```

### 2.3 节点类型与打点要求（落地清单）

| node | 必备 | 打点要求 | 指标锚点 |
|---|---|---|---|
| `request` | 必须 | 一次 HTTP 请求端到端一条；status 三态；output=答复摘要 | 维度2 请求级（§4.5） |
| `llm_call` | LLM 类 agent 必须（cc 除外） | **逻辑调用**：内部退避重试为 attempt 不拆条，最终成功 `status=ok` 不出错；**最终失败标 error**（2.3.2） | 维度2 LLM 调用级 |
| `tool_call`/`retrieve` | 有 function calling/检索的 agent | 一次工具/检索调用一条；v1 不填 `retrieve_hit`（2.8） | 不参与指标（子节点计数可展示） |
| `db`/`redis` | 建议 | 单独打点；耗时入该节点；失败 `status=error` 走 L2 候选 | 不参与指标 |
| `log` | 建议 | `structlog`/日志 handler 捕获；占 seq 槽位 | — |

**node 兼容性**：`query`/`search` 等同义节点**不得自创**——取数统一 `retrieve`（向量检索）或 `tool_call`（工具/DB 查询），由接口字典归一（§8.5）。

### 2.4 锚点语义与打点规约（v3.5.1 口径落地）

1. `request` 只承载请求级指标；**异常判定/回流是 trace 级聚合**（§4.3），不以 `request.status` 单点定论。
2. 回流判定依据 = trace 内 LLM 动态事实（出现 `llm_call` 或 `llm_*` error），不依赖接口字典 `llm` 标记；**L2 门控例外** = trace 动态事实 **OR** 接口字典 `llm=true`（首次 llm_call 前的程序错误也能回流，§6.1）。缓存命中（无 llm_call 的 trace）不出回流。
3. **【埋点前提·关键】LLM 最终失败无论上层是否 catch 转兜底，`llm_call` 一律 `status=error`**：SDK 打点须包住裸调用，异常先记后传（先记 error 事件、再抛给业务兜底分支）。这是「request ok + llm_call error」兜底劣化现场能被一期基础可见性（指标 §4.5 + trace 红显）捕捉的前提，验收用例见 §14.2。
4. `interface` 动态路径归一化规则（SDK 侧实现，消费侧复核）：
   `{session_id}` `{review_id}` `{task_id}` `{job_id}` `{document_id}` `{report_id}` → 段值一律替换为 `{id}`（多动态段各替换）。带 query string 的入参不并入 interface。
5. **seq 单一计数器**：节点事件与日志行共用 trace 内 contextvar 原子计数，log 行也占槽位（否则与节点 `_id=sha256(agent|trace_id|seq)` 互覆，§5.2）。`branch` 仅标注并行分支、不产生独立计数。

### 2.5 错误分类（error_type）全集与分层映射

| error_type | 判定语义（SDK 打点侧） | 回流层 | 说明 |
|---|---|---|---|
| `llm_timeout` | provider 超时透传到接口 error | **L1** | 最终失败且错误暴露为接口错误 |
| `llm_rate_limit` | 限流且未自愈、透传 error | **L1** | |
| `llm_connection` | 连接失败/断连透传 error | **L1** | |
| `llm_context_exceeded` | 超上下文透传 error | **L1** | |
| `llm_empty_response` | 空响应透传 error | **L1** | |
| `llm_parse_error` | 解析失败透传 error | **L1** | |
| `llm_other` | 其他 provider 层失败透传 error | **L1** | 预留兜底 |
| `llm_interface_business` | LLM 相关接口上的程序错误（含 LLM 错被 catch 转抛为业务错误） | **L2** | LLM 相关判定见 §6.1 OR 门控 |
| `external_non_llm` | 外部服务（非 LLM）调用失败 | **L2** | 同上 |
| `db_error` / `redis_error` | DB / Redis 访问失败 | **L2** | 同上 |
| `auth_error` / `validation_error` 等 | 非 LLM 接口业务错误 | 不出回流 | 出指标、出 trace |

**catch 转抛归属规则**（L1/L2 边界，SDK 侧必须按此打标）：
- LLM provider 错误未被业务 catch、直接冒泡成接口错误 → 接口标 `llm_*`（L1）。
- LLM 错误被业务 catch 后转抛为自身业务/程序错误暴露给客户端 → 接口标 `llm_interface_business`（L2）。
- `llm_call` 子节点只采集、不单独定层；最终层由 request.error_type 表达。

### 2.6 脱敏（键级掩码，SDK 完成，平台只复核不还原）

掩码键正则（平台标准，SDK 复用 offline `mask_dict` 提升版）：
```
authorization | token | password | secret | api[_-]?key | fernet | credential
| auth_config | cookie | set-cookie | x-api-key | private[_-]?key | access_token | refresh_token
```
- 作用范围：序列化前对 `input/output/extra/log_message` 递归掩码命中键 → 值替换 `***`。
- 消费侧脱敏复核（§4.2 step3）：检出未掩码敏感键 → 打回/丢弃并计数告警（自监控）。
- 平台**不存还原逻辑**；键级掩码 ≠ 内容级脱敏——地址/合同正文/证件号等由采集策略控制（2.7）。

### 2.7 正文/入参采集与展示面控制（D14 + input 同级约束，v3.5.1）

| 控制点 | 一期规则 |
|---|---|
| 采集开关 | 正文 `output` 与入参 `input` 的 **可检索/可展示** 面**默认关**；需要还原"当时如何答复/入参为何"的接口（优先对话类）逐接口评估开启（§8.5 interface.body_search 标记）；落库前内容型最小化 |
| 截断 | `input/output/log_message` 单条 ≤ **8K 字符**；`error_msg` ≤512；超长截断须保留语义头（【实现约定】前 8K，不按 UTF-16 半字截断告警处理） |
| 权限 | 查看 `input/output` 需 viewer 及以上 + 该接口 `body_search=true`；统一 viewer 无 per-agent 授权域（R2） |
| 保留期 | 随事件 ILM 30 天，不独立延长 |

> v1 无会话历史摘要（N 轮收敛二期，C1），`input` 仅当前请求 `input_turns`；因此本表是 v1 唯一正文/入参暴露面。错误现场快照（§5.1④ `input_snapshot`）与正文同级约束。

### 2.8 二期占位字段约束（勿实现、勿误传）

| 字段/机制 | 一期约束 |
|---|---|
| `quality` / `retrieve_hit` | schema 声明类型、**恒缺省**；SDK 不填充；ES mapping 对应字段**显式禁用索引**（dynamic:false 兜底，§5.2）；后端 schemas 保留定义供二期 |
| 会话上下文摘要（N 轮）、`session_state` 钩子 | v1 无对应 SDK 采集方法、无信封字段填充（§7.1）；`record_quality/record_retrieve/record_session_state` 不在 v1 SDK 暴露（§11.1） |
| `agent_version` 空值 | 允许，但回流链路建议 trigger_version 非空（仅溯源；回查锚定 fix_version 见 §7.6） |

### 2.9 `extra` 白名单（agent 扩展，消费侧丢弃白名单外键）

- 白名单【实现约定】：`{request_id, task_id, job_id, conv_id, sub_agent, prompt_kind}`。其余键整条丢弃并计数（自监控）。任何新增扩展键须回平台评审加白。

---

---

## 3. 采集与上报传输（SDK 内嵌 + Kafka）

> 依据：solution.md §5。本文只定**采集链路与传输契约**（任何 agent 通用）；SDK 打点 API 的逐调用签名、structlog/双通道覆盖细节与 4 个 agent 的存量整改清单放 §11。

### 3.1 SDK 采集链路（有界、异步、可降级；本地一张状态机图）

```
agent 业务线程
   │ record_*()  → contextvar(trace_id/seq/branch) 组装事件 dict（含键级掩码）
   ▼
内存有界队列  (≤2000 条【实现约定】；写满 → 丢弃并计数 + 降级告警，绝不阻塞业务)
   │ 批量冲刷 ≤500 条 / ≤2s 先到先发
   ▼
kafka-python producer (topic obs.agent.<name>)
   │ 失败退避 ≤3 次
   ▼
本地磁盘兜底文件（默认持久卷，路径可配；写入即视为已提交）→ 后台恢复线程补传成功块后删除
```

### 3.2 可靠性规约（对应 §16「SDK 绝不影响业务」风险行）

| 环节 | 规则 |
|---|---|
| 内存队列 | 有界；写满**丢弃并计数**（不无限阻塞）；丢弃计数进 SDK 自监控 |
| 批量 | ≤500 条 或 ≤2s（先到先发）；同 trace 事件尽量同批（【实现约定】按 (agent, trace_id) 分组尽量保序） |
| 失败处理 | producer 发送失败退避重试 ≤3 次；仍失败写本地兜底文件 |
| 本地兜底 | **默认挂持久卷**（`OBS_SDK_SPOOL_DIR` 可配，不写死 `/tmp`）；容器重启不丢；恢复补传成功块后删除 |
| 自监控 | 上报成功率 / 丢弃量 / spool 存量 → 平台自身可观测（走单独指标事件或 heartbeat，见 §3.6） |

### 3.3 Kafka 契约与上报鉴权（R3：首版即上 ACL）

| 项 | 值 |
|---|---|
| broker | KRaft 单 broker；`auto.create.topics=false`（先建 topic 后发凭证，防投毒） |
| topic 划分 | 每 agent 一个 `obs.agent.<name>`（name = agent 标识，§10 agent 表）+ 自监控 `obs.selfmonitor`（§3.6）；**partition=1**（同 trace 近似保序）；共享集群租户带 `{env}.` 前缀（§12.2 O-7）。**topic/ACL/消费 group 由平台向 infra 申请落权后凭证才生效**（§13.2），平台无 broker 建删权 |
| SASL/TLS | 开启；每 agent 独立凭证（`agent_credential` 表映射 producer 身份，§5.1⑨），topic 级 ACL：`obs.agent.<name>` 仅该 agent 可写、仅 backend consumer principal 可读；自监控 topic 与消费 group principal 同建同绑（§13.2）；agent 间不可互写 |
| 消息体 | 单条 JSON 事件（§2.1），消息内必带 `agent` 字段，消费侧与 topic 归属**双重校验**（不一致整条丢弃计数，§4.2） |
| 幂等 | Kafka 幂等 producer（`enable.idempotence=true`）；消费侧 ES `_id` 幂等吸收 at-least-once（§5.2） |

### 3.4 时间口径与时钟漂移

- 事件 `ts` 由 agent 本地时钟打点。消费侧对 `ts` 明显偏离设定漂移窗【实现约定：与消费侧现时差 > 24h 记漂移告警】**只告警不丢弃**（丢弃会破坏"恢复补传不丢"，§4.2）。
- `ts` 用于 `(ts, seq)` 顺序还原与水位；判定与聚类以**消费侧落库时间与事件 ts 双口径**并存（§4.3/§6.2 用事件 ts 归窗）。

### 3.5 SDK 与 agent 集成约束（详见 §11 各 agent 整改）

- `init()` 读取部署环境注入 `agent_version`（`AGENT_VERSION` 变量；未配置字段空不拒收，接入验收判不过）。
- 双接入：stdlib `logging.Handler` + structlog processor（sp 例外约束见 §11.3）。
- **init 时序**：必须在 agent 日志体系装配（`structlog.configure`/`setup_logging`）之后执行，防覆盖（§11.3）。

### 3.6 SDK 自身观测信号

**自监控信号（v1.1 裁定）**：用专用 topic `obs.selfmonitor`（与业务 topic 同建同 ACL，§3.3/§13.2）承载每 agent **心跳** `{agent, sent_ok, dropped, spool_pending, ts}`（1/min，随批次 flush 附带发送，不单独起连接）。backend 消费后写入事件 index（以 `node=heartbeat` 区分，不进入业务 node 枚举），前端 /admin/agents 页出「agent 上报健康」小卡——数据源 = §8.5 `GET /agents/{id}/health`（聚合最近 1min/5min 心跳；**未接入=无 last_seen**，供 §9.1 EmptyState 区分「未接入 vs 无流量」）。自监控不占用业务事件指标，心跳发送失败不重试惩罚（不干扰上报主链路）。

> 二期占位：`record_retrieve`/`record_quality`/`record_session_state` 不在 v1 SDK 暴露（§11.1 方法清单）。

---

## 4. 消费与处理（online 侧 worker）

> 依据：solution.md §6。consumer 是唯一 Kafka 消费方；产出两条支路——(a) ES 入库（维度1/2/3 查询源）、(b) MySQL 判定态累积（维度3 判定源，不依赖 ES 回读，§4.3）。

### 4.1 消费流水线（consumer/main.py 主循环）

| 步 | 处理 | 产物 / 异常处理 |
|---|---|---|
| 1 订阅批量拉取 | 订阅 `obs.agent.*`（每 agent 独立消费组/协程组），批量拉取 | — |
| 2 校验 | schema 强校验（§2.1 校验列）：必填、枚举、`agent` 与 topic 一致、interface 与字典匹配；`ts` 漂移只告警不丢弃（§3.4） | 校验失败整条丢弃 + `selfmonitor.dropped` 计数；interface 不匹配字典 → 自动注册为未知接口（§8.5 待补 llm 标记） |
| 3 脱敏复核 | 递归检测未掩码敏感键（§2.6） | 命中 → 丢弃并计数告警（平台不还原） |
| 4 trace 累积态 | per-trace 累积缓冲更新 + 落 MySQL 判定态表（表 `trace_judge_state`，§5.1⑩）：root 到达 / 子节点 error 汇入两态迁移；**root 到达同刻落 `input_snapshot_clean`（脱敏截断≤8K 明文快照）+ `input_truncated`（原始>8K 判截断置 1，v1.7 R-18）**；**判定不在本步执行**（judge_scan_job 到期判，§4.3）；**v1.9 R-21 root-late 例外：root 到达且判定态已 `judged=1`（残 trace 已按子节点判过）→ 不重跑整 trace，本步对 root 级触发一次补判（§4.3④/§4.4 幂等）** | **写失败 → 不提交 offset + 退避重试 + 自监控计数**；禁止"丢弃并提交"（丢判定态=该 trace 永不回流且 offset 已推进不可找回，§14.2） |
| 5 ES 分派 | `event_kind` 分流：event→事件 index、log→日志 index；`_id=sha256(agent|trace_id|seq)` | ES 写失败 → 落待补写 spool（恢复回填）或显式丢弃并在该小时 rollup 标缺口（§5.3），**不静默丢**（丢了=7d 指标/迟到回填永久少计）；重投由 `_id` 幂等覆盖。**分析/回流不依赖 ES**（判定源=step4 判定态） |
| 6 offset/重试 | 处理后提交 offset；失败重试队列，超阈值丢弃计数 | 自监控暴露 |

### 4.2 校验规则明细（validate.py 与 §2.1 校验列共用）

- 必填缺 / 类型错 / 枚举外值 → 丢弃（计数 `dropped.schema`）。
- `event_kind=log`：只允许 log_level/log_message；`input/output/usage/model` 必须空。
- `event_kind=event`：`node=request` 必须 seq=0 且 parent=null（与 2.4 冲突整条丢弃）；`duration_ms` 缺失补 0 不丢弃（告警计数）。
- `interface` 格式：`METHOD /path`，非 HTTP 路径/空 → 丢弃计数。
- `agent` 与 topic 归属不一致 → 丢弃计数（防跨 agent 伪报，§3.3）。

### 4.3 trace 累积判定态（决策 R1 + 判定态持久化，表 `trace_judge_state` §5.1⑩）

**目的**：判定"该 trace 是否需回流"基于**消费侧跨 SSE/多批/子节点分批到达的完整累积态**，非单事件自判断；重启/重平衡从 MySQL 重建缓冲，不依赖 ES 回读。

| 状态要素 | 字段 | 迁移 |
|---|---|---|
| 子节点 error 汇总 | `err_summary_json`（条目数组，每条 = `{error_type: 原值枚举，与 error_cluster.error_type 同值域，禁 L1/L2 分类键, error_msg: 脱敏 ≤512, count}`，顶层 `agent_version`；L2 判定/聚合消费按原值分组还原，v1.6 R-6 钉死） | 每个 error 子节点到达更新 |
| root 是否到达 | `root_ok` | `node=request` 到达置 1（记 request ts/interface/status/input_hash + **落 `input_snapshot_clean` 明文快照 / `input_truncated` 截断标，v1.7 R-18**） |
| 是否已判定 | `judged` | L1/L2 判定 + per-trace 归并完成后置 1（判 false 不再重复判定） |
| 完成窗口 | `ttl_until` | = 最后事件 ts + 完成窗口 + 宽限（【实现约定】窗口 60s + 宽限 300s，§6.1）；过期行惰性清理 |

**判定时机**：
1. root 到达且 trace 判定未做 → 等窗口内补采迟到的子节点（SSE/多批）：root 到达即标记可判定，待窗口闭合后判定；
2. **残 trace（root 未到达但已有子节点 error）不悬挂等待**——按已有子节点判定（防超长 SSE 连接长期不闭合导致漏判；§4.3 规则与 §6.1 判定共用）；
3. `judged=1` 后判定产出进聚类（§4.4），处理完置 `processed=1`，防止重放重复进聚类（judged/processed 分离，见 §4.1 step4/§5.1⑩）。
4. **root-late 补判（v1.9 R-21）**：root 在 `judged=1` 之后才到达（root_ok 0→1，即残 trace 判定已按子节点 error 归因、root 的 error 因迟到未参与聚类）且 `root_status ∈ {error, timeout}` → **不重跑整 trace、不推翻已判结果**——仅对迟到 root 级**补一次候选**（step4 root 到达同刻触发，非 judge_scan_job 到期；候选 = root_error_type 经 §6.1 L1/L2 值域筛，命中才产）→ 复用 §6.2 聚类：同键已有 cluster → count+1/补快照；异键 → 开新 cluster；同键已 closed（fixed/inactive）→ 跳过不翻案。补判原子性 = root 到达事务内 CAS `root_late_complement`（§4.4/§5.1⑩），防重放/多实例重复补候选。

**判定执行方（v1.1 裁定）**：consumer/step4 只更新累积态与 `ttl_until`，**不做判定**。到期判定由 `judge_scan_job`（worker，周期 1min，§1.2/§1.3）扫 `judged=0 AND ttl_until≤now()` → classify（§6.1）→ 写 `judgement_json`+`judged=1`，随后进聚类（§4.4 置 processed）。残 trace/root 未达同规则，`ttl_until` 以最后子节点事件 ts 起算（§5.1⑩ idx_judge_scan 定位）；`judged=1` 后重复到期不重判。judge_scan_job 顺带清理 `processed=1` 且超 `trace_judge_purge_days`（默认 7 天，§10.1）的过期判定行——判定态只在完成窗口+清理保留期内停留，不膨胀。

**判定输出（classify.py → §6.1）**：trace 层一次产出 `{agent, interface, root_status, root_error_type, err_summary, llm_fact_ok, layer(L1/L2/none), candidate_error_sets[]}`，per-trace 归并后交给聚类（§6.2）。quality 信号二期才入累积态（v1 不采集，§2.8）。

> **判定固化 gate 语义边界（v1.14 用户拍板：接受现状、仅注记不动判定代码）**：`judged=1` 后「重复到期不重判」对 **gate 关闭窗口内判 `none` 的 trace 同样成立**（gate-close 行也按 judged=1 处理——与 backflow_allow=0/agent_enabled 关停同属配置态关闭的幂等固化，判定 CAS 单行只推进一次）。语义 = **关闭即"暂停该 agent 回流"**：之后配置回摆**不回填**这些已固化判定；归因/排障以 `judgement_json.gate` 快照（判定时各 gate 布尔）为准，而非现时配置。

### 4.4 幂等与位点（表 `trace_judge_state` §5.1⑩ + §6.2 唯一索引兜底）

- MySQL 侧幂等三件套：`trace_judge_state`（已判定集合）+ `error_cluster` 唯一索引（agent+去重键+generation，§6.2）+ `error_case_link` 幂等键（`payload_id`，§6.3 step4）。
- **root-late 补判幂等（v1.9 R-21）**：`trace_judge_state.root_late_complement`（TINYINT 默认 0，§5.1⑩）= root 迟到补判已触发标记。root 到达事务内 CAS 0→1 成功才触发 §4.3④ 补候选；CAS 失败（已 1）→ 跳过（重放/多实例重复投递不重复补、不重复聚类计数）。
- 消费/分析多实例、offset 重投/进程重启：不重复判定、cluster 计数不虚增、不重复建 case（唯一索引冲突即视为已建，跳过错杀计数）。

### 4.5 顺序与还原（供 ES 查询侧与 trace 视图共同依据）

- partition=1 保证相对有序；链路树还原统一按 `(ts, seq, parent)`（父引用 = trace 内全局唯一 seq，无歧义；并行分支按 `(ts, seq)` 排序）。
- trace 详情视图（§9.1）据此重建树形 + 红显 `status=error/timeout` 子节点。

---

---

## 5. 数据层（MySQL `obs` + ES + rollup）

> 依据：solution.md §7。DDL 为**目标形态**（Alembic 迁移需在 v3.5.1 语义下对齐）；所有 `DATETIME(3)` 存 UTC。

### 5.1 MySQL（库 `obs`）——表设计与 DDL

枚举值先行（Alembic 内用 CHECK/ENUM，均含语义注释）：

| 枚举 | 值 | 语义 |
|---|---|---|
| `cluster.status` | open / claim / fixed / inactive / needs_review | §7.6 状态机 |
| `error_case_link.offline_status` | assembled / draft / active / invalidated | assembled=已组装待 offline 拉取；draft=已拉取；active=offline 已激活；invalidated=offline 驳回/人工失效（v1=error 结构自检失败） |
| `error_case_link.verify_status` | pending / passed / failed / invalidated / superseded | superseded 不抹历史 passed |
| `error_case_link.case_type` | `regression_error`（v1；二期加 `regression_quality` 需回方案） | 与 pull-API 白名单一致 |
| `user.role` | admin / viewer | 平台三域之一 |
| `conversion_record.closed_by` | auto_regression / admin_review | 置 fixed 依据 |
| `agent_credential`（Kafka 凭证） | 见 §13.3 | 与 topic/ACL 映射 |

```sql
-- ① 平台账号（独立体系，viewer/admin 两角色，不做独立 role 表）
CREATE TABLE `user` (
  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(64)  NOT NULL,
  password_hash VARCHAR(128) NOT NULL,              -- bcrypt
  display_name  VARCHAR(64)  NULL,
  role          ENUM('admin','viewer') NOT NULL DEFAULT 'viewer',
  status        TINYINT NOT NULL DEFAULT 1,          -- 1 启用 0 禁用
  created_at    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_user_username (username)
) COMMENT='平台账号（viewer/admin）';

CREATE TABLE `user_session` (                        -- JWT refresh 会话
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id      BIGINT UNSIGNED NOT NULL,
  refresh_hash CHAR(64) NOT NULL,                    -- sha256(refresh_token)
  expires_at   DATETIME(3) NOT NULL,
  revoked_at   DATETIME(3) NULL,
  created_at   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_session_refresh (refresh_hash),
  KEY idx_session_user (user_id)
) COMMENT='登录会话（refresh token 吊销）';

-- ② agent（自发现注册 + 字典宿主）
CREATE TABLE `agent` (
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name         VARCHAR(64)  NOT NULL,                -- good-question / customer-service / contract-check / smart-procurement
  display_name VARCHAR(64)  NOT NULL,
  base_url     VARCHAR(255) NULL,
  enable       TINYINT NOT NULL DEFAULT 1,
  route_source ENUM('fastapi','openapi','manual','auto_register') NOT NULL DEFAULT 'auto_register',
  backflow_allow TINYINT NOT NULL DEFAULT 1,         -- 维度3 白名单；cc=0（D18）
  created_at   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_agent_name (name)
) COMMENT='agent 字典';

-- ③ interface 接口字典（online 自发现；key=与事件 interface 同串）
CREATE TABLE `interface` (
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  agent_id     BIGINT UNSIGNED NOT NULL,
  interface    VARCHAR(256) NOT NULL,                -- 同事件字段：`POST /api/chat/{id}`
  method       VARCHAR(8)   NULL,                    -- 拆出便于 UI（可选）
  path         VARCHAR(256) NULL,
  llm          TINYINT NOT NULL DEFAULT 0,           -- 看板分类标记（自动补标/人工）
  llm_source   ENUM('config','manual','auto_observed') NULL,
  llm_suspect  TINYINT NOT NULL DEFAULT 0,           -- 疑似漏标观察窗内
  body_search  TINYINT NOT NULL DEFAULT 0,           -- 正文/入参可检索可查看开关（§2.7），默认关
  status       TINYINT NOT NULL DEFAULT 1,
  first_seen_ts DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  last_seen_ts  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_by   VARCHAR(64) NULL,
  UNIQUE KEY uk_interface (agent_id, interface),
  KEY idx_interface_llm (agent_id, llm, llm_suspect)
) COMMENT='接口字典（事件自动注册 + llm 补标）';

-- ④ error_cluster 错误聚类（去重键 + generation + 代表快照含 input 实文）
CREATE TABLE `error_cluster` (
  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  agent         VARCHAR(64)  NOT NULL,
  interface     VARCHAR(256) NOT NULL,
  layer         ENUM('L1','L2') NOT NULL,            -- v1 只有 error 层；L3 二期另表/另判
  error_type    VARCHAR(48)  NOT NULL,               -- error_type 原值（llm_timeout…）
  input_hash    CHAR(64)     NOT NULL,               -- sha256(normalize(input))，normalize=strip+折叠空白+截断上限 8192（v1.6 R-10：4096→8192 对齐复现截断 ≤8K，防去重键粒度 < 复现粒度漂移；一期上线前定稿无存量迁移）
  input_snapshot MEDIUMTEXT   NULL,                  -- 代表事件 input 实文（脱敏+截断≤8K，v3.5.1 扩存；组装取数源，不依赖 ES 回读）
  input_truncated TINYINT     NOT NULL DEFAULT 0,     -- 复现输入源原始 input>8K 被截断（v1.6 R-10 + v1.7 R-18：判定时点 = §4.1 消费 step4 root 到达时判打点原始 request.input>8192 置 1 落判定态 trace_judge_state，§4.3——唯一见原始明文处；本列自判定态 input_truncated 复制。H7-1 曾标「cluster 首现判」已下钻：聚类/组装仅见 ≤8K 截断快照不可判，勿在聚类/组装判）；置 1 → 该 claimed case 相关 run pass 不计 K 转 needs_review(reason=input_truncated)，§7.6 v1.6 ②。**v1.8 R-13（判定位窗口化）：本列语义 =「该 cluster 当前判定态」非首现快照——同键窗口内新现 trace 判定态到达开簇/回填时刷新（≤8K 判定态 0 清 0、>8K 置 1，单 trace 即刷，§6.2）；cluster 已 closed 不刷新（终态只读不翻案）；首现截断历史留已产出 needs_review 产物 + 详情警示不抹**）
  error_msg     VARCHAR(512) NOT NULL,               -- 脱敏错误摘要
  first_trace_id VARCHAR(64) NOT NULL,
  trigger_version VARCHAR(64) NULL,                  -- 首现 agent_version（仅溯源）
  first_ts      DATETIME(3)  NOT NULL,
  latest_ts     DATETIME(3)  NOT NULL,
  count         INT NOT NULL DEFAULT 1,              -- 7d 窗口内同键合并计数
  generation    INT NOT NULL DEFAULT 1,              -- 生命周期代数（复发/重开 +1）
  status        ENUM('open','claim','fixed','inactive','needs_review') NOT NULL DEFAULT 'open',
  fix_version   VARCHAR(64) NULL,                    -- claim 时填写（R5 回查锚定版本；error 回流下与 offline run.version 共享版本字面量域、不强行 semver，Task #4-② B-5）
  claimed_by    BIGINT UNSIGNED NULL,
  claimed_at    DATETIME(3) NULL,
  claim_due_ts  DATETIME(3) NULL,                    -- claim 复核窗 TTL（默认14d）
  claim_k       TINYINT UNSIGNED NOT NULL DEFAULT 2, -- claim 时固化的 K（值域 {1,2}，R-1/A1 v1.5；claim CAS 同批写，缺省取全局 dict_config.auto_fixed_k_default=2；TTL 回退 open 重 claim 可改值，观察期零推进可降）
  needs_review_reason VARCHAR(512) NULL,
  created_at    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  -- 去重唯一索引：同代并发首现双写吸收 + 复发代数+1 不与已归档同键冲突
  UNIQUE KEY uk_cluster_dedup (agent, interface, error_type, input_hash, generation),
  KEY idx_cluster_list (status, first_ts),
  KEY idx_cluster_watch (agent, interface, error_type, input_hash)   -- reentry 观察哨位按 error 去重键
) COMMENT='错误聚类（error 去重键 + 快照 + 代数）';

-- ⑤ error_case_link 错误↔offline 回归用例关联（状态机双列 + payload 幂等）
CREATE TABLE `error_case_link` (
  id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  cluster_id     BIGINT UNSIGNED NOT NULL,
  payload_id     CHAR(36) NOT NULL,                  -- D19 幂等键（uuid4；offline upsert 幂等、重拉不重建）
  case_id        VARCHAR(64) NULL,                   -- offline case id（draft 建后回写）
  case_type      ENUM('regression_error') NOT NULL,  -- v1 白名单仅此；二期加值须回方案
  source_trace_id VARCHAR(64) NOT NULL,
  trigger_version VARCHAR(64) NULL,                  -- 仅溯源（错误确存在于 V_obs）
  fix_version    VARCHAR(64) NULL,                   -- 关联 claim 填的修复版本（回查锚定）
  input_truncated TINYINT    NOT NULL DEFAULT 0,     -- 复现输入源原始 input>8K 被截断（v1.6 R-10 + v1.7 R-18：来源链 = 消费 step4 判定态 input_truncated → cluster 复制 → 本列随 link 落；H7-4 补载体：随 D19 信封透传 offline 只读上下文，判定仍如实）
  offline_status ENUM('assembled','draft','active','invalidated') NOT NULL DEFAULT 'assembled',
  verify_status  ENUM('pending','passed','failed','invalidated','superseded') NOT NULL DEFAULT 'pending',
  payload_json   MEDIUMTEXT NOT NULL,                -- D19 信封完整体（重推复用 + pull 重试自足）
  assembled_ts   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  invalidate_reason VARCHAR(512) NULL,
  invalidated_by BIGINT UNSIGNED NULL,               -- 人工 invalidate 操作人（admin）
  created_at     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_link_payload (payload_id),
  cur_key       BIGINT UNSIGNED GENERATED ALWAYS AS (IF(verify_status='pending', cluster_id, NULL)) STORED,  -- 现行位：仅 pending 占位，终态自动释放（v1.1 裁定，见 §5.1 注）
  UNIQUE KEY uk_link_current (case_type, cur_key),   -- 同 cluster 同 case_type 至多一条现行(pending) link；passed/failed/superseded 不占坑（reopen 可再生成，§5.1 注）
  KEY idx_link_pull (offline_status, assembled_ts),  -- pull-API 扫描 assembled
  KEY idx_link_verify (verify_status)
) COMMENT='回流用例关联（offline 镜像 + pull 传输）';

-- ⑥ verify_run_record 复验回查历史（单错级 × 版本时间线）
CREATE TABLE `verify_run_record` (
  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  link_id       BIGINT UNSIGNED NOT NULL,
  run_id        VARCHAR(64) NOT NULL,                -- offline run id
  bound_version VARCHAR(64) NOT NULL,                -- 该 run 绑定的 agent 版本（=fix_version 对应）
  case_pass     TINYINT NULL,                        -- 该 case 在 run_results 的 pass_fail（0/1；null=对应 run_results pass_fail='na'，run 缺行则不产生本记录——Task #4-② B-1(b) 修正）
  run_status    VARCHAR(16) NOT NULL,                -- offline error_regression run 终态字面量（completed/partial_failed/timeout/cancelled；与 verify_status 五值域不同源，勿混用，Task #4-② B-6）
  raw_json      JSON NULL,                           -- run_results 原样留档
  verified_ts   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_verify_run (link_id, run_id)
) COMMENT='回归 run 单错级结果（终态只读：已定 passed/failed/superseded 不被迟到 run 改写，见 §7.6）';
-- 消费注（v1.4，B-11/R6；v1.5 R-1/R-2 修订）：verify_run_record = 跨版本稳定序列 K 的逐版本时间线载体（§7.6 判定语义 v1.5）——每「claimed case 纯净可判」版 error run 终态判定后追加一行（run_status=该版终态字面量）；K 读 claim 固化值 `claim_k`（cluster.claim_k，claim 生命周期内不可变、同 link 时间线共享同值 → 不加逐行快照列，R6 载体承诺保持）；纯净性由 recheck 从「该 case 行 + run 内 na 行的 error_type 影响域（环境/case）」派生，run 级 na_case 不再直接作判据（保留读面：展示/审计/告警）

-- ⑦ conversion_record 回流/人工审计
CREATE TABLE `conversion_record` (
  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  cluster_id BIGINT UNSIGNED NULL,
  link_id    BIGINT UNSIGNED NULL,
  action     VARCHAR(48) NOT NULL,                   -- assemble/claim/ignore/fixed/reopen/requeue/auto_activate/invalidate/…
  detail     VARCHAR(1024) NULL,
  closed_by  ENUM('auto_regression','admin_review') NULL,
  actor_user_id BIGINT UNSIGNED NULL,                -- 系统动作记 NULL（system）
  ts         DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_conv_cluster (cluster_id)
) COMMENT='回流审计（trace→case→人工处置）';

-- ⑦b needs_review_batch error run 判定产物批量聚合载体（Task #4-② B-4 + v1.4 reason 值域 + v1.5 R-2 批纯化：本表**仅承载 unclean_run 批**——同 run 同环境级 error_type 下多个 pass 行 cluster 聚为单条批、不逐 case 置 needs_review；reason 值域 = {unclean_run}；纯 na cluster 退批走 cluster 级单点处置（§8.4 needs-review-resolve）——聚合归属/撞键规避见 §7.6 判定语义 v1.5。**v1.8 R-14/R-15：批引 cluster 保持 claim、不入 needs_review 态 + 详情/列表实时派生「被未决批 Bx 挂起」标注（join link_refs）；link_refs 排除自身 input_truncated=1 的截断 cluster（同 run 双条件走截断单条、R-15 优先级，§7.6 v1.8）**）
CREATE TABLE `needs_review_batch` (
  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  run_id        VARCHAR(64) NOT NULL,                -- offline error run id（判定源 run）
  agent         VARCHAR(64) NOT NULL,                -- 被测 agent（同 error_cluster.agent 串）
  bound_version VARCHAR(64) NOT NULL,                -- = claim fix_version（run 绑定版本，版本字面量域 §7.5）
  error_type    VARCHAR(64) NOT NULL,                -- 聚合键：同 run 同 error_type 一条
  status        ENUM('open','resolved') NOT NULL DEFAULT 'open',   -- open 待处置 / resolved 整批已处置
  link_refs     JSON NOT NULL,                       -- 引用列表 [{link_id, cluster_id, case_id}]；run 缺行 case 不产生
  reason        VARCHAR(512) NULL,                   -- reason 值域 = {unclean_run}（§7.6 判定语义 v1.5）；本列 = 批判定附注（污染源环境级 na 的 error_type 明细）
  resolve_action VARCHAR(24) NULL,                   -- reopen_cluster / escalated（§7.6 动作集）
  resolved_by   BIGINT UNSIGNED NULL,                -- 处置人（viewer/admin）
  created_ts    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  resolved_ts   DATETIME(3) NULL,
  UNIQUE KEY uk_batch_agg (run_id, agent, bound_version, error_type),   -- 同 (run,error_type) 至多一条：仅承载 unclean_run 批（同 run 环境级 na 污染下 pass 行 cluster）；na 不并入批（v1.5 R-2 批纯化/撞键裁定收窄，§7.6）
  KEY idx_batch_status (status)
) COMMENT='回归 na 聚合批（整批同动作单事务处置，见 §7.6）';

-- ⑧ dict_config 平台配置（per-agent 或全局；wordlist_version 即本表 version）
CREATE TABLE `dict_config` (
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  agent_id     BIGINT UNSIGNED NULL,                 -- NULL=全局
  config_key   VARCHAR(64) NOT NULL,                 -- fallback_utterance / cluster_window_days / ttl_claim_days / body_search…
  config_value JSON NOT NULL,
  version      INT NOT NULL DEFAULT 1,               -- 变更 +1；fallback_utterance 的 version 即词表 wordlist_version（随 D19 固化）
  updated_by   VARCHAR(64) NOT NULL,                 -- 词表变更 admin-only + 审计
  updated_ts   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_dc (agent_id, config_key)
) COMMENT='平台配置（v1 键清单见 §10）';

-- ⑨ agent_credential Kafka 上报凭证（加密存储与轮换见 §13.2）
CREATE TABLE `agent_credential` (
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  agent_id     BIGINT UNSIGNED NOT NULL,
  kafka_username VARCHAR(64) NOT NULL,               -- SASL principal（=producer 身份，topic 不可互写）
  secret_cipher VARCHAR(512) NOT NULL,               -- 加密后密码
  topic        VARCHAR(128) NOT NULL,                -- obs.agent.<name>
  active       TINYINT NOT NULL DEFAULT 1,
  rotated_at   DATETIME(3) NULL,
  created_at   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_cred_agent (agent_id)
) COMMENT='每 agent Kafka 凭证';

-- ⑩ trace_judge_state 判定态（R1 持久化，§4.3）
CREATE TABLE `trace_judge_state` (
  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  agent         VARCHAR(64)  NOT NULL,
  trace_id      VARCHAR(64)  NOT NULL,
  root_ok       TINYINT NOT NULL DEFAULT 0,
  root_ts       DATETIME(3) NULL,
  interface     VARCHAR(256) NULL,
  root_status   VARCHAR(16) NULL,                    -- root request 终态 ok/error/timeout（残 trace 恒 NULL）
  root_error_type VARCHAR(48) NULL,                  -- root_status=error/timeout 时 root 的 error_type（L1 透传/§6.1）
  root_input_hash CHAR(64) NULL,                     -- root request.input 判重键 = sha256(normalize(input))，与 error_cluster.input_hash 同算法（§6.2，跨 trace 同键判定与 cluster 键可比；原「HMAC 键」注释为全仓孤儿标注，H7-6 清除——若确需防字典 HMAC 独立立项另定）
  input_snapshot_clean MEDIUMTEXT NULL,              -- root request.input 脱敏截断≤8K 明文快照（v1.7 R-18：消费 step4 root 到达同刻落库，§4.1/§4.3——唯一见原始明文处；聚类开 cluster/组装取数源，不依赖 ES 回读）
  input_truncated TINYINT    NOT NULL DEFAULT 0,     -- 原始 request.input>8K 截断标记（v1.7 R-18：消费 step4 判原始 len>8192 置 1；cluster/error_case_link 自本列复制，H7-1 判点下钻到 step4）
  err_summary_json JSON NULL,                        -- 子节点 error 汇总（条目 error_type = 原值枚举、同 error_cluster.error_type 值域，禁 L1/L2 分类键；error_msg 脱敏≤512；v1.6 R-6）
  llm_fact_ok   TINYINT NOT NULL DEFAULT 0,          -- trace 内出现 llm_call / llm_* error
  judged        TINYINT NOT NULL DEFAULT 0,          -- judge_scan_job classify 完成后置 1（判后不再重复判定）
  processed     TINYINT NOT NULL DEFAULT 0,          -- 判定产出进聚类处理完置 1（与 judged 分离，防重放重复进聚类，§4.4）
  root_late_complement TINYINT NOT NULL DEFAULT 0,   -- v1.9 R-21：root 在 judged=1 后迟到 → root 级补判已触发标记（root 到达事务内 CAS，§4.3④/§4.4）
  judgement_json JSON NULL,                          -- 判定产出（layer/candidate/input_hash…）
  ttl_until     DATETIME(3) NOT NULL,                -- 最后事件 ts + 窗口 + 宽限；judge_scan_job 扫描位点
  updated_ts    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_trace (agent, trace_id),
  KEY idx_judge_scan (judged, ttl_until),            -- judge_scan_job 待判定扫描：judged=0 ∧ ttl_until≤now（§4.3）
  KEY idx_purge (processed, updated_ts)              -- 过期判定行清理（§10.1 trace_judge_purge_days）
) COMMENT='消费侧 trace 累积判定态（判定执行方=judge_scan_job，§4.3/§6.1）';
```

> **关键约束（v1.1 裁定，2026-09-03）**：现行 link = `verify_status='pending'`（待 offline 拉取/激活/回归中）。唯一键 `(case_type, cur_key)`——cur_key 为生成列，仅 `verify_status='pending'` 时取值 cluster_id、终态自动置 NULL 释放占位——保证同 cluster 同 case_type **至多一条现行 link**，且终态不再占用。由此两条派生语义：
> 1. **reopen/回归 failed 后再 claim（新 fix_version）**：旧 link 已终态（`verify_status='failed'`，或 superseded）自动让位 → assemble_job 依 §6.3 直接为同 cluster 生成新 link（新 payload_id，绑定新 fix_version 与触发时刻），无需人工"解除唯一索引"（§7.6 claim 流转）；
> 2. **invalidated 未重推的 pending 行仍占现行位**（可 requeue 复用同一行 payload_id，§7.4）；只有明确弃用才置 `superseded` 让位。
>
> `error_cluster` 唯一索引含 `generation`，同键复发时新开 cluster 行 generation+1；旧行 status 置 fixed/inactive（保留供查），**不再复用同一行**。

### 5.2 Elasticsearch 索引与映射

| 项 | 值 |
|---|---|
| index | `obs-event-yyyyWW`（event）/ `obs-log-yyyyWW`（log），按周滚动；ILM 30 天 delete。共享集群租户带 `{env}.` 前缀（`{env}.obs-event-yyyyWW`，§13.3）；**index template/ILM 由平台提交、infra 建** |
| `_id` | `sha256(agent\|trace_id\|seq)`（seq trace 内全局唯一；agent 入键防跨 agent 同 trace_id 互覆） |
| mapping 基线 | `dynamic:false`（防二期字段被 dynamic mapping 提前建索引，见 §2.8）；仅白名单字段入 mapping |
| 正文字段 | `input/output/log_message` 用 `text` + 中文分词（`ik_max_word` 或安装 `analysis-ik`；无插件则标准分词并回退，检索面仍在） |

核心 mapping（示意，v1 落全部字段）：
```jsonc
{
  "settings": { "number_of_shards": 1, "number_of_replicas": 0,   // 本地/独立集群默认；租户共享集群时 shards/replicas/ILM 归 infra 覆盖（§13.3）
    "analysis": { "analyzer": { "zh": { "type": "ik_max_word" } } } },
  "mappings": {
    "dynamic": false,
    "properties": {
      "schema_version": {"type":"keyword"}, "event_kind": {"type":"keyword"},
      "trace_id": {"type":"keyword"}, "agent": {"type":"keyword"},
      "agent_version": {"type":"keyword"}, "interface": {"type":"keyword"},
      "node": {"type":"keyword"}, "seq": {"type":"integer"}, "branch": {"type":"integer"},
      "parent": {"type":"integer"}, "ts": {"type":"date", "format":"epoch_millis"},
      "@timestamp": {"type":"date"},
      "duration_ms": {"type":"long"}, "status": {"type":"keyword"},
      "error_type": {"type":"keyword"}, "error_msg": {"type":"text","analyzer":"zh"},
      "input": {"type":"text","analyzer":"zh", "fields":{"kw":{"type":"keyword"}}},
      "output": {"type":"text","analyzer":"zh"},
      "usage": {"properties":{"prompt_tokens":{"type":"long"},"completion_tokens":{"type":"long"},"total_tokens":{"type":"long"}}},
      "model": {"type":"keyword"}, "log_level": {"type":"keyword"},
      "log_message": {"type":"text","analyzer":"zh"},
      "quality": {"enabled":false},            // 二期占位：不索引无倒排成本
      "retrieve_hit": {"enabled":false},       // 同上
      "session_ctx": {"enabled":false},        // 二期占位
      "extra": {"enabled":false}
    }
  }
}
```
> `input/output/log_message` 仅 index 中始终保留全文（ILM 30d 内）；**可检索/可查看展示面**由接口级 `body_search` 开关控制（§2.7）——即"存 ≠ 可查可看"，检索 API 层做开关过滤（§8.2/§8.3）。

### 5.3 指标：双路查询 + 7d 小时级 rollup（决策 R7）

**双路路由**：

| 时间窗 | 数据源 | 说明 |
|---|---|---|
| 1h / 24h | ES 实时 agg | `date_histogram × percentiles(duration_ms)[p50/95/99] × filter(status=error/timeout)`；request/llm_call 双锚点分别 agg |
| 7d（>24h） | `{env}.obs-metrics-rollup` | 小时桶预聚合 + **尾小时实时补齐**（趋势不截断） |

**rollup index `{env}.obs-metrics-rollup`**（单 index 非周滚动，小时粒度总量可控；worker 每小时 job 写，doc 维度 agent×interface×node×hour；mapping `dynamic:false` + 白名单，实现定稿 v1.12）：

| 字段 | 含义 |
|---|---|
| agent / interface / node（request·llm_call）/ model（request 级为空串） | 分桶键 |
| hour / ts | 小时（`yyyy-MM-ddTHH:00`，UTC，keyword）/ 小时起点 epoch_millis（hour/ts 双写：hour 供 keyword 归并、ts 供 date_histogram） |
| doc_type | `group`=组 doc / `meta`=小时 meta doc（检索判别；meta doc 记该小时源计数供廉价迟到探测） |
| schema_version | sketch 版式版本（=1，消费侧判新旧） |
| total / error / timeout | status 互斥计数桶（usage 只在 llm_call 桶；llm 失败率口径 = (error+timeout)/total） |
| prompt_tokens / completion_tokens | llm_call 桶 token 汇总 |
| sketch | **t-digest 可合并分位草图**（自研 JSON-base64 存 keyword，`{v:1, c:[[mean,weight],…]}`）——跨小时可合并出 7d 单值 p50/95/99 |
| updated_ts | 写入时刻（date） |

**确定性 `_id`** = `sha256("rollup|agent|interface|node|model|hour")`：整小时重算同 `_id` 覆写 = 幂等不双计（迟到重算同小时天然收敛）；小时级 meta doc `_id = "rollup-meta|{hour}"`。

**job 机制（worker 进程内 asyncio 自管循环，非 APScheduler——阶段 2 实现裁定，见修订记录 v1.12）**：
1. **首启回填**：历史已完成小时。
2. **迟到事件幂等重算**：事件晚到 ≤6h（`K` 默认 6）内重算对应小时桶——下轮对尾窗先发廉价 `count(size:0)` 比对 `rollup-meta|{hour}` 源计数、仅差异小时全量重算（确定性 `_id` 覆写、重叠不双计）；超窗迟到只进实时 agg，rollup 该小时明示缺口。
3. **失败降级**：记最近成功时间；7d 查询命中缺失/过期小时桶 → 该小时回退 ES 实时 agg + 页面标注"回退实时口径" + 自监控告警（对应 §16 rollup 行）。
4. **尾小时口径**：最后未完成小时不预聚合 → 实时 agg 补齐拼最后一段。

**7d 读取口径（实现钉定，用户拍板 v1.12；metrics API 复用 store 读助手）**：`source ∈ {rollup, realtime, mixed}`。
- **覆盖基准 = rollup 小时级 meta doc**（非 request 组 doc）：rollup_job 对处理过的小时**恒写 meta**（含"处理过但零流量"小时）→ 空小时算已覆盖、不算缺口（实现修订见修订记录 v1.12 行）。
- **卡片 p50/p95/p99** = 仅 merge **已覆盖整点小时**的 request-node sketch（跨源分位不可精确合成；未覆盖小时与进行中小时不进分位 merge）。
- **total/error/timeout 计数与 series** = 保持**实时整窗**（精确超集、不回退、不与 rollup 计数掺——rollup 计数与源一致由 meta 探测保证）。
- **interfaces 行级分位** = 保持实时 agg（覆盖小时样本不足以支撑行级 covered-only 近似）。
- **source/fallback 派生**：`fallback_hours` 只列**已闭合**小时中无 rollup 覆盖的缺口——当前进行中小时由 rollup 设计上不预聚合（尾小时实时回补），**不计缺口** → 全部已闭合小时覆盖 = `source=rollup`、有缺桶 = `mixed`（响应带 `fallback_hours`）、无任何覆盖（index 缺失 / ES 异常 / worker 从未跑 = covered 空）= 整窗实时 `source=realtime` 且 `fallback_hours=[]`。前端对 mixed 标「部分时段回退实时口径」。

---

---

## 6. 回流分析处理（判定 → 聚类 → 组装）

> 依据：solution.md §10.1/§10.2/§10.3。v1 = L1/L2 error-only；L3 quality 一律不实现（§1.4）。分析源 = §4.3 消费侧累积判定态，**不依赖 ES 回读**。

### 6.1 L1/L2 分层判定（analyzer/classify.py，**judge_scan_job 到期触发**，§4.3）

**判定输入** = `trace_judge_state`（§4.3）判定完成后的 trace 级结果。

**步骤（顺序判定，命中断言）**：

| 步 | 规则 | 结果 |
|---|---|---|
| 1 白名单 | `agent.backflow_allow ∈ {gq, cs, sp}`（cc 硬排除，D18）**且** `backflow_enabled` 开（agent 表 enable=0 或全局回流配置关停 → 不产候选；先查 allow 硬排、再查 enabled，两处任一关即停） | 否 → 不回流 |
| 2 动态事实 | trace 内出现 `llm_call` 子节点 或 `llm_*` error → `llm_fact_ok=true` | 用于 L2 OR |
| 3 L1 判定 | request 根事件 `error_type ∈ llm_*`（7 类透传，§2.5） | 命中 → **L1 候选** |
| 4 L2 判定 | request 或子节点 `error_type ∈ {llm_interface_business, external_non_llm, db_error, redis_error}` **且**（`llm_fact_ok` **OR** 接口字典 `interface.llm=true`） | 命中 → **L2 候选** |
| 5 出口 | 均未命中（含 `auth_error/validation_error`、缓存命中无 llm 事实、login 类） | 不回流（出指标/trace） |

- 多条 error 同 trace：per-trace 归并成**一次候选**；候选携带该 trace 全部 error 明细（供 §6.2 按错误分类各自去重——同一 trace 不同 interface/error_type 分属不同去重键，各自进对应 cluster）。
- **root-late 补候选（v1.9 R-21）**：正常归并后（judged=1）迟到的 root 走**单事件候选**（§4.3④，step4 触发，不走 judge_scan_job 归并）——候选 = root_error_type 单值，经本表 L1/L2 值域筛（root 属该 interface 的 request，`llm_fact_ok` 用判定态既有值；命中任一值域 → 补候选进 §6.2，root_late_complement 置 1）。与正常候选唯一差异 = 只带 root 级证据、不含子节点明细（子节点 error 已在正常判定时各自聚类过）。
- **重试自愈已天然过滤**（SDK 逻辑调用最终成功 `status=ok`，§2.4）；兜底吸收现场（request ok + llm_call error）不产 L1/L2 候选（L3 二期）——但其 trace 本身仍可被维度 1 查询、其 llm_call error 仍进指标（§2.4 前提）。
- judge_scan_job 将判定产出写回 `trace_judge_state.judgement_json` + 置 `judged=1`；聚类消费后置 `processed=1`（judged/processed 分离，§4.3/§4.4），防重放重复进聚类。

### 6.2 聚类与去重（analyzer/cluster.py + worker/cluster_job.py）

**error 去重键（v1）**：`agent + interface + error_type 分类 + input_hash`
- `error_type 分类`：**不使用 error_type 原值**，按 §2.5 归类到 L1/L2 层语义键（`llm_timeout` 与 `llm_other` 是否合并？）——**【实现约定】按 §2.5 error_type 原值去重（不跨类合并）**，与 §6 复发检测/reentry 观察键（agent+interface+error_type+input_hash，§7.5）同源一致。
- `input_hash = sha256(normalize(input))`；normalize = strip + 折叠空白 + 截断 8192 字符（v1.6 R-10：4096→8192，与 §5.1④ DDL 截断上限一致、去重键粒度 ≥ 复现粒度；H7-3）；对话型取 input_turns（v1 无会话历史摘要，§2.8）。

**窗口与生命周期（对应 §10.2）**：

| 状态场景 | cluster 动作 | link 动作 |
|---|---|---|
| 同键首现 | 开 cluster（status=open，generation=1），落代表快照（input_snapshot 取该 trace 判定态 `input_snapshot_clean`——消费 step4 已脱敏截断 ≤8K 明文快照，§4.3 v1.7 R-18；**input_truncated 自判定态列复制**；error_msg ≤512；first_trace_id；trigger_version） | 触发组装一次 → 建 link（§6.3） |
| 窗口（默认 7d）内同键新现 | 只 `count+1`、刷新 `latest_ts`；**不重生成**（link 已存在）——**每次同键新现按新现 trace 判定态刷新 `input_truncated`（v1.8 R-13：单 trace 即刷，≤8K 判定态 0 → 清 0、>8K → 置 1；cluster 已 closed 不刷新、终态只读不翻案）**；代表快照若缺 input 实文而新现 trace 判定态含 `input_snapshot_clean` → 复制回填快照 + 按 §6.3 补组装一次（v3.5.1 + v1.7 R-18 取数源改判定态） | 不变 |
| 窗口内同键新现 但 link 已 invalidated（error 自检失败，§6.3） | 只 `count+1`（计数 = offline 重扫可重推恢复的信号）；**不自动重生成** | offline 重扫自愈或 admin 重推复位（§7.4） |
| 同键静默超窗口 | cluster → inactive（归档，保留 count/最近 ts/快照） | — |
| claim→fixed（回归证据或 admin 复核） | 旧 cluster 终态 fixed；旧 link superseded | 同键再现 → **新开 cluster generation+1**（不与已归档同键冲突，唯一索引含 generation，§5.1） |

**root-late 补候选聚类（v1.9 R-21；v1.15 修正 closed 语义）**：补候选（§6.1）与正常候选**共用本表生命周期与去重键**——同键已有**非终态** cluster（open/claim/needs_review）→ 按「窗口内同键新现」只 count+1 / 刷新 latest_ts / 按需补快照（open 且缺 input 实文 → 现 root input 已落 `input_snapshot_clean` 可补组装一次，§6.3）；同键**已 closed（fixed/inactive）→ 跳过不翻案**（§4.3④/E-28：root-late 迟到补候选不重开已终态 cluster，与正常候选的「closed 后复发新开 generation+1」（上表末行，cluster_job `reopen_after_terminal=True`）严格区分）；同键**从未出现** → 按「同键首现」开新 cluster（generation=1）+ 触发组装建 link；同键现行 link 已 invalidated 但 cluster 非终态 → 只 count+1（重扫可重推信号，沿 §6.2 既有行）。**幂等**：补判触发受 `root_late_complement` CAS 约束（§4.3④），聚类侧沿用唯一索引吸收同代并发双写。

**并发/幂等**：cluster 落库用唯一索引吸收同代并发首现双写；`judgement_json` 处理后置 `processed`，防止重放重复进聚类（§4.4）。

### 6.3 组装 D19 信封落库（converter + worker/assemble_job.py）

触发：cluster 首现开（§6.2）即自动组装一次（在线错误处置"自动生成默认开"）；组装失败/重试由 `assemble_job` 补偿扫描兜底（【实现约定】每分钟扫 open 且无现行 link 的 cluster）。**实现形态（v1.16 定音，用户拍板）**：纯 `assemble_job` 周期补偿扫描（`ASSEMBLE_INTERVAL_S=60`）承担全部组装——不做 cluster 首现「即时内联」触发（cluster_job 与 consumer root-late 两处产 open 由同一扫描幂等覆盖，单一写路径；新开簇至出 link ≤60s）。

**组装步骤（converter/envelope.py）**：
1. **取数源**：从 `error_cluster.input_snapshot`（快照实文）取 input，**不依赖 ES 回读**（v3.5.1）；快照缺 input 实文（如残 trace 无 request 根）→ 该 cluster 只计数不组装（§10.2 现场缺；待同键新现补齐快照）。
2. 构造信封元数据 + evidence + assert 区（信封 schema 见 §7.1）：`payload_id=uuid4()`、`case_type=regression_error`、`source{agent,interface,trace_id,cluster_id,generation}`、`versions{trigger_version, fix_version=cluster.fix_version}`（组装时 cluster 可能尚无 claim → fix_version 空，由回写/重推路径在 claim 后补？——**【实现约定】fix_version 在 claim 时写入 cluster，组装即取的即时值；若组装先于 claim，则 link 建后当 cluster.claim 发生时不重建，回查时以 claim 后 cluster.fix_version 为准（§12.2 O-2 已裁定；单错级回查锚定见 §7.6）**）。
3. **assert 区固化 no_fallback_config**（converter/no_fallback_cfg.py）：组装瞬间读 `dict_config(agent_id, 'fallback_utterance')` → 词表数组 + `wordlist_version = dict_config.version`；空表/未配置 → 记录"空词表"标记，信封照建，offline 结构自检会判不过（fail-closed：offline 结构自检不过 → 回写 invalidated，见 §7.1 assert 区 no_fallback 判定语义 / §7.3 结构自检失败驳回行）。
4. 写 `error_case_link`（offline_status=assembled、verify_status=pending、payload_json=信封全文）+ `conversion_record(action=assemble)`。

**窗口抑制**：同 cluster 已有现行 link（assembled/draft/active）时不再重复组装；link invalidated 后不自动重组装（§7.4）。

---

---

## 7. 平台间契约与复验闭环（D19/D20，online 侧实现 + offline 期望行为）

> 依据：solution.md §10.3/§10.5/§11/§12。**本平台间的三组端点 online 侧全部实现**；offline 侧只列「期望行为」（Task #4 落）。方向澄清：pull 为 **offline 主动来 online 拉**；回查为 **online 主动查 offline**。

### 7.1 D19 统一 case payload 信封（online 组装产物，offline 拉取体）

| 分区 | 字段 | v1 值 / 规则 |
|---|---|---|
| 信封元数据 | `schema_version` | `"1.0"` |
| | `case_type` | `"regression_error"`（仅此；其余类型返回空集，§8.7 白名单） |
| | `payload_id` | uuid4 字符串（幂等键；offline upsert、重拉不重建） |
| | `source` | `{agent, interface, trace_id, cluster_id, generation}` |
| | `versions` | `{trigger_version, fix_version}`（fix_version 组装时刻取值，**claim 前组装恒空、事后不重写**——回查锚定 `cluster.fix_version`，§6.3/§7.6，O-2 已裁定；可空） |
| 通用 evidence | `input` | 快照 input 实文（脱敏、≤8K）；error 型仅当前请求 input_turns |
| | `input_truncated` | 复现输入源原始 input>8K 被截断标记（v1.6 R-10 + H7-4 补载体：组装时自 cluster 列复制随 link 透传；offline 只读上下文、判定仍如实不因截断改判，phase2 v0.7 §2.3 注⑤） |
| | `output` | 代表事件 output 正文摘要（脱敏；随接口 body 采集策略） |
| | `session_snapshot` / `retrieve_hit[]` | **【二期】** v1 恒 null/缺省（offline 反序列化不得因缺省误判有数据，§8.7 契约注） |
| 类型化 assert | `assert` | v1 `regression_error` 子结构：`{no_fallback: {rule: "wordlist", config_ref: {wordlist_version}}}`（判定执行归 offline；`config_ref.wordlist_version` === 下行 `no_fallback_config.wordlist_version`，组装同一时刻固化，**单一版本源**——`snapshot_id` 为残留概念，已删） |
| assert 区附加 | `no_fallback_config` | **随 payload 固化**：`{words: [...], wordlist_version: N}`（per-agent，组装时从 dict_config 快照，§6.3 step3）。offline 结构自检/verifier 判分**以 payload 内这份为准**；改词表不 retroactively 影响已激活 case（v3.5.1；assert.config_ref 与 no_fallback_config 同刻固化同源，无第二版本源） |
| assert 区附加 | `no_fallback` 判定语义 | 空词表/未配置 → 信封照建并带「空词表」标记（§6.3 step3）→ **offline 结构自检不过（error draft 不激活，回写 invalidated）**＝v1 fail-closed，不静默 pass；`inconclusive` 属二期 judge 态（v1 无 verifier scoring，不产生） |

信封 JSON 完整样例（供 pull-API 契约测试与 offline 反序列化参考）：
```json
{
  "schema_version": "1.0",
  "case_type": "regression_error",
  "payload_id": "3f0e8c7a-…",
  "source": {"agent": "good-question", "interface": "POST /api/chat/{id}",
             "trace_id": "tr-9f2c1a", "cluster_id": 1001, "generation": 1},
  "versions": {"trigger_version": "2026.08.31-r47", "fix_version": null},
  "evidence": {
    "input": {"session_id": "{id}", "question": "帮我查一下XX政策"},
    "output": null,
    "session_snapshot": null,
    "retrieve_hit": null
  },
  "assert": {
    "no_fallback": {"rule": "wordlist", "config_ref": {"wordlist_version": 7}}
  },
  "no_fallback_config": {"words": ["抱歉，暂时无法回答", "系统繁忙，请稍后再试", "当前功能维护中"], "wordlist_version": 7}
}
```

> **结构自检必填/可空字段集（offline 照做清单，Task #4 输入）**：必填=`schema_version / case_type / payload_id / source.agent / source.interface / source.trace_id / versions.trigger_version / evidence.input / assert.no_fallback.config_ref.wordlist_version / no_fallback_config`；**可空**=`versions.fix_version`（claim 前组装恒 null，不得因此驳回）、`evidence.output`（body 采集默认关恒 null，**不得因 null 驳回**，§8.7 契约注）、`evidence.session_snapshot / retrieve_hit`（二期恒 null）、`source.cluster_id / generation`（溯源可空）。

### 7.2 pull 语义（offline 定时来拉，online 只备好 payload 等着）

- online 侧 **不 push、不设拉取调度/时钟**：只维护 `offline_status` + `assembled_ts`，暴露 pull-API（§8.7）。
- 聚类页「已待 N 天」= `now - assembled_ts` 由 API 现算展示（**展示非告警**；超阈值提示性标记"offline 疑似停摆，人工核查"，文案见 §9.3）。
- 恢复后积压限速/新鲜度窗口属 offline 拉取侧行为（Task #4 输入），online 不参与。

- pull-API 返回 assembled 按 `assembled_ts` 升序 + `next_token` 分页游标（§8.7）；offline 崩溃重拉以 `payload_id` upsert 幂等去重。**requeue 刷新 `assembled_ts=now()`**（§7.4），使重推案重新进入增量拉取范围——否则 offline 按 since/位置游标会跳过已读旧档。**契约修订 R1（v1.2）**：响应每条 payload 附顶层 `assembled_ts`（online 组装/最近 requeue 时刻，ISO8601 UTC，§8.7）——offline 增量锚唯一可靠来源（水位取 max、空轮不前移），不依赖 offline 本地墙钟。

### 7.3 平台间状态回写与回查（online 侧处理）

| 事件 | 方向 | 触发 | online 侧动作 |
|---|---|---|---|
| 拉取建 draft | offline→online | offline pull 到 payload、建 case 成功 | 回写 `offline_status=draft` + `case_id`（幂等：按 payload_id upsert；重复 ack 不报错） |
| 结构自检失败驳回 | offline→online | error draft 结构自检不通过 → rejected（携带 reason） | 回写 `offline_status=invalidated` + `invalidate_reason`；cluster 保持 open（可重推观察态，§6.2） |
| 激活 | offline→online | rejected 后 offline 重扫自检通过 / 收单即激活 | 回写 `offline_status=active` + `case_id`（复用 payload_id 幂等；**收单即激活也须带 case_id**，否则单错级回查断链，§7.6） |
| 人工 invalidate（online） | online 本地 | admin 对未激活 case（assembled/draft）判无效 | `offline_status=invalidated` + `conversion_record`；**active 后不走此路**（superseded+reopen，§7.6） |
| 回查 run_results | online→offline | cluster claim 后按 fix_version 轮询回归 run | 逐条判单错 → 写 `verify_run_record` + 更新 `verify_status`（§7.6 单错级回查） |

**ack 前置矩阵（v1.2，含契约修订 R2 例外）**：`draft` 要求当前 `offline_status=assembled`；`active` 要求 ∈{assembled,draft}（收单即激活），或 ∈{invalidated 且 `invalidate_reason='offline_cap_gap'`}（offline 重扫自愈回写 active，复用 payload_id，§7.4 上行；**契约修订 R2**），或对同一 payload 重复 ack（幂等）；`invalidated`（驳回）要求 ∈{assembled,draft} 且**必带结构化 reason**。前置不符 → `ERR_CLUSTER_0003`(400，**响应带当前 `offline_status`+`invalidate_reason`，契约修订 R3**)/`ERR_PULL_0003`(404)；对**已知** payload_id 的重复 ack → 200 幂等成功。reason 码见 §7.4。

**offline 期望行为（Task #4 输入，online 侧依赖不变式）**：
1. pull 拉取后**不改写 case 内容**；发现内容缺口不就地编辑补全 → 驳回 rejected + 回写 invalidated，由 online 修正现场重推（§7.4）——防内容与线上现场漂移。
2. `list_runs` 需支持按 `agent + version + status` 过滤回归 run 且**按含 case_id 过滤**；`run_results` 返回 `case_id + case_type + pass_fail`。
3. 回归 run 不占互斥槽、不参与 max_active_runs；对回归 run 设独立保留档（pinned/豁免 cleanup），清理先归档 pass_fail 终态（归档前保留终态字面量 + na 计数，Task #4-② B-6）。
4. error-only run 的 `pass_fail` = executor 技术判定 ∧ verifier no_fallback 合成，由 verifier 阶段落终值（不经 SCORING、不产 agent_score）——online 回查对 error 生效依赖此语义。

### 7.4 invalidated / rejected 重推（自愈闭环，online 侧落点）

| 驳回来源 | 重推执行方 | online 侧动作 |
|---|---|---|
| offline 能力缺（adapter/判定器未注册等，reason 属 offline） | **offline 重扫自愈**：配置变更后周期重跑结构自检 → 通过回写 active（复用 payload_id） | 只被动收 `active` 回写；不设 online 时钟 |
| online 现场内容缺（payload 字段不全，reason 指明缺项） | online admin 在聚类详情「重新组装/重推」 | `requeue_job`：`invalidated → assembled` 复位（复用 payload_id + 重填 payload_json 修正现场）→ **刷新 `assembled_ts=now()`**（「已待 N 天」归零、增量拉取可见，§7.2）→ 重新进入 pull 范围；记 conversion_record（detail 含 reason 码） |

**requeue 守卫（v1.9 R-24 状态域精确化）**：仅 `offline_status=invalidated` 且 **`cluster.status ∈ {open, claim, needs_review}`** 可复位——**fixed/inactive（已 closed）禁 requeue**（需重测走 superseded+reopen 重建新 link/新 payload_id，防对已收敛证据翻案）；claim / needs_review 态**允许**（供 claim 回归 run / needs-review-resolve 补充证据的拉取复位，§7.6）。**锚点保护**：requeue 仅复位 link（invalidated→assembled，复用 payload_id + 重填 payload_json + 刷新 `assembled_ts`），**不动 cluster 锚点**——fix_version / claim_k / TTL 保留，run 回查仍以现 claim 锚定（§7.6）；复位不改 `verify_status`（保持 pending → 仍占现行位，§5.1 注）。**verify 兜底**：仅 `verify_status=pending` 的 invalidated link 走此路（已推进 passed/failed/superseded 的不在此路）。防抖限流：同一 link 人工重推间隔 ≥【实现约定】5 分钟。

**批量 requeue（v1.6 R-7）**：`POST /backflow/links/requeue-batch`（§8.4）——admin 筛选 `offline_status=invalidated + invalidate_reason='online_content_gap'`（可加 agent/缺项过滤）批量复位，逐行复用本守卫 + 防抖 ≤N/min【实现约定 20】。**可愈性标注**：按 invalidate detail 缺项区分「补齐+重推可愈」（字段缺/词表空，补齐 `no_fallback_config` 即愈）vs「requeue 不愈」（版本不识别：schema_version 非 1.0 / case_type 新白名单值，需 offline 升级/联调同步才愈，phase1 §6.3 同源语义）——批量 UI 对不愈行**默认禁勾（强确认才放行）**，防误导 admin 反复重推。返回逐行结果（requeued / skipped+原因）并记 conversion_record（actor、筛选条件、逐行结果）。

**invalidate reason 结构化码（驳回与人工统一）**：`offline_cap_gap`（offline adapter/判定器缺）→ 归 offline 重扫自愈（本表上行）；`online_content_gap`（payload 内容缺，reason 指明缺项）→ 归 online admin 重推（本表下行）；`manual_invalidate`（admin 人工判无效，可附补充理由）。code 随 §8.7 ack/聚类详情透出，前端按码出文案（§9.3）。

### 7.5 reentry：线上观察哨位（worker/reentry_job.py）

- 观察键 = error 去重键（agent+interface+error_type+input_hash，与 §6.2 同源）。
- 触发：cluster 已 claim/fixed 后，同键错误**线上再现**（judged 为 L1/L2 的新事件）。**版本门控（v1.1，序比较语义 Task #4-② B-5 细化见下）**：仅当新现事件版本与 `cluster.fix_version` 满足**等值+日期前缀门控**（修复确已上线、回归有据）才开 reentry；修复上线中/未上线再现 → 只按 §6.2 窗口 `count+1`，不开新 cluster（防修复落地前反复抖 cluster、空转回归）。**reentry 产物 cluster（generation>1）后续 claim 受 R7 约束（§7.6 v0.6.1 判定）**：claim 版本若 = 该 (agent,version) 已有 completed 回归 run 的版本 → 回查旧 run pass 不 auto-fixed、转 needs_review（reason=`reentry_same_version`）。
- 动作：新开 cluster（generation 独立计数沿用 §6.2 复发规则）；`conversion_record(action=reentry, detail="线上仍复发，claim 或回归失守，请核对 fix_version 是否覆盖线上路径")`。offline 侧对应回到待修复集（Task #4）。

> **版本门控序比较语义（Task #4-② 契约修订 B-5，2026-09-03）**：`agent_version ≥ cluster.fix_version` 的比较采用 **等值+日期前缀门控**（error 回流版本字面量域——fix_version/agent_version 均为被测 agent 自报字面量、不强行 semver，§8.4）：先截两版本前 10 位日期前缀（`YYYY.MM.DD`；非该形态 → 整体按不透明字面量仅做等值比较）。日期前缀相等 → 仅**完全等值**放行 reentry，同日不等值按"修复上线中/未上线"只 `count+1`（防 `r100` < `r47` 类字典序乱序把已上线误判为未上线）；日期前缀不等 → 按日期前缀字符串序比较（跨日可靠，构建标签不参与比较）。同日多版本 hotfix 复发若需立判，走 §7.6 reopen 人工路径。**门控不过（blocked）复发可见性（v1.3 排查补正；v1.20 派生口径修正）**：claim/fixed 期同键复发虽不进 open 队列（TTL 设计静默，§7.5 / solution §10.4 人工处置）——**门控不过时 merge 返 "blocked"、DB 零落**（v1.19 §7.5：不建簇不 count 不 conv，judged 行仍被 processed CAS=1 消费；**非「只 count+1」**）——该复发事实须在 fixed/claim cluster 详情与复发行展示「同键新版本 &lt;最新版本&gt; 复发 N 次，若非属本 fix 请 re-claim/reopen」；**读数（v1.20 定音）= 后端读 MySQL `trace_judge_state`（近 `trace_judge_purge_days` 保留窗，默认 7d）现算，非前端 ES 派生**（前端无 ES 通道；ES 仅存原始 trace 事件、无 judged/root_input_hash/candidate 语义，无法还原判定侧归一哈希）——命中键 = `agent` + `root_input_hash`（与 `error_cluster.input_hash` 同源）+ `interface` + `error_type ∈ candidate_error_sets`；`mode=fixed` 只计 `ts ≥ fixed 锚 ∧ 门控不过`（fix_version 空 → 不展示）、`mode=claim` 计 `ts ≥ claimed_at` 全计；**不新增存储列**，防同日 hotfix 复发被无声吞掉（计数受保留窗限制：超窗 blocked 行物理消失、计数回退，属「不新增存储列」的必然代价，caption 标注「近 N 天」）。
- online = 观察事实权威，offline = 验证事实权威；二者互不替代、互相反馈。

### 7.6 状态机矩阵与人工处置

**cluster.status × link 状态迁移总表**（CAS 条件更新，`WHERE status=期望旧值`）：

| 状态 | 触发 | 可迁移 | 约束 |
|---|---|---|---|
| `open` | 新候选 / 复发 / 归档反悔 | → claim / inactive / needs_review | 有现行 link 时同键只计数（§6.2） |
| `claim` | viewer 认领，**必填 fix_version** + 说明 | → fixed（auto_regression：自该 fix_version 起**连续 `claim_k` 个纯净可判版本回归 run 均无 fail**（claim_k = claim 固化值、k=1 快路径，§7.6 判定语义 v1.5））/ fixed（admin_review）/ open（回归 failed 或 TTL 超窗回退）/ needs_review（error run 判定产物，reason 值域 = {`na`, `reentry_same_version`, `input_truncated`}，§7.6；**unclean_run 不入本态——只经 batch 载体处置、批引 cluster 保持 claim 挂起，v1.8 R-14 口径归一**） | TTL 复核窗口默认 14d；**收敛 = 两时钟先到者**：K 满 → fixed（TTL 停钟）/ TTL 超窗 → 回退 open（K 观察中止、下轮 claim 重计），K 观察/回查推进不延长 TTL（§7.6 v0.6.1）。超窗自动回退 open 记 conversion_record（`claim_ttl_job` 执行，§1.2；防认领驻车抑制告警）。**再 claim 新 fix_version → 同 cluster 生成新 link（新 payload_id 绑定新版本）**：旧 link 已终态自动让位（§5.1 注），见文末 reopen 条 |
| `needs_review` | v1 源 = claim 回归 error run 结果行的判定产物，四类 reason（值域 = {`na`, `unclean_run`, `reentry_same_version`, `input_truncated`}，聚合归属见 §7.6 判定语义 v1.6③）：`na` 结果行（**cluster 级单点、退批**）/ 含**环境级** na run 内 **pass 行** → `unclean_run`（**批聚合 = 仅 unclean_run 批**，v1.5 纯化）/ reentry 产物同版本 claim 的旧 run **pass 行** → `reentry_same_version`（claim 级单条、不产批）/ 复现 input>8K 截断、证据不完整 → `input_truncated`（claim 级单条、不产批，v1.6 R-10） | → open（补充证据/升级） | 判分 na/会话快照不足等仍二期/D18；**run 超时非源**（兜底 = claim TTL 超窗回退 open） |
| `fixed` | 回归 passed（closed_by=auto_regression）或 admin 复核（admin_review） | → open（reopen：复发/误判） | viewer 不能单方置 fixed（R4） |
| `inactive` | ignore | → open（反悔/复发重新开） | link 已 superseded 才停回查（§7.5） |

**link 维度（error_case_link）**：

| offline_status | 含义 | 可人工 invalidate？ | verify 流转 |
|---|---|---|---|
| assembled | 已组装待拉取 | ✅（admin/权限见 §8.7） | pending |
| draft | 已拉取待激活 | ✅ | pending |
| active | offline 已激活 | ❌（废弃走 superseded+reopen） | pending → passed/failed |
| invalidated | offline 驳回/人工判无效 | — | pending（**重推位**：requeue §7.4）；弃用位置 `superseded`（释放现行占位，§5.1 注） |

- `verify_status`：pending（含"待 &lt;version&gt; 回归 run"）/ passed / failed / invalidated / superseded。**终态只读**：已定 passed/failed/superseded 的 link 不被迟到 run 改写（只追加 `verify_run_record` 时间线；§7.6 单错级回查/终态只读）。
- **单错级回查规则（solution §10.5；auto-fixed 判定语义 v1.5 = claim 固化 `claim_k` + claimed-case 级纯净判据，见下 v1.5 blockquote）**：回查锚定 = **claim 填的 fix_version** 起该 (agent,case) 的回归 run 序列，逐版取 `run_results.pass_fail` 判定；**不取乱序 run**（防多版本先后触发拿错 run）；该 case 纯净可判版 pass → 计入 K（计满 `claim_k` → verify passed → cluster fixed，闭环）；run 内他错仍红不阻塞本错 closed（na 影响域归类见下 v1.5）。

> **回归 run 判定语义（Task #4-② 契约修订 B-1(a)/B-1(b)，2026-09-03）**：
> - **判定源限定**：recheck 只消费 offline error_regression run 终态 `status ∈ {completed, partial_failed, timeout, cancelled}`，**绝不含 running/pending**（半态先落库的部分 pass 行不可作终值，防 premature fixed）。
> - **同 (agent,version) 多 run 选取序**：锚定 claim fix_version 后，该 (agent,version) 若存在多条 run（崩溃重跑/坏终态重建产物），优先最近 `completed`；无 completed 取最近可判终态（`status ∉ {pending, running}`）。claim 未 closed 期间每次回查取「当前最近可判 run」判定、有推进即更新（未定前用新 run；不覆写已 closed）。
> - **per-case 值域映射**（`run_results.pass_fail`；auto-fixed 触发在**纯净 run 前提 + K 稳定序列**下执行——v0.6.1 精化见下，本条保留 pass/fail/na/缺行四值语义）：`pass` → 该 case 该版判定**通过**（纯净可判版内计入 K；置 verify passed 需 K 满，非纯净 run 内 pass 不触发 verify passed、转 needs_review(`unclean_run`)）；`fail` → error 仍在（verify failed → 即时 reopen，cluster 回退 open、K 清零）；`na` 行（携带 `error_type`）→ 该 case infra 无法判定 → claimed cluster 置 needs_review（reason=`na`，同 run 同 error_type 聚合为批，见下）；case 在该 run **无结果行（缺行）≠ na** → 无终值，继续轮询至 claim TTL 超窗回退 open（K 不计数不终止），不触发 needs_review。

> **na 批量聚合载体（Task #4-② 契约修订 B-4，2026-09-03）**：同 run 同 error_type 的多个 `na` case 只生成**单条 review 批**——载体 `needs_review_batch`（run_id + agent + bound_version + error_type + 引用 case/link 列表 + status(open/resolved) + created_ts/closed_ts/closed_by 审计），不逐 case 置 needs_review；被引用各 claimed cluster **保持 claim**、由该批处置统一收口（批量 reopen → 各 cluster 回退 open 走 reopen；或补证据/升级），claim TTL 超窗仍兜底回退 open。单 case na（无同批）走上表 cluster 级 needs_review。处置入口：批量 `POST /backflow/needs-review-batches/{id}/resolve`（§8.4）；单 case na（无同批）走 cluster 级既有 `needs-review-resolve`。DDL §5.1 ⑦b。**（v1.4：本表亦承载 `unclean_run` 批，reason 值域 = {na, unclean_run}，聚合归属/撞键规避见下 v0.6.1 精化 blockquote。）**【v1.5 修订：批纯化 = 仅 unclean_run 批，na 退批改 cluster 级单点处置（§7.6 v1.5 ④）——本条 B-4 na 聚合不再适用。】**
>
> **处置语义（v1.3 排查补正）**：resolve 动作集 = {`reopen_cluster`（引用各 cluster CAS `claim→open`，conversion_record action=needs_review_resolve、detail 带批 id + reason；旧 link 已终态自动让出 cur_key 走 reopen 条）、`escalated`（超时升级走 §16 既有通道，批置 resolved，引用 cluster 由人工后续处置）}；**整批同动作、单事务原子**，不支持部分处置（同 run 同 error_type 同因，拆开无意义）；引用各 cluster 在批处置前保持 claim、不逐 case 置 needs_review。单 case 级处置动作同上、以 cluster 为单位。**【v1.6 R-9 放宽：语义化跳过非 claim 引用 cluster】** resolve(reopen_cluster) 事务内逐引用 cluster CAS `claim→open`；CAS 失败读当前态分流——已 open（claim TTL 超窗/回归 failed 自然回退）→ 目标态已达成，计 `skipped_already_open` 幂等跳过（非部分处置——处置目标「该错不再被 claim 锁死」已达成）；fixed（极端：K 满 auto-fixed 提前收敛）→ 计 `skipped_fixed`（错误确已修不再 reopen）；其余不可预期态 → 该 cluster 不处置、返回明细待人工复核。批整体仍**单事务**置 resolved；批级 CAS（status open→resolved）仍防双 admin 并发（后到者 409）；重试幂等安全。conversion_record 记逐 cluster 结果（reopened / skipped_already_open / skipped_fixed / manual_review）。

> **auto-fixed 判据重构落字（v1.4：纯净 run + 跨版本稳定序列，Task #4-② R5-R7 = offline `error-backflow-phase2.md` v0.6.1，2026-09-07 终审通过）**——B-1 语义「单 run pass→fixed」不再单独作 auto-fixed 依据，auto-fixed 仅在下列收敛条件下置：**【v1.5 修订指针：本条目 ① K 取值、② 纯净判据粒度、③ 聚合归属中 na 批部分已被下一条 v1.5 blockquote 修订，读取以 v1.5 为准；reentry(B-12) 与 K-TTL 收敛终点不变。】**
> - **K 稳定序列（B-11/R6）**：该 case 自 claim fix_version 起、**连续 K 个「纯净可判」版本 run 均无 fail** 才置 verify passed（K=2 默认、可配【实现约定】dict_config；fix_version 自身为第 1 版确认；K=1 兼容 v1.3 单版行为）。fail 任一版本 → verify failed、即时 reopen、K 清零；逐版判定追加 `verify_run_record` 时间线（载体为既有表，**不加纯净性列、不加 offline 字段**——纯净性由 recheck 从关联 run 的 `na_case==0` 派生，R6 载体承诺保持）。
> - **纯净 run 前提（B-10/R5）**：含技术性 na（`na_case>0`，error_type ∈ 技术失败域）的 run = 复现环境不可靠 → 其内 **pass 行不触发 verify passed**、转 needs_review；fail 行不受影响（强证据即时 reopen）；不纯净 run 不计 K 不清零（中断观察，非否定）。
> - **reason 值域与聚合归属（v0.6.1 定义①）**：needs_review reason 值域 = {`na`（error run na 结果行）、`unclean_run`（含技术 na run 内 pass 行）、`reentry_same_version`（R7）}；判分 na/会话快照不足等二期源不入值域。聚合：`na` 与 `unclean_run` 共用 `needs_review_batch`（聚合键 run_id+error_type），**同 (run, error_type) 至多一条、不撞 uk_batch_agg**——不纯净 run 该 error_type 同时含 na+pass 行时并入**单条 reason=`unclean_run` 批**（link_refs 引两类 case、reason 附技术 na error_type 明细），仅 na 无 pass 走 reason=`na` 批（沿 B-4）；`reentry_same_version` → **claim 级单条、不产批**（走 cluster 级 `POST /backflow/clusters/{id}/needs-review-resolve`）。resolve 动作集 {reopen_cluster, escalated}/整批单事务/处置前引用 cluster 保持 claim，均沿 B-4（§8.4）。
> - **reentry 同版本禁 auto-fixed（B-12/R7）**：generation>1（reentry 产物）cluster claim 填的 fix_version = 该 (agent,version) 已有 completed run 的版本 → 旧 run pass 属修复前证据 → **不得 auto-fixed**、转 needs_review（reason=`reentry_same_version`，处置详情提示「升级验证需人工或升版」）；改填新版本 → 新 run 走纯净 run + K 正常判据。§7.5「completed 不重建」守卫不放开（重建通道引入同版复验振荡、成本高收益低）。
> - **K-TTL 收敛终点（v0.6.1 定义③）**：verify passed 仅 K 满时置；收敛 = **两时钟先到者**——K 满 → cluster fixed（TTL 停钟）/ claim TTL(14d) 超窗 → 回退 open（K 观察中止、下轮 claim 重计）；TTL 自认领起算，K 观察/回查推进不重置、不延长 TTL；缺行/不纯净中断观察继续轮询至 K 满或 TTL 到期，无无限期挂起。
>
> **auto-fixed 判定语义 v1.5（R-1 claim_k + R-2 claimed-case 级纯净判据，2026-09-07 评审拍板落字）**——修订上 v1.4 ① K 取值、② 纯净判据粒度、③ 聚合归属三处，其余（判定源限定、多 run 选取序、reentry B-12 同版本禁 auto-fixed、K-TTL 收敛终点）沿 v1.4 不变：
> - **① K 取 claim 固化 `claim_k`（R-1/A1）**：claim 时将 K 固化为 `error_cluster.claim_k`（值域 {1,2}，claim CAS 同批写；claim API 可选入参 `k`、超域 400，缺省取 dict_config `auto_fixed_k_default`=2 并**写死固化值**）；verify passed = 「自 claim fix_version 起连续 **claim_k** 个纯净可判版本 run 均无 fail」。K **只读 claim 固化值、不实时读全局键**（防观察期改全局键致已攒序列验收标准漂移）。`claim_k=1` = fix_version 纯净可判版 pass 即 verify passed（等价 v1.3 单版判，判据仍含纯净 run + 判定产物体系，比 v1.3 严）。
> - **② K 观察窗口零推进可降、推进后锁死（R-1 评审②）**：claim 生命周期内 claim_k 默认不可改；**例外 = 零推进可降**——自 claim 起 K 序列尚无纯净 pass 入账时，claim 人可显式降 K（CAS + 审计 conversion_record）；一旦任一纯净 pass 入账（序列推进）即**锁死**至 claim 结束，防已攒序列验收标准被重释。TTL 回退 open 后重 claim 可改值、TTL 自新认领起算。**重 claim 同 fix_version 提示（R-1⑦，产品 guard 非硬校验）**：TTL 回退后重 claim 若 fix_version 与上次相同 → claim 表单动态提示「该版本 error run 已存在/可能已 pass，auto-fixed 将等第 {claim_k} 个不同版本；agent 不再发版请升版、选 k=1、或走 admin_review」（offline run 状态 claim 时不可见 → 只提示不强判；动态提示数据源 = R-5 版本活跃度查询，claim 表单交互并入 R-5 范围，R-1 只留接口）。
> - **③ 纯净判据粒度下钻 claimed case + na 影响域分流（R-2/B1）**：判据锚点从「整 run 纯净（`na_case==0`）」改为 **claimed cluster 对应 case 在 run R 的行 + run 内 na 的影响域**；na 的污染力按 error_type 归 **环境级 vs case 级**（error_type 值域权威源 = offline phase2 §6.4 影响域标注；online 消费侧按标注归类，**无标注的新 error_type 默认从严 = 按环境级 → 触发 unclean_run + 告警**）；**v1.7 R-19 修订（2026-09-07 拍板落字）**：case 级清单字面量对齐 executor 真值（`connect/sse_parse/http` → `connect_error/sse_parse_error/http_error`）+ **补入 `no_usage`/`contract_error`**（executor 契约/兜底层产出，executor.py L22-31，归 case 级）——从严兜底回归「仅兜底非常态」，不再因名字错位常态误触 unclean_run（权威标注随 offline phase2 v0.7.1 §6.4）：
>
> | error_type（na 源） | 归类 | 对同 run 其它 case pass 的影响 |
> |---|---|---|
> | circuit_open / interface_disabled / scheduler_unexecuted（调度未执行/回收） | **环境级** | 整 run 复现会话不可靠 → 他 case pass 存疑 → 触发 unclean_run |
> | http_client_error / pool_error（出站连接/执行池） | 环境级（从严） | 同上（executor 到被测 agent 通道层失败，疑 agent/环境整体） |
> | timeout / connect_error / sse_parse_error / http_error / no_done / body_too_large / no_usage / contract_error（该 case 与 agent 交互/契约失败；**v1.7 R-19 字面量对齐 executor 真值**——connect/sse_parse/http 补 _error 后缀，no_usage/contract_error 补入） | **case 级** | 只说明该 case 无证据，**不牵连**他 cluster 已跑通 pass |
> | missing_assertion / assertion_shape（判定素材缺失） | case 级 | 主路径 load 过滤前置、运行期仅防御；同左 |
>
> - **④ 判定映射（claimed cluster X，在 run R）**：① X 行 = fail → reopen + K 清零（强证据，不变）；② X 行 = pass 且 R **无环境级 na**（不论有无 case 级 na）→ 计 K（纯净可判）；③ X 行 = pass 且 R 存在**环境级** na → 不 verify passed、转 needs_review(reason=`unclean_run`)，不计 K 不清零（中断观察，非否定）；④ X 行 = na（case 自身，任意 error_type）→ needs_review(reason=`na`)，不计 K 不清零；⑤ X 缺行 → 无终值，轮询至 claim TTL（缺行≠na，不变）。
> - **⑤ reason 值域不变、触发与聚合收窄（R-2 评审②③）**：reason 值域 {`na`, `unclean_run`, `reentry_same_version`} 不变；`unclean_run` 触发从「含技术 na run 内 pass 行」窄化为「含**环境级 na** run 内 pass 行」；`needs_review_batch` **纯化 = 仅承载 unclean_run 批**（同 run 同环境级 error_type 下多个 pass 行 cluster 聚为单条批，沿 uk_batch_agg）；**纯 na cluster 退批** → cluster 级单点 `needs-review-resolve`（动作 reopen_cluster / escalated，或保持 claim 等下轮 error run 自然补判）；撞键裁定收窄 = v1.4「na+pass 并入单条 unclean_run 批」仅适用于**多个 unclean（pass 行）cluster** 之间，na cluster **不再被并入批**无辜批量 reopen。运行级 `na_case` 读面保留（展示/审计/告警），不再直接作纯净判据。
>
> **v1.6 修订（R-4 缺行成因诊断 + R-10 截断证据降级 + reason 值域 3→4，2026-09-07 R-3~R-10 评审拍板落字；offline 依据 error-backflow-phase2.md v0.7）**：
> - **① 缺行成因诊断（R-4）**：claimed case 持续缺行（自 fix_version 起无该版本 run 终值、按 ⑤ 轮询）时，claim 详情给出成因诊断入口——可能成因 = offline cap 截断挤出（newest-active-first 挡在 run 外）或未达终态。**v1.8 R-16（自动核对升级）**：recheck 判缺行时自动 GET runs?agent=&version= 拉该版 run、判 `case_id ∈ excluded_case_ids`（R-4 溢出 case 列表字段，落 list/detail 位置留 Phase B 核对）——∈ → 自动判**「窗口外欠测」**（非修复失败）→ 走错误量治理 / 人工 fixed；∉ → 维持「未达终态/其他」并引导人工去 offline 平台 `excluded-cases` 只读面兜底核对（§9.3）。判定维持：不自动 reopen、不进 needs_review、不计 K 不清零（维持 ⑤ 无终值轮询至 TTL）。不跨端保窗口（phase2 v0.6 L111 拍板维持）。
> - **② 截断复现证据降级（R-10）**：复现输入源原始 input >8K 被截断（`error_cluster.input_truncated=1`，§5.1④）→ 该 claimed case 相关 run 的 pass **不计 K、不置 verify passed** → needs_review(reason=`input_truncated`，claim 级单条、不产批)；fail 强证据不变（即时 reopen）；缺行不变。
> - **③ reason 值域 3→4（R-10）**：{`na`, `unclean_run`, `reentry_same_version`} + **`input_truncated`**（v1.5 R-2 钉死值域的有意扩展；聚合归属 = claim 级单条不产批，走 cluster 级单点 needs-review-resolve 同 reentry_same_version 通道）；`needs_review_batch` **仍仅承载 unclean_run 批**（input_truncated 不入批）。
>
> **v1.8 修订（R-13~R-17 H7 批 B 类 5 条，2026-09-07 逐条评审拍板落字；除 R-16 读面字段落点 + R-13 §6.2 刷新复制 = Phase B 立项/核对项外，offline 零机制）**：
> - **① R-13 截断判定位窗口化（接 v1.6 ②）**：`error_cluster.input_truncated` 语义从「首现只置不清」改 **当前判定态**——同键窗口内新现 trace 判定态到达（消费 step4）开簇/回填时**刷新**（单 trace 即刷：≤8K 判定态 0 → 清 0、>8K → 置 1，§6.2）；cluster 已 closed 不刷新（终态只读、迟到截断 trace 不推翻已 fixed）。效果：同键首现截断后，后续小输入纯净 trace 到达 → 位清 → 该 claim 观察窗内对应 run pass **可计 K**（escape 可达）；首现截断历史留已产出 needs_review(input_truncated) 产物 + cluster 详情警示，不因清位抹除。K 判据读位不变，仅位取值随判定态刷新。§6.2 同簇刷新复制 = online 机制代码新增，Phase B 立项。
> - **② R-14 unclean_run 载体口径归一（接 v1.5 ⑤/状态机表）**：unclean_run = 存疑非否定 → **只经 needs_review_batch 载体处置**，批引 cluster **保持 claim、不入 needs_review 态**（状态机 claim 迁移 reason 列已收窄剔除 unclean_run）；批引用期间 cluster 详情/列表**实时派生「被未决 unclean_run 批 Bx 挂起（该 run 环境级 na、pass 存疑、K 观察中断）」标注**（join 未 resolved 批 link_refs、JSON_CONTAINS cluster_id，免加列）；TTL 不豁免——批引用属不纯净中断观察，TTL 到期照常回退 open，批 resolve 时 R-9 skipped_already_open 幂等覆盖（处置目标「该错不再被 claim 锁死」已达成）。
> - **③ R-15 双通道优先级 = input_truncated 优先（接判定映射 ③/v1.6 ②）**：claimed case X 行 pass 同 run 同时满足「cluster input_truncated=1（截断证据）」+「R 存在环境级 na」→ 走 **input_truncated 单条**通道（cluster 级 needs-review-resolve，处置 = 人工复核/小输入重测治本），**不并入**该 run 的 unclean_run 批——批聚合 link_refs **排除自身截断的 cluster**；同 run 其余无截断 pass cluster 照常走批；reason=input_truncated、note 附「同版 run 含环境级 na」。依据 = 截断为该 case **纵向跨 run 固有**证据缺陷 > unclean_run 为该 run **横向单次**环境脏，横向批量归因不吞纵向个案治本。
> - **④ R-16 缺行成因诊断自动核对（接 v1.6 ① R-4）**：`excluded_case_ids`（offline run 只读面溢出列表）核对从「UI 引导人工」升级为**自动**——recheck 判 claimed case 在 bound_version run 缺行时自动 GET runs?agent=&version=、判 case_id ∈ excluded_case_ids：∈ 自动标「窗口外欠测」（cap 挤出、非修复失败）；∉ 维持未达终态并人工兜底。字段落 runs list/detail 位置 = Phase B 实现核对项。
> - **⑤ R-17 K 序列版本锚 = versions 读面（接 v1.4/v1.5 K 判据）**：候选版本序列从「出现过 error run 的版本序」改 **R-5 versions 读面（agent 已见 manual/held_out 版本全集 = 发版拓扑权威）取 ≥ fix_version 的全版本序**（window_days 默认覆盖 claim TTL 14d）逐版判：versions 有该版且 error run 有终值 → 判 K；versions 有该版但无 error run → **缺行中断**（下一可见 error run 不续缺环——中间版丢 run 时不得 v1(pass)+v3(pass) 假连续 → K 满 false-fixed）；该版 error run 迟到补建（R-3 差集）终态到达 → 补判推进。error run 由 manual/held_out 终态触发 → error run version ⊆ versions 全集，versions 恰补「有发版无 error run」维度。
>
> **v1.9 修订（R-22 收尾回填 na 统一 + R-23 timeout 三层语义分界 + R-21 root-late 幂等标记，2026-09-07 R-20~R-24 评审拍板落字）**：
> - **① R-22 收尾回填 na 统一钉死 `scheduler_unexecuted`（offline run 收尾语义，online 消费侧读面注）**：offline run 收尾三路径回填 na = **scanner 回收 + orchestrator cancel + run 级超时收尾**，一律同源 `error_type=scheduler_unexecuted`（调度级原因、非 case 交互失败）——「na case 必带 error_type」不变量（v1.4，§8.7 run_results）**全覆盖收尾路径**，needs_review_batch 聚合键 run_id+error_type 不回断链；timeout **不作收尾回填原因**（只作 case 级 na 源 + run 终态，见下 R-23）。实现期 offline 单测护栏断言收尾回填 na error_type 非空（offline phase2 §11.1 补注）。
> - **② R-23 timeout 三层语义分界（消除 run-timeout 文案/聚合张力，B-3 兜底边界闭合）**：① **case 级 na 源**——该 case 与 agent 交互超时 → run_results 该 case 行 na（error_type 走影响域矩阵 case 级行 timeout），reason=na、不牵连他 cluster pass；② **run 终态 timeout**——run 级超时中断（status=timeout）只表征该 run 未跑完，**不直接触发 needs_review**（na 行本身已承载，B-3：run 超时非 needs_review 源，兜底 = claim TTL 超窗回退 open）；③ **run 级超时收尾回填 na**（error_type=`scheduler_unexecuted`，环境级）→ 该 run 不纯净 → 关联 pass case 入 unclean_run 批（v1.5 R-2 环境级牵连，§7.6 v1.8 ②）——「run 超时非源」排除的是 timeout 事件**直接驱动** cluster 状态、**不排除**环境级回填污染的**间接作用**（② 与 ③ 合读消除文案张力：case 级 timeout 该 case na、run 收尾 scheduler_unexecuted 归环境、run 终态 timeout 仅中断观察）。
> - **③ R-21 root-late 幂等标记列**：`trace_judge_state.root_late_complement`（§4.3④/§4.4/§5.1⑩）——残 trace 判定后迟到的 root 级补判触发标记，防重放/多实例重复补候选重复聚类（§4.3④/§6.2 root-late 段落）。
>
- claim TTL 到期 / 回归 failed / 回查连续失败超时 → 分别回退 open / 保持 open / 聚类详情提示"回查失败待人工"（§16 容错，online 不退避重试超上限即提示）。

**reopen / 回归 failed 后再 claim（新 fix_version）**：回归 failed 回退 open → 旧 link 已终态（failed）自动让出 `cur_key`（§5.1 注）→ viewer 再 claim 填新 fix_version → assemble_job 为同 cluster 生成**新 link**（新 payload_id + 绑定新 fix_version，§6.3）→ offline 按新版本重新回归。历史 failed 留 `verify_run_record` 时间线，终态只读不被迟到 run 改写（§7.3）。

**`verify_status='invalidated'`（v1.1）本期不单独产生**：枚举值保留兼容，废弃统一走 `superseded`（含「人工判无效且不再重推」），避免 invalidated×invalidated 状态二义；结构自检驳回由 `offline_status=invalidated` + `verify_status=pending`（重推位）表达（§7.4）。

---

---

## 8. 后端 API 契约全集（backend `app/api/`）

> 依据：solution.md §8/§9/§12/§10/§11。前缀统一 `/api/v1`。鉴权三域：平台 JWT（viewer/admin）、Kafka SASL（agent 上报，**无 HTTP ingest**）、平台间服务凭证（offline，§8.7）。分页/错误码见 §1.5/§8.9。时间窗取值 `1h|24h|7d`。

### 8.1 认证（auth）

| Method & Path | 权限 | 说明 |
|---|---|---|
| `POST /auth/login` | 公开 | body `{username,password}` → `{access_token(15min), refresh_token, user{id,role}}`；失败计数锁定（§13.2） |
| `POST /auth/refresh` | 公开(refresh) | body `{refresh_token}` → 新 access/refresh；吊销即时生效（token version） |
| `POST /auth/logout` | 登录 | revoke refresh 会话 |
| `GET /auth/me` | 登录 | 当前用户 + 角色 |

### 8.2 链路查询 trace（维度1，§2/solution§8）

| Method & Path | 权限 | 说明 |
|---|---|---|
| `GET /traces` | viewer | 参数：`trace_id?` `keyword?`（任一即可都输）、`agent?` `interface?` `start_ts?` `end_ts?`、`page/page_size`。命中 trace 列表（`search_after` 深翻页；检索面限 **最近 7d**（可配）+ 结果上限 ≤200 + 超时 ≤3s + 慢查询熔断/限流）。**检索落 ES 前按 `body_search` 开关过滤 input/output/log_message 命中**（§5.2 注） |
| `GET /traces/{agent}/{trace_id}` | viewer | 该 trace 全节点：`(ts,parent,seq)` 树排序事件行（含 log 行引用）；异常节点红显标记；llm_call 高亮。**大 trace 防护**：日志行不进本响应（走 8.2 logs）；事件行单 trace 上限（【实现约定】500）+ 超时 |
| `GET /traces/{agent}/{trace_id}/logs` | viewer | 日志行分页懒加载（`page/page_size`），单独接口防上千日志行一次拉爆 |

> **body_search 后端置空（v1.1）**：接口级 `body_search=false`（默认）时，traces 列表/详情/logs 响应在**后端序列化前将 `input/output/log_message` 置空**，前端隐藏仅兜底（§13.4）；检索面在 ES 查询层已按开关过滤命中（§5.2 注）——两层都不泄露正文。

### 8.3 指标看板 metrics（维度2，时间窗路由 §5.3）

| Method & Path | 权限 | 说明 |
|---|---|---|
| `GET /metrics/overview` | viewer | 参数 `agent?`（缺省/空=**全站跨 agent**，§9.2）`window`。返回：时序点列（QPS + 失败率/超时率曲线，1h/24h/7d）+ 概览卡（QPS/P50/P95/P99/失败率/超时率）。数据源按窗口路由 rollup/实时（§5.3） |
| `GET /metrics/interfaces` | viewer | 参数同；返回接口明细：请求级 + LLM 调用级双指标 tab（含按 `model` 分组的 LLM 指标）；支持 `interface=` 过滤。LLM 失败率 = `status∈{error,timeout}` llm_call ÷ 总数 |
| `GET /metrics/anomalies` | viewer | 异常聚焦：**request 级**失败/超时排序 → 异常 trace 列表（联动 trace 详情）。不进 `request ok + llm_call error`（那归 llm-failures） |
| `GET /metrics/llm-failures` | viewer | **『LLM 调用失败』下钻段（v3.5.1）**：`request ok + 子节点 llm_call error/timeout` 的 trace 列表，逐条标注「降级/兜底现场，v1 不回流、L3 二期接入」——承载一期兜底劣化基础可见性（§2.4 前提成立才查得到） |
| `GET /metrics/agents` | viewer | **agent 下拉数据源（v1.13 新增）**：近 7d **纯实测去重 agent 列表**（`agent` terms agg freq desc、size ≤100），非白名单/字典合成；供指标过滤条 + 链路查询表单共用 |

> **metrics 端点默认护栏（O-1 已裁定，§10.1/§12.2）**：`agent` 缺省=全站 1h/24h 实时 agg **强制结果缓存** `metric_agg_cache_ttl_s=60` + agg 查询超时 `metric_agg_timeout_ms=3000`；`window=24h` 全站档另提供「按 agent 维度」下钻缩小扫描面；缺桶回退实时口径时响应带标记（§5.3）。overview/interfaces/anomalies/llm-failures 同套；agents 列表端点固定 7d 窗、缓存 key=`agents|*|7d` 同套护栏（v1.13）。

> **metrics 端点响应形状（实现钉定 v1.12 + agents 补 v1.13，与 §9.2 前端消费逐字段对齐）**：
> - `GET /overview` → `{window, agent?, source(rollup|realtime|mixed), fallback_hours[], covered_hours, cards{qps,p50,p95,p99,total,error,timeout,error_rate,timeout_rate}, series[{ts,count,qps,error_rate,timeout_rate}]}`。卡片 p50/95/99 = request 锚全量 duration_ms（含 error/timeout）；失败率=error÷total、超时率=timeout÷total；7d 卡片分位仅并 rollup 覆盖小时（§5.3，尾小时省略）。**`covered_hours`（v1.14）** = 7d 已 rollup 小时数（meta 判别、含"处理过零流量"小时），1h/24h 恒 0——UI 据此标注"分位基于 N 个已完成小时"（分位与计数不同样本口径，v1.14 注）。**series qps（v1.14）** = count ÷ **桶实际覆盖秒** `min(ts+桶宽,end) − max(ts,start)`：date_histogram 对齐整边界使首桶左越窗、尾桶（进行中小时）右越窗，按满桶宽除会虚低 → 尾桶折算后即真实"已过秒数"口径；error/timeout_rate 分母仍桶内 count。
> - `GET /interfaces` → `{window, agent?, source, fallback_hours[], request[{interface,total,error,timeout,p50,p95,p99}], llm[{interface,total,error,llm_failure_rate,models[{model,total,error,prompt_tokens,completion_tokens}]}]}`。支持 `interface=` 过滤；LLM 失败率 = `status∈{error,timeout}` llm_call ÷ 总数；7d 行级分位保持实时（§5.3）。
> - `GET /anomalies` → `{window, agent?, total, truncated, items[{agent,trace_id,interface,status,error_type,error_msg,ts,duration_ms}]}`——request 级 error/timeout 排序列表（sort ts desc、size ≤100，联动 trace 详情）；不进 `request ok + llm_call error`（归 llm-failures）。**total/truncated（v1.14）**：total = 窗口内真实条数（body `track_total_hits: True` 关闭近似），truncated = total > len(items)（size≤100 截断，UI「仅显示最新 N 条」提示）。
> - `GET /llm-failures` → `{window, agent?, total, truncated, items[{agent,trace_id,interface,request_status,llm_node_status,llm_error_type,llm_error_msg,model,ts}]}`——`request ok + 子节点 llm_call error/timeout` 兜底吸收现场，逐条前端标注「降级/兜底现场，v1 不回流、L3 二期接入」。**total/truncated（v1.14）**：total = 窗口内**失败 trace 去重数**（collapse 不改 hits.total → body `aggs.trace_total = cardinality(trace_key)` 独立算，缺 agg 回退 hits.total 仅容测试），truncated = total > len(items)。
> - `GET /agents`（v1.13 新增，v1.14 补 total/truncated）→ `{total, truncated, agents:[name,...]}`——total = `distinct` cardinality(agent) **真实去重总数**（terms size≤100 top 截断后仍需如实计数），truncated = total > len(agents)（UI「下拉仅显示最活跃 N 个」）；近 7d `agent` terms agg freq desc、size ≤100，agent 下拉与链路查询共用；不带 agent/window 参数、固定 7d 实测窗。
> 以上数据源按窗口路由 rollup/实时（§5.3）；anomalies/llm-failures/agents 是列表非聚合，恒读原始事件 index（rollup 丢 trace 身份）。

### 8.4 回流-聚类/用例（backflow，§7.6 状态机）

| Method & Path | 权限 | 说明 |
|---|---|---|
| `GET /backflow/overview` | viewer | 复验总览：open+claim 错误数、关联回归用例 verify 分布、**待修复集规模**（本地镜像推导 = offline_status=active ∧ verify∈{pending,failed}，标注「近似 offline 权威集」）、按 agent/接口/层分布 |
| `GET /backflow/clusters` | viewer | 列表/筛选：`agent interface layer status`（status 含 open/claim/fixed/inactive/needs_review + `watch=assembled/draft` 待拉取/确认筛选）；返回代表 trace（**`first_trace_id`**，ErrorCluster 既有列，前端跳 trace 详情）、input_hash、去重/生成计数、关联 link 摘要 |
| `GET /backflow/clusters/{id}` | viewer | 详情：cluster 元数据 + links（case_id/case_type/offline_status/verify_status/source/payload_id）+ 该 case 历次回归 run **版本×pass/fail 时间线**（verify_run_record）+ conversion_record 审计时间线 + 「已待 N 天」与 requeue 状态 + **`reentry_observe`（v1.20：claim/fixed 态 blocked 复发读数 `{count, latest_version, since_ts, mode}`，后端读 `trace_judge_state` 保留窗现算，非 claim/fixed 态为 null，§7.5）** + **`open_batches`（v1.20：`NeedsReviewBatch.status=open` 且 `link_refs` JSON 含该 cluster_id 的未决批，前端「被批挂起」徽标 + 处置整批入口，items = `{batch_id, run_id, agent, bound_version, error_type, ref_count}`）** |
| `POST /backflow/clusters/{id}/ignore` | viewer | ignore → cluster inactive（link 若现行 → superseded 后再停回查） |
| `POST /backflow/clusters/{id}/claim` | viewer | **必填** `{fix_version, note}`，可选 `k`（值域 {1,2}、超域 400；缺省取全局 dict_config `auto_fixed_k_default`=2）→ status=claim 并把 K **固化为** `claim_k`=k（claim CAS 同批写 + 审计；fix_version 为 R5 回查锚定，输入给候选提示 + trim/大小写归一防人手版本 ≠ agent 自报——Task #4-②）；返回复核窗截止（TTL 默认 14d）。**R7 联动（v1.4）**：generation>1（reentry 产物）cluster claim 的 fix_version 若命中该 (agent,version) 已有 completed 回归 run → 详情即提示「同版本旧 run 不作 auto-fixed 证据，需人工/升版验证」（最终判定见 §7.6 `reentry_same_version`）。**R-1 联动（v1.5）**：TTL 回退后重 claim 若 fix_version 与上次 claim 相同 → 表单按 agent 近期版本活跃度动态提示（数据源 = R-5 版本活跃度查询，R-1 只留接口）；claim 观察期降 K = 零推进可降、推进后锁死（§7.6 v1.5 ②，CAS + 审计） |
| `POST /backflow/clusters/{id}/reopen` | viewer | reopen → open（复发/误判） |
| `POST /backflow/clusters/{id}/needs-review-resolve` | viewer | **单条 needs_review 处置**（cluster 级；源 = **纯 `na` cluster**（退批后唯一通道，v1.5）、或 `reentry_same_version` / `input_truncated` 单条（R7 / R-10 v1.6），reason 值域 §7.6）：`{action: reopen_cluster 或 escalated, note}` → open（reopen）/ 超时升级走 §16；**unclean_run 聚合批走下表 `needs-review-batches`**（仅 unclean_run 批，v1.5） |
| `POST /backflow/needs-review-batches/{id}/resolve` | viewer/admin | **批量（unclean_run 聚合批，reason 值域 = {unclean_run}，v1.5 批纯化）处置**：`{action: reopen_cluster 或 escalated, note}` → **整批同动作单事务**（CAS `status=open`）；`reopen_cluster` = 引用各 cluster `claim→open` + conversion_record(action=needs_review_resolve)；返回逐 cluster 处置结果（reopened / skipped_already_open / skipped_fixed / manual_review，v1.6 R-9 语义化跳过非 claim） |
| `POST /backflow/clusters/{id}/fixed-review` | admin | admin 复核置 fixed：`{approve:true}` → fixed(closed_by=admin_review)；`approve:false` → reopen |
| `POST /backflow/links/{id}/invalidate` | admin | **仅 offline_status∈{assembled,draft}** 可人工 invalidate（`{reason}`；active 后不提供——废弃走 superseded+reopen） |
| `POST /backflow/links/{id}/requeue` | admin | invalidated→assembled 复位重推（复用 payload_id；§7.4 守卫 + 防抖） |
| `POST /backflow/links/requeue-batch` | admin | **批量 requeue（v1.6 R-7）**：body `{filter:{agent?, invalidate_reason:'online_content_gap'}}` → 逐行 §7.4 守卫 + 防抖 → 返回逐行结果 + skipped 原因（含可愈性标注，不愈行需 force 确认） |

### 8.5 Agent 与接口字典（admin；solution §12.1 Agent 管理 → 本文件 §9.2）

| Method & Path | 说明 |
|---|---|
| `GET /agents` | agent 清单（enable、route_source、维度3 白名单） |
| `POST /agents/{id}/toggle` | 启停 agent（停用=停止该 agent 回流/指标入口？——**仅停回流生成与展示，消费不停**【实现约定】，防数据黑洞） |
| `GET /agents/{id}/interfaces` | 接口字典清单（自动发现、llm/llm_source/llm_suspect/body_search、first/last_seen） |
| `PUT /interfaces/{id}` | admin 补标：`{llm?, llm_source?, body_search?}`（归一化核对 = 修改 interface 串需记 conversion 审计【实现约定】）；疑似漏标告警处理（§8.5） |
| `GET /agents/{id}/credential` | Kafka 凭证查看（secret 脱敏 + 轮换入口；admin） |
| `POST /agents/{id}/credential/rotate` | 凭证轮换（版本化、吊销即时生效=撤 ACL+断连接，§13.2） |
| `GET /agents/{id}/health` | agent 上报健康小卡：最近 1min/5min 上报事件量、dropped、spool_pending、last_seen_ts（读自监控心跳 `obs.selfmonitor`，§3.6/§13.2）；agent 未接入=无 last_seen，前端据此出「未接入 SDK」文案（§9.1） |

**8.5.1 疑似漏标自动补标（§10.1 观察窗，v3.4.5 裁定）**：接口观测到 llm_call 且 `llm=false` → `llm_suspect=1`；连续观测达阈值（【实现约定】窗口 24h 内 ≥ 10 次）→ 自动 `llm=true`（source=auto_observed）不再疑似；观察窗内存疑 → `llm_suspect=1` 进 admin 复核列表 + 看板/Agent 管理「疑似漏标告警」。

### 8.6 配置与用户（admin）

| Method & Path | 说明 |
|---|---|
| `GET /configs?agent=` | dict_config 全量；**分「v1 生效 / 二期规划（灰置）」两组渲染**（§9.1/§9.2 两组渲染规则；后端只返回 v1 键，二期键不建） |
| `PUT /configs` | body `{agent_id?, key, value}` → 写 dict_config，`version+1`、记审计（admin-only；detail 记到 **config_key 粒度 + 旧/新值摘要**，§13.5；词表键变更特别提示 §10） |
| `GET /users` `POST /users` `PUT /users/{id}` | 账号 CRUD：角色 admin/viewer、启停（禁用即吊销会话，token version+1，§13.2） |

### 8.7 平台间（D20；offline 服务凭证，独立最小面）

**offline → online（pull 侧，v1）**：

| Method & Path | 说明 |
|---|---|
| `POST /pull/payloads` | 拉取 assembled payload：请求 `{schema_version:"1.0", case_type:"regression_error", agent?, limit≤100, since_ts?}`。**case_type 白名单校验：非白名单返回空集而非全量**（§12 加固）。响应 `{payloads:[{…信封全文(§7.1), assembled_ts}], next_token?}`，按 `assembled_ts` 升序。**契约修订 R1（v1.2）**：payloads 每条元素 = 信封全文 + 顶层 `assembled_ts`（online 组装/最近 requeue 时刻，ISO8601 UTC）——offline 增量锚唯一可靠来源（水位取 max、空轮不前移），不依赖 offline 本地墙钟；`since_ts` 语义 = `assembled_ts ≥ since_ts`，requeue 刷新后重推案重新进入范围（§7.2/§7.4） |
| `POST /pull/ack` | 拉取/状态回写：`{payload_id, action∈{draft,active,invalidated}, case_id?, reason?}` → 按 §7.3 表更新（payload_id upsert 幂等；**已知** payload_id 重复 ack=200）。**ack 前置矩阵（v1.2，含契约修订 R2 例外）**：draft 前置 `assembled`；active 前置 ∈{assembled,draft} 且**必带 case_id**，或 ∈{invalidated 且 reason=`offline_cap_gap`}（重扫自愈回写，契约修订 R2）；invalidated 前置 ∈{assembled,draft} 且必带结构化 reason（码见 §7.4）；前置不符→`ERR_CLUSTER_0003`（**响应带当前 `offline_status`+`invalidate_reason`**，契约修订 R3）、未知 payload_id→`ERR_PULL_0003` |

**online → offline（回查侧，v1；offline 实现，online 侧 client 契约）**：

| Method & Path | 说明 |
|---|---|
| `GET {offline_base}/api/v1/runs?agent=&version=&status=&case_id=` | 按 agent+version+status 过滤回归 run（`status` 取值集 = `{completed, partial_failed, timeout, cancelled}`，recheck 轮询**不传 running/pending**——Task #4-② 契约修订 B-1(c)）且**支持按含 case_id 过滤**（offline 补强，Task #4）；响应该版 run 含 cap 溢出 case 列表 `excluded_case_ids`（R-4 字段），供缺行诊断自动核对（v1.8 R-16，§7.6 v1.6 ①） |
| `GET {offline_base}/api/v1/runs/{run_id}/results?case_id=` | run_results：`case_id + case_type + pass_fail`，na case 必带 **`error_type`**（platform 只读面补强，Task #4 批 1 §8.2；**v1.9 R-22：收尾回填 na 三路径 scanner 回收/orchestrator cancel/run 级超时收尾统一 `error_type=scheduler_unexecuted`，「na case 必带 error_type」不变量全覆盖收尾路径，offline phase2 §6.3/§6.4**） |
| `GET {offline_base}/api/v1/agents/{agent}/versions?window_days=` | **agent 已见版本列表（v1.6 R-5 新增只读面，offline 实现/online 消费）**：manual/held_out runs 的 distinct version + 最近终态时间（含 cap 溢出 case 数 `case_truncated_count` 聚合，供 R-4 核对）——claim 软校验「fix_version ∉ 已见版本」告警与版本活跃度 K 提示数据源（§7.5/§8.4/§9.3）；**v1.8 R-17 用途升级 = K 判据序列源**——recheck 以其取 ≥ fix_version 全版本序作回查候选版本序列（§7.6 v1.8 ⑤），window_days 默认需覆盖 claim TTL 14d 防序列截断 |

> online 消费规则：回查只读、不写 offline；连续失败退避重试、超上限在聚类详情提示「回查失败待人工」（§7.6/§16）。online `http.py` 客户端持 offline 服务凭证、双向认证（§13.5）。**v1.5 判定依赖（R-2/B1 修订）**：run 级读面 `na_case`（保留展示/审计/告警）+ per-case `error_type`（判定按 §7.6 v1.5：claimed case 行纯净判据 + na error_type 影响域 环境/case 归类，`na_case==0` 不再直接作纯净判据）。

### 8.8 鉴权与守卫要点（后端）

- 平台 JWT：短效 access(15min) + refresh(7d)；token version 吊销；失败锁定。
- 路由级：`viewer` 可访问 8.1~8.4；`admin` 才可 8.5/8.6 + 8.4 中 admin 动作；**前端隐藏 + 后端二次鉴权双保险**。
- 平台间端点仅接受 evaluator 服务凭证（独立签发路径），不接平台 JWT。
- 正文查看需 viewer + 接口 `body_search=true`（无 per-agent 授权域，R2）；`body_search=false` 时后端响应前置空正文（§8.2 注/§13.4）。
- metrics agg / trace 检索默认带超时与结果护栏（`metric_agg_timeout_ms` / `trace_query_timeout_ms` / 结果上限，§8.2/§8.3/§10.1），超时熔断引导缩小范围而非长查询拖死。

### 8.9 错误码（统一 `core/errors.py`）

| 码 | HTTP | 场景 |
|---|---|---|
| `ERR_AUTH_0001` | 401 | 凭证缺失/过期/吊销 |
| `ERR_AUTH_0002` | 403 | 角色不足 |
| `ERR_AUTH_0003` | 423 | 失败锁定 |
| `ERR_TRACE_0001` | 404 | trace 不存在/超保留期 |
| `ERR_TRACE_0002` | 400 | 检索超时/结果超上限（引导缩小范围） |
| `ERR_METRICS_0001` | 400 | 时间窗/聚合参数非法；rollup 缺桶回退提示随响应体 |
| `ERR_CLUSTER_0001` | 404 | cluster/link 不存在 |
| `ERR_CLUSTER_0002` | 409 | CAS 状态冲突（他人已操作），返回当前状态 |
| `ERR_CLUSTER_0003` | 400 | 非法迁移（如 active case 人工 invalidate；claim 缺 fix_version）。**ack 前置不符时（契约修订 R3）响应体带当前 `offline_status`+`invalidate_reason`**（供 offline 对账 manual-invalidate 竞态等，§8.7） |
| `ERR_CONFIG_0001` | 403 | 词表等 admin-only 键变更被拒 |
| `ERR_PULL_0001` | 401 | evaluator 凭证无效 |
| `ERR_PULL_0002` | 400 | case_type 非白名单 / schema_version 不识别（返回空集约定在 8.7，强校验失败 400） |
| `ERR_PULL_0003` | 404 | payload_id 不存在（对**已知** payload_id 的重复 ack = 200 幂等成功；对**未知** payload_id = 404；§7.3 ack 矩阵） |

---

---

## 9. 前端页面规格（Vue3 + Vite；依据 solution.md §12.1 + §9.3）

### 9.1 全局约定

- 路由/菜单树见 §1.2/§12.1（solution）；**viewer/admin 按角色渲染菜单，admin-only 路由前端隐藏 + 后端二次鉴权**。
- 默认落点 = 指标看板 `/dashboard`（全站纵览 tab）——**v1.11 注（历史）**：dashboard 属阶段 2（T-2.4）未就位，阶段 1 登录后先落 `/traces`（链路查询列表）；**v1.12 兑现（阶段 2 平台轨收口）**：dashboard 已落地，登录成功落点 + `'/'` redirect + catch-all 路由守卫已改回 `/dashboard`（task.md 阶段 2 收口注）；**v1.13 重构（前端 IA）**：dashboard 内四段拆**五个一级菜单 1:1 落页**（总览 `/dashboard` / 接口 `/interfaces` / 异常 `/anomalies` / LLM 失败 `/llm-failures`，链路查询 `/traces` 接独立壳），默认落点 `/dashboard`（= 总览页）不变；布局壳 = App.vue 吸顶双行（品牌+用户行 / 一级菜单行，登出态整壳隐藏）。**四个 metric 页共享 `MetricFilterBar`**（Q3，§9.2 下表注）：agent 下拉（全站 + §8.3 agents 实测列表）+ window 1h/24h/7d，默认 24h/全站、localStorage 持久化跨页继承；agent 下拉同源复用链路查询表单（Q6）。**v1.14 MetricFilterBar 增强**：① 幽灵 agent 清除——localStorage 持久化的 agent 掉出「近 7d 有流量」列表时 `<select>` 会空显但 filter 仍指向它（静默"全站口径却有过滤"），现检测到即显 warn「『X』已不在近 7d 有流量 agent 列表（可能已下线/改名）——当前筛选实际无数据命中」+「清除为全站」；② top100 截断提示——`agents.truncated` 时显「近 7d 共 N 个 agent，下拉仅显示最活跃 M 个」；③ 前台可见性刷新——`visibilitychange` 回前台且距上次拉取 >60s 才 `loadAgents(true)`（会话中新上线 agent ~1min 内可见，不引轮询）。**v1.20 第六个一级菜单登记**：新增「回流看板」`/backflow`（= v1.13 五菜单之后第 6 项，§9.2）；详情 `/backflow/clusters/:clusterId` 走独立路由壳 + 父菜单高亮映射（仿 `trace-detail`→`traces`）；**回流页 viewer/admin 均可见（无菜单级 gating，admin-only 动作按钮详情页内按角色隐藏）**；**二期物（弃留墙入口 / trace quality 过滤）在本页零入口——整条隐藏不渲染（非灰置）**。
- 空态与误读防呆（v3.5.1 易用性规则，实现为统一 `<EmptyState type=.../>` 组件）：
  - `needs_review` 状态筛选保留（error run 的 `na` 结果行可入列——case 级 infra 无法判定，reason 带 run_id+error_type，同批聚合，§7.6），**缺省为空属正常非功能缺失**。
  - 二期物（L3 质量出口 tab、弃留墙入口、trace quality 过滤/标记）**整条隐藏不可达、不灰置**；仅原始事件 JSON 不可避免暴露 `quality:null` 时行内提示「quality 观测为二期规划（v1 未采集），为空属预期，非采集故障」。
  - 配置管理「二期规划」组灰置 + 角标 + tooltip（键清单 §10.2）。
  - **看板「无数据」区分（防空报「采集故障」）**：`EmptyState.type` 细分——`no_agent`（该 agent 无 last_seen，未接入 SDK，数据源 §8.5 health）／`no_traffic`（有心跳但窗口无请求量）／`no_rollup`（7d 档缺桶，回退实时口径标注 §5.3）／`second_phase`（二期物，隐藏不可达）；接口/tab 按各自数据源落 type 与文案。**v1.13 空态分页归位**：总览 = no_traffic/no_rollup（沿上）；接口双 tab 均空 = no_traffic（有桶才出明细 section）；**异常/LLM 失败的空列表 = 「窗口内无异常 / 无 LLM 失败现场」有效空态，非 no_traffic**（各自 section 自带准确空文案，payload 未就绪不渲染该文案以免误导，§9.2 行注）。

### 9.2 页面功能点 → 数据源（API §8）

| 页面（路由） | 功能点 | 数据源 |
|---|---|---|
| 登录 `/login` | 登录、会话维持、角色归属 | §8.1 |
| 总览 `/dashboard` | 跨 agent 指标纵览（QPS 时序 + 失败率/超时率叠加 + 概览卡），agent 缺省=全站；数据源徽标（实时/小时聚合/mixed）+ 7d 缺口横幅；**7d 分位口径注（v1.14）**：「分位(P50/P95/P99) 基于 N 个已完成小时聚合（截至上一整点，迟到流量不计入分位）；总数/失败率/序列为实时全窗」——source∈{rollup,mixed} 时渲染（卡片下、无缺口时也显）；**自动刷新 v1.14**：45s + 后台（document.hidden）暂停 + 回前台且 >15s 陈旧补一轮（45< 后端 60s 缓存 TTL 非整约 → tick 命中缓存存活期、后端实查约减半；仅本页自动） | §8.3 overview |
| 接口 `/interfaces` | 接口明细：请求级 + LLM 级双 tab（model 分组）；行级分位/计数实时整窗；空（双 tab 均空）= no_traffic | §8.3 interfaces |
| 异常 `/anomalies` | request 级 error/timeout 倒序列表；行点击下钻 trace 详情；空列表 = 「窗口内无异常（错误=0）」有效空态；**截断提示（v1.14）**：`total > len(items)` 时「窗口内共 N 条，仅显示最新 M 条」 | §8.3 anomalies |
| LLM 失败 `/llm-failures` | request ok + 子节点 llm_call error/timeout 兜底/降级现场列表（标注「v1 不回流、L3 二期」）；行点击下钻 trace 详情；空列表 = 「窗口内无 LLM 失败现场」有效空态；**截断提示（v1.14）**：同上（total = 失败 trace 去重数） | §8.3 llm-failures |
| 链路查询 `/traces` | traceId/关键字自由输入（可任一）；命中列表 + **动态 agent 下拉**（全站 + §8.3 agents 实测列表，Q6）→ trace 详情 | §8.2 traces |
| trace 详情（共享抽屉） | `(ts,parent,seq)` 树时间轴；异常节点红显；日志行分页懒加载；input/output/error_msg 脱敏展示；llm_call 高亮；正文查看受 `body_search` | §8.2 traces + logs |
| 回流-错误聚类 `/backflow`（v1.20 已实现） | cluster 列表/筛选 + overview 卡；**代表 trace（`first_trace_id`，点击跳 trace 详情）**、input_hash、状态 pill·generation·count·first/latest ts·fix_version；复验总览（cluster 状态分布 / link verify 分布 / 待修复集规模标注「本地近似 offline 权威集」/ by_agent 分布）；筛选 agent·interface（近 7d 实测并集）·layer·status·watch + 分页；静态 + 手动刷新（不轮询） | §8.4 backflow/clusters + overview |
| 回流-聚类详情 `/backflow/clusters/:id`（v1.20 已实现，独立路由） | links 表（case_type/offline_status/verify_status/source + **admin** invalidate/requeue）、版本×pass/fail 时间线、conversion_record 中文时间线、人工操作区（ignore/claim/needs_review-resolve/fixed-review/admin 动作，按 §9.4 门控置灰）、claim 复核窗倒计时（1s tick + 45s 可见轮询，超时回退 open 提示）；**input_truncated 当前判定态警示 + 被未决 unclean_run 批挂起徽标 + open_batches「处置整批」入口（v1.8 R-13/R-14、v1.20 R-14 批读面：读 `link_refs` 关联、不新增存储列）**；**reentry_observe 复发 caption（v1.20，§9.3）** | §8.4 cluster/{id} + link 操作 |
| Agent 与接口字典 `/admin/agents` | agent 启停；接口字典（llm 补标/疑似漏标告警/归一化核对/正文开关）；凭证查看/轮换；**agent 上报健康小卡**（未接入/无流量区分依据，§9.1） | §8.5 |
| 配置管理 `/admin/configs` | dict_config 两组渲染（v1 生效/二期灰置）；词表维护（空表守卫提示） | §8.6 |
| 用户管理 `/admin/users` | 账号 CRUD、角色、启停 | §8.6 |

### 9.3 关键交互与状态文案（实现时逐条对照）

| 场景 | 文案/交互 | 规则来源 |
|---|---|---|
| link offline_status=assembled | 标「已生成（待 offline 拉取）」 | §7.3/§12.1 |
| offline_status=draft | 标「已生成用例（待 offline 确认）」 | 同上 |
| offline_status=invalidated | 「结构自检失败（invalidated）——本错误仍在观察：窗口期内同键不再自动重生成；offline 能力补齐/修正现场后可重推；长期停留请联系平台管理员」+ 重推状态展示（offline 重扫自愈中 / admin 可重推） | §6.2/§7.4 |
| verify pending + fix_version 无 run | 提示「待 &lt;version&gt; 回归 run」 | §7.6 |
| 回查连续失败 | 提示「回查失败待人工」 | §7.6 |
| claim 行 | 展示复核窗口剩余时间 + 固化 K（claim_k）取值；表单含 k 选择（1/2，缺省取全局默认）+ 版本活跃度动态提示 + claim 前 fix_version 软校验告警「未观测到该 agent 该版本评测 run——可能未发版或字面量不匹配，已见版本：…」（数据源 = offline `agent 已见版本`读面 §8.7，v1.6 R-5 兑现，非硬拦；**v1.20 做全**：P2-6 claim 端点前置查 `agent_versions(agent, window_days)` 读面 best-effort——fix_version 未见于已见版本 → 行内告警列出已见版本，offline 未配置/读面不可达 → 返 None 沿用既有 generation>1 软提示；**仍非硬拦**，正常新 fix 尚未跑回归时可能亮属 informational）；超窗回退提示 | §7.6/§8.4 |
| claim/fixed 同键复发 caption（v1.20 新增钉定措辞） | `mode=fixed`（count>0 才显）：「同键新版本 &lt;latest&gt; 复发 N 次（judge 保留窗内现算；版本未过 reentry 门控未开新簇）；若非属本 fix 请 re-claim / reopen」；`mode=claim`：「自认领起同键线上再现 N 次（已计入观察计数），最新版本 &lt;latest&gt;」——读数 = 后端 `reentry_observe`（§7.5 现算口径，非 ES 派生）；保留窗 `trace_judge_purge_days`（默认 7d）外 blocked 行物理消失、计数回退属预期，caption 已标「保留窗内」 | §7.5 v1.20/§8.4 |
| 未决 unclean_run 批挂起 + 处置整批（v1.20 前端兑现） | 批引 cluster 详情/操作区显「被未决批 B&lt;id&gt; 挂起」徽标 + 「处置整批」按钮（调 `needs-review-batches/{id}/resolve`，整批同动作）；读面 = detail 响应 `open_batches`（`link_refs` JSON 关联，v1.8 R-14 的实时派生口） | §7.6 v1.8（R-14）/§8.4 |
| claim 回查持续缺行（无该版本 run 终值） | 诊断「可能 = offline cap 截断挤出（newest-active-first 挡在 run 外）或未达终态」+ 引导核对 offline 平台 `excluded-cases` 只读面；确认为挤出 → 标「窗口外欠测，非修复失败」→ 错误量治理/人工 fixed（不自动 reopen、不进 needs_review、轮询至 TTL） | §7.6 v1.6（R-4）/offline 只读面 |
| assembled 已待 N 天超阈值 | 提示性标记「offline 疑似停摆，人工核查」（非告警、不设时钟） | §7.2/§13.5 |
| link invalidated 驳回（reason 码区分） | `offline_cap_gap`→「offline 能力补齐后自动恢复（重扫自愈）」；`online_content_gap`→「现场已修正，待 admin 重推」；`manual_invalidate`→「已人工判无效，可重推或弃用」 | §7.4/§8.7 |
| invalidated 列表批量重推 | 「批量重推」动作 + 可愈性标注（空词表/字段缺=可愈可勾选；版本不识别=禁勾、强确认才放行）+ 结果逐行回显 | §7.4/§8.4 v1.6（R-7） |
| cluster status=needs_review | reason 值域 {`na`（该 case infra 无法判定，cluster 级单点处置）、`unclean_run`（环境级 na 污染下 pass 存疑，批量处置）、`reentry_same_version`（同版本旧 run pass，需人工/升版）、`input_truncated`（复现输入截断证据不可信，需人工复核或小输入重测，v1.6 R-10）}：补充证据回 open / 升级（v1.6 口径） | §7.6 |
| 词表空 | 配置页/组装提示「空词库守卫不生效（fail-closed）」 | §10.1/§7.1 |
| 历史通过被 superseded | 展示「历史通过于 V_x / 现又复发」 | §6.2 |
| 总览 7d 分位口径（v1.14） | rollup/mixed 时卡片下注「分位(P50/P95/P99) 基于 N 个已完成小时聚合（截至上一整点，整点后迟到流量不计入分位）；总数/失败率/序列为实时全窗」——明示分位与计数是不同样本，防空读「卡与图对不上」 | §8.3/§9.2 |
| 幽灵 agent（v1.14） | 持久化 agent 掉出活跃列表：「『X』已不在近 7d 有流量 agent 列表（可能已下线/改名）——当前筛选实际无数据命中」+「清除为全站」（=`agent=''`） | §9.1/§8.3 agents |
| agent top100 截断（v1.14） | 「近 7d 共 N 个 agent，下拉仅显示最活跃 M 个」 | §8.3 agents |
| 列表截断提示（v1.14） | anomalies/llm-failures `truncated`：「窗口内共 N 条，仅显示最新 M 条」（llm-failures 文案为「共 N 条失败现场」） | §8.3 |

### 9.4 viewer 可操作集（不含测试集确认）

ignore / claim（必填 fix_version+说明）/ needs_review 处置 / reopen；**不能单方置 fixed**（需回归 passed 或 admin 复核，R4）。case 级 invalidate 仅 admin（§8.4）。

**动作 × 状态门控（后端同规则，前端据此置灰/禁用，防点后被 409/400 拒）**：
- claim：仅 `cluster.status=open`；claim 中 → 置灰；
- ignore：`status∈{open,claim}`（claim 中先回退 open 再 ignore，需二次确认）；
- reopen：`status∈{fixed,inactive}`；
- needs-review-resolve：`status=needs_review`；
- fixed-review(admin)：`status=claim`；
- link invalidate(admin)：仅 `link.offline_status∈{assembled,draft}`（§8.4）；
- link requeue(admin)：仅 `offline_status=invalidated` 且 `verify_status=pending` 且 `cluster.status ∈ {open, claim, needs_review}`（§7.4 守卫 v1.9 R-24 + 防抖；fixed/inactive 禁 → superseded+reopen）。

---

## 10. 配置项清单（dict_config；admin-only 维护 + 审计）

> 键分「v1 生效」与「二期规划（不建键，前端灰置占位）」。`version` 字段：任何变更 +1；`fallback_utterance` 的 version 即 `wordlist_version`（随 D19 `no_fallback_config` 快照固化，§7.1）。

### 10.1 v1 生效键

| key | 作用域 | 默认 | 校验/说明 |
|---|---|---|---|
| `fallback_utterance` | per-agent | 空表 | JSON 数组（词条）。**no_fallback 断言唯一词源**；词条仅子串/关键词匹配（不按正则）；变更 admin-only + 审计；**空表=守卫 fail-closed**：信封照建→offline 结构自检不过→回写 invalidated（v1.1 语义收敛，`inconclusive` 属二期）→ 配置页提示 |
| `timeout_ms` | per-agent | 【实现约定】LLM 请求 30_000 | 上报打标阈值参考（SDK 按接入约定打标，平台不二次判；此键供看板"疑似超时"标签与接入约定单源） |
| `cluster_window_days` | 全局 | 7 | error 去重窗口（§6.2） |
| `claim_ttl_days` | 全局 | 14 | claim 复核窗（§7.6；**收敛 = 两时钟先到者**：K 满 → fixed 停钟 / 本 TTL 先到 → 回退 open，K 观察/回查推进不延长本 TTL，v1.4） |
| `auto_fixed_k_default` | 全局 | 2 | claim 表单缺省 K / `claim_k` 缺省取值（§7.6 判定语义 v1.5，R-1/A1；值域 {1,2}；claim 时固化 `claim_k`，观察期只读固化值、不实时读本键） |
| `backflow_enabled` | per-agent | true | 回流总开关（gq/cs/sp；cc 恒 false） |
| `llm_call_observe_window_min` / `llm_call_observe_threshold` | 全局 | 24h / 10 次 | 疑似漏标自动补标窗口（§8.5） |
| `trace_judge_window_s` / `trace_judge_grace_s` | 全局 | 60 / 300 | 判定态完成窗口（§4.3） |
| `rollup_late_k_h` | 全局 | 6 | rollup 迟到重算窗（§5.3） |
| `keyword_search_days` | 全局 | 7 | 关键字检索限窗（§8.2） |
| `metric_agg_cache_ttl_s` | 全局 | 60 | metrics 四端点**全站**实时 agg 结果缓存（§8.3 护栏 / §12.2 O-1） |
| `metric_agg_timeout_ms` | 全局 | 3000 | metrics agg 查询超时（超时熔断 → 提示缩小范围，§8.8） |
| `trace_query_timeout_ms` | 全局 | 3000 | trace 检索超时（§8.2） |
| `trace_judge_purge_days` | 全局 | 7 | 判定态已处理行清理保留期（judge_scan_job 顺带清，§4.3/§5.1⑩） |

### 10.2 二期键（v1 不建键、不提供入口）

`session_context_rounds`（N 轮，C2）、`theta_low_confidence`、`refusal_decline`、`hedge_uncertainty` 词表、弃留墙阈值、judge 放行开关等——前端按「二期规划组」灰置展示 tooltip，后端无对应行（§9.1 空态规则）。

---

---

## 11. agent 接入与存量整改（obs-sdk + 4 agent）

> 依据：solution.md §13.0/§13.1。**平台是权威、agent 只适配**；接入本质 = 新增「观测边带」，产出 §2 同构事件。SDK 是 Python 参考实现，任何语言产出同构 JSON 事件即视为已接入（就近 Kafka 直发，§3.3）。

### 11.1 obs-sdk 对外 API（v1，`sdk/obs_sdk/`）

| 调用 | 签名要点 | 语义 |
|---|---|---|
| `init()` | `init(agent, *, kafka_servers, sasl_username, sasl_password, topic, spool_dir="/var/lib/obs-sdk", flush_batch=500, flush_interval_s=2, log_mode="stdlib")` | 装配：读 `AGENT_VERSION` env 注入；挂 logging Handler（默认）或等 structlog processor（§11.3 sp）；**必须在 agent 日志体系装配后调用** |
| `begin_request()/end_request(...)` | 入口生成/透传 `trace_id`；出口收口 `status/duration_ms/error_type/input/output` | 归一化 interface 由内部 `normalize_route(method, path)` 完成（动态段→`{id}`） |
| `record_llm(...)` | `record_llm(model, status, error_type?, error_msg?, usage, duration_ms, attempt_total?)` | **每逻辑调用一条**；裸调用异常先记 error 再抛（§2.4 前提）；内部退避 attempt 不上报 |
| `record_tool/record_retrieve` | v1 仅 `record_tool(name, status, duration_ms)`；`record_retrieve` **二期不暴露** | 取数节点 v1 只记基本调用 |
| `record_db/record_redis` | `(host?, status, duration_ms, error_type?)` | 建议打点 |
| `log(...)` | 通过 logging Handler / structlog processor 自动注入 trace_id/seq | 日志行占 seq 槽位 |
| `heartbeat()` | 平台自监控信号（1/min，`obs.selfmonitor`） | §3.6 |

**trace 上下文（SDK 内部）**：contextvar 承载 `(trace_id, seq_counter, branch)`；seq 原子自增（节点与日志行共用一把计数器，§2.4）；并行分支由业务显式 `branch()` 标注。

**二期方法不暴露**：`record_quality` / `record_retrieve(hit)` / `record_session_state` 不在 v1 包导出（§2.8）。

### 11.2 接入流程落地（Step 0 → 三步 → checklist 转代码/验收）

| 阶段 | 动作 | 产物（进 agent 仓库） |
|---|---|---|
| Step 0 盘点 | 填 §13.0 8 项盘点表 | `docs/obs_access_inventory.md`（接入验收对照基线） |
| Step 1 | 观测通道：事件协议 + 日志接入三选一 + trace 上下文 + 必需打点 + 可靠降级 | `obs_sdk` 依赖 + 入口/出口插桩 + LLM 覆盖点清单 |
| Step 2 | 平台注册：topic/凭证（admin）、agent 录入、接口字典核对、正文开关/词表、回流白名单 | 平台侧 §8.5 操作记录 |
| Step 3 | 灰度 1~2 个代表接口 → 放量门禁（#1/#2/#3/#6/#7/#9）→ 全量 | 验收记录 + checklist 打分 |

### 11.3 4 个 agent 存量整改（对齐 solution §13.1，v1 只做 #1~#4/#6~#9，#5 二期延后）

| # | 整改项 | gq | cs | sp | cc |
|---|---|---|---|---|---|
| 1 | SDK init + 日志接入 | stdlib Handler | stdlib Handler | **structlog processor**：`core/logging.py` processors 链在 JSONRenderer 前插 SDK 转发器（或改 `PrintLoggerFactory`→stdlib LoggerFactory）；SDK init 在 `setup_logging()` 后执行；**sp 自有 `request_id` 规约为 `trace_id`** 注入事件帧 | stdlib Handler |
| 2 | `request` 入口/出口打点 | ✅（含 SSE 在 handler 出口聚合打一条） | ✅ | ✅ | ✅ 仅 request 级（上传/结果查询）；维度 3 不纳入 |
| 3 | `llm_call` 覆盖 | 统一网关 + **httpx 直连流式** 旁路；`ChatOpenAI.invoke`（rewrite 现注释禁用，接入时按实际核对） | 统一层 | 统一层 + **`conversation_service._summarize_with_llm` 自建 AsyncOpenAI 汇总旁路** | 不涉（无 LLM 回流；有 LLM 也仅指标？cc 属 D18 之外，llm_call 按需打点供指标） |
| 4 | `db`/`redis` 子节点 | 建议 | 建议 | 建议 | 建议 |
| 6 | 收敛自有埋点 | `_json_log` 并入 SDK | Prometheus `/metrics` 保留端点兼容 | — | — |
| 7 | 接口字典可枚举 | FastAPI/OpenAPI 自发现 | 同 | 同 | 同 |
| 8 | 正文默认关逐接口评估 | ✅ | ✅ | ✅ | ✅ |
| 9 | 回流白名单 | **开放（v1 error 侧）** | **开放** | **开放** | 否（D18） |

> #5（record_quality/retrieve_hit）二期整改，v1 不接——**§13.1 #5 的 sp `source_count/max_score/confidence_band` → retrieve_hit 归一映射属二期盘点记档**，接入时仅核对字段口径留档。

### 11.4 fallback_utterance 词表盘点（error 复验门禁前提，§13.0 checklist #10）

- 各 agent 在 §13.1 兜底逻辑处盘点已知兜底话术（**新增兜底话术即补词表**），产出 per-agent 词表 → 配入 dict_config（§10.1）。
- 词表语义：**子串/关键词命中**（不按正则）；组装时快照固化（§7.1 `no_fallback_config`）；空表守卫不生效（fail-closed）。
- 【盘点模板】`agent / 兜底分支位置 / 兜底话术样例 / 是否入词表 / 备注`——随 §11.2 盘点表进 agent 仓库。

### 11.5 接入验收 checklist 转可执行用例

放量门禁 #1/#2/#3/#6/#7/#9 → §14.1 冒烟用例；维度 3 开放验收 #4/#8/#10 → §14.2 回流用例（#4 含「兜底吸收基础可见性」埋点前提用例；#10 词表覆盖度随回流验收）。二期 #5 随 L3 开放补验。

---

---

## 12. 二期占位索引与 open 清单

### 12.1 二期占位索引（本文件各处「【二期】」集中登记；开发勿建）

| 面 | 占位物 | 一期处理 |
|---|---|---|
| schema 字段 | `quality` / `retrieve_hit` / `session_ctx` | §2.8（缺省/不索引） |
| SDK | `record_quality` / `record_retrieve(hit)` / `record_session_state` | §11.1 不暴露 |
| ES mapping | 二期字段 `enabled:false` + `dynamic:false` | §5.2 |
| dict_config 键 | 会话轮数 / θ / 三词表其余两张 / judge 开关 | §10.2 不建键 |
| 信封 | `regression_quality` / `session_snapshot` / `retrieve_hit[]` / assert 二期项 | §7.1 恒 null/缺省 + case_type 白名单空集 |
| DB | `error_cluster.signature_hash`（L3）等 | 不建列/不填 |
| UI | L3 质量出口 / 弃留墙 / trace quality 过滤 / 配置二期组 | §9.1 整条隐藏 |
| offline | quality 人工确认激活 / rejected 软删归档 / verifier quality 通道 | Task #4 二期排期 |
| needs_review | error run 结果行判定产物入 v1 源（reason 值域 {`na`, `unclean_run`, `reentry_same_version`, `input_truncated`(v1.6 R-10)}；v1.5 起 **unclean_run 批量聚合、na cluster 级单点（退批）、reentry_same_version claim 级单条**，§7.6 v1.5）；会话快照不足/判分 na/cc 文件型仍二期 | §7.6 needs_review 流转 |

### 12.2 open 清单（开发前需明确；O-1~O-3 已于 v1.1 裁定落稿，O-6/O-7 为部署约束派生项；余项不阻塞 P0/P1）

| # | 项 | 现状 | 建议 |
|---|---|---|---|
| O-1 | 全站 1h/24h 实时档无 agent 过滤的全量扫描护栏（性能评审 F-2） | **已裁定（v1.1）**：默认护栏 = agent 缺省「全站」档实时 agg 强制走结果缓存 `metric_agg_cache_ttl_s=60` + agg 查询超时 `metric_agg_timeout_ms=3000`（§8.3/§10.1/§14.4）；24h 档另提供「按 agent 维度」切换缩小扫描面 | P1 看板实现即落地，勿再拖（§12.2 不再视为开放） |
| O-2 | `fix_version` 组装时序（组装先于 claim 时 link 不含 fix_version） | **已裁定（v1.1）**：组装（§6.3）不写 fix_version；claim 后回查锚定 `cluster.fix_version`（§7.6 recheck_job + §5.1 verify_run_record.bound_version）；requeue 重推复用 payload_id | 与 Task #4 对账仅剩 offline 侧 run 绑定版本解析 |
| O-3 | 现行 link 唯一索引对「终态后再生成」的支持 | **已裁定（v1.1）**：改生成列 `cur_key`（仅 `verify_status='pending'` 占位），终态自动释放 → reopen / 回归 failed 后再 claim 可在同 cluster 生成新 link（新 payload_id，§5.1 注/§7.6） | — |
| O-4 | 7d 小时级 rollup 的 t-digest 库选型 | **已落地（2026-09-08，裁定变更）**：自研纯 Python t-digest（`backend/app/store/tdigest.py`）——原拍板引 PyPI `tdigest`，其 C 依赖（accumulation-tree）在无 MSVC 的 Windows 上只能源码编译（pip 实测失败）、本环境索引无纯 Python 替包 → **改自研**（用户确认）。JSON-base64 序列化（`{v:1, c:[[mean,weight],…]}`），只喂去重带权样本 + 超 K 单遍压缩 + 确定性（同输入同输出、跨平台无外部依赖） | 跨小时合并 vs 全量重算 p95 误差 <1%（§14.4 rollup 用例）；真实 rollup data 实测偏差 p50 0.35% / p95 0.04% / p99 0.17% 达标 |
| O-5 | agent 路由自动发现扫描器实现（仅 FastAPI/OpenAPI 可枚举 agent） | cc/cs 枚举方式待核实 | Step 2.2 时定 |
| O-6 | 公共网关拓扑与 SSO 透传（部署约束派生新项） | 默认最简【实现约定】：公网 API 网关终止 TLS + 域名；平台内部自持 JWT（登录取代网关侧 SSO，§13.1）；backend 服务仅接受网关转发来源 | 若 infra 强制前置 SSO → 需 infra 提供**带签名**的用户身份透传头并在 backend 验签（防伪造）；P0 上线前与 infra 敲定 |
| O-7 | 共享集群租户命名与环境前缀（部署约束派生新项） | 默认 `{env}.` 前缀由部署参数注入：`{env}.obs` 库 / `{env}.obs-*` index / `{env}.obs.*` topic / consumer group（§3.3/§5.2/§13.3）；无前缀=独立集群默认 | 上线前定 `env` 值域并与 infra 登记命名一致 |

---

## 13. 安全实现（三域隔离落地，依据 solution.md §12 + §4.5/§4.6）

### 13.1 平台用户域（JWT）

- 短效 access（15min）+ refresh（7d）双 token；口令 bcrypt + 登录失败锁定（5 次/15min）；**token version** 吊销（用户禁用/改密 `user_version+1` → 历史 token 全失效）。
- viewer/admin 两角色（R2 无 per-agent 数据隔离）；admin-only 路由前端隐藏 + 后端二次鉴权。

### 13.2 agent 上报域（Kafka SASL/TLS + ACL，R3 首版即上）

- 每 agent 独立凭证 → `agent_credential`（加密存储）；topic 级 ACL：`obs.agent.<name>` 仅对应 agent 可写、backend 消费 principal 单独入 ACL，自监控 topic `obs.selfmonitor` 与消费 group principal 一并登记（§3.3/§3.6）。**轮换（rotate）语义**：向 infra 申请新 SASL 账号 → `agent_credential` 落新密 → 旧账号 ACL 撤销 → SDK 断线重连读新凭证；「吊销即时生效」= 撤销 ACL + 断开现有连接（非仅改密等过期）。
- broker 若为**公共共享集群（多租户）**：topic 白名单、ACL、消费 group 均由平台向 infra **申请落权**后发放 SASL 账号（§3.3）；平台不持有 broker 管理权，凭证最小化（读写各一）。
- broker 侧：`auto.create.topics.enable=false`；authorizer 默认拒绝；**先建 topic + 绑 ACL，后发凭证**；topic 名白名单 `^(?:[a-z0-9-]+\.)?obs\.(?:agent\.[a-z0-9-]+|selfmonitor)$`（`{env}.` 前缀按部署注入，§12.2 O-7）；消费 group principal 同建同绑；认证后消费侧遇未授权 topic 消息**丢弃并计数告警**。
- 伪造/灌爆防护：每 agent 上报与回流候选量级**速率闸**（异常激增告警 + 阈值熔断）；消费侧双重校验 agent↔topic 一致（§4.2）。

### 13.3 存储与网络

- MySQL/ES/Kafka 为**公共 infra 租户**：endpoint + 最小权限账号（backend 专用）由 infra 分配，TLS 与网段白名单在 infra 侧收敛；backend 容器**不对外暴露** 3306/9200/9092（无 host 端口映射），浏览器侧仅能到达公共 API 网关——原「9200 不得对浏览器可达网段开放」由「网关为唯一对外入口 + 容器不映射」承接，杜绝绕过权限模型。
- **网络策略为 infra 必配项（非仅"容器不映射"）**：overlay 内仅 backend 容器/网段可达三依赖端口；其他租户服务不得直连 backend 服务端口——backend 服务本身仅接受网关/白名单来源（§12.2 O-6 网关拓扑）。
- 租户内命名：`obs` 库、`obs-*` index/topic、consumer group 均带**环境前缀 `{env}.`** 且与 infra 侧登记一致（§3.3/§5.2/§12.2 O-7）；无前缀=独立集群默认。

### 13.4 脱敏与内容安全

- 键级掩码 SDK 完成，平台**只复核不还原**（检出未掩码 → 丢弃计数告警）。
- `input/output` 可检索可查看面受接口级 `body_search` 门控（默认关，§2.7）；查看需 viewer + 开关已开。**门控关闭时后端在序列化响应前置空** `input/output/log_message`（前端隐藏仅兜底，防展示面泄露），见 §8.2/§8.8 注。
- 事件/正文 ILM 30 天；error_cluster 快照 input 实文留档（≤8K，脱敏；供组装不依赖 ES，但**不放大 PII 留存**——脱敏口径同正文）。`input_snapshot / error_msg` 为**受控列**：仅组装/复验链路 + admin 聚类详情可读，普通 trace 检索不可达。**降级清理（v1.1）**：cluster 终态（fixed/inactive）且超【实现约定】90 天 → 清空快照 input 实文（保留去重键/计数/时间字段），与 ES 30d 生命周期解耦的长审计面收口。

### 13.5 审计与平台间

- config/词表变更、人工操作（claim/ignore/invalidate/requeue/fixed-review）、auto 动作（assemble/activate/reentry）→ `conversion_record`（actor_user_id / system）。**config/词表变更的 detail 记到 `config_key` 粒度**（哪个 agent 的哪个 key、旧值摘要→新值摘要、操作人），审计列表可按 key/操作人筛选。
- 平台间：offline 专用服务账号（evaluator）+ 独立凭证 + 端点白名单 + 双向认证；pull-API `case_type` 白名单 + `schema_version`；响应 evidence 二期字段恒 null 契约（§8.7）。online→offline 回查凭证轮换同步。

---

---

## 14. 测试与验收用例（指导 tests/ 编写与阶段验收）

> 单测覆盖核心逻辑（Service/analyzer/converter 分支）；Controller/Repository/工具不强制（项目质量规范）。单测聚焦：L1/L2 判定、去重归一、聚类窗口、信封构造、词表快照、claim CAS、回查守卫、幂等。

### 14.1 冒烟用例（P0~P1，可手工/脚本执行）

| # | 场景 | 期望 |
|---|---|---|
| S-1 | 手工 Kafka 投合法 request+llm_call+log 事件 | trace 可查、日志穿插、llm_call 高亮（P0 验收） |
| S-2 | 非法事件（schema 缺字段 / agent≠topic / 未掩码敏感键） | 丢弃并计数（selfmonitor 可见） |
| S-3 | 同 trace 重放（Kafka 重复投递） | `_id` 幂等，无重复行、判定不重复 |
| S-4 | request ok + llm_call error/timeout | trace 子节点红显；`/metrics/llm-failures` 可下钻（P1 兜底吸收基础可见性，§2.4 前提验收） |
| S-5 | 关键字检索命中 error_msg | 命中 trace 列表 + search_after 深翻页；限 7d/超时/上限生效 |

### 14.2 回流端到端用例（P2，含故障注入）

| # | 场景 | 期望 |
|---|---|---|
| E-1 | 制造透传 LLM 错误 | 落 L1 → 开 cluster → 自动组装信封（含 no_fallback_config）→ link=assembled → pull-API 可拉 |
| E-2 | 制造 LLM 相关程序错误（首次 llm_call 前） | 靠接口字典 llm=true 兜住 → L2 回流（OR 门控） |
| E-3 | 重试自愈（最终 ok） | 不回流、无 error 子节点 |
| E-4 | 7d 窗口内同键再现 | 只 count+1，不重复生成 link |
| E-5 | 词表 fail-closed | dict_config fallback_utterance 置空 → 组装信封照建但结构自检不通过（offline 驳回 invalidated 回写）；词条命中 → no_fallback fail（§7.1） |
| E-6 | invalidated 重推 | offline 驳回（能力缺 reason）→ online 展示重推状态；admin requeue（内容缺 reason）→ 复位 assembled 重新可拉（复用 payload_id） |
| E-7 | claim → 单错级回查 | claim 填 fix_version → offline 回归 run（含该 case）→ run_results 该 case pass → verify=passed → cluster fixed（closed_by=auto_regression）；同 run 他错仍红不阻塞 |
| E-8 | claim TTL 超窗 | 自动回退 open + conversion_record |
| E-9 | reentry | claim/fixed 后同键线上再现 → 新 cluster + conversion_record「线上仍复发」提示 |
| E-10 | 终态只读 | verify=passed 后迟到 run 结果不覆盖；只追加时间线 |
| E-11 | offline 停摆 | assembled 已待 N 天 → 超阈值提示性标记（不自动告警、不设 online 时钟）；offline 恢复继续拉取不丢 |
| E-12 | 多实例/重放 | 双 consumer 消费同 offset 不重复建 cluster/link（唯一索引吸收） |
| E-13 | 残 trace（root 未达） | 按已有子节点判定；快照缺 input → 只计数不组装 |
| E-14 | SSE/分批 | 长 SSE 分批到达仍等窗口补全后判定（root 到达标记） |
| E-15 | 拉取 ack 幂等 | pull 重放 ack（draft/active/invalidated）重复调用不报错、状态幂等 |
| E-16 | 判定到期补判（判定执行方） | 构造 `ttl_until` 到期的未判 trace → judge_scan_job 扫到（judged=0 ∧ ttl≤now）→ classify 落 L1/L2 候选 → judged=1；重复到期不重判（§4.3/§6.1） |
| E-17 | reopen / 回归 failed 后再 claim 新版本 | 回归 failed 回退 open → 改 fix_version 再 claim → 同 cluster 自动生成**新 link（新 payload_id）** → 新版本回归 passed → fixed（旧 failed 留 verify_run_record 时间线）（§5.1 注/§7.6） |
| E-18 | 故障注入：Kafka broker 停 | consumer 停拉退避挂起（不提交空推进）→ broker 恢复续拉不丢、判定态补齐（§4.1/§4.3） |
| E-19 | 故障注入：ES 不可用 | 事件落待补写 spool 或显式丢弃 + 该小时 rollup 缺口标注；判定/聚类/回流不受影响（判定源=MySQL 判定态，§4.1/§5.3） |
| E-20 | 故障注入：MySQL 不可用 | 判定态写失败 → **不提交 offset + 退避自监控**；恢复后判定不丢（禁"丢弃并提交"，§4.1 step4） |
| E-21 | 故障注入：网关/offline 不可达 | 回查退避重试、超上限提示「回查失败待人工」；assembled 已待 N 天提示性标记；不设 online 时钟（§7.2/§7.6） |
| E-22 | requeue 刷新游标 | admin requeue 后 `assembled_ts` 刷新 → offline 增量 since_ts 重拉可见（复用 payload_id 幂等）（§7.2/§7.4） |
| E-23 | R-13 同键截断→小输入洗白 | 同键首现 input>8K（input_truncated=1、该版不计 K）→ claim 观察窗内同键 ≤8K 纯净 trace 到达 → cluster 位刷新清 0 → 对应版 run pass 计 K、escape 可达；已 fixed cluster 迟到截断 trace 不翻案（终态只读） |
| E-24 | R-14 unclean_run 批引 claim 挂起标注 | 环境级 na 污染 run 下 claim cluster pass 存疑 → 聚 unclean_run 批、cluster 保持 claim + 详情实时显「被未决批挂起」；批未 resolve 期间 TTL 照走（到期回退 open）；批 resolve 时已 open → skipped_already_open 幂等 |
| E-25 | R-15 双通道优先级 | 同 run 同 cluster 同时 input_truncated=1 + 环境级 na → 走 input_truncated 单条处置（reason 截断）、不并入批；同 run 其他无截断 pass cluster 照常走批 |
| E-26 | R-16 缺行自动核对 excluded | claim 缺行 → recheck 自动拉该版 run → case_id ∈ excluded_case_ids → 自动标「窗口外欠测」不自动 reopen；∉ → 人工兜底 |
| E-27 | R-17 K 序列 versions 锚 | 中间版 v2 丢 error run（洪峰拒建）→ recheck 以 versions 读面见 v2 有发版无 run → 缺行中断，v1+v3 不假连续 K 满；v2 差集补建 fail → 补判触发 reopen，不出现 false-fixed |
| E-28 | R-21 root-late 补判 | 残 trace 已按子节点判定（judged=1、root_error 未聚类）后 root 迟到（root_status=error、root_error_type ∈ L1/L2 值域）→ step4 补一次 root 级候选：同键已有 open cluster → count+1（缺快照可补组装）；异键 → 开新 cluster 组装；同键已 closed（fixed/inactive）→ 跳过不翻案；root_late_complement 置 1，重放/多实例不重复补（§4.3④/§4.4/§6.2） |
| E-29 | R-24 requeue guard 状态域 | fixed/inactive cluster 的 pending invalidated link → requeue 拒（409，提示走 superseded+reopen 重建）；open/claim/needs_review cluster 的 pending invalidated link → requeue 复位 assembled、**fix_version/claim_k/TTL 锚点不变**、回查仍以现 claim 锚定（§7.4/§9.4） |

### 14.3 阶段验收对齐（solution §15 P0~P2 → 用例映射）

- P0：S-1 通过（手工投事件按 trace 查回）。
- P1：S-4 通过；看板出现真实 P50/P95/P99 + 全站 QPS 趋势（gq/cs/sp 接入）。
- P2：E-1~E-29 通过（E-23~E-29 = R-13~R-24 修订包端到端，见 §14.2）+ §11.5 维度 3 开放验收（checklist #4/#8/#10，含兜底吸收埋点前提用例 S-4 在真实 agent 上复验）+ 词表覆盖度（对 §13.1 兜底逻辑盘点）。

### 14.4 性能与健壮性用例（护栏）

- rollup：迟到事件（≤6h）重算幂等不双计；缺桶回退实时 + 页面标注；**t-digest 跨小时合并 ≈ 全量重算 p95（误差 <1%）**（O-4 验证）。
- 检索/看板：慢查询熔断/限流 + 单 trace 日志懒加载分页（§8.2 大 trace 防护）。
- **O-1 护栏已裁定（§12.2，含数值判据）**：agent 缺省=全站 1h/24h 实时 agg 强制结果缓存 `metric_agg_cache_ttl_s=60` + agg 超时 `metric_agg_timeout_ms=3000`；全站 24h agg P95 ≤5s；trace 检索超时 `trace_query_timeout_ms=3000`、命中 ≤200 上限。
- **写侧/后台判据**：判定态表单行 upsert P95 ≤10ms；rollup 每小时任务完成 ≤2min；judge_scan/cluster/assemble/claim_ttl/recheck 各时间驱动 job 单飞无重复执行（§1.3）；requeue 防抖 ≥5min 生效。

### 14.5 集成异常与边界用例（task.md 阶段 4 T-4.13/T-4.14 编号化，X 系列）

> 本小节把 `task.md` 阶段 4 的 T-4.13（异常 6 组 ①~⑥）/ T-4.14（边界 7 组 ①~⑦）**追加补充场景编号化为验收用例**（X-1~X-13），防用例口径漂移；与 §14.1（S 冒烟）/§14.2（E 回流端到端）语义区分。T-4.13/T-4.14 为 X 系列的来源容器，验收以本小节 X 编号为权威口径。期望列尾锚本文件内部章节（§0.2 规约，无前缀 = 本文件）+ 关联 S/E 用例复验锚。

| # | 场景 | 期望 |
|---|---|---|
| X-1 | 消费侧 schema 异常 | 缺必填字段/字段类型错/多余未知字段/整体 null 事件 → S-2 拒绝路径集成复验（丢弃 + selfmonitor 计数）；topic 与 agent 不匹配、白名单外 agent 事件拒收（§4.2） |
| X-2 | 脱敏死角 | 脱敏键不存在/值已是掩码形态/超长值/嵌套异常层级 → 不炸、不二次脱敏、可追踪（§4.5） |
| X-3 | 埋点前提 | 裸 LLM 调用失败被业务 catch 转兜底返回 200 → `request ok + llm_call status=error` 先记后传、trace 子节点红显、失败率计数不丢（§2.4/§4.2 前提验收；S-4 真实 agent 复验在本环境的补强） |
| X-4 | 检索注入与转义 | 关键字含引号/通配符/保留字符/中文分词边界词 → 查询不报错、不误命、不返回错误 scope；search_after 末页后再翻稳定返回空（§8.2 检索） |
| X-5 | 平台间契约异常 | pull-API 收到 case_type 非白名单 → 返回空集；schema_version 不匹配 → 拒单并计数；回写字段非法/状态越界 → 幂等拒绝不污染状态机（§7.3/§7.4） |
| X-6 | 大对象边界 | payload 超 Kafka 上限、evidence 实文恰 8K/超 8K 截断、缺 input 残现场只计数（E-13 集成复验）（§3/§6.2） |
| X-7 | 时间边界 | 事件 ts 未来/1970/UTC 与本地时区交界 → 周 index 归属与 date_histogram 分桶正确；跨周切换落在前后两周的检索去重不重不漏（§2.1 周滚动） |
| X-8 | 窗口边界 | error 同键恰 7d 聚类窗边缘（第 7 vs 8 天）→ count+1 vs generation 新开（E-4 补强）；指标 24h 实时 vs 24h+1s rollup 路由切换；rollup 迟到恰 6h 幂等重算/超 6h 不再重算/缺桶回退实时 + 页面标注/尾小时实时补齐（§5.3） |
| X-9 | 判定时序边界 | judge_scan 到期瞬间补判、重复到期不重判（E-16 补强）（§4.3/§6.1） |
| X-10 | 数量级边界 | trace 检索命中恰 200 与超 200 截断、末页后翻；单 trace 日志上万行首屏懒加载不拉爆（S-5 补强）（§8.2） |
| X-11 | 并发/竞态边界 | 双实例同 offset 不重复建（E-12 复验）、CAS claim/requeue 与 offline pull 并发、requeue 防抖恰 ≥5min、ack 幂等重放与并发拉取交错（E-15 复验）（§1.3/§7.4） |
| X-12 | 词表边界死角 | 空表/极短表 fail-closed（E-5 复验）；动态前缀/拼接/大小写/换行/空白差异/超长词/重复词在词表残余承认范围内行为可观测（solution §16 登记口径，不要求全拦、要求假绿时可抽查发现） |
| X-13 | 保留期边界 | ILM 30 天删除后检索与看板缺口标注行为（衔接 T-5.2）（§7.1） |

---

## 附：solution.md ↔ solution_detail.md 章节映射（可追溯）

| solution.md | solution_detail.md |
|---|---|
| §一~§三（背景/决策/架构） | §0/§1 |
| §四 观测契约（4.1~4.6） | §2（+§4.5 消费侧校验） |
| §五 采集 / §5.1 SDK / §5.2 Kafka | §3（+§11 SDK 打点 API） |
| §六 消费与处理 | §4 |
| §七 数据层（7.1 ES / 7.2 MySQL / 7.3 保留） | §5 |
| §八 trace 查询 / §九 指标口径·看板 | §8.2/§8.3 + §9 + §5.3 |
| §十 回流（10.1 判定 / 10.2 聚类 / 10.3 组装 D19 / 10.4 人工 / 10.5 复验） | §6 / §7 / §8.4 |
| §十一 offline 配套 | §7.3（online 侧依赖契约）+ Task #4 |
| §十二 鉴权三域 / §12.1 页面 | §8 + §9 + §13 |
| §十三 通用接入 / 存量整改 | §11（+§13.0 checklist → §14） |
| §十四 工程结构 / §十五 阶段 | §1 / §14.3 |
| §十六 风险 / §十七 默认值 | §12.2 open + §10（逐项落点见正文） |

