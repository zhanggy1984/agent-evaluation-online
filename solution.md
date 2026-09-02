# agent-evaluation-online 线上观测平台 技术方案

> 版本：v3.4.5（待评审）
> 定位：**平台定标准，agent 适配**。观测平台是规则制定者，4 个现有 agent（good-question / customer-service / contract-check / smart-procurement）及未来接入 agent，一律按本平台统一规范整改接入。
> v3 变更：吸收独立架构评审意见（锚点与异常判定模型、接口字典来源、回归隔离面、offline 配套细项）+ 4 项方向决策（兜底归属 L3 / cc 第一版不回流 / 正文默认关逐 agent 评估 / L3 offline 自动化判分）。
> v3.1 变更：修订第二轮变更增量评审问题——§11 回归状态机按 case_type 分叉（error-only 不进 SCORING / 含 quality 必须进 SCORING）、L3 offline 判分穿透面与 no_fallback 达标线（防假绿）、seq 幂等回退 trace 级全局单调（branch 仅标注）、L1/L2 catch 转抛边界、llm_call 逻辑调用与重试自愈不出回流、L3 去重伪分类、看板 quality 出口、sp structlog 落地约束。
> v3.2 变更：补充 §12.1 前端页面体系——浏览器层角色（viewer/admin）→ 菜单树 → 页面清单与功能点 → 权限/归属阶段映射，与 §12 三域隔离、D11 研发人工操作口径对齐。
> v3.3 变更：针对自估 3 个最薄弱点的修正——(a) §11 #3/#4 回归 quality 判分改**独立判定器路径**（不借道 SCORING/score_run、不进 agent_score，规避 offline 闭集合穿透）；(b) §10.1 LLM 判定改 **trace 内动态事实**（llm_call/llm_* error/quality），`interface.llm` 标记退化为看板分类 + 自动补标 + 疑似漏标告警；(c) §10.3/§5.1 复现门槛**按层差异化**（error 用例不依赖会话历史）+ SDK 增 `record_session_state()` 状态快照钩子。
> v3.4 变更：§13 重构为「agent 接入与统一整改」——新增 §13.0 **通用接入方案**（面向任何 agent、语言中立：接入前契约核对（Step 0 盘点）→ 三步接入（Step 1~3）→ 接入验收 checklist；非 Python/Serverless 走事件协议直发），存量 4 agent 整改清单保留为 §13.1。
> v3.4.1 变更：吸收 §13.0 独立变更增量评审（无致命）——checklist 拆「放量门禁/维度 3 开放验收」两档（M1）；collector 明确为非首版能力并登记 §14（M2）；Step 0 盘点补接口枚举方式、后台任务型对齐 D18（M3）；§13.1 #1 补 sp `request_id` 规约、§5.1 rewrite 禁用口径单源、db/redis 建议口径、Step 2.4 存量 gq/cs/sp 例外、§10.1 引用修正（N1~N4）。
> v3.4.2 变更：吸收六方向独立评审（逻辑/数据流、安全、性能、异常容错、易用性、offline 对接；无致命）——§4.3 回流前置与 §10.1 L2 门控改 **trace 内 LLM 动态事实**（不依赖 `interface.llm` 人工标记，消除补标滞后静默过滤）；自愈示例修正 + **静默降级盲区**缓解（§10.1）；cluster 生命周期重写（首现即开→静默归档，§10.2）+ L3 现场留痕快照（§7.2）；ts 水位只告警不丢弃 + 维度 3 分析源改同批消费事件（§6.1）、MySQL 侧幂等（§6.2）；error_cluster/error_case_link 幂等与快照（§7.2）；offline 配套补强 block 并入 §11（单错级回查、verifier 状态机、互斥槽、no_fallback 判分、豁免集）；安全补强 block 并入 §12（JWT refresh/吊销、Kafka SASL/TLS+ACL、最小 API 面）；§10.4 人工确认审计可 reopen、§10.5 单错级回查；§16 风险表登记 8 项。易用性增强（跨 agent 首页汇总、漏标归属 viewer、ES 分 index、预聚合、offline 用例保留）列入 §17 待确认。
> v3.4.3 变更：吸收第二轮六方向全量复评去重后的**无争议修**（方向性决策点另列待用户逐项裁定）——ES `_id` 幂等键补 agent 维度（D16/§6.1/§7.1，防跨 agent 同 trace_id 互覆，容错 N-1）；§4.2 删"只要接口为 LLM 相关即进入聚类候选"残留旧口径、统一 trace 内动态事实 + 缓存命中不回流出（逻辑 M-3）；quality 落库形态明确为 schema 事件字段、不新增事件不参与计数（逻辑 N-5）；verify_status 枚举补 superseded（逻辑 N-7）；conversion_record 补 actor_user_id（安全 N5）；trace 详情日志行分页懒加载 + 关键字检索补 error_type/error_msg 与时间窗（性能 M-4/易用 M4）；§16 修正"文本与指标 index 分离"为实际机制（性能 M-3）、回查不因 cluster 归档跳过在途 case（逻辑 M1/容错 N6）、补 needs_review 无主堆积风险行（易用 M1，修复 §10.4 落空引用）；§5.1 本地兜底默认挂持久卷（容错 N2）；上报鉴权对齐 Kafka-only——§12.1 agent 行改 Kafka SASL/ACL、§14 目录去 HTTP ingest 残留、agent_credential 语义改 Kafka 凭证（安全 M7/M8）。
> v3.4.4 变更：**7 个方向性决策点逐项裁定并修入**（编号 R1~R7，与 §2 既有 D1~D18 关键决策表独立）——R1 跨批 trace 累积态（§6.1：判定"是否缺完整 trace"基于消费侧跨 SSE/多批/子节点分批的累积态，非单事件自判断；§10.1 判定源同步）；R2 Agent 数据隔离**维持统一 viewer**（延续 §12.1"无 agent 级数据隔离"既有结论）；R3 上报通道访问控制**首版即上**（§17 #9 默认改 Kafka SASL/TLS + topic 级 ACL，§12.1/§7.2 凭证映射 producer 身份）；R4 人工"标记已修复"拆 **claim 认领 → 置 fixed 两步**（§7.2 error_cluster 增 claim 中间态；§10.4/§12.1/D11：置 fixed 需回归证据通过或 admin 复核，viewer 不单方 closed）；R5 回归回查契约**本轮落定边界**（§10.5/§10.3/§11：case 建时记触发版本、按版本锚定回归 run 判单错不取最新 run；回归 run 与 manual 共存、不占互斥槽、不参与 max_active_runs；quality 型 L3 判分回写 run_results.pass_fail 供 online 单错级判定）；R6 L1 error 用例补**兜底断言**（§10.3/§11 #3/#4：判"接口无技术错误 + 未落入兜底/低置信"才生成 error 用例，且 error 用例技术跑通后 offline 补判 no_fallback，防 catch 硬错转兜底话术返回 200 假绿过门禁）；R7 指标 7d 小时级 rollup **提前到 v1**（§7.1/§9.2 双路：1h/24h 实时 agg + 7d 查 `obs-metrics-rollup`；§17 #8、§16 容量行同步）。
> v3.4.5 变更：吸收**第三轮六方向全量独立评审**（逻辑/数据流、安全、性能、异常容错、易用性、offline 对接；均无致命）+ **7 项方向性裁定修入**——①R5 回查锚定改 **claim.fix_version**（错误在已发布缺陷版发现、回归 run 绑待发布修复版，按触发版本回查恒取空；事件 schema 补 `agent_version` 打点、SDK init 从部署环境注入；trigger_version 仅溯源；fix_version 无对应 run → pending + 待发布提示）；②R1 累积缓冲重建改 **判定态持久化**（§6.1：判定态/水位落 MySQL、重平衡重建不回读 ES；残 trace 按已有子节点判定）；③L2 门控补 **OR 条件**（trace 动态事实 或 接口字典 llm=true，恢复首次 llm_call 前程序错误回流；L1/L3 仍纯动态事实）；④§17 #12 改**回归 run 独立保留档**（cleanup 删 run 不删 case，#12 描述由"用例保留"改写为"run 保留"）；⑤L3 判据 **subtype 分叉**（fallback→no_fallback 兜底话术 / low_confidence→携带检索命中与会话快照判"仍无据硬答"独立判据 / judge na→inconclusive 重试）；⑥§17 #11 **admin-only + 自动补标观察窗**；⑦input/session_ctx PII 与正文**同级约束**（采集照旧，检索/落 ES 展示面纳入逐接口开关/截断/保留期/权限）。无争议修并入：claim 生命周期状态机（TTL/回归 failed 回退/超窗升级 + closed_by）、R3 broker 侧落地（auto.create.topics 默认关 + 先建 topic 后发凭证 + 消费侧未授权丢弃）、rollup 运行机制小节（t-digest 可合并草图 + 调度/回填/迟到幂等/降级 + 时间窗枚举）、error_cluster 唯一索引含生命周期代数 generation、日志行占 seq 防 `_id` 互覆、superseded 保留 passed 终态、offline verifier 期覆盖 error-only run、eval_result 复用既有列不加列、最小 API 面端点、§17 表状态列。**补充裁定（offline 确认 gate，激活全归 offline）**：回归用例生成一律 **draft 推送 offline，online 不再设任何测试集人工/激活环节**（只保留去重 + 幂等 + 生成质量下限自校验）——激活决策在 offline 平台内闭环：error 型（L1/L2）draft 由 offline 自动化校验激活（客观复现无需人看）、quality 型（L3）draft 由 offline 人工确认（通过→active / 驳回→删 case + online 回写 link invalidated，reopen 可让错误再流转）；draft 未激活期间 online 侧 cluster 保持 open、`error_case_link` 标"已生成用例（待 offline 确认）"、verify_status 保持 pending（§10.5 不判红不催 admin 复核）；offline 确认积压由 **TTL 告警（默认 7 天可配）顶置提示、不自动绕过、可人工 ignore**；online 人工仅剩 §10.4 线上错误处置（claim/ignore/needs_review 处置/fixed 复核），与测试集无关（§7.2/§10.3/§10.5/§11 #5/§11 补强/§12.1/§16）。**三机制子裁定**：error 型 draft **收单即结构自检激活**（语义验证延迟回归 executor，结构自检失败 → 驳回 rejected，offline 能力补齐可重推）；quality 驳回 → offline **软删 status=rejected 归档**（online 回查感知 → invalidated，保可追溯不真删行）；确认积压 TTL 告警归 **offline 确认 owner**（online 仅展示"已待 N 天"、不设自身时钟防双时钟）。

---

## 一、背景与目标

现有 4 个 agent 各自独立开发，日志/埋点/指标碎片化，上线后缺统一观测手段。本平台补齐线上侧观测，与 agent-evaluation-offline（离线评测）形成闭环：**线上异常 → 自动转回归用例 → offline 复验 → 修复上线 → 线上观测验证修复**。

**三个维度：**

| 维度 | 能力 | 消费方 |
|---|---|---|
| 1 | traceId 链路日志查询（请求全节点，正常+异常） | 开发排障 |
| 2 | agent × 接口 metrics 看板（P50/P95/P99、失败率、超时率） | 研发/负责人 |
| 3 | 异常日志分析 → 异步转 offline 回归测试用例（相同错误不重复） | 研发 → offline 复验 |

---

## 二、关键决策总览（逐条评审已确认）

| # | 决策项 | 定案 |
|---|---|---|
| D1 | 实现方式 / 技术栈 | **全自研**，技术栈跟随 offline：FastAPI + React + MySQL + Alembic + JWT |
| D2 | 采集架构 | **obs-sdk 内嵌 agent 进程**，数据发 MQ，online 平台异步消费、处理、入库、显示 |
| D3 | 消息队列 | **Kafka**（单 broker KRaft），SDK 侧 kafka-python，每 agent 一个 topic `obs.agent.<name>`，partition=1 |
| D4 | 指标形态 | **请求级 + LLM 调用级双指标**（request 事件 / llm_call 事件分别统计）；error/timeout/ok 互斥 |
| D5 | 观测接口范围 | **全接口观测**（不区分 llm 标记）；接口字典 **online 自发现**——源为 agent **真实路由**（FastAPI 路由/OpenAPI），**与 offline 评测 manifest 解耦**；`llm` 标记仅用于**看板分类**（自动补标：窗口内观测到 llm_call → 置 llm=true 待确认；疑似漏标告警）；**回流 LLM 判定以 trace 内动态事实为准，不依赖该标记**（**例外：L2 门控 = trace 动态事实 OR 接口字典 `llm=true`**，兼容首次 llm_call 前的程序错误，v3.4.5 裁定） |
| D6 | 链路覆盖 | request 为 HTTP 指标锚点根节点；子节点打 llm_call / tool_call / retrieve / **db / redis** |
| D7 | 回流分层 | **L1 透传型 LLM/接口硬错误** / **L2 LLM 相关接口的程序错误** / **L3 兜底与低置信（quality 信号）**；LLM 调用失败被兜底吸收、请求仍 ok → **归 L3**，不归 L1 |
| D8 | quality 信号 | agent 在兜底/低置信分支显式上报；平台关键词兜底为辅 |
| D9 | 回流输入范围 | 文本 / 对话（input_turns）双通道可回流；**文件型输入第一版不回流**；L1/L2 error 用例复现**不依赖会话历史**（C1）；会话型 quality 用例采集**状态相关快照**（session_state 钩子，C2）辅助复现 |
| D10 | 去重 | 键 = agent + interface + error_type 分类 + input_hash；时间窗口聚类合并；**不带 agent 版本**；per-trace 归并、分层优先 |
| D11 | 人工确认 | **轻量版**：自动生成 + 去重（**生成即 draft 推送 offline，case 激活归 offline、online 无测试集人工确认**——本决策"人工确认"指研发对线上错误的处置，非测试集准入，§10.3/§11 #5），回流看板可人工 invalidate/ignore/**claim 认领**（决策 R4：置 fixed 需回归证据通过或 admin 复核，viewer 不单方标记已修复）；不引入审批工作流 |
| D12 | 鉴权 | **三域隔离**：平台用户（viewer/admin）、agent 上报凭证、online↔offline 平台间服务凭证 |
| D13 | 脱敏 | 键级掩码复用 offline `mask_dict` 规则集提升为标准，**SDK 侧完成，平台不还原**；**内容型 PII 依赖采集策略（正文默认关 + 最小化）控制，不以键级掩码为底线**；**input/session_ctx 的检索/落 ES 展示面与正文同级控制**（§4.6，第三轮裁定——输入类 PII 暴露面大于 output） |
| D14 | 正文存储 | 回复正文保存进 ES（支持 traceId/关键字检索）；**默认关，按接口逐 agent 评估数据属性后开**；带开关/截断/权限/保留期 |
| D15 | 日志查询 / 指标口径 | 查询页 traceId 与关键字**自由输入、可都输可任一**；p95/p99 **正常显示，不考虑样本 <30** |
| D16 | 数据层 | **Elasticsearch 8.x 单节点**为主（事件+日志**分 index**，ILM 30 天自动删，index 按周滚动，`_id=sha256(agent\|trace_id\|seq)` 幂等——agent 入键防跨 agent 同 trace_id 互覆）；MySQL 只放平台元数据；指标用 ES agg |
| D17 | offline 配套 | 见 §11：回归评测模式 + **回归复验硬门禁区块**（发布两道门禁并列）；L3 走 **offline 无 golden 语义判分通道**（第一版落地） |
| D18 | cc 范围 | **contract-check（后台任务型）第一版只出 request 级指标与链路，维度 3 不纳入**；task/job 根节点模型 P2 评估 |

