# agent-evaluation-online 线上观测平台 技术方案

> 版本：v3.4.1（待评审）
> 定位：**平台定标准，agent 适配**。观测平台是规则制定者，4 个现有 agent（good-question / customer-service / contract-check / smart-procurement）及未来接入 agent，一律按本平台统一规范整改接入。
> v3 变更：吸收独立架构评审意见（锚点与异常判定模型、接口字典来源、回归隔离面、offline 配套细项）+ 4 项方向决策（兜底归属 L3 / cc 第一版不回流 / 正文默认关逐 agent 评估 / L3 offline 自动化判分）。
> v3.1 变更：修订第二轮变更增量评审问题——§11 回归状态机按 case_type 分叉（error-only 不进 SCORING / 含 quality 必须进 SCORING）、L3 offline 判分穿透面与 no_fallback 达标线（防假绿）、seq 幂等回退 trace 级全局单调（branch 仅标注）、L1/L2 catch 转抛边界、llm_call 逻辑调用与重试自愈不出回流、L3 去重伪分类、看板 quality 出口、sp structlog 落地约束。
> v3.2 变更：补充 §12.1 前端页面体系——浏览器层角色（viewer/admin）→ 菜单树 → 页面清单与功能点 → 权限/归属阶段映射，与 §12 三域隔离、D11 研发人工操作口径对齐。
> v3.3 变更：针对自估 3 个最薄弱点的修正——(a) §11 #3/#4 回归 quality 判分改**独立判定器路径**（不借道 SCORING/score_run、不进 agent_score，规避 offline 闭集合穿透）；(b) §10.1 LLM 判定改 **trace 内动态事实**（llm_call/llm_* error/quality），`interface.llm` 标记退化为看板分类 + 自动补标 + 疑似漏标告警；(c) §10.3/§5.1 复现门槛**按层差异化**（error 用例不依赖会话历史）+ SDK 增 `record_session_state()` 状态快照钩子。
> v3.4 变更：§13 重构为「agent 接入与统一整改」——新增 §13.0 **通用接入方案**（面向任何 agent、语言中立：接入前契约核对（Step 0 盘点）→ 三步接入（Step 1~3）→ 接入验收 checklist；非 Python/Serverless 走事件协议直发），存量 4 agent 整改清单保留为 §13.1。
> v3.4.1 变更：吸收 §13.0 独立变更增量评审（无致命）——checklist 拆「放量门禁/维度 3 开放验收」两档（M1）；collector 明确为非首版能力并登记 §14（M2）；Step 0 盘点补接口枚举方式、后台任务型对齐 D18（M3）；§13.1 #1 补 sp `request_id` 规约、§5.1 rewrite 禁用口径单源、db/redis 建议口径、Step 2.4 存量 gq/cs/sp 例外、§10.1 引用修正（N1~N4）。

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
| D5 | 观测接口范围 | **全接口观测**（不区分 llm 标记）；接口字典 **online 自发现**——源为 agent **真实路由**（FastAPI 路由/OpenAPI），**与 offline 评测 manifest 解耦**；`llm` 标记仅用于**看板分类**（自动补标：窗口内观测到 llm_call → 置 llm=true 待确认；疑似漏标告警）；**回流 LLM 判定以 trace 内动态事实为准，不依赖该标记** |
| D6 | 链路覆盖 | request 为 HTTP 指标锚点根节点；子节点打 llm_call / tool_call / retrieve / **db / redis** |
| D7 | 回流分层 | **L1 透传型 LLM/接口硬错误** / **L2 LLM 相关接口的程序错误** / **L3 兜底与低置信（quality 信号）**；LLM 调用失败被兜底吸收、请求仍 ok → **归 L3**，不归 L1 |
| D8 | quality 信号 | agent 在兜底/低置信分支显式上报；平台关键词兜底为辅 |
| D9 | 回流输入范围 | 文本 / 对话（input_turns）双通道可回流；**文件型输入第一版不回流**；L1/L2 error 用例复现**不依赖会话历史**（C1）；会话型 quality 用例采集**状态相关快照**（session_state 钩子，C2）辅助复现 |
| D10 | 去重 | 键 = agent + interface + error_type 分类 + input_hash；时间窗口聚类合并；**不带 agent 版本**；per-trace 归并、分层优先 |
| D11 | 人工确认 | **轻量版**：自动生成 + 去重，回流看板可人工 invalidate/ignore/标记已修复；不引入审批工作流 |
| D12 | 鉴权 | **三域隔离**：平台用户（viewer/admin）、agent 上报凭证、online↔offline 平台间服务凭证 |
| D13 | 脱敏 | 键级掩码复用 offline `mask_dict` 规则集提升为标准，**SDK 侧完成，平台不还原**；**内容型 PII 依赖采集策略（正文默认关 + 最小化）控制，不以键级掩码为底线** |
| D14 | 正文存储 | 回复正文保存进 ES（支持 traceId/关键字检索）；**默认关，按接口逐 agent 评估数据属性后开**；带开关/截断/权限/保留期 |
| D15 | 日志查询 / 指标口径 | 查询页 traceId 与关键字**自由输入、可都输可任一**；p95/p99 **正常显示，不考虑样本 <30** |
| D16 | 数据层 | **Elasticsearch 8.x 单节点**为主（事件+日志，ILM 30 天自动删，index 按周滚动，`_id=hash(trace_id+seq)` 幂等）；MySQL 只放平台元数据；指标用 ES agg |
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