---

## 三、总体架构

```
                    4 个 agent 后端（Python，SDK 内嵌）
                    ┌──────────────────────────────────────┐
                    │  obs-sdk（logging handler + 事件打点） │
                    │  内存队列 → 批量 → kafka-python        │
                    └───────────────┬──────────────────────┘
                                    │ obs.agent.<name>（每 agent 一 topic, p=1）
                                    ▼
                              ┌───────────┐
                              │  Kafka    │  KRaft 单 broker
                              └─────┬─────┘
                                    │ 异步消费
                    ┌───────────────▼───────────────────────────────┐
                    │            agent-evaluation-online           │
                    │  (独立容器，走 api-gateway eval-online.local)  │
                    │                                               │
                    │  ┌──────────────┐    ┌─────────────────────┐  │
                    │  │ 消费 worker   │───▶│ Elasticsearch       │  │
                    │  │ 校验/脱敏复核 │    │ 事件 index（周滚动） │  │
                    │  │ 水位/幂等     │    │ ILM 30 天           │  │
                    │  └──────┬───────┘    └─────────┬───────────┘  │
                    │         │                      │ 指标 agg       │
                    │         ▼                      ▼                │
                    │  ┌────────────┐     ┌────────────────────┐      │
                    │  │ 分析 worker  │     │  API 层             │      │
                    │  │ L1/L2/L3 分层 │     │  logs/metrics/cases│      │
                    │  │ 聚类去重      │     └─────────┬──────────┘      │
                    │  └──────┬───────┘               │                 │
                    │         │ error_case_link      ▼                 │
                    │  ┌──────▼────────┐        React 前端（三层页面）   │
                    │  │ converter     │                               │
                    │  │ 生成回归用例    │                               │
                    │  └──────┬────────┘                               │
                    │         │ 调 offline API（服务凭证）               │
                    └─────────┼────────────────────────────────────────┘
                              ▼
                    agent-evaluation-offline（回归评测模式，§11）
                    回归 run 复验 → 全绿 → online 回查 → 错误标「已复验」
```

- **复用共享 infra**：MySQL 8（库 `obs`）、Kafka（独立 compose）、ES 8.x（独立容器）。前端经 api-gateway `eval-online.local` 路由。
- **技术栈跟随 offline**：FastAPI + React + MySQL + Alembic + JWT。
- **范围声明**：第一版观测 gq / cs / sp 三个 LLM 相关 agent + cc 的 HTTP 接口层；维度 3（回流）仅覆盖 gq / cs / sp（D18）。

---

## 四、统一观测契约（平台定标准）

> 平台定义事件 schema、节点、错误分类与脱敏口径，agent 按契约埋点。**契约即标准，禁止 agent 自定义字段覆盖标准字段**；agent 自有埋点（gq `chat_request`、cs Prometheus 等）整改时统一收敛到 SDK。

### 4.1 统一事件 schema

```json
{
  "schema_version": "1.0",
  "event_kind": "event",               // event | log（日志行）
  "trace_id": "网关 X-Request-ID 或 SDK 兜底生成",
  "agent": "good-question",
  "agent_version": null,                 // agent 部署版本（SDK init 从环境注入，可空）；R5 回查版本锚定数据源
  "interface": "POST /api/chat/{session_id}",   // 归一化路径（动态段 → {id}）
  "node": "request",                   // 节点类型（4.2）
  "seq": 0,                            // trace 内全局单调自增（根 request=0，contextvar 原子递增）
  "branch": 0,                         // 并行分支标注（仅文本标记，不入幂等键/引用）
  "parent": null,                      // 父节点 seq（request 为根；seq 全局唯一，引用无歧义）
  "ts": 1735800000000,                 // 毫秒，UTC
  "duration_ms": 3200,
  "status": "ok",                      // ok | error | timeout（互斥）
  "error_type": null,                  // 4.3 错误分类
  "error_msg": null,                   // 脱敏错误摘要 ≤512 字符
  "input": null,                       // 入参（脱敏后）；对话型含 input_turns + session 上下文摘要
  "output": null,                      // 出参/答复正文摘要（脱敏后，正文规则 4.6）
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
  "model": null,                       // llm_call 节点：模型名
  "quality": null,                     // {level: "low_confidence"|"fallback", reason}
  "log_level": null,                   // event_kind=log：DEBUG/INFO/WARNING/ERROR
  "log_message": null,                 // event_kind=log：日志正文（脱敏后）
  "extra": {}                          // agent 自定义扩展（白名单字段）
}
```

- 日志行（event_kind=log）与节点事件同链路、都带 trace_id；**日志行占用 `seq` 槽位**（同一把 trace 内 contextvar 原子计数，不与节点事件分开计数）——否则同 trace 大量日志行与节点事件共享 `_id=sha256(agent|trace_id|seq)` 空间会互相覆盖（日志行 seq 与节点 seq 相同即后者覆盖前者，第三轮逻辑评审 S2 修正）。
- **动态路径归一化**：session_id/review_id/task_id 等 → `{id}`，保证指标按「接口」稳定聚合。
- **会话上下文**：会话型接口（cs/gq）事件附最近 N 轮消息摘要（默认 10 轮，截断 + 脱敏），供回归复现（§10.3）。

### 4.2 节点类型与锚点语义

| node | 含义 | 要求 |
|---|---|---|
| `request` | 一次 HTTP 请求端到端 | **必须**；**仅作维度 2 指标锚点** |
| `llm_call` | 一次 LLM 逻辑调用（内部退避重试不拆条、仅最终失败标 error） | 观测范围内 LLM 类 agent（cc 除外） |
| `tool_call` / `retrieve` | 工具 / 向量检索召回 | 有 function calling / 检索的 agent |
| `db` / `redis` | DB / Redis 访问（单独打点） | 建议 |

**锚点语义（关键修订）**：
- `request` 只承载维度 2 的请求级指标（P50/95/99、失败率、超时率）。
- **异常判定 / 回流聚类是 trace 级聚合**，不依赖 `request.status` 单点：该 trace 内任一 `llm_call`/`db`/`redis` 子节点 `status∈{error,timeout}`、或 `request` 自身 error、或 `quality` 信号即进入聚类候选，但**是否回流以该 trace 内 LLM 动态事实为准**（出现 `llm_call` / `llm_*` error / quality，§4.3/§10.1），不依赖 `interface.llm` 接口标记（§4.3 前置修正）——缓存命中（§9.1，无 llm_call）等无 LLM 事实的 trace 不出回流。适配"LLM 调用失败被兜底吸收、请求仍 ok"的结构（归 L3，见 4.3/4.4）。
- **重试自愈**：`llm_call` 按逻辑调用打点（一次请求=一条，内部退避重试为 attempt、不拆条不标 error）；最终成功 → `status=ok`，不产生 error 子节点、不出回流（§10.1）；最终仍失败才标 error。

### 4.3 错误分类（error_type）→ 回流分层映射

| error_type | 含义 | 回流层 |
|---|---|---|
| `llm_timeout` / `llm_rate_limit` / `llm_connection` / `llm_context_exceeded` / `llm_empty_response` / `llm_parse_error` / `llm_other` | LLM provider 层失败且**透传到接口错误**（request 直接报错） | **L1** |
| `llm_interface_business` / `external_non_llm` / `db_error` / `redis_error` | LLM 相关接口上的程序错误（接口直接 error） | **L2** |
| —（quality 信号） | LLM 调用失败被兜底吸收（请求仍 ok）或返回正常但低置信 | **L3** |
| `auth_error` / `validation_error` 等非 LLM 相关接口错误 | login 等非 LLM 接口 | 不出回流 |

**降级型异常归属**：LLM 调用失败 → agent 兜底 → 请求返回 ok → 请求级不标 error，**不计 L1**；由 agent 在兜底分支打 `quality=fallback`，**归 L3**（L3 的 offline 复验判据 = "不再兜底"，见 §11）。L1 仅覆盖透传型（错误直达接口）。
**catch 转抛归属（L1/L2 边界规则）**：`request.error_type` 表达接口**最终暴露**的错误类别——LLM provider 错误未被业务 catch、直接冒泡为接口错误的，标 `llm_*`（L1）；LLM 错误被业务代码 catch 后转抛为自身业务/程序错误暴露给客户端的，标 `llm_interface_business`（L2）。llm_call 子节点仅作采集，不单独定层。

> 回流前置 = 该 trace 内 **LLM 动态事实成立**（出现 `llm_call` / `llm_*` error / quality 信号，见 §10.1 动态判定），**不依赖 `interface.llm` 人工标记**——该标记只做看板分类（§12.1）；login 等无 LLM 事实的接口出指标不出回流。**例外（第三轮裁定）：L2 门控 = trace 内 LLM 动态事实成立 OR 接口字典 `llm=true`**——首次 `llm_call` **之前**的 L2 程序错误（入口查库/检索/校验失败）发生时该 trace 尚无 LLM 动态事实，单靠动态事实会漏这类错误；字典 `llm` 标记带自动补标（§10.1）故可作为 OR 兜底。L1（error_type∈llm_* 本身即事实）与 L3（quality 本身即事实）仍纯动态判定，不受影响。仍避免人工补标滞后造成静默过滤（评审修正）。

### 4.4 quality 信号（L3）

agent 在自身「兜底/低置信」业务分支显式调用 `sdk.record_quality(trace_id, level, reason)`：
- `level=fallback`：LLM 失败后降级兜底，或知识库未命中降级答复；
- `level=low_confidence`：检索未命中/置信度低仍硬答。

平台侧辅以**兜底话术关键词库**（dict_config，可维护）兜底识别，主判 agent 显式上报。SDK 自动判定兜底不靠谱，以 agent 插桩为准（4 agent 统一整改项）。

- **落库形态（评审修正，逻辑 N-5）**：quality 是 schema 事件**字段**（§4.1），不是独立节点/独立事件行。`record_quality()` 在 SDK 内更新该 trace 当前 request 根事件（或最近活跃事件）的 `quality` 字段，随原事件一起 flush 落库——**不新增事件、不参与 request 计数**（§9.1 请求指标只统计 request/llm_call 锚点事件），消除"quality 是否作为独立 request node 发出"的歧义。

### 4.5 脱敏规范（键级掩码，SDK 侧完成）

复用 offline `mask_dict` 规则集提升为平台标准：

```
_SENSITIVE_KEY = authorization | token | password | secret | api[_-]?key
                | fernet | credential | auth_config | (白名单扩展)
```

- SDK 序列化前对 input/output/extra/log_message 递归掩码敏感键 → `***`；平台消费侧脱敏复核（命中未脱敏敏感键 → 打回/丢弃并告警）；平台不存还原逻辑。
- **边界（修正）**：键级掩码 ≠ 内容级脱敏。订单地址、合同全文、身份证号等**内容型 PII 不在键级掩码能力内**，由采集策略控制：正文默认关（D14）、事件 input/output 的最小化采集、角色权限与 30 天保留期。不以键级掩码作为内容安全的唯一底线。

### 4.6 回复正文采集（D14，默认关）

回复正文（含 LLM 生成的答复内容）脱敏后存 ES，供 traceId/关键字检索还原"当时 LLM 如何答复"。**input/session_ctx（事件入参与会话上下文摘要）的检索/展示面与正文同级控制（第三轮裁定）**：采集照旧（input_hash 去重、回归复现、会话重建是功能需要，input 事件字段属 §4.1 schema），但**落 ES 可检索/可查看面默认关，逐接口评估后开**——防输入类 PII 暴露面大于 output；trace 详情对 input 的展示随该接口开关。控制点：

| 控制点 | 规则 |
|---|---|
| 开关 | **默认关**；需要正文的接口（优先 llm=true 对话类）**逐个评估数据属性后开**，落库前做内容型检测/最小化 |
| 截断 | 单条 ≤ 8K 字符 |
| 权限 | 查看正文需 viewer 及以上 + **该 agent 正文开关已开**（统一 viewer、无 per-agent 授权域，决策 R2；§12） |
| 保留期 | 随事件 ILM（30 天），不做独立延长 |

---

## 五、采集架构（SDK 内嵌 + Kafka 推送）

**结论（D2/D3）：SDK 内嵌 agent 进程，数据异步批量发 Kafka，online 异步消费。**

### 5.1 obs-sdk 职责

- **依赖**：`kafka-python`（纯 Python）+ 标准库。
- **日志采集（双接入，修正）**：SDK 同时提供
  1. stdlib `logging.Handler`（gq/cs/cc 走标准库日志）；
  2. **structlog processor / LoggerFactory 集成**（sp 用 `PrintLoggerFactory` 直出 stdout，不经 stdlib logging → Handler 采不到）。**落地约束（写进整改清单）**：sp 须在 `core/logging.py` 的 processors 链（JSONRenderer 之前）插入 SDK 转发 processor，或改 LoggerFactory 为 stdlib.LoggerFactory；且 SDK `init()` 在 sp `setup_logging()`（structlog.configure）**之后**执行防覆盖；把 sp 的 `request_id` 规约为 `trace_id` 注入事件帧。
- **节点打点**：`record_request()` / `record_llm()` / `record_tool()` / `record_retrieve()` / `record_db()` / `record_redis()` / `record_quality()`。agent 在请求入口/出口、LLM 调用、DB/Redis 访问、兜底分支插桩。
- **LLM 通道覆盖（修正）**：除统一客户端/网关层的打点外，SDK 提供"第二通道显式打点"清单——gq 的 httpx 直连流式 + `ChatOpenAI.invoke`（rewrite/compress，其中 rewrite 通道现于 agent 侧注释禁用，接入时按实际状态核对）、sp 的 `conversation_service._summarize_with_llm` 自建 AsyncOpenAI 汇总通道等旁路 LLM 调用都要接入（统一包装或 `@record_llm` 装饰器），否则 usage/错误率存在黑洞。
- **版本注入（R5 打点源，v3.4.5）**：SDK init() 读取部署环境 `AGENT_VERSION`（agent 侧构建时注入 image tag / git commit），写入每个事件 `agent_version` 字段——R5 回查版本锚定与聚类溯源的数据源（§10.5/§13.0 checklist #9）；未配置则该字段空、事件不拒收，但接入验收判不通过。
- **trace 上下文**：contextvar 承载 trace_id、全局单调 seq（原子递增）、branch（并行分支标注）；日志 handler 自动注入。
- **可靠性与降级**：内存队列 + 批量（≤500 条 / ≤2s 冲刷）+ 失败退避（≤3 次）→ 本地磁盘兜底（默认挂**持久卷**、路径可配，容器重启不丢——不写死 `/tmp` 易失盘，对齐 §16）→ 恢复补传；**平台/Kafka 故障绝不影响 agent 业务**。
- **会话状态钩子（可选，会话型 agent）**：`record_session_state(trace_id, state)` 采集影响后续判断的状态快照（检索命中文档 id、用户已确认/否决的约束、累计轮数），供 L3 会话型用例重建会话（§10.3 C2）。
- **自监控**：SDK 上报成功率/丢弃量作为平台自身可观测信号。

### 5.2 传输（Kafka）

- 每 agent 一个 `obs.agent.<name>` topic，`partition=1`（同 trace 近似保序，消费简单）。
- SDK 内 kafka-python producer；消息为单条 JSON 事件（schema §4.1），消息内带 `agent` 供消费侧双重校验。

---

## 六、消费与处理

### 6.1 消费 worker（online 侧）

1. 订阅 `obs.agent.*`，批量拉取；
2. **校验**：schema 强校验、必填字段、`ts` 明显偏离设定漂移窗（agent 时钟可能不精确）**只告警不丢弃**——丢弃会破坏 §5.1「恢复补传不丢」；乱序由 `_id` 幂等 + `(seq,ts)` 树序校验吸收；interface 与字典匹配（不匹配 → 自动注册 + 待人工补 llm 标记）、agent 标识与 topic 一致；
3. **脱敏复核**（§4.5）；
4. **trace 级累积态（决策 R1）**：partition=1 相对有序 → 消费侧维护 per-trace 累积缓冲（TTL=完成窗口）：request 根事件到达 → 标记该 trace 可判定；子节点 error/quality 汇入该 trace 状态；**trace 完成才做 L2/L3 判定 + per-trace 归并（§10.2）**——SSE/多批/子节点分批到达下判定不缺完整 trace。**重建 = 判定态持久化（第三轮裁定）**：per-trace 累积态三要素（已见子节点含 error/quality 汇总、root 是否到达、是否已判定）**落 MySQL 判定态表（TTL=完成窗口 + 宽限）**，重启/重平衡从持久化判定态重建缓冲、**不依赖 ES 回读**（offset 已过则已消费子节点无从回读，纯内存缓冲重平衡会静默漏判）；**残 trace（root 未到达但已有子节点 error/quality）不悬挂等待——按已有子节点判定**，防超长 SSE 连接在缓冲 TTL 内不闭合导致漏判；判定完成记处理位点防重放重复建 case（§6.2）；
5. **分派入库 ES**（event_kind 分流；`_id = sha256(agent|trace_id|seq)`，seq 全局唯一 → 重复投递覆盖）；ES 写失败丢弃不阻断维度 3 判定（分析源在 step4 累积态内）；
6. offset 管理；失败重试队列，超阈值丢弃并计数。

### 6.2 幂等与顺序

- **seq 语义（v3.1 回退 trace 级全局单调）**：`seq` = trace 内 contextvar 原子递增的全局单调序号（根 request=0），全 trace 唯一；`branch` 仅作文本标注，**不入幂等键与引用**——避免 per-parent 自增导致的嵌套/递归重复 seq 与 `parent` 引用歧义（并行先后按 `(ts, seq)` 排序还原）。
- ES `_id` 幂等吸收 Kafka at-least-once 重复投递；
- **顺序还原**：partition=1 保证相对有序；链路树按 `(ts, parent, seq)` 还原，`parent` 指向全局唯一 seq 无歧义。
- **MySQL 侧幂等（评审补）**：cluster/用例生成按 trace 幂等键记录处理位点（§7.2 去重唯一索引 + link 幂等键），消费/分析 worker 多实例、offset 重投/进程重启不重复计数、不重复建 case（§10.2）；判定态表（§6.1 step4）记录已判定 trace 幂等集，重平衡/重放不重复判定、cluster 计数不虚增。
- **seq 分配器（trace 级共享，第三轮确认）**：seq 自增 = trace 的 contextvar 原子计数，**同一 trace 内并发分支（branch>0）共享同一把计数器**（不 per-branch 独立分配）——保证 `_id=sha256(agent|trace_id|seq)` 全 trace 无碰撞，`parent` 引用无歧义。

---

## 七、数据层（D16）

### 7.1 Elasticsearch

| 项 | 规划 |
|---|---|
| 集群 | 8.x 单节点（内部环境，独立部署，与 offline 无关） |
| Index | 按周滚动 `obs-event-yyyyWW` / `obs-log-yyyyWW`（**事件 + 日志分 index 为基线**——性能/容错评审共识，见 §17 #1；仅当容量实测极端不足时回退合并单 index、doc 带 event_kind） |
| ILM | 30 天自动删除；正文保留期同 ILM |
| 幂等 | `_id = sha256(agent\|trace_id\|seq)`（seq 全局唯一；agent 入键防跨 agent 同 trace_id 互覆，评审修正） |
| 映射 | trace_id/agent/interface/node(keyword)、ts(date)、duration_ms(long)、status、error_type、quality、input/output/log_message(text 中文分词)、usage(object)、session_ctx(text 截断) |
| 容量 | 内部环境 4 agent 峰值 ≤500 事件/s + 日志同量级，周滚动 index 远低于单节点压力 |
| 指标 | **双路（决策 R7）**：1h/24h 实时 agg（date_histogram × percentiles(p50/95/99) × filter(error/timeout)，近实时 <5s）；**7d 查小时级 rollup**（`obs-metrics-rollup`，每小时 job 预聚合 agent×interface×node×小时（计数桶 + t-digest 可合并分位草图，机制见 7.1 表后））——7d 深聚合超单节点实时能力，P1 看板页需 rollup 前置（见 §17 #8） |

**rollup 运行机制（v3.4.5 补全，决策 R7 实现细化——第三轮性能/容错/逻辑三方向同源）**：

- **存储形态**：`obs-metrics-rollup` 每小时 job 预聚合，分桶粒度 agent×interface×node（request/llm_call）×小时；每桶存 **status/usage 计数桶**（total/error/timeout 互斥计数、token 汇总，request/llm_call 锚点）+ **t-digest 可合并分位草图**（duration 值分布按小时存草图，跨小时可合并出 7d 单值 p50/95/99）——"按小时存已算 percentiles、跨小时不可再合并"是 7d 分位查询的关键盲区，草图化解；llm_call 桶按 model 维度分。
- **调度/回填/迟到**：job 挂平台 worker（§14 周期任务，APScheduler 同族）；**首启回填**历史已完成小时；**迟到事件幂等重算**——事件晚到 ≤K 小时（默认 6h）内重算对应小时桶（重算与落库原子替换、重叠不双计），超窗迟到只进实时 agg、rollup 该小时明示缺口。
- **失败降级**：job 记录最近成功时间；7d 查询命中缺失/过期小时桶 → 该小时回退 ES 实时 agg + 页面标注"回退实时口径"，自监控告警（§16）。
- **尾小时口径**：7d 视图最后未完成小时不在 rollup → 实时 agg 补齐拼最后一段，趋势不截断。
- **时间窗路由枚举（§9.2）**：≤24h → ES 实时 agg；7d（>24h）→ rollup + 尾小时实时补齐。

### 7.2 MySQL（平台元数据，库 `obs`）

| 表 | 用途 |
|---|---|
| `user` / `role` / 会话 | 平台账号（独立体系，§12） |
| `agent` | 自发现注册（name、base_url、enable、**路由来源标记**） |
| `interface` | 接口字典缓存（agent_id、归一化 interface、**llm 标记（配置驱动+人工补标）**） |
| `error_cluster` | 错误聚类（error_type、input_hash、首次/最近 ts、次数、**代表事件最小快照**、状态 open/claim/fixed/inactive/needs_review、**claim 时填的修复版本 fix_version（回查锚定依据，§10.5）**、**生命周期代数 generation**——复发重开代数 +1，§10.2） |
| `error_case_link` | 错误 ↔ offline 回归用例关联（case_id、case_type、verify_status、**offline case 激活态 offline_status∈{draft,active,invalidated}**（draft=已推送待 offline 激活——error 型收单即结构自检、quality 型等人工确认；active=offline 已激活可进回归 run；invalidated=offline 驳回（quality reject 软删 rejected / error 结构自检失败）回写失效，reopen 可再流转——online 侧冗余镜像 offline case 状态，供"待 offline 确认"筛选标记，§10.3/§10.5）、source trace_id、**建 case 时记录的触发 agent 版本（仅溯源：确认错误在缺陷版 V_obs 存在）**、**回查锚定版本 = 关联 claim 填的 fix_version**（决策 R5 修正——错误在已发布版发现、回归 run 绑待发布修复版，按触发版本回查恒取空，§10.5）、**建 case 幂等键**） |
| `conversion_record` | 回流审计（trace→case、action、detail、ts、actor_user_id——系统自动回流记 system，人工确认/回退记操作人；置 fixed 记录 **closed_by∈{auto_regression, admin_review}** + 依据，§10.4） |
| `agent_credential` | agent 上报凭证（Kafka SASL/ACL 映射，加密存储 + 轮换，§12） |
| `dict_config` | 平台配置（兜底话术库、超时阈值、正文开关白名单、会话上下文轮数、聚类窗口等） |

> MySQL 一致性补强（六方向评审 + v3.4.5）：`error_cluster` 去重键（agent+interface+error_type 分类+input_hash）加**唯一索引、含生命周期代数 generation**——同代并发首现双写由唯一索引吸收（失败重试），复发重开（§10.2 superseded 后同键再现）代数 +1 开新行、不与同键已归档 cluster 冲突；`error_case_link` 带 source trace 幂等键防重试/重放重复建 case（§10.3 对账）；`error_cluster` 存**首次异常代表事件最小快照**（input_hash、error_type、error_msg≤512、首次 trace_id、触发 agent 版本），供 ES ILM 过期后聚类处置仍有可辨原文（needs_review/人工处置场景）。

### 7.3 保留策略

- ES 事件/日志/正文：ILM 30 天自动删（第一版不冷存）。
- MySQL 元数据（聚类/回流/字典）：长期保留（"已复验"是长期业务事实，供闭环与审计）。

---

## 八、维度 1：traceId 链路日志查询（D15）