- 日志行（event_kind=log）与节点事件同链路、都带 trace_id。
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
- **异常判定 / 回流聚类是 trace 级聚合**，不依赖 `request.status` 单点：该 trace 内任一 `llm_call`/`db`/`redis` 子节点 `status∈{error,timeout}`、或 `request` 自身 error、或 `quality` 信号，只要接口为 LLM 相关，即进入聚类候选。适配"LLM 调用失败被兜底吸收、请求仍 ok"的结构（归 L3，见 4.3/4.4）。
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

> 回流只针对 LLM 相关接口（`interface.llm=true`，login 等非 LLM 接口出指标不出回流）。判定规则优先、不依赖 LLM 分类器；LLM 分类器仅作 P2 兜底。

### 4.4 quality 信号（L3）

agent 在自身「兜底/低置信」业务分支显式调用 `sdk.record_quality(trace_id, level, reason)`：
- `level=fallback`：LLM 失败后降级兜底，或知识库未命中降级答复；
- `level=low_confidence`：检索未命中/置信度低仍硬答。

平台侧辅以**兜底话术关键词库**（dict_config，可维护）兜底识别，主判 agent 显式上报。SDK 自动判定兜底不靠谱，以 agent 插桩为准（4 agent 统一整改项）。

### 4.5 脱敏规范（键级掩码，SDK 侧完成）

复用 offline `mask_dict` 规则集提升为平台标准：

```
_SENSITIVE_KEY = authorization | token | password | secret | api[_-]?key
                | fernet | credential | auth_config | (白名单扩展)
```

- SDK 序列化前对 input/output/extra/log_message 递归掩码敏感键 → `***`；平台消费侧脱敏复核（命中未脱敏敏感键 → 打回/丢弃并告警）；平台不存还原逻辑。
- **边界（修正）**：键级掩码 ≠ 内容级脱敏。订单地址、合同全文、身份证号等**内容型 PII 不在键级掩码能力内**，由采集策略控制：正文默认关（D14）、事件 input/output 的最小化采集、角色权限与 30 天保留期。不以键级掩码作为内容安全的唯一底线。

### 4.6 回复正文采集（D14，默认关）

回复正文（含 LLM 生成的答复内容）脱敏后存 ES，供 traceId/关键字检索还原"当时 LLM 如何答复"。控制点：

| 控制点 | 规则 |
|---|---|
| 开关 | **默认关**；需要正文的接口（优先 llm=true 对话类）**逐个评估数据属性后开**，落库前做内容型检测/最小化 |
| 截断 | 单条 ≤ 8K 字符 |
| 权限 | 查看正文需该 agent viewer 及以上角色（§12） |
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
- **trace 上下文**：contextvar 承载 trace_id、全局单调 seq（原子递增）、branch（并行分支标注）；日志 handler 自动注入。
- **可靠性与降级**：内存队列 + 批量（≤500 条 / ≤2s 冲刷）+ 失败退避（≤3 次）→ 本地磁盘兜底（`/tmp/obs_buffer`）→ 恢复补传；**平台/Kafka 故障绝不影响 agent 业务**。
- **会话状态钩子（可选，会话型 agent）**：`record_session_state(trace_id, state)` 采集影响后续判断的状态快照（检索命中文档 id、用户已确认/否决的约束、累计轮数），供 L3 会话型用例重建会话（§10.3 C2）。
- **自监控**：SDK 上报成功率/丢弃量作为平台自身可观测信号。

### 5.2 传输（Kafka）

- 每 agent 一个 `obs.agent.<name>` topic，`partition=1`（同 trace 近似保序，消费简单）。
- SDK 内 kafka-python producer；消息为单条 JSON 事件（schema §4.1），消息内带 `agent` 供消费侧双重校验。

---

## 六、消费与处理

### 6.1 消费 worker（online 侧）

1. 订阅 `obs.agent.*`，批量拉取；
2. **校验**：schema 强校验、必填字段、`ts` 水位防乱序、interface 与字典匹配（不匹配 → 自动注册 + 待人工补 llm 标记）、agent 标识与 topic 一致；
3. **脱敏复核**（§4.5）；
4. **分派入库 ES**（event_kind 分流；`_id = sha256(trace_id|seq)`，seq 全局唯一 → 重复投递覆盖）；
5. offset 管理；失败重试队列，超阈值丢弃并计数。

### 6.2 幂等与顺序

- **seq 语义（v3.1 回退 trace 级全局单调）**：`seq` = trace 内 contextvar 原子递增的全局单调序号（根 request=0），全 trace 唯一；`branch` 仅作文本标注，**不入幂等键与引用**——避免 per-parent 自增导致的嵌套/递归重复 seq 与 `parent` 引用歧义（并行先后按 `(ts, seq)` 排序还原）。
- ES `_id` 幂等吸收 Kafka at-least-once 重复投递；
- **顺序还原**：partition=1 保证相对有序；链路树按 `(ts, parent, seq)` 还原，`parent` 指向全局唯一 seq 无歧义。

---

## 七、数据层（D16）

### 7.1 Elasticsearch

| 项 | 规划 |
|---|---|
| 集群 | 8.x 单节点（内部环境，独立部署，与 offline 无关） |
| Index | 按周滚动 `obs-event-yyyyWW` / `obs-log-yyyyWW`（第一版单 index、doc 带 event_kind 亦可，按容量定） |
| ILM | 30 天自动删除；正文保留期同 ILM |
| 幂等 | `_id = sha256(trace_id\|seq)`（seq 全局唯一） |
| 映射 | trace_id/agent/interface/node(keyword)、ts(date)、duration_ms(long)、status、error_type、quality、input/output/log_message(text 中文分词)、usage(object)、session_ctx(text 截断) |
| 容量 | 内部环境 4 agent 峰值 ≤500 事件/s + 日志同量级，周滚动 index 远低于单节点压力 |
| 指标 | 直接 ES agg：date_histogram × percentiles(p50/95/99) × filter(error/timeout)，近实时（<5s），不落分钟预聚合 |

### 7.2 MySQL（平台元数据，库 `obs`）

| 表 | 用途 |
|---|---|
| `user` / `role` / 会话 | 平台账号（独立体系，§12） |
| `agent` | 自发现注册（name、base_url、enable、**路由来源标记**） |
| `interface` | 接口字典缓存（agent_id、归一化 interface、**llm 标记（配置驱动+人工补标）**） |
| `error_cluster` | 错误聚类（error_type、input_hash、首次/最近 ts、次数、状态 open/fixed/inactive） |
| `error_case_link` | 错误 ↔ offline 回归用例关联（case_id、case_type、verify_status） |
| `conversion_record` | 回流审计（trace→case、action、detail、ts） |
| `agent_credential` | agent 上报凭证 |
| `dict_config` | 平台配置（兜底话术库、超时阈值、正文开关白名单、会话上下文轮数、聚类窗口等） |