**能力：** 查询页可自由输入 traceId 和/或关键字（可都输入、可任一）。
- **traceId 查询**：返回该 trace 全部事件（`(ts,parent,seq)` 树排序，branch 仅标注）→ 前端时间轴（request 根 + 子节点），异常节点红显，日志行穿插，详情含脱敏后堆栈/正文。**大 trace 防护（评审）**：日志行（event_kind=log）分页懒加载，避免单 trace 上千日志行一次拉爆；事件行设单 trace 返回上限 + 超时（§16 登记）。
- **关键字查询**：全文检索 input/output/log_message/**error_type/error_msg**（评审补：error_msg 需可命中才能按错误摘要找链路）→ 命中 trace 列表（**search_after 深翻页**，避免大 from 偏移拖垮单节点）→ 进入 trace 视图；检索面限最近 7d（可调）+ 结果上限 + 超时（§16 登记）。
- **边界**：链路覆盖 agent 后端进程内打点；网关/前端 access log 第一版不纳入。

---

## 九、维度 2：metrics 看板（D4/D5/D15）

### 9.1 指标口径（平台统一）

**双指标体系，error/timeout/ok 互斥：**

| 指标 | 锚点 | 定义 |
|---|---|---|
| 请求级 P50/P95/P99 | `request.duration_ms` | agent × 接口 耗时百分位 |
| 请求失败率 / 超时率 | request | `status=error` / `status=timeout` 请求数 ÷ 总请求数 |
| LLM 调用级 P50/P95/P99 | `llm_call.duration_ms` | 每次 LLM 调用耗时（区分模型） |
| LLM 失败率 | llm_call | `status=error/timeout` 的 llm_call ÷ 总数 |
| token / 估算成本 | llm_call.usage | 总量与趋势 |

- **超时口径（修正）**：超时率以 `status=timeout` 为准——由 agent 侧 SDK 按接入约定阈值打标；平台不对 duration 二次判超时（只对明显异常高标"疑似超时"展示标签，不参与互斥计数），避免双源口径漂移。
- **缓存命中（gq 等）**：缓存命中请求计入 request 指标、无 llm_call（LLM 指标反映真实调用）；缓存命中不进入 L1/L3 错误判定。
- **降级型劣化口径（L3 现场）**：`request ok + 子节点 llm_call error + quality` 三字段共存 = LLM 失败被兜底/降级；请求仍计 ok、不计失败率，但 quality 事件维度 1 可查、看板单列（§9.3），不进失败/超时排序。
- **样本口径**：p95/p99 正常显示，不考虑样本 <30。
- **接口范围**：字典内全部接口（含 login 等非业务接口）；看板可按 agent 切换；cc 仅展示 HTTP 接口指标（D18）。

### 9.2 查询链路

前端选 agent + 接口 + 时间窗 → `GET /api/v1/metrics` → **时间窗路由（决策 R7）**：1h/24h → ES 实时 agg（date_histogram + percentiles + filter）；7d → 查小时级 rollup index（obs-metrics-rollup）。近实时。

### 9.3 看板视图

Agent 概览卡（QPS、P50/P95/P99、失败率、超时率、趋势 1h/24h/7d）→ 接口明细（全接口 + 双指标 tab）→ 异常聚焦（失败/超时排序 → 异常列表 → trace 视图联动）→ **L3 质量出口**（quality 事件计数 + fallback/low_confidence 占比，接口维度；P1 提供——否则兜底劣化在 status=ok 下研发不可见）。

---

## 十、维度 3：异常回流（三层模型，核心业务）

### 10.1 分层与判定（D7）

| 层 | 定义 | 判定来源 | offline 复验目标 |
|---|---|---|---|
| L1 | LLM 硬错误**透传**到接口（request 直接 error） | trace 内 request `error_type ∈ llm_*` | 接口不再报该错误 |
| L2 | LLM 相关接口的程序错误（接口直接 error） | trace 内 request / 子节点 `error_type ∈ {llm_interface_business, external_non_llm, db_error, redis_error}` 且 **该 trace 内 LLM 动态事实成立 或 接口字典 `llm=true`**（决策：L2 OR——兼容首次 llm_call 前的程序错误，§4.3/§10.1 注） | 接口不再报该错误 |
| L3 | LLM 失败被兜底吸收 / 低置信硬答（请求仍 ok） | `quality.level ∈ {fallback, low_confidence}`（agent 插桩为主 + 关键词兜底） | 不再兜底/低置信 |

- **异常判定 = trace 级聚合**（§4.2）：子节点 error 或 quality 与 request 是否 error 无关，都能进入聚类。**判定源 = 消费侧 trace 累积态（trace 完成判定，§6.1 step4，决策 R1；判定态持久化重建、残 trace 按子节点判定，v3.4.5）**，不依赖 ES 回读。request 级 status 只服务维度 2 指标。
- **自愈不出回流（修正举例）**：llm_call 内部退避重试最终成功 → 仅 `status=ok`、无 error 子节点（§4.2），自然不进候选。真正需盯的是**静默降级盲区**：LLM 最终失败被业务吞掉（请求仍 ok）且未插桩 quality——不进回流、也不进 quality 出口（§9.3 只数 quality 事件）。缓解：agent 兜底分支必打 quality（§13.1 #5）+ 该场景 P2 以 agent 自监控/看板告警收敛（§16 登记）。
- **LLM 判定 = trace 内动态事实（v3.3 修正）**：trace 内出现 `llm_call` 子节点 / `llm_*` 错误 / quality 信号即视为 LLM 相关，**不依赖 `interface.llm` 人工标记**；该标记退化为看板分类——平台自动补标（**观察窗机制，§17 #11 裁定**：观测到 llm_call 且字典 llm=false → 置"疑似漏标"；连续观测达阈值 → **自动置 llm=true 不再疑似**；观察窗内尚未达阈值/存疑 → 置 llm=true 待确认并进 admin 复核，仅 admin 处置——不引入"该 agent 的 viewer"归因步，R2 无 per-agent viewer 承载）+ **疑似漏标告警**（§12.1 Agent 管理）。
- 回流前置：agent ∈ 白名单（gq/cs/sp，硬排除 cc）+ 该 trace 内 LLM 事实成立（**L2 例外：或接口字典 llm=true**，§4.3）；login 等非 LLM 接口出指标不出回流。
- 范围：**gq / cs / sp**（D18，cc 不纳入维度 3）。

### 10.2 聚类与去重（D10）

**去重键：** `agent + interface + error_type 分类 + input_hash`
- `input_hash = sha256(normalize(input))`；normalize = strip + 折叠空白 + 截断 4096 字符；对话型取 input_turns + 会话上下文摘要归一。
- **L3 去重键用伪分类**：L3 是 quality 信号非 error_type，键内 `error_type 分类` 映射为 `quality/fallback`、`quality/low_confidence`，不与 error 类空串混键、两类互不合并。
- **per-trace 归并**：同一 trace 多异常（如 LLM error + 兜底）按**分层优先 L1/L2 > L3** 归并为一次候选；**已知取舍（明示）**：同 trace 含 L1/L2 时该 trace 的 L3 现场被吞并、不单独生成回归用例（回归重点是其硬错误）；纯 L3 现场（无 error）独立生成。
- **L3 现场留痕（评审补）**：被 L1/L2 归并吞掉的 L3 现场（兜底/低置信）只存 ES、随 ILM 30 天过期后不可补回流；若需在 L1/L2 修复周期 >30 天时补回 L3，在 `conversion_record` 留 L3 观察标记（P2 可选）。
- **生命周期（评审修正，消除首现/静默语义死结）**：同键**首现即开** `error_cluster` 并自动生成一次回归用例（§10.4 自动生成默认开——生成即 **draft 推送 offline，激活决策全归 offline（§11 #5）**：error 型 offline 自动化激活、quality 型 offline 人工确认激活；draft 未激活期间 cluster 保持 open、link 标"已生成用例（待 offline 确认）"，见 §10.3/§10.5）→ `error_case_link` 处于待复验时，窗口（默认 7 天）内同键新现**只计数、刷新最近 ts、不重复生成**；同键持续静默超窗口 → cluster 转 inactive（归档，保留最近 ts/计数供查）；被 ignore，或 claim 后经回归证据/admin 复核置 fixed（§10.4 决策 R4）→ 旧 link superseded，同键再现允许**重新开 cluster 再生成（generation+1，§7.2）**。不再采用"窗口内无新现→转 open"表述（与首现即生成冲突）。**superseded 只标注旧 link"已被取代"，不覆盖其历史 passed 终态**——旧 link 曾 passed 的复验证据保留，同键复发时展示"历史通过于 V_x / 现又复发"，供研发判断是否回归失守。
- **不带版本**：同错误跨版本持续存在直到修复。

### 10.3 回归用例生成（D9）

worker 按聚类生成回归用例，映射 offline（`agent+interface → offline agent_id+interface_id` 配置驱动）：

| 层 | case_type | input | 判定方式 |
|---|---|---|---|
| L1 | `regression_error` | 出错请求 input（脱敏，含会话上下文摘要） | offline 判"接口无技术错误" **+ 未落入兜底/低置信**（决策 R6：防研发 catch 硬错转兜底话术返回 200 假绿过门禁；error 用例技术跑通后亦过 §11 #3/#4 的 `no_fallback` 兜底断言，落兜底→fail） |
| L2 | `regression_error` | 同上 | 同上 |
| L3 | `regression_quality` | 兜底/低置信现场 input（含检索命中/会话快照上下文） | offline **无 golden 语义判分通道**判"不再兜底（fallback）/ 不再无据硬答（low_confidence）"（§11 #4 subtype 分叉判据） |

- **复现门槛按层差异化（C1）**：L1/L2 error 用例用现场 input 直接复现（技术错误与历史会话基本无关），**不依赖会话重建**；仅 L3 quality 用例与强依赖历史语义的错误需要会话上下文。**L3 现场 input 携带检索命中/工具调用与会话快照上下文**（adapter 还原，§5.1 record_session_state）——low_confidence 判据需判"仍无据硬答"，仅裸文本不足判"自信硬答"（§11 #4 分叉判据，第三轮裁定）。
- **会话重建（C2）**：会话型接口（cs/gq）经 SDK `record_session_state()` 采集**状态相关快照**（检索命中文档 id、用户已确认/否决的约束、累计轮数等影响后续判断的状态事实）重建会话，较逐字 N 轮更精准省；快照不足以自动组装可执行现场 → cluster 标 `needs_review` 交属主 viewer 认领处置补上下文（§16/§10.4）——**补足可复现后转出 quality draft 推送 offline 人工确认激活（online 研发只补上下文、不自动激活、不裁决用例准入，§11 #5）；仍无法补足或 cc 文件型（D9）→ 不产 draft**（防失真绿）。
- **文件型输入**（cc）第一版不回流（D9），cluster 标 `needs_review`。
- 调 offline 建 **draft** case（一律 draft，§11 #5），写 `error_case_link` + `conversion_record`；offline 不可用 → 重试队列。**激活决策全归 offline（v3.4.5 裁定，online 不再设任何测试集激活/人工环节）**：error 型（L1/L2 regression_error）draft → offline **收单即结构自检激活**——结构自检（字段完整 / adapter 映射 resolve / no_fallback rubric 就绪）通过即 active；**语义验证延迟到回归 run executor 期（§11 #3），激活期不试跑、无需人看**；结构自检失败 → 驳回 rejected、online 回写 invalidated，offline 能力补齐后修正可重推；quality 型（L3 regression_quality，含 needs_review 处置补足上下文后转出的现场，C2）draft → 等 offline **人工确认**——确认通过 → 激活；驳回（quality 人工 reject）→ offline **软删 status=rejected 归档**（从 active 集移除、永不装载 run、不进常规评测聚合；保留行供审计与 online 回查，§11 补强）+ online 回写 link invalidated（reopen 后同错再现可再次流转，error_case_link 唯一索引含代数、不阻挡，§7.2）。draft 未确认期间：cluster 保持 open、link 标"已生成用例（待 offline 确认）"、verify_status 保持 pending（§10.5 不判红不催 admin 复核）；offline 长期不确认 → **offline 侧确认 owner 的 TTL job 顶置告警**（默认 7 天可配、不自动绕过、offline admin 可 ignore/续期）——online 不设自身时钟、仅聚类页展示"已待 N 天"（展示非告警，防双时钟）。online 保证 draft 质量下限（现场完整、needs_review 标清失败上下文），防低质样本灌爆 offline 确认队列；online 人工仅剩 §10.4 线上错误处置（claim/ignore/needs_review 处置/fixed 复核），与测试集确认无关。

### 10.4 线上错误人工处置（轻量版，D11）

每条 `error_cluster` 可 ignore（inactive）、**claim（人工认领标记已修复，进入"待复核"中间态，须填修复版本 fix_version + 说明，conversion_record 审计；fix_version 是 R5 回查锚定版本，缺失无法走 auto_regression 闭环，§10.5）**、查看已生成用例与复验状态。**置 fixed 需回归证据（该 case 单错级 passed，§10.5）或 admin 复核**——viewer 不能单方面 closed（决策 R4，防绕过 pending 回归门禁）。可 reopen。自动生成默认开启（生成即 draft 推送 offline、激活归 offline，§11 #5）。`needs_review` 聚类由 cluster 属主 viewer 认领处置、超时升级（§16 易用性登记），避免无主堆积。

**claim 生命周期状态机（v3.4.5，安全/易用/容错三方向同源——无 TTL/无回退会让 claim 无限挂起并抑制复发回流）**：

| 状态 | 触发 | 可迁移 |
|---|---|---|
| open | 新候选 / 复发 | → claim（viewer 认领填 fix_version）/ inactive（ignore）/ needs_review |
| claim | 认领填 fix_version | → fixed（该 fix_version 回归 run 中 case passed，closed_by=auto_regression）/ fixed（admin 复核通过，closed_by=admin_review）/ **open（回归 failed 或复核窗口 TTL 超时未复核 → 自动回退，错误重新暴露与计数）** / needs_review（回归 infra-error 无法判定） |
| needs_review | 会话快照不足 / 判分 na | → open（补充证据） |
| fixed | 置 fixed | → open（reopen：复发/误判） |
| inactive | ignore | → open（反悔/复发再现重新开） |

- 复核窗口 TTL 默认 14 天（dict_config 可配）：claim 到期无回归结果、无 admin 复核 → 自动回退 open 并记 conversion_record（防"认领驻车"——被认领的错误在研发未跟进时不再复发回流、也不再出现在 open 计数，等于人工关掉了该错误的线上告警）。
- 状态迁移一律 **CAS 条件更新**（`WHERE status=期望旧值`），双 viewer 并发 claim / admin 复核 / ignore 不产生 lost-update（逻辑 M2 关联）；置 fixed 记 closed_by∈{auto_regression, admin_review} + 依据（§7.2 conversion_record）。

### 10.5 offline 复验闭环

```
研发修复 → claim 时填 **fix_version**（待发布修复版本）→ offline 触发该 agent regression run（绑定该版本）
  → online 回查（**单错级，评审修正 + 决策 R5 锚定修正**）：以 error_case_link.case_id 对**锚定版本 = claim 填的 fix_version 所对应**的回归 run 的 run_results.pass_fail **逐条判单错**——错误在**已发布缺陷版 V_obs** 发现、回归 run 绑**待发布修复版 V_fix**，建 case 时记录的 trigger_version（V_obs）只能溯源"错误确存在于 V_obs"，**不能作回查锚点**（按 V_obs 取 run 恒取到缺陷版 run 或取不到）；回查取"绑定版本 = fix_version 的回归 run"（**不取"最新 run"**，防 v1.4/v1.5 先后触发拿错 run）；该 case pass 即该错 verify_status=passed → error_cluster 标 fixed（闭环）；与 run 级绿解耦（run 内他错仍红不阻塞本错 closed）
case 处于 draft（quality 型待 offline 人工确认、error 型收单即结构自检激活，draft 窗口极短，§10.3/§11 #5）→ verify_status 保持 pending + 聚类列表/详情标"已生成用例（待 offline 确认）"（offline_status=draft，不判红、不催 admin 复核；offline 长期不确认 → offline 确认 owner TTL job 告警顶置、不自动绕过（§11 补强））
fix_version 尚无对应回归 run（版本未发布/回归未触发）→ verify_status 保持 pending + 聚类详情提示"待 &lt;version&gt; 回归 run"（不判 fail、不催 admin 复核）
回归未通过（该 case 仍 error / 仍兜底 / low_confidence 仍无据硬答）→ verify_status=failed，错误保持 open
  → 聚类窗口内同类新错误并入该 cluster，不再生成新用例
回查连续失败（offline API 不可用）→ verify_status 保持 pending + 退避重试，超时在聚类详情提示"回查失败待人工"（§16）
```

- `verify_status ∈ {pending, passed, failed, invalidated, superseded}`（superseded：旧 link 被 ignore 或 claim→fixed 流程取代，见 §10.2；**superseded 不抹去历史 passed 终态**）；verify_status=invalidated = **offline 判定该 draft 不成案/不可回归**（quality 人工驳回 → rejected、error 结构自检失败）或回流看板人工 invalidate，online 回写——与 superseded（被更新链路取代）语义区分，均不抹去曾 passed 历史，reopen 可让同错再现重新流转。聚类详情展示**该 case 历次回归 run 的 版本×pass/fail 时间线**（三版本联动展示，易用评审），已 passed 又被 superseded 的可视作"历史通过记录"。
- 修复后又复发 → 新 cluster 重新生成。
- **闭环归属（边界）**：回归 run 的触发、版本绑定、与发布流程的门禁集成在 **offline 侧**（§11 #7，offline 改造方案范围）；online 负责生成用例集、回查 verify_status、展示回流看板。online 侧 P2 回流看板提供"该 agent 当前 open+claim 错误数 + 关联回归用例/复验状态"总览（claim 计入待闭环口径，与聚类列表一致）。

---

## 十一、offline 平台配套改造（D17，独立清单，随 P2 排期）

> 与 §10 闭环的 offline 侧能力：引入**回归评测模式**与**回归复验硬门禁**——发布门禁由一道（质量分达标）变为**两道并列**（质量分达标 + 回归复验全绿），都是硬 gate。此清单是 online 对 offline 的**能力依赖/边界契约**；落地细节由 offline 侧独立方案承担（独立评审）。

| # | 改造项 | 说明 |
|---|---|---|
| 1 | `EvalRun.trigger_type` 加 `"regression"` | MySQL ENUM + Alembic；`RunCreate.trigger_type` Literal 同步扩；回归 run 与 manual/held_out 平行 |
| 2 | `TestCase.case_type` 加 `regression_error / regression_quality` | 标识来源与语义；online 生成的用例打标，名称/元数据带 `source` 溯源（可回溯 online trace） |
| 3 | 回归评测语义 + 状态机 | **executor**：regression_error 判技术错误（报错/超时→error，跑通→pass），不进 LLM-judge/score_case；**R6 兜底断言**：error 用例技术跑通后由独立回归 verifier（#4）补判 `no_fallback`（回复未落入兜底/低置信），落入兜底/低置信 → 该 case 判 fail——防研发 catch 硬错转兜底话术返回 200 假绿过门禁；**orchestrator 按用例构成分叉（v3.3 采用独立 verifier，不借道 SCORING）**：① 仅含 regression_error 的 run → 全技术通过 ∧ 全未落兜底（R6）即终态绿 / 任一 error 或落兜底→红，**不落 SCORING、不产 agent_score**（现有"全 pass→SCORING→score_run"需按 trigger_type 分支）；**error-only run 的 no_fallback（R6）断言同样在 verifier 期完成**——不进 SCORING 也要 verifier 中间态 holding（lease 续租 + scanner 回收豁免，与 quality run 同机制），否则 executor"全技术通过"与 verifier"未落兜底"两判之间 run 无中间态归属（第三轮 offline S1）；② 含 regression_quality 的 run → error 用例由 executor 技术判定 + no_fallback 断言后，orchestrator **直接触发独立回归 verifier**（#4）完成 quality 判分，不依赖 scoring 态；run 绿 = error 用例全技术通过 ∧ 全未落兜底（R6）∧ quality 用例全达标 |
| 4 | **L3 无 golden 语义判分通道（独立判定器，v3.3 首选）** | offline 为回归 quality 判分开**独立 `regression_verifier`**（首选路径，避开常规评测链路）：对 quality 用例直接调 judge client 做无 golden 判分（judge `build_messages` 在无 golden + 无 reference 时可用、不空标签误导），结果单落（**eval_result 既有 JSON/detail 承载字段，不加新列**，v3.4.5 与下行"run/result 不加列"统一），**不进 agent_score / score_per_dimension / 常规门禁聚合**——offline 常规评测零污染，**规避 SEMANTIC_DIMENSIONS / metrics 插件注册 / metric_def / dimension.code 等闭集合穿透**。仍需：新增 `no_fallback` rubric（**按 quality subtype 分叉双判据，第三轮裁定**：`fallback` → judge 判回复"是否仍落兜底话术"，quality 用例判"未兜底"达标、error 用例判"未落兜底"即 pass（R6，#3）；`low_confidence` → judge 判"**是否仍无据硬答**"——携带原现场检索命中/工具调用与会话快照上下文（adapter 还原，§10.3），判"已给出有据应答/合理拒答/明确信息不足"即达标、"检索仍无命中仍自信硬答"即 fail——no_fallback 兜底话术判据抓不住"自信硬答"这类假绿）；**judge 判分 na/超时 → 该 case 判 inconclusive（不直接 pass/fail）：重试或标 needs_review 交人工**，防判分服务抖动造成假红/假绿。**必配达标线**（无 target 时门禁缺省全 pass=假绿；按 agent 配 baseline_target 或独立规则）。**备选路径**（不用 verifier 时）：走现有维度体系，则须穿透上述闭集合。横切约束：现有维度判分依赖 golden 基准，无 golden 时 judge 无基准乱判（并非默认 na）→ **regression_error 在任何判分路径下都须按 case_type 跳过 judge 任务** |
| 5 | 装载/激活改造 | run 创建校验与 `case_loader` 加 **case_type 谓词**（普通 run 排除 regression 用例、regression run 只装载对应 case_type；现谓词仅 `status=active + is_held_out`）；online 推送一律 **draft**（现 create_case 默认 draft 恰好对齐——**激活决策全归 offline，v3.4.5 裁定：online 不设任何测试集激活/人工环节**）：error 型 draft 由 offline **收单即结构自检激活**（`PUT /cases/{id}` status=active——字段完整 / adapter 映射 / no_fallback rubric 就绪即 active，语义验证延迟 run executor，§10.3）、quality 型 draft 经 offline **人工确认激活**（含 needs_review 聚类补足上下文后转入的现场——快照仍不足不产 draft，§10.3 C2）（确认 UI 通过→active / 驳回→offline 软删 status=rejected 归档 + online 回写 link invalidated，reopen 后同错再现可再流转）；未激活 draft 不装载进任何 run（现谓词 `status=active + is_held_out` 天然排除）；online 只保证去重 + 幂等 + 质量下限自校验；明确 regression 用例归属独立 suite |
| 6 | 看板隔离（**8 处**） | dashboard.py 的 `EvalRun.trigger_type != "held_out"` 实为 8 处（L43/60/85/87/139/174/196/254，compare 为双查询）→ 常规聚合全部加排除 regression；全仓核对 `==/!= "held_out"` 两类语义：**防污染排除**（加排除 regression）vs **held_out owner 隐藏**（保持 manual 语义，不套用 regression） |
| 7 | **回归复验区块（硬门禁展示）** | gate 墙旁按 agent 显示最近回归 run：版本/触发时间/error 回归 M/N + quality 回归 K/L + 结论绿/红 + 未通过错误源列表；评测记录列表加"回归"标签 + trigger_type 筛选 |
| 8 | 权限 | 回归 run/case 语义同 manual（Staff 可见）；不套 held_out 的裁剪/隐藏逻辑 |
| 9 | 触发与版本绑定 | 回归 run 触发、版本绑定、发布门禁集成由 offline 侧定义（offline 改造方案范围）；online 依赖：建回归用例、回查 verify_status |

> offline 改动集中在 runner（executor/orchestrator/case_loader/scorer）/ judge（rubric）/ **verifier（新增独立回归判定器，v3.3 首选——据此避免改动 SEMANTIC_DIMENSIONS / metrics 注册 / dimension.code）** / dashboard。run/result 表不加列（PASS_FAIL 四态已承载），TestCase/EvalRun 各加一个枚举/标记字段。**verifier 判分详情落 eval_result 既有 JSON/detail 承载字段**（按 dimension 记录 `no_fallback`/quality 达标条目）——"eval_result 需加字段"与"run/result 不加列"表述统一为：**不加新列、复用既有 JSON 结构承载**（第三轮修，offline S2；加列会触碰闭集合且与 §11 底线矛盾）。此项单独出方案、单独评审（Task #4）。

> **offline 配套补强（六方向评审，全部并入 Task #4 offline 方案输入）**：
> - **回查契约（单错级，修正 §10.5 全绿口径 + 决策 R5 锚定修正 v3.4.5）**：`error_case_link` 建 case 时记录触发时 agent 版本（**仅溯源**）；**回查锚定版本 = claim 声明的 fix_version**（错误在已发布缺陷版发现、回归 run 绑待发布修复版——按触发版本取 run 恒取错/取空，三方向独立确认的死锁）。online 以 `case_id` + fix_version 对**该版本对应**的回归 run 的 `run_results.pass_fail` **逐条判单错**——该 case pass 即 passed，与 run 级绿解耦（同 run 内他错修复不阻塞本错 closed）。offline 侧补齐：`list_runs` 按 **agent+version+status** 过滤回归 run 且**支持按含 case_id 过滤**（现无 trigger_type 过滤）、`run_results` 返回 case_id+case_type+pass_fail（现只 case_id+pass_fail，case_type 需 join）。
> - **verifier 期状态机**：含 quality 的回归 run，verifier 判分发生在 run 终态路径，需**保活心跳/续租**或新增 verifier 中间态并让 scanner 回收豁免（lease 过期标 timeout 的 `score_run_salvage` 存在竞态）。
> - **quality 判分回写（决策 R5）**：含 quality 的回归 case，verifier 判分详情落 eval_result 后，**case 级 pass_fail 由 verifier 结果回写 run_results**（quality 达标线 → pass；na/error/不达标 → fail），使 §10.5 单错级回查对 quality 型 L3 用例同样生效；error-only case 的 pass_fail 仍由 executor/scorer 常规判——两型并行走回查。
> - **no_fallback 落库前置**：新增 `no_fallback` dimension 行（dimension.code）+ seed judge_rubric(interface_id=0)；否则 rubric/达标线 FK 落不了库；误入常规判分 `get_metric("no_fallback")` 会 KeyError——印证独立 verifier 路径必要。
> - **回归 run 与 manual 互斥槽（决策 R5：共存，不互斥）**：`create_run._MUTEX_STATUS`（pending/running）计数需评估——发布门禁触发回归时同 agent 常规 run 在跑会 409；**结论：回归 run 不占互斥槽、不参与 max_active_runs 计数，与 manual/held_out 共存**；代价是回查可用性窗口受常规 run 排队影响——online 判绿以 claim 的 fix_version 对应 run 为准，跑哪个 run 属 offline 调度自由度。
> - **看板/清理豁免 + 回归 run 保留档（§17 #12，第三轮裁定）**：`/coverage` 与 gate stale_suites 的 case/suite 计数排除回归（否则门禁恒显"陈旧 suite"/覆盖率虚高）；`cleanup_rules` 按 agent+suite 保留 N=50 **只清 run 不清 case**（TestCase 从不被批量清理——#12 原"回归用例保留"描述失准，已改写为 **run 保留**）；对**回归 run 设独立保留档（pinned/豁免 cleanup）**，否则 R5 回查历史被清、闭环断；确需清理超老回归 run 时，其 pass_fail 终态先落归档快照（offline 侧），online 回查据此仍有判单错依据。
> - **offline 确认 gate（激活全归 offline，v3.4.5 收敛裁定）**：online 生成回归用例一律 draft 推送、不设 online 激活/人工确认；激活在 offline 平台内闭环——error 型由 offline **收单即结构自检激活**（语义验证延迟回归 run executor，§10.3）、quality 型经 offline 人工确认（通过→active / 驳回→**软删 status=rejected 归档**——从 active 集移除、不装载 run、保留行供审计与 online 回查，online 感知 rejected → link invalidated）。draft 未激活期间 online 侧 cluster 保持 open、`error_case_link` offline_status=draft 标"已生成用例（待 offline 确认）"、verify_status=pending（§10.5，不判红不催 admin）；确认积压由 **offline 侧确认 owner 的 TTL job 告警**（默认 7 天可配、不自动绕过、offline admin 可 ignore/续期）；online 不设自身时钟（防双时钟），仅聚类页展示"已待 N 天"（展示非告警）。offline 侧需新增：case status 枚举加 rejected、error draft 收单结构自检、draft 超时 TTL job——列入 Task #4 offline 方案。online 需承担 draft 质量下限（现场完整 + needs_review 失败上下文标注），否则低质样本灌爆 offline 确认队列、TTL 告警常态化。
> - **回放强契约**：executor 缺 usage/done 标 `ERROR_NO_USAGE`——L1 原现场若 agent 不产 usage 会假红，SDK 侧 llm_call 必带 usage（采集契约，§13.1）；SDK input ↔ offline adapter `build_request` 字段映射需 converter 落结构（配置驱动需定形）；回归 run 跳过 `_probe_before_run` 或指定专用探测用例（首条用例探测失真）。

---

## 十二、鉴权与权限（D12，三域隔离）

| 域 | 主体 | 机制 |
|---|---|---|
| 平台用户 | 观测平台登录（React） | 独立账号体系（JWT），viewer/admin；viewer 观测/回流**查看** + 回流**人工操作**（D11 研发闭环），admin 另管 agent/接口字典/配置/用户/正文开关 |
| agent 上报 | obs-sdk → Kafka（§5.2） | Kafka SASL + topic 级 ACL（每 agent 凭证映射 producer 身份、topic 不可互写，§12 补强）；`agent_credential` 存 Kafka 凭证、加密存储并轮换 |
| 平台间 | online → offline | offline 专用服务账号（evaluator 角色）+ 独立凭证，最小 API 面 |

正文查看需该 agent viewer 及以上（§4.6）；脱敏底线见 §4.5。

> **安全补强（六方向评审）**：平台用户域——JWT 用短效 access + refresh、口令散列 + 失败锁定、admin 禁用用户即吊销。agent 上报域——**Kafka 启用 SASL/TLS + topic 级 ACL**（每 agent 凭证映射 producer 身份、topic 间不可互写；否则可写 topic 者即能伪造任意 agent 事件：跨 agent 投毒、伪造 input/quality 制造回流候选、借 §6.1 自动注册污染接口字典）；**broker 侧前置（R3 落地，第三轮）**：`auto.create.topics.enable=false`（防任意主体自建 topic 绕过白名单）、authorizer 默认拒绝（未显式授权即不可读写）、**先建 topic + 绑定 ACL、后发凭证**（消除"先发后建"窗口内凭证持有者可预建/预写）；topic 名白名单（`obs.agent.[a-z0-9-]+`）；**online 消费侧 principal 单独入 ACL**（消费与生产主体分离），开启认证后消费侧遇未授权 topic 消息**丢弃并计数告警**（不静默忽略）；`agent_credential` 加密存储并轮换（版本化、吊销即时生效）。平台间域——online↔offline 最小 API 面（端点白名单 + 双向认证 + 凭证轮换）。存储访问——ES/MySQL 仅 backend 网段可达并启认证 + 传输加密（TLS）、MySQL 按 schema 最小账号权限（9200 对浏览器可及网段开放即绕过本权限模型）。平台用户域——JWT 吊销支持升级为 **token version**（用户表版本号自增，强制历史 token 失效）；被攻陷 agent 借真实凭证刷回流候选/灌指标 → **每 agent 上报/回流候选量级速率闸**（异常激增告警 + 阈值熔断）。

### 12.1 前端页面体系（浏览器层：角色 / 菜单 / 页面 / 功能点）

**浏览器登录角色**（独立账号体系；agent 上报凭证、online↔offline 服务凭证不进浏览器）：

| 角色 | 定位 | 权限范围 |
|---|---|---|
| viewer | 研发/负责人（排障与观测闭环） | 三个维度页面**查看** + 回流看板**人工操作**（ignore / **claim 认领（必填修复版本 fix_version + 说明，回查锚定依据）** / needs_review 处置，D11 研发闭环入口；置 fixed 需回归证据通过或 admin 复核，决策 R4；claim 后回归 failed 或超复核窗口 → 回退 open，§10.4）+ 正文查看 |
| admin | 平台维护 | viewer 全部 + **系统管理**：Agent/接口字典（llm 标记补标、归一化核对）、dict_config 配置、正文开关、用户管理 |

> 角色为内部工具模型，**不做 agent 维度的数据隔离**（统一 viewer 可查全部 agent）；正文查看开放范围按 agent 在 Agent 管理中配置（默认 viewer 可见，可收缩 admin only）。

**导航与权限控制**：
- 登录后默认落点 = 指标看板（dashboard，作为首页）；按角色渲染菜单；admin-only 路由对 viewer 隐藏并前端拦截 + 后端按 §12 三域（平台用户域 JWT roles）二次鉴权。
- 首个 admin 初始化（§17 #7），后续由系统管理-用户管理建号。
- 页面归属阶段：登录/链路查询（P0+P1）、指标看板（P1）、回流看板与系统管理（P2；Agent/用户管理随 P0/P1 先行）。

**菜单树**（一级 → 页面）：

```
指标看板    → agent 概览卡 / 接口明细 / 异常聚焦 / L3 质量出口（单页 tab，§9.3）
链路查询    → 链路查询列表 / trace 详情（共享抽屉）
回流看板    → 错误聚类列表 / 聚类详情（回归用例 + 复验状态 + 人工操作）
系统管理    → Agent 与接口字典 / 配置管理 / 用户管理        （admin）
```

**页面与功能点**：

| 页面 | 主要功能点 | 权限 | 阶段 |
|---|---|---|---|
| 登录（/login） | JWT 登录、会话维持、角色归属 | 全部 | P0 |
| 指标看板（/dashboard） | agent × 时间窗切换；概览卡（QPS/P50/P95/P99/失败率/超时率 + 趋势 1h/24h/7d）；接口明细（全接口 + **请求级/LLM 级双指标 tab**）；异常聚焦（失败/超时排序 → trace 联动）；**L3 质量出口**（quality 计数 + fallback/low_confidence 占比） | viewer | P1 |
| 链路查询（/traces） | traceId 和/或关键字自由输入（可任一）；命中 trace 列表 + agent/接口过滤 → trace 详情 | viewer | P0+P1 |
| trace 详情（共享抽屉） | `(ts,parent,seq)` 树时间轴；异常节点红显；日志行穿插；input/output/error_msg 脱敏展示；quality/llm_call 标记高亮；正文查看（受 agent 配置，§4.6） | viewer | P1 |
| 回流-错误聚类（/backflow） | cluster 列表/筛选（agent、接口、层、状态 open/**claim**/fixed/inactive/needs_review + **待 offline 确认**（关联 case offline_status=draft，§10.3））；代表 trace 与 input_hash；去重与生成计数；复验总览（open+claim 错误数 + 关联回归用例 verify 分布） | viewer 查看 | P2 |
| 回流-聚类详情 | 关联回归用例（case_id/case_type/**offline 激活态 offline_status（draft 标"已生成用例（待 offline 确认）"，§10.3）**/verify_status、`source` 溯源、**该 case 历次回归 run 的 版本×pass/fail 时间线**）；conversion_record 审计时间线；**人工操作**：ignore、**claim 认领（必填 fix_version）**、needs_review 处置（决策 R4：置 fixed 需该 link 回归 passed 或 admin 复核——admin 复核动作落本页，通过→fixed / 驳回→reopen，closed_by 记 admin_review）；claim 行展示复核窗口剩余时间（超窗回退 open 提示） | viewer 可操作 + admin 复核 | P2 |
| Agent 与接口字典 | agent 启停；接口字典（自动发现清单、llm 标记补标 + **疑似漏标告警**、归一化核对）；正文开关 | admin | P1 |
| 配置管理 | dict_config：兜底话术关键词库、超时阈值、会话上下文轮数、聚类窗口、回流总开关 | admin | P1/P2 |
| 用户管理 | 账号 CRUD、角色（viewer/admin）、启停 | admin | P0 |