### 7.3 保留策略

- ES 事件/日志/正文：ILM 30 天自动删（第一版不冷存）。
- MySQL 元数据（聚类/回流/字典）：长期保留（"已复验"是长期业务事实，供闭环与审计）。

---

## 八、维度 1：traceId 链路日志查询（D15）

**能力：** 查询页可自由输入 traceId 和/或关键字（可都输入、可任一）。
- **traceId 查询**：返回该 trace 全部事件（`(ts,parent,seq)` 树排序，branch 仅标注）→ 前端时间轴（request 根 + 子节点），异常节点红显，日志行穿插，详情含脱敏后堆栈/正文。
- **关键字查询**：全文检索 input/output/log_message → 命中 trace 列表 → 进入 trace 视图。
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

前端选 agent + 接口 + 时间窗 → `GET /api/v1/metrics` → ES agg（date_histogram + percentiles + filter）。近实时，不落预聚合。

### 9.3 看板视图

Agent 概览卡（QPS、P50/P95/P99、失败率、超时率、趋势 1h/24h/7d）→ 接口明细（全接口 + 双指标 tab）→ 异常聚焦（失败/超时排序 → 异常列表 → trace 视图联动）→ **L3 质量出口**（quality 事件计数 + fallback/low_confidence 占比，接口维度；P1 提供——否则兜底劣化在 status=ok 下研发不可见）。

---

## 十、维度 3：异常回流（三层模型，核心业务）

### 10.1 分层与判定（D7）

| 层 | 定义 | 判定来源 | offline 复验目标 |
|---|---|---|---|
| L1 | LLM 硬错误**透传**到接口（request 直接 error） | trace 内 request `error_type ∈ llm_*` | 接口不再报该错误 |
| L2 | LLM 相关接口的程序错误（接口直接 error） | trace 内 request / 子节点 `error_type ∈ {llm_interface_business, external_non_llm, db_error, redis_error}` 且接口 llm=true | 接口不再报该错误 |
| L3 | LLM 失败被兜底吸收 / 低置信硬答（请求仍 ok） | `quality.level ∈ {fallback, low_confidence}`（agent 插桩为主 + 关键词兜底） | 不再兜底/低置信 |

- **异常判定 = trace 级聚合**（§4.2）：子节点 error 或 quality 与 request 是否 error 无关，都能进入聚类。request 级 status 只服务维度 2 指标。
- **自愈不出回流**：子节点 error 但 request ok 且无 quality（如 LLM 退避重试最终成功）→ 不进入回流候选（§4.2 重试自愈口径）。
- **LLM 判定 = trace 内动态事实（v3.3 修正）**：trace 内出现 `llm_call` 子节点 / `llm_*` 错误 / quality 信号即视为 LLM 相关，**不依赖 `interface.llm` 人工标记**；该标记退化为看板分类——平台自动补标（窗口内观测到 llm_call 的接口 → 置 llm=true 待确认）+ **疑似漏标告警**（llm=false 却观测到 llm_call，§12.1 Agent 管理）。
- 回流前置：agent ∈ 白名单（gq/cs/sp，硬排除 cc）+ 该 trace 内 LLM 事实成立；login 等非 LLM 接口出指标不出回流。
- 范围：**gq / cs / sp**（D18，cc 不纳入维度 3）。

### 10.2 聚类与去重（D10）

**去重键：** `agent + interface + error_type 分类 + input_hash`
- `input_hash = sha256(normalize(input))`；normalize = strip + 折叠空白 + 截断 4096 字符；对话型取 input_turns + 会话上下文摘要归一。
- **L3 去重键用伪分类**：L3 是 quality 信号非 error_type，键内 `error_type 分类` 映射为 `quality/fallback`、`quality/low_confidence`，不与 error 类空串混键、两类互不合并。
- **per-trace 归并**：同一 trace 多异常（如 LLM error + 兜底）按**分层优先 L1/L2 > L3** 归并为一次候选；**已知取舍（明示）**：同 trace 含 L1/L2 时该 trace 的 L3 现场被吞并、不单独生成回归用例（回归重点是其硬错误）；纯 L3 现场（无 error）独立生成。
- **聚类窗口**：同键在窗口（默认 7 天）内持续出现 → 合并为一个 `error_cluster`；窗口内无新出现 → 转 open 保留待复验。
- **去重**：`error_case_link` 处于 open/待复验 → 只计数不重复生成；被 invalidate/标记已修复 → 允许重新生成（旧记录 superseded）。
- **不带版本**：同错误跨版本持续存在直到修复。

### 10.3 回归用例生成（D9）

worker 按聚类生成回归用例，映射 offline（`agent+interface → offline agent_id+interface_id` 配置驱动）：

| 层 | case_type | input | 判定方式 |
|---|---|---|---|
| L1 | `regression_error` | 出错请求 input（脱敏，含会话上下文摘要） | offline 判"接口无技术错误" |
| L2 | `regression_error` | 同上 | 同上 |
| L3 | `regression_quality` | 兜底/低置信现场 input | offline **无 golden 语义判分通道**判"不再兜底/低置信"（§11） |

- **复现门槛按层差异化（C1）**：L1/L2 error 用例用现场 input 直接复现（技术错误与历史会话基本无关），**不依赖会话重建**；仅 L3 quality 用例与强依赖历史语义的错误需要会话上下文。
- **会话重建（C2）**：会话型接口（cs/gq）经 SDK `record_session_state()` 采集**状态相关快照**（检索命中文档 id、用户已确认/否决的约束、累计轮数等影响后续判断的状态事实）重建会话，较逐字 N 轮更精准省；快照不足以复现 → cluster 标 `needs_review` 交人工，不自动转（防失真绿）。
- **文件型输入**（cc）第一版不回流（D9），cluster 标 `needs_review`。
- 调 offline 建 case + 补激活（§11 #5），写 `error_case_link` + `conversion_record`；offline 不可用 → 重试队列。

### 10.4 人工确认（轻量版，D11）

每条 `error_cluster` 可 ignore（inactive）、标记已修复（人工确认，跳过回归）、查看已生成用例与复验状态。自动生成默认开启。

### 10.5 offline 复验闭环

```
研发修复 → offline 触发该 agent regression run（绑定待发布版本）→ 全绿
  → online 回查 error_case_link.verify_status=passed → error_cluster 标 fixed（闭环）
回归未通过（仍 error / 仍兜底）→ verify_status=failed，错误保持 open
  → 聚类窗口内同类新错误并入该 cluster，不再生成新用例
```

- `verify_status ∈ {pending, passed, failed, invalidated}`。
- 修复后又复发 → 新 cluster 重新生成。
- **闭环归属（边界）**：回归 run 的触发、版本绑定、与发布流程的门禁集成在 **offline 侧**（§11 #7，offline 改造方案范围）；online 负责生成用例集、回查 verify_status、展示回流看板。online 侧 P2 回流看板提供"该 agent 当前 open 错误数 + 关联回归用例/复验状态"总览。

---

## 十一、offline 平台配套改造（D17，独立清单，随 P2 排期）

> 与 §10 闭环的 offline 侧能力：引入**回归评测模式**与**回归复验硬门禁**——发布门禁由一道（质量分达标）变为**两道并列**（质量分达标 + 回归复验全绿），都是硬 gate。此清单是 online 对 offline 的**能力依赖/边界契约**；落地细节由 offline 侧独立方案承担（独立评审）。