---

## 十三、agent 接入与统一整改（通用接入流程 + 存量整改清单）

> **§13.0 是任何 agent 接入本平台的通用流程**（语言/框架中立，适用未来任意新 agent，含非 Python/Serverless）；**§13.1 是 4 个存量 agent 的整改清单**（落点对应 §13.0 各步骤，接入时按清单逐项清零）。接入不改动 agent 对外业务行为，也不触碰 offline 评测契约——online 观测契约与 offline 评测契约解耦，观测整改是叠加层。

### 13.0 通用接入方案

**接入的本质**：agent 侧新增一条「观测边带」——按 §4.1 事件 schema 产出事件，经 obs-sdk（Python 参考实现）或等价实现送出，为平台提供三类数据：`request` 事件（维度 2 指标锚点）、全节点子事件（维度 1 链路）、error/quality 信号（维度 3 回流）。**平台是权威，agent 只适配**：schema 与字段语义由平台定，agent 不发明私有字段；平台对不合规事件强校验、不兼容即拒（§6.1）。

**接入前契约核对（Step 0，一次性盘点）**——动代码前先对 agent 做形态盘点，产出《接入盘点表》，回答：

| # | 盘点项 | 决定什么 |
|---|---|---|
| 1 | 运行形态：常驻服务 / Serverless / 批任务 | 内嵌 SDK vs 事件协议直发（见「非 Python 路径」） |
| 2 | 语言与 HTTP 框架、日志方式（stdlib / structlog / print / JSON lines） | 日志接入三选一（Step 1.2） |
| 3 | 请求入口形态：同步 / SSE 流式 / 后台任务（无 HTTP 生命周期覆盖） | `request` 根节点打法（SSE 在 handler 出口聚合打一条；后台任务型首版仅 request 级观测，任务根模型 P2 评估，对齐 D18） |
| 4 | LLM 通道清单：统一网关/客户端？有无直连/旁路（自行构造 HTTP、stream、重写/压缩、汇总）？ | `llm_call` 覆盖点（每逻辑调用一条，§4.2） |
| 5 | 会话状态驻留位置（server / 客户端） | 是否接 `record_session_state()`（§5.1，仅会话型） |
| 6 | 兜底 / 低置信分支位置 | `record_quality()` 插桩点（§4.4） |
| 7 | 数据属性：接口是否涉 PII、正文是否需要检索 | 正文开关与掩码配置（§4.5/§4.6） |
| 8 | 接口枚举方式：OpenAPI / 路由注册表 / 需人工维护字典 | Step 2.2 字典核对方式（仅可枚举 agent 走自动发现；否则首次上报经 §6.1 自动注册 + 人工补标） |