| # | 改造项 | 说明 |
|---|---|---|
| 1 | `EvalRun.trigger_type` 加 `"regression"` | MySQL ENUM + Alembic；`RunCreate.trigger_type` Literal 同步扩；回归 run 与 manual/held_out 平行 |
| 2 | `TestCase.case_type` 加 `regression_error / regression_quality` | 标识来源与语义；online 生成的用例打标，名称/元数据带 `source` 溯源（可回溯 online trace） |
| 3 | 回归评测语义 + 状态机 | **executor**：regression_error 判技术错误（报错/超时→error，跑通→pass），不进 LLM-judge/score_case；**orchestrator 按用例构成分叉（v3.3 采用独立 verifier，不借道 SCORING）**：① 仅含 regression_error 的 run → 全技术通过即终态绿 / 任一 error→红，**不落 SCORING、不产 agent_score**（现有"全 pass→SCORING→score_run"需按 trigger_type 分支）；② 含 regression_quality 的 run → error 用例由 executor 技术判定后，orchestrator **直接触发独立回归 verifier**（#4）完成 quality 判分，不依赖 scoring 态；run 绿 = error 用例全技术通过 ∧ quality 用例全达标 |
| 4 | **L3 无 golden 语义判分通道（独立判定器，v3.3 首选）** | offline 为回归 quality 判分开**独立 `regression_verifier`**（首选路径，避开常规评测链路）：对 quality 用例直接调 judge client 做无 golden 判分（judge `build_messages` 在无 golden + 无 reference 时可用、不空标签误导），结果单落（eval_result 独立字段/表），**不进 agent_score / score_per_dimension / 常规门禁聚合**——offline 常规评测零污染，**规避 SEMANTIC_DIMENSIONS / metrics 插件注册 / metric_def / dimension.code 等闭集合穿透**。仍需：新增 `no_fallback` rubric（judge 判"是否仍兜底"）+ **必配达标线**（无 target 时门禁缺省全 pass=假绿；按 agent 配 baseline_target 或独立规则）。**备选路径**（不用 verifier 时）：走现有维度体系，则须穿透上述闭集合。横切约束：现有维度判分依赖 golden 基准，无 golden 时 judge 无基准乱判（并非默认 na）→ **regression_error 在任何判分路径下都须按 case_type 跳过 judge 任务** |
| 5 | 装载/激活改造 | run 创建校验与 `case_loader` 加 **case_type 谓词**（普通 run 排除 regression 用例、regression run 只装载对应 case_type；现谓词仅 `status=active + is_held_out`）；online 建 case 后补**激活**（`PUT /cases/{id}` status=active，现 create_case 默认 draft，不激活跑不了 run）；明确 regression 用例归属独立 suite |
| 6 | 看板隔离（**8 处**） | dashboard.py 的 `EvalRun.trigger_type != "held_out"` 实为 8 处（L43/60/85/87/139/174/196/254，compare 为双查询）→ 常规聚合全部加排除 regression；全仓核对 `==/!= "held_out"` 两类语义：**防污染排除**（加排除 regression）vs **held_out owner 隐藏**（保持 manual 语义，不套用 regression） |
| 7 | **回归复验区块（硬门禁展示）** | gate 墙旁按 agent 显示最近回归 run：版本/触发时间/error 回归 M/N + quality 回归 K/L + 结论绿/红 + 未通过错误源列表；评测记录列表加"回归"标签 + trigger_type 筛选 |
| 8 | 权限 | 回归 run/case 语义同 manual（Staff 可见）；不套 held_out 的裁剪/隐藏逻辑 |
| 9 | 触发与版本绑定 | 回归 run 触发、版本绑定、发布门禁集成由 offline 侧定义（offline 改造方案范围）；online 依赖：建回归用例、回查 verify_status |

> offline 改动集中在 runner（executor/orchestrator/case_loader/scorer）/ judge（rubric）/ **verifier（新增独立回归判定器，v3.3 首选——据此避免改动 SEMANTIC_DIMENSIONS / metrics 注册 / dimension.code，但 eval_result 需加字段承载 verifier 判分）** / dashboard。run/result 表不加列（PASS_FAIL 四态已承载），TestCase/EvalRun 各加一个枚举/标记字段。此项单独出方案、单独评审（Task #4）。

---