盘点表是接入验收（Step 3 checklist）的对照基线。

**接入流程（Step 0 盘点 + 三步接入）**：

**Step 1 观测通道接入（产出事件）**——目标：让每个请求产出一条可对账的观测流。

1. **事件协议**：标准是 §4.1 JSON 事件（字段、`node`、`seq` 全局单调/`branch` 标注、`status` 互斥、`error_type`、quality 信号，§4.2/§4.3）。SDK 只是便捷封装；**任何语言产出同构事件即视为已接入**。
2. **日志接入三选一**（日志与观测合并为一条流，见 §5.1）：
   - a) **stdlib logging.Handler**：业务走标准库日志的框架 → SDK 注入 trace 字段并转发（默认路径）；
   - b) **structlog processor / LoggerFactory 集成**：structlog 直出（不经 stdlib）的框架 → 在 processors 链（renderer 之前）插 SDK 转发 processor，且 SDK `init()` 在业务日志初始化**之后**执行防覆盖；
   - c) **非 Python / 无法内嵌 SDK**：按事件协议直发（见下）。
3. **trace 上下文**：入口生成/透传 `trace_id`；请求内全局单调 `seq` 原子递增、并行 `branch` 标注（§4.1）；日志行自动携带。
4. **必需打点覆盖**（新老 agent 同标准）：
   - `request` 根事件：请求入口/出口（归一化 interface，动态段→`{id}`；`status` ok/error/timeout 互斥；`duration_ms`）；
   - `llm_call`：**每逻辑调用一条**（内部退避重试不拆分，仅标最终失败；重试自愈不回流，§4.2 口径）；
   - 存在 DB/Redis 访问的 agent 打 `db` / `redis` 子节点（§4.2 建议口径）；工具/检索视业务打 `tool_call` / `retrieve`；
   - 兜底/低置信分支打 `record_quality(level∈{fallback, low_confidence}, reason)`；
   - 会话型按 Step 0 结论接 `record_session_state()`。
5. **可靠性与降级默认值**：内存队列 + 批量（≤500 条/≤2s）+ 退避 + 本地磁盘兜底 + 恢复补传；**平台/Kafka 故障绝不影响 agent 业务**（§5.1）；键级掩码 SDK 侧默认开（§4.5）。

**Step 2 平台注册与配置**——平台侧登记 agent、开通信道（admin，§12.1 Agent 管理）：

1. 建 Kafka topic `obs.agent.<name>`（p=1），授 agent 上报凭证（§12 agent 域）；
2. 录入 agent；接口字典核对：可枚举 agent（FastAPI/OpenAPI）自动发现后核对；不可枚举 agent 首次上报经 §6.1 自动注册 + 人工补标（疑似漏标告警 → llm 标记置"待确认"；该标记只做看板分类，不卡回流 §10.1）；
3. 按 Step 0 数据属性结论配置：正文开关、掩码、超时阈值、兜底关键词库（dict_config）；
4. 回流白名单登记：对**新接入 agent**，维度 3 **默认不开放**，平台评估（含 LLM 通道覆盖与兜底插桩到位性，见下 checklist #4/#5/#8）后加入；未加入的只出维度 1/2。存量 gq/cs/sp **例外**：首版即开放维度 3（对齐 D18/§3），不走此默认关闭。

**Step 3 灰度与验收（维度 1/2 基础验收）**——先 1~2 个代表性接口（覆盖同步/SSE 各一，含兜底分支）跑通观察 1~2 天，过【放量门禁】（下 checklist #1/#2/#3/#6/#7）；无未决项才允许全量放量：

1. **链路完整性**：线上抽检 N 条请求，trace 详情能按 `(ts, parent, seq)` 还原全树、日志行与节点穿插、异常节点红显（维度 1 达标）；
2. **指标正确性**：看板 request 级 P50/P95/P99/失败率/超时率 + LLM 级双指标 与 agent 自监控对账（维度 2 达标）；
3. **回流判定正确**：制造一次透传 LLM 错误与一次兜底，确认分别落 L1 / L3、聚类去重符合预期、同错不重复生成（维度 3 达标，§10.2）——**仅当该 agent 已开放维度 3（Step 2.4 白名单）时执行**；未开放则随维度 3 开通后再验。

**接入验收 checklist（新老 agent 通用）**：

> 分两档：#1/#2/#3/#6/#7/#9 = **放量门禁**（维度 1/2 达标 + 版本溯源，任何 agent 放量前必过；#3 llm_call 覆盖同时支撑维度 2 的 LLM 级双指标；#9 版本注入支撑维度 1 溯源与 R5 回查锚定）；#4/#5/#8 = **维度 3 开放验收**，仅对申请/已开放维度 3 白名单的 agent 生效（作为 Step 2.4 加入白名单的前提），不入放量门禁。

| # | 检查项 | 通过标准 | 对应 |
|---|---|---|---|
| 1 | request 根事件 | 全部业务接口（含 SSE）每请求有且仅一条 request，interface 归一化与字典一致 | §4.2/§6.1 |
| 2 | traceId 全链路回放 | 抽检 trace：树可还原、日志穿插、异常红显、input/output 已脱敏 | §8 |
| 3 | llm_call 覆盖 | **每逻辑调用**一条；旁路通道（直连流式/重写/汇总/stream）逐一入账，无 usage/错误黑洞 | §4.2/§5.1 |
| 4 | L1/L2/L3 判定 | 透传硬错落 L1、被兜底吸收落 L3（不误入 L1）、重试自愈不回流 | §10.1 |
| 5 | quality 信号 | 兜底/低置信分支必发 quality；关键词兜底可佐证 | §4.4 |
| 6 | 脱敏 | 键级掩码 SDK 侧生效；正文接口逐评估后开（默认关） | §4.5/§4.6 |
| 7 | 可靠性降级 | 平台 Kafka 停 5 分钟：agent 业务无感、恢复后补传不丢（抽检 ES `_id` 幂等） | §5.1 |
| 8 | 回流范围 | 白名单/接口范围与配置一致；同错不重复生成（去重键验证） | §10.2 |
| 9 | 版本注入（R5 打点源） | SDK init 注入 `agent_version`（读 `AGENT_VERSION` env/构建注入，agent 侧 CI 保证），事件可溯源到部署版本——回查版本锚定与聚类溯源依赖，缺失即版本锚定无数据源 | §5.1/§4.1 |

**非 Python / Serverless / 无法内嵌 SDK 的接入**：以 §4.1 schema 为标准实现最小采集边带——入口中间件产 `request`，拦截日志把日志行与业务事件合并为统一 JSON 事件流，送出方式：**就近 Kafka**（agent 自身或独立小进程产 Kafka 消息；topic/结构/幂等要求与 SDK 相同）。**这是首版唯一承诺路径**。平台侧 **collector/边车代收组件**（可选，非首版能力）未来由平台实现统一代收（登记 §14/§15，P2 后排期）；接入标准不依赖它，agent 侧按直发实现即可，未来接入 collector 无需改协议。
LLM 打点若无封装层可钩，用最外层包装（工具函数/装饰器）或出口统一补记 usage 汇总。**核心约束不变：事件同构、平台强校验**。

### 13.1 4 个 agent 存量整改清单（按 §13.0 逐项清零）

| # | 整改项（对齐 §13.0） | 涉及 |
|---|---|---|
| 1 | 引入 obs-sdk `init()`，日志接入三选一：gq/cs/cc 走 stdlib Handler；**sp 走 structlog processor**（sp `core/logging.py` processors 链插 SDK 转发器或改 LoggerFactory；SDK init 在 sp setup_logging 后执行防覆盖；sp 自有 `request_id` 规约为 `trace_id` 注入事件帧，§5.1） | 4 agent |
| 2 | 业务请求入口/出口打 `request` 事件（归一化 interface、status、duration_ms、input/output 脱敏） | 4 agent |
| 3 | LLM 调用打 `llm_call`（error_type、model/usage）：统一网关层 + **第二通道显式打点**（gq httpx 直连流式 / `ChatOpenAI.invoke`（rewrite/compress，rewrite 现注释禁用，接入时按实际核对）/ sp `conversation_service._summarize_with_llm` 自建 AsyncOpenAI 汇总通道），旁路通道逐一接入 | gq/cs/sp |
| 4 | DB/Redis 访问打 `db` / `redis` 子节点 | 4 agent |
| 5 | 兜底/低置信分支调 `record_quality()`（L3） | gq/cs/sp 兜底逻辑处 |
| 6 | 移除/收敛自有埋点（gq `_json_log`、cs Prometheus `/metrics` 保留端点兼容） | gq/cs |
| 7 | 接口字典：online 侧按**真实路由（FastAPI 路由/OpenAPI）**自发现，agent 确保路由可枚举；`llm` 标记配置维护 | 4 agent |
| 8 | 正文采集默认关，需正文接口逐个评估后开（对齐 D14） | 4 agent |
| 9 | cc：仅接 request 级事件（上传/结果查询），维度 3 不纳入（D18） | cc |

> 整改不触碰 offline 评测对 agent 的契约约定——online 观测契约与 offline 评测契约解耦，观测整改是叠加层。

---

## 十四、平台工程结构

```
agent-evaluation-online/
├── backend/
│   ├── app/
│   │   ├── api/            # logs / metrics / clusters / auth / agents(字典)（无 HTTP ingest——上报走 Kafka，§5.2）
│   │   ├── consumer/       # Kafka 消费、校验、脱敏复核、ES 分派
│   │   ├── store/          # ES 客户端 + MySQL 元数据
│   │   ├── analyzer/       # L1/L2/L3 分层、聚类、归一化、去重
│   │   ├── converter/      # offline 回归用例构造 + 调用 + 复验回查
│   │   ├── worker/         # 后台任务（聚类、用例生成、复验轮询）
│   │   ├── models/         # SQLAlchemy + Alembic
│   │   └── core/           # config / logging / auth / errors / http / dict_config
│   └── tests/
├── sdk/                    # obs-sdk（kafka-python + 标准库 + structlog 可选集成）
├── frontend/               # React：链路查询 / 指标看板 / 回流记录
├── docker-compose.yml      # + Kafka / ES
└── docs/                   # 观测契约规范 + agent 接入文档
```

> 未来可选组件（P2 后排期，非首版）：`collector/` 非 Python/Serverless agent 事件代收组件（§13.0 非 Python 路径）。

---

## 十五、阶段划分

| 阶段 | 内容 | 验收 |
|---|---|---|
| **P0 平台骨架** | backend + Kafka 消费 + ES 存储 + SDK 雏形 + MySQL 元数据 + 链路查询 API | 手工投 Kafka 事件能按 trace 查回链路 |
| **P1 两维落地** | gq/cs/sp 接入 SDK（cc 仅 HTTP 层）；维度 1 链路视图；维度 2 指标看板 | 任取线上请求 trace 可查；看板出现真实 P50/P95/P99 |
| **P2 回流闭环** | 维度 3 三层回流（gq/cs/sp）；offline 配套（§11，独立方案独立评审）；回归复验闭环 | 真实 LLM 错误自动生成回归用例且不重复；修复后回归全绿→错误标已复验；**needs_review 占比纳入观测（>50% 触发回炉会话快照采集，§10.3）** |

P0→P1→P2 顺序推进，每阶段独立交付；agent 整改（P1）与平台开发并行；offline 配套（§11）随 P2 排期。

---

## 十六、风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| SDK 影响 agent 业务 | 高 | 异步批量 + 降级丢弃 + 本地磁盘兜底 + 熔断；SDK 自监控 |
| ES 单节点故障 | 中 | 事件可丢（观测不阻塞业务）；offset 回溯补数据；P2 评估多副本 |
| 去重误判/漏判 | 中 | 归一化 + 聚类窗口 + per-trace 归并分层优先 + 人工 ignore 兜底 + 审计 |
| 降级型异常漏采（LLM 失败被兜底） | 中 | 异常判定 trace 级聚合 + quality 插桩（§4.2/4.4）；agent 兜底分支必打 quality |
| L3 兜底劣化不可见（request status=ok） | 中 | 看板 quality 出口 + trace 按 quality 过滤（§9.1/9.3） |
| L3 回归假绿（no_fallback 无达标线） | 高（offline） | no_fallback 必配 baseline_target 或独立达标规则（§11 #4） |
| 会话态回归失真（"全绿"失真） | 中 | 会话上下文最小集采集 + 不可复现 cluster 标 needs_review（§10.3） |
| 正文/内容型 PII 泄漏（含 input/session_ctx 检索展示面） | 中 | 正文与 input/session_ctx 检索展示面默认关 + 逐接口评估开 + 内容型最小化/检测 + 角色权限 + 30 天保留（§4.6/§4.5） |
| agent 埋点口径不一致 | 中 | 契约强校验 + 双日志接入 + 第二通道打点清单 + 冒烟用例 |
| offline 不可用 | 低 | 回归生成重试队列；不影响指标与链路 |
| 回归隔离遗漏污染常规门禁 | 高（offline） | §11 #6 真实 8 处排除 + case_type 谓词 + 状态机分支；offline 方案自审 checklist 全仓核对 `== "held_out"` |
| 指标口径漂移 | 中 | 双指标口径文档 + 统一 agg + 归一化路径一致 + 超时口径单源（agent SDK 打标） |
| Kafka 无访问控制、可伪造上报（评审） | 高 | Kafka SASL/TLS + topic 级 ACL（每 agent 凭证隔离、topic 不可互写）；ES/MySQL 仅 backend 网段并认证（§12 安全补强） |
| ES 容量/性能论证缺失（评审） | 中 | Step 3 灰度实测后定容量档；事件/日志 index 分离 + size rollover；指标 7d 走小时级 rollup（**v1，决策 R7**，§17 #8/§7.1/§9.2）；单 trace 详情日志分页懒加载（§17 #1/§8） |
| 静默降级盲区：LLM 失败被吞且未插桩 quality（评审） | 中 | 兜底分支必打 quality（§13.1 #5）+ P2 agent 自监控/看板告警收敛（§10.1） |
| 回归用例携 PII 进 offline（评审；回归 run/case 独立保留档下留存更长，v3.4.5） | 中 | 回流前会话快照与 input 内容最小化 + 正文同级约束（§4.5/§4.6）；offline 侧 case/run 数据面 PII 处置策略（含 judge 判分不扩散原始输入，入 offline 方案 §11）；保留档不豁免脱敏底线 |
| 关键字全文检索打满单节点拖垮看板/链路（评审） | 中 | 检索限 7d + 超时 + 结果上限 + 慢查询熔断/限流（§8/§17 #1）——input/output 与指标同住事件 index（无独立文本 index，基线为事件/日志分 index），隔离靠限流/熔断而非索引拆分 |
| SDK「绝不影响业务」承诺前提未成文（评审） | 高 | 有界队列 + 写满**丢弃并计数**（非无限阻塞）+ 本地盘路径可配持久卷（容器重启不丢）+ 降级自监控（§5.1） |
| ES 写失败丢弃导致维度 3 漏判（评审） | 中 | 分析源 = 消费同批事件（§6.1 step4），不依赖 ES 回读；丢弃/失败计数进自监控 |
| error_cluster / 建 case 并发与重试非幂等（评审） | 中 | §7.2 去重唯一索引 + link 幂等键 + 处理位点（§6.2）；回查不因 cluster 归档跳过在途 case（防 case pass 而 cluster 永不 fixed）；仅人工 ignore（link 已 superseded）的 cluster 停回查 |
| needs_review 聚类无主堆积/无人认领（评审） | 中 | 属主 viewer 认领处置 + 超时升级（§10.4） |
| claim 长期挂起（认领抑制复发回流，评审） | 中 | claim 复核窗口 TTL（默认 14 天）+ 回归 failed 回退 open + 超窗自动回退 + CAS 条件更新防竞态（§10.4 状态机） |
| 指标 rollup job 失败/迟到（评审） | 中 | 记录最近成功时间 + 缺失/过期小时桶回退 ES 实时 agg + 页面标注 + 自监控告警（§7.1 rollup 机制） |
| 7d 单值分位不可跨小时合并（rollup 盲区，评审） | 低 | 存 t-digest 可合并分位草图按小时落桶（§7.1），跨小时合并出 7d 单值 p50/95/99 |
| R5 回查无版本数据源/锚定取空（评审） | 中 | 事件 schema + SDK 注入 agent_version；回查锚定 claim.fix_version；fix_version 无对应 run → pending + 提示（§10.5/§11/§13.0 #9） |
| L3 quality 激活积压/迟到（offline 确认 gate，v3.4.5） | 中 | L3 quality 激活等 offline 人工确认，积压使复验闭环延迟 → offline 确认 owner TTL job 告警（默认 7 天可配）顶置、不自动绕过、offline admin 可 ignore/续期；error 型收单即结构自检激活不受影响；online 保证 draft 质量下限防灌爆确认队列（§10.3/§11 #5/§11 补强） |