## 十二、鉴权与权限（D12，三域隔离）

| 域 | 主体 | 机制 |
|---|---|---|
| 平台用户 | 观测平台登录（React） | 独立账号体系（JWT），viewer/admin；viewer 观测/回流**查看** + 回流**人工操作**（D11 研发闭环），admin 另管 agent/接口字典/配置/用户/正文开关 |
| agent 上报 | obs-sdk → online | 每 agent 一对平台 token（`agent_credential`），请求级鉴权 |
| 平台间 | online → offline | offline 专用服务账号（evaluator 角色）+ 独立凭证，最小 API 面 |

正文查看需该 agent viewer 及以上（§4.6）；脱敏底线见 §4.5。

### 12.1 前端页面体系（浏览器层：角色 / 菜单 / 页面 / 功能点）

**浏览器登录角色**（独立账号体系；agent 上报凭证、online↔offline 服务凭证不进浏览器）：

| 角色 | 定位 | 权限范围 |
|---|---|---|
| viewer | 研发/负责人（排障与观测闭环） | 三个维度页面**查看** + 回流看板**人工操作**（ignore / 标记已修复 / needs_review 处置，D11 研发闭环入口）+ 正文查看 |
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
| 回流-错误聚类（/backflow） | cluster 列表/筛选（agent、接口、层、状态 open/fixed/inactive/needs_review）；代表 trace 与 input_hash；去重与生成计数；复验总览（open 错误数 + 关联回归用例 verify 分布） | viewer 查看 | P2 |
| 回流-聚类详情 | 关联回归用例（case_id/case_type/verify_status、`source` 溯源）；conversion_record 审计时间线；**人工操作**：ignore、标记已修复、needs_review 人工处置 | viewer 可操作 | P2 |
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

> 分两档：#1/#2/#3/#6/#7 = **放量门禁**（维度 1/2 达标，任何 agent 放量前必过；#3 llm_call 覆盖同时支撑维度 2 的 LLM 级双指标）；#4/#5/#8 = **维度 3 开放验收**，仅对申请/已开放维度 3 白名单的 agent 生效（作为 Step 2.4 加入白名单的前提），不入放量门禁。

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
│   │   ├── api/            # ingest / logs / metrics / clusters / auth / agents(字典)
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
| 正文/内容型 PII 泄漏 | 中 | 正文默认关 + 内容型最小化/检测 + 角色权限 + 30 天保留（§4.6） |
| agent 埋点口径不一致 | 中 | 契约强校验 + 双日志接入 + 第二通道打点清单 + 冒烟用例 |
| offline 不可用 | 低 | 回归生成重试队列；不影响指标与链路 |
| 回归隔离遗漏污染常规门禁 | 高（offline） | §11 #6 真实 8 处排除 + case_type 谓词 + 状态机分支；offline 方案自审 checklist 全仓核对 `== "held_out"` |
| 指标口径漂移 | 中 | 双指标口径文档 + 统一 agg + 归一化路径一致 + 超时口径单源（agent SDK 打标） |

---

## 十七、待评审确认的残留默认值

| # | 项 | 默认值 | 备选 |
|---|---|---|---|
| 1 | ES index 分合 | 事件+日志单 index（doc 带 event_kind） | 拆分两类 |
| 2 | 正文截断 | ≤8K 字符/条 | 可配 |
| 3 | 会话复现上下文 | 状态快照（session_state 钩子）为主 + 最近 N 轮消息兜底（N 默认 10） | 按 agent 可配 |
| 4 | 超时判定 | agent SDK 按接入约定阈值打标（平台不二次判） | 平台统一下发 |
| 5 | 错误聚类窗口 | 7 天 | 可配 |
| 6 | 接口 `llm` 标记 | 配置驱动 + 人工补标 | 从 agent 元数据推断 |
| 7 | 平台账号 | 独立体系（首 admin 初始化） | 复用 offline 账号 |

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

> 待办（Task #4）：online 方案定稿后，单独推进 offline 配套改造方案（§11 依赖清单为输入），独立方案文档 + 独立评审。