---

## 十七、待评审确认的残留默认值

| # | 项 | 默认值 | 备选 |
|---|---|---|---|
| 1 | ES index 分合 | **事件 + 日志分 index（已定）**（评审共识：性能/容错两方向独立建议拆分，缓解单 trace 体积与读写互相干扰）；**滚动机制定为周 yyyyWW + ILM delete（v3.4.5 落定，消除"周滚动 + size rollover"双机制含糊），size rollover 降级为容量告警触发的预案** | 合并单 index（doc 带 event_kind，弃） |
| 2 | 正文截断 | ≤8K 字符/条 | 可配 |
| 3 | 会话复现上下文 | 状态快照（session_state 钩子）为主 + 最近 N 轮消息兜底（N 默认 10） | 按 agent 可配 |
| 4 | 超时判定 | agent SDK 按接入约定阈值打标（平台不二次判） | 平台统一下发 |
| 5 | 错误聚类窗口 | 7 天 | 可配 |
| 6 | 接口 `llm` 标记 | 配置驱动 + 人工补标 | 从 agent 元数据推断 |
| 7 | 平台账号 | 独立体系（首 admin 初始化） | 复用 offline 账号 |
| 8 | 指标预聚合 | **小时级 rollup（v1，决策 R7）**：7d 看板查 `obs-metrics-rollup`、1h/24h 实时 agg（§7.1/§9.2 双路） | 首版无 rollup 后置（弃） |
| 9 | 上报通道访问控制 | **首版 Kafka SASL/TLS + topic 级 ACL（决策 R3）**：每 agent 凭证映射 producer 身份、topic 不可互写、防伪造上报（§12.1/§16） | 首版内网信任后置（弃） |
| 10 | 首页跨 agent 汇总 | 登录落点 = 单 agent 指标卡（agent 选择前置） | 顶部跨 agent 汇总行：open 错误数 / QPS / 失败率 TOP（易用评审：先览全局再下钻） |
| 11 | 疑似漏标告警处置 | **admin 复核 + 自动补标观察窗**（已定，v3.4.5）：窗口内观测到 llm_call 连续达阈值 → 自动置 llm=true 不再疑似；仅存疑进 admin（§10.1） | 该 agent 的 viewer 确认 + admin 复核（弃：R2 无 per-agent viewer 承载归因步，漏标历史可在 trace 详情自查） |
| 12 | offline 回归 run 保留 | **回归 run 独立保留档**（已定，v3.4.5）：pinned/豁免 cleanup_rules——cleanup 删 run 不删 case（TestCase 从不被批量清理，原"回归用例保留"描述失准已改写为 run 保留）；确需清理超老回归 run 前先归档其 pass_fail 终态快照，回查仍有判单错依据 | 随常规清理（弃：回查历史被清，R5 闭环断） |
| — | 状态总览 | #1~#9 **已定**（#8 rollup/#9 ACL 于 v3.4.4 裁定；#1~#7 更早轮已定，本轮仅微调）；**#10 首页跨 agent 汇总仍待定**；#11/#12 于 **v3.4.5** 裁定如上 | — |

---

## 附：修订记录

| 版本 | 变更 |
|---|---|
| v1 | 早期全自研草稿（HTTP ingest + MySQL/MinIO，未评审） |
| v2 | 整合逐条确认决策（Kafka + ES、双指标、全接口观测、三层回流、回归评测模式 + 硬门禁区块） |
| v3 | 吸收独立架构评审：锚点/异常判定改 trace 级聚合；字典来源改真实路由（与 manifest 解耦）；降级型异常归 L3；回归隔离清单修正为 8 处；补 case_type 谓词/激活/状态机分支；L3 无 golden 判分通道；SDK 双日志接入 + 第二通道打点；seq 分支盐；4 项方向决策（兜底归 L3 / cc 第一版不回流 / 正文默认关 / L3 offline 自动化判分） |
| v3.1 | 吸收第二轮变更增量评审：§11 回归状态机按 case_type 分叉（error-only 不进 SCORING / 含 quality 必须进 SCORING 且判分按 case_type 分支）；L3 判分穿透面（SEMANTIC_DIMENSIONS / metrics 插件注册 / metric_def / 达标线防假绿）；修正"无 golden 默认 na"为"评分阶段按 case_type 跳过 judge"；seq 幂等回退 trace 级全局单调 + branch 仅标注；L1/L2 catch 转抛边界；llm_call 逻辑调用口径 + 重试自愈不出回流；L3 去重伪分类 + 归并取舍明示；看板 quality 出口；cc llm_call/agent 白名单限定；sp structlog 落地约束 |
| v3.2 | 补充 §12.1 前端页面体系：浏览器层角色（viewer/admin，含回流人工操作归 viewer）→ 菜单树 → 页面清单与功能点 → 权限/归属阶段映射 |
| v3.3 | 针对自估 3 个最薄弱点的修正：§11 #3/#4 回归 quality 判分改**独立判定器路径**（不借道 SCORING/score_run、不进 agent_score，规避 offline 闭集合穿透）；§10.1 LLM 判定改 **trace 内动态事实**（llm_call/llm_* error/quality），`interface.llm` 标记退化看板分类 + 自动补标 + 疑似漏标告警；§10.3/§5.1 复现门槛按层差异化（error 用例不依赖会话历史）+ SDK 增 `record_session_state()` 状态快照钩子 |
| v3.4 | §13 重构为「agent 接入与统一整改」：新增 **§13.0 通用接入方案**（语言/框架中立——接入前契约核对 Step 0 盘点 → 三步接入 Step 1~3（观测通道产出事件 / 平台注册配置 / 灰度验收）→ 接入验收 checklist；日志接入三选一；非 Python/Serverless 事件协议直发）；存量 4 agent 整改清单保留为 §13.1 |
| v3.4.1 | 吸收 §13.0 独立变更增量评审（无致命）：checklist 拆放量门禁 / 维度 3 开放验收两档（维度 3 验收作为 Step 2.4 白名单前提）；collector 明确为非首版能力并登记 §14（首版非 Python 仅承诺就近 Kafka 直发）；Step 0 盘点补接口枚举方式（可枚举/不可枚举 agent 字典核对路径）；后台任务型对齐 D18（任务根模型 P2）；§13.1 #1 补回 sp `request_id` 规约 `trace_id`；§5.1 与 §13.1 rewrite 禁用口径统一单源；db/redis 改建议口径（§4.2）；Step 2.4 加存量 gq/cs/sp 例外；§10.1 自愈口径引用改 §4.2 |
| v3.4.2 | 吸收六方向独立评审（逻辑/数据流、安全、性能、异常容错、易用性、offline 对接；**无致命**）：回流前置与 L2 门控改 trace 内 LLM 动态事实（§4.3/§10.1，消除 `interface.llm` 补标滞后静默过滤）；自愈示例修正 + 静默降级盲区缓解（§10.1，兜底必打 quality + P2 收敛）；cluster 生命周期重写 首现即开→静默→归档（§10.2）+ L3 现场留痕（§7.2 代表事件最小快照）；ts 水位只告警不丢弃 + 维度 3 分析源改同批消费事件（§6.1 step2/step4）、MySQL 侧幂等（§6.2）；error_cluster 去重唯一索引 + error_case_link 幂等键（§7.2）；offline 配套补强 block 并入 §11（单错级回查契约、verifier 期状态机/lease/scanner salvage、回归 run 与 manual 互斥槽、no_fallback dimension 行 + 判分豁免、coverage/gate/cleanup_rules 豁免集、ERROR_NO_USAGE/probe 跳过）；安全补强 block 并入 §12（JWT 短效 + refresh + 吊销；Kafka SASL/TLS + topic 级 ACL + 每 agent 凭证隔离；ES/MySQL 仅 backend 网段；agent_credential 加密轮换；online↔offline 最小 API 面）；§10.4 标记已修复审计 + 可 reopen、§10.5 回查改单错级；§16 风险表登记 8 项；**新增待确认**（§17 表 8~12）：指标预聚合、上报通道访问控制、首页跨 agent 汇总、疑似漏标归 viewer、offline 回归用例保留，及 §17 #1 改**事件+日志分 index**（评审共识） |
| v3.4.3 | 吸收第二轮六方向全量复评去重后的**无争议修**（方向性决策点另列待用户逐项裁定）：ES `_id` 幂等键补 agent 维度（D16/§6.1/§7.1）；§4.2 删残留"只要接口为 LLM 相关即进入聚类候选"旧口径、统一 trace 内动态事实 + 缓存命中不回流出；quality 落库形态明确为 schema 事件字段、不新增事件不参与计数（§4.4）；verify_status 补 superseded；conversion_record 补 actor_user_id；trace 详情日志行分页懒加载 + error_type/error_msg 检索与时间窗（§8）；§16 修正 index 分离表述、回查不因归档跳过在途 case、补 needs_review 行；§5.1 本地兜底默认持久卷；上报鉴权对齐 Kafka-only（§12.1/§7.2/§14） |
| v3.4.4 | **7 个方向性决策点（第二轮复评去重后，编号 R1~R7）逐项裁定并修入**：R1 跨批 trace 累积态（§6.1 step4~step6：SSE/多批/子节点分批下"判定不缺完整 trace/分派/offset"均基于消费侧累积态，非单事件自判；§10.1 判定源同步）；R2 Agent 数据隔离**维持统一 viewer**（延续 §12.1"无 agent 级数据隔离"既有结论，本轮确认）；R3 上报通道访问控制**首版即上**（§17 #9 默认改 Kafka SASL/TLS + topic 级 ACL、每 agent 凭证映射 producer 身份，备选"内网信任后置"弃）；R4 人工"标记已修复"拆 **claim 认领中间态**（§7.2 error_cluster.status 增 claim；§10.4/§12.1/D11 先 claim 再置 fixed，置 fixed 需回归证据或 admin 复核、viewer 不单方 closed，审计可 reopen；聚类页筛选与人工操作入口补 claim）；R5 回归回查契约**本轮落定边界**（§10.5/§10.3/§11：case 建时记触发 agent 版本 → 按版本锚定对应回归 run 判单错，不取最新 run；回归 run 与 manual 共存、不占互斥槽、不参与 max_active_runs；新增 quality 判分回写 bullet——verifier 结果回写 run_results.pass_fail 使单错级回查覆盖 quality 型 L3）；R6 L1 error 用例补**兜底断言**（§10.3/§11 #3/#4：判"接口无技术错误 + 未落入兜底/低置信"才生成 error 用例，且 error 用例技术跑通后 offline 补判 no_fallback，防 catch 硬错转兜底话术返回 200 假绿过门禁）；R7 指标 7d 小时级 rollup **提前到 v1**（§7.1/§9.2 双路：1h/24h 实时 agg + 7d 查 `obs-metrics-rollup`；§17 #8 默认改 rollup v1、§16 容量行同步） |
| v3.4.5 | 吸收**第三轮六方向全量独立评审**（逻辑/数据流、安全、性能、异常容错、易用性、offline 对接；均无致命）+ **7 项方向性裁定**：①R5 回查锚定改 claim.fix_version（§10.5/§7.2/§11；事件 schema 与 SDK 补 `agent_version` 打点、trigger_version 仅溯源、fix_version 无对应 run → pending，防按触发版本恒取空）；②R1 累积缓冲重建改判定态持久化（§6.1/§10.1/§6.2：判定态与水位落 MySQL、重平衡重建不回读 ES、残 trace 按子节点判定）；③L2 门控补 OR（§4.3/§10.1：trace 动态事实 或 字典 llm=true，修复首次 llm_call 前程序错误盲区；L1/L3 仍纯动态事实）；④§17 #12 改回归 run 独立保留档（cleanup 删 run 不删 case、原描述失准改写）；⑤L3 subtype 分叉双判据（§11 #4/§10.3：low_confidence 独立判据、judge na→inconclusive）；⑥§17 #11 admin-only + 自动补标观察窗；⑦input PII 正文同级约束（§4.6/D13/§16）。无争议修：claim 生命周期状态机 + 状态×动作矩阵 + closed_by（§10.4/§12.1）；R3 broker 前置项（§12）；rollup 运行机制小节（§7.1）；error_cluster 唯一索引含 generation（§7.2/§10.2）；日志行占 seq（§4.1）；superseded 保留 passed 终态（§10.2/§10.5）；offline 契约措辞（verifier 期覆盖 error-only、eval_result 复用既有列、run_results 精确化，§11）；§17 表状态列；**补充裁定（offline 确认 gate，激活全归 offline）**：回归用例一律 draft 推送，online 不设测试集人工/激活（仅去重 + 幂等 + 质量下限自校验），error 型 offline 自动化激活、quality 型 offline 人工确认（通过→active / 驳回→删 case + 回写 invalidated 可 reopen）；draft 未确认期 link 标"待 offline 确认" verify pending；error 收单即结构自检激活、quality 驳回软删 rejected、TTL 告警归 offline owner（§7.2/§10.3/§10.5/§11 #5/§11 补强/§12.1/§16） |

> 待办（Task #4）：online 方案定稿后，单独推进 offline 配套改造方案（§11 依赖清单为输入），独立方案文档 + 独立评审。
