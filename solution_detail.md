# agent-evaluation-online 线上观测平台 — 开发前详细设计（solution_detail）

> 基线：`solution.md` **v3.5.1**（error-only 一期定稿；v3.5.0 六方向复评修入）。
> 本文件把 v3.5.1 方案落到「可直接指导开发」的粒度：**字段级 schema、DDL、API 契约、状态机矩阵、时序、页面功能点、接入与验收用例**。
> 文档关系：**`solution.md` 是权威（定标准、定边界、定口径）；本文件是实现基线（定字段、定接口、定实现顺序）**。两者冲突时以 `solution.md` 为准，并把冲突点记录到 solution.md §17 / 本文件 §12.2。
> 修订记录：2026-09-03 **v1.1（六方向独立评审修入）**——判定执行方裁定（judge_scan_job）、现行 link 唯一键语义（cur_key 生成列）、公共 infra 故障降级与 `{env}.` 租户命名、平台间 ack 前置矩阵与 requeue 游标、全站实时护栏默认值（O-1 裁定）、引用清理；其余见 §12.2 与文内标注。

---

## 0. 范围与一致性规约

### 0.1 本次开发范围（锁定，来自 v3.5.1）

| 面 | 范围 | 落点 |
|---|---|---|
| online 平台 | FastAPI backend + React frontend 完整实现细节 | 本文件全章 |
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
| 前端 | React（SPA，只经 backend API） | 无直连 ES/MySQL |
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
├── frontend/                     # React：页面与路由规格见 §9.2（菜单/数据源）
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
| needs_review | v1 仅「claim 回归 infra-error 无法判定」边缘触发；常态触发源（快照不足/判分 na）均为二期/D18 不回流 |

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
| `status` | enum | ✅ | `ok/error/timeout` 三态互斥；timeout 由 SDK 按接入约定阈值打标（§12.4），平台不二次判 |
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
| 4 trace 累积态 | per-trace 累积缓冲更新 + 落 MySQL 判定态表（表 `trace_judge_state`，§5.1⑩）：root 到达 / 子节点 error 汇入两态迁移；**判定不在本步执行**（judge_scan_job 到期判，§4.3） | **写失败 → 不提交 offset + 退避重试 + 自监控计数**；禁止"丢弃并提交"（丢判定态=该 trace 永不回流且 offset 已推进不可找回，§14.2） |
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
| 子节点 error 汇总 | `err_summary_json`（error_type 分类计数、error_msg 脱敏、agent_version） | 每个 error 子节点到达更新 |
| root 是否到达 | `root_ok` | `node=request` 到达置 1（记 request ts/interface/status/input_hash） |
| 是否已判定 | `judged` | L1/L2 判定 + per-trace 归并完成后置 1（判 false 不再重复判定） |
| 完成窗口 | `ttl_until` | = 最后事件 ts + 完成窗口 + 宽限（【实现约定】窗口 60s + 宽限 300s，§6.1）；过期行惰性清理 |

**判定时机**：
1. root 到达且 trace 判定未做 → 等窗口内补采迟到的子节点（SSE/多批）：root 到达即标记可判定，待窗口闭合后判定；
2. **残 trace（root 未到达但已有子节点 error）不悬挂等待**——按已有子节点判定（防超长 SSE 连接长期不闭合导致漏判；§4.3 规则与 §6.1 判定共用）；
3. `judged=1` 后判定产出进聚类（§4.4），处理完置 `processed=1`，防止重放重复进聚类（judged/processed 分离，见 §4.1 step4/§5.1⑩）。

**判定执行方（v1.1 裁定）**：consumer/step4 只更新累积态与 `ttl_until`，**不做判定**。到期判定由 `judge_scan_job`（worker，周期 1min，§1.2/§1.3）扫 `judged=0 AND ttl_until≤now()` → classify（§6.1）→ 写 `judgement_json`+`judged=1`，随后进聚类（§4.4 置 processed）。残 trace/root 未达同规则，`ttl_until` 以最后子节点事件 ts 起算（§5.1⑩ idx_judge_scan 定位）；`judged=1` 后重复到期不重判。judge_scan_job 顺带清理 `processed=1` 且超 `trace_judge_purge_days`（默认 7 天，§10.1）的过期判定行——判定态只在完成窗口+清理保留期内停留，不膨胀。

**判定输出（classify.py → §6.1）**：trace 层一次产出 `{agent, interface, root_status, root_error_type, err_summary, llm_fact_ok, layer(L1/L2/none), candidate_error_sets[]}`，per-trace 归并后交给聚类（§6.2）。quality 信号二期才入累积态（v1 不采集，§2.8）。

### 4.4 幂等与位点（表 `trace_judge_state` §5.1⑩ + §6.2 唯一索引兜底）

- MySQL 侧幂等三件套：`trace_judge_state`（已判定集合）+ `error_cluster` 唯一索引（agent+去重键+generation，§6.2）+ `error_case_link` 幂等键（`payload_id`，§6.3 step4）。
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
  input_hash    CHAR(64)     NOT NULL,               -- sha256(normalize(input))，normalize=strip+折叠空白+截断4096
  input_snapshot MEDIUMTEXT   NULL,                  -- 代表事件 input 实文（脱敏+截断≤8K，v3.5.1 扩存；组装取数源，不依赖 ES 回读）
  error_msg     VARCHAR(512) NOT NULL,               -- 脱敏错误摘要
  first_trace_id VARCHAR(64) NOT NULL,
  trigger_version VARCHAR(64) NULL,                  -- 首现 agent_version（仅溯源）
  first_ts      DATETIME(3)  NOT NULL,
  latest_ts     DATETIME(3)  NOT NULL,
  count         INT NOT NULL DEFAULT 1,              -- 7d 窗口内同键合并计数
  generation    INT NOT NULL DEFAULT 1,              -- 生命周期代数（复发/重开 +1）
  status        ENUM('open','claim','fixed','inactive','needs_review') NOT NULL DEFAULT 'open',
  fix_version   VARCHAR(64) NULL,                    -- claim 时填写（R5 回查锚定版本）
  claimed_by    BIGINT UNSIGNED NULL,
  claimed_at    DATETIME(3) NULL,
  claim_due_ts  DATETIME(3) NULL,                    -- claim 复核窗 TTL（默认14d）
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
  case_pass     TINYINT NULL,                        -- 该 case 在 run_results 的 pass_fail（0/1；null=infra 无法判定）
  run_status    VARCHAR(16) NOT NULL,                -- offline run 终态（passed/failed/…）
  raw_json      JSON NULL,                           -- run_results 原样留档
  verified_ts   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_verify_run (link_id, run_id)
) COMMENT='回归 run 单错级结果（终态只读：已定 passed/failed/superseded 不被迟到 run 改写，见 §7.6）';

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
  root_input_hash CHAR(64) NULL,                     -- root request.input 的 HMAC 键（§6.1 L2 去重/§13.4）
  err_summary_json JSON NULL,                        -- 子节点 error 汇总（error_type 分类/error_msg/agent_version）
  llm_fact_ok   TINYINT NOT NULL DEFAULT 0,          -- trace 内出现 llm_call / llm_* error
  judged        TINYINT NOT NULL DEFAULT 0,          -- judge_scan_job classify 完成后置 1（判后不再重复判定）
  processed     TINYINT NOT NULL DEFAULT 0,          -- 判定产出进聚类处理完置 1（与 judged 分离，防重放重复进聚类，§4.4）
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
| 7d（>24h） | `obs-metrics-rollup` | 小时桶预聚合 + **尾小时实时补齐**（趋势不截断） |

**rollup index `obs-metrics-rollup`**（每小时 job 写，doc 维度 agent×interface×node×hour）：

| 字段 | 含义 |
|---|---|
| agent / interface / node（request·llm_call）/ model(null for request) | 分桶键 |
| hour | 小时（`yyyy-MM-ddTHH:00`） |
| total / error / timeout | status 互斥计数桶（usage 只在 llm_call 桶） |
| prompt_tokens / completion_tokens | llm_call 桶 token 汇总 |
| sketch | **t-digest 可合并分位草图**（序列化 base64 存 keyword）——跨小时可合并出 7d 单值 p50/95/99 |

**job 机制（rollup_job.py，APScheduler 同族每小时运行）**：
1. **首启回填**：历史已完成小时。
2. **迟到事件幂等重算**：事件晚到 ≤6h（`K` 默认 6）内重算对应小时桶（读-重算-原子替换，重叠不双计）；超窗迟到只进实时 agg，rollup 该小时明示缺口。
3. **失败降级**：记最近成功时间；7d 查询命中缺失/过期小时桶 → 该小时回退 ES 实时 agg + 页面标注"回退实时口径" + 自监控告警（对应 §16 rollup 行）。
4. **尾小时口径**：最后未完成小时不预聚合 → 实时 agg 补齐拼最后一段。

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
- **重试自愈已天然过滤**（SDK 逻辑调用最终成功 `status=ok`，§2.4）；兜底吸收现场（request ok + llm_call error）不产 L1/L2 候选（L3 二期）——但其 trace 本身仍可被维度 1 查询、其 llm_call error 仍进指标（§2.4 前提）。
- judge_scan_job 将判定产出写回 `trace_judge_state.judgement_json` + 置 `judged=1`；聚类消费后置 `processed=1`（judged/processed 分离，§4.3/§4.4），防重放重复进聚类。

### 6.2 聚类与去重（analyzer/cluster.py + worker/cluster_job.py）

**error 去重键（v1）**：`agent + interface + error_type 分类 + input_hash`
- `error_type 分类`：**不使用 error_type 原值**，按 §2.5 归类到 L1/L2 层语义键（`llm_timeout` 与 `llm_other` 是否合并？）——**【实现约定】按 §2.5 error_type 原值去重（不跨类合并）**，与 §6 复发检测/reentry 观察键（agent+interface+error_type+input_hash，§7.5）同源一致。
- `input_hash = sha256(normalize(input))`；normalize = strip + 折叠空白 + 截断 4096 字符；对话型取 input_turns（v1 无会话历史摘要，§2.8）。

**窗口与生命周期（对应 §10.2）**：

| 状态场景 | cluster 动作 | link 动作 |
|---|---|---|
| 同键首现 | 开 cluster（status=open，generation=1），落代表快照（input_snapshot 取该 trace request.input 脱敏截断 ≤8K；error_msg ≤512；first_trace_id；trigger_version） | 触发组装一次 → 建 link（§6.3） |
| 窗口（默认 7d）内同键新现 | 只 `count+1`、刷新 `latest_ts`；**不重生成**（link 已存在）——代表快照若缺 input 实文而新现含 request.input → 回填快照并按 §6.3 补组装一次（v3.5.1） | 不变 |
| 窗口内同键新现 但 link 已 invalidated（error 自检失败，§6.3） | 只 `count+1`（计数 = offline 重扫可重推恢复的信号）；**不自动重生成** | offline 重扫自愈或 admin 重推复位（§7.4） |
| 同键静默超窗口 | cluster → inactive（归档，保留 count/最近 ts/快照） | — |
| claim→fixed（回归证据或 admin 复核） | 旧 cluster 终态 fixed；旧 link superseded | 同键再现 → **新开 cluster generation+1**（不与已归档同键冲突，唯一索引含 generation，§5.1） |

**并发/幂等**：cluster 落库用唯一索引吸收同代并发首现双写；`judgement_json` 处理后置 `processed`，防止重放重复进聚类（§4.4）。

### 6.3 组装 D19 信封落库（converter + worker/assemble_job.py）

触发：cluster 首现开（§6.2）即自动组装一次（在线错误处置"自动生成默认开"）；组装失败/重试由 `assemble_job` 补偿扫描兜底（【实现约定】每分钟扫 open 且无现行 link 的 cluster）。

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

- pull-API 返回 assembled 按 `assembled_ts` 升序 + `next_token` 分页游标（§8.7）；offline 崩溃重拉以 `payload_id` upsert 幂等去重。**requeue 刷新 `assembled_ts=now()`**（§7.4），使重推案重新进入增量拉取范围——否则 offline 按 since/位置游标会跳过已读旧档。

### 7.3 平台间状态回写与回查（online 侧处理）

| 事件 | 方向 | 触发 | online 侧动作 |
|---|---|---|---|
| 拉取建 draft | offline→online | offline pull 到 payload、建 case 成功 | 回写 `offline_status=draft` + `case_id`（幂等：按 payload_id upsert；重复 ack 不报错） |
| 结构自检失败驳回 | offline→online | error draft 结构自检不通过 → rejected（携带 reason） | 回写 `offline_status=invalidated` + `invalidate_reason`；cluster 保持 open（可重推观察态，§6.2） |
| 激活 | offline→online | rejected 后 offline 重扫自检通过 / 收单即激活 | 回写 `offline_status=active` + `case_id`（复用 payload_id 幂等；**收单即激活也须带 case_id**，否则单错级回查断链，§7.6） |
| 人工 invalidate（online） | online 本地 | admin 对未激活 case（assembled/draft）判无效 | `offline_status=invalidated` + `conversion_record`；**active 后不走此路**（superseded+reopen，§7.6） |
| 回查 run_results | online→offline | cluster claim 后按 fix_version 轮询回归 run | 逐条判单错 → 写 `verify_run_record` + 更新 `verify_status`（§7.6 单错级回查） |

**ack 前置矩阵（v1.1）**：`draft` 要求当前 `offline_status=assembled`；`active` 要求 ∈{assembled,draft}（收单即激活）或对同一 payload 重复 ack（幂等）；`invalidated`（驳回）要求 ∈{assembled,draft} 且**必带结构化 reason**。前置不符 → `ERR_CLUSTER_0003`(400)/`ERR_PULL_0003`(404)；对**已知** payload_id 的重复 ack → 200 幂等成功。reason 码见 §7.4。

**offline 期望行为（Task #4 输入，online 侧依赖不变式）**：
1. pull 拉取后**不改写 case 内容**；发现内容缺口不就地编辑补全 → 驳回 rejected + 回写 invalidated，由 online 修正现场重推（§7.4）——防内容与线上现场漂移。
2. `list_runs` 需支持按 `agent + version + status` 过滤回归 run 且**按含 case_id 过滤**；`run_results` 返回 `case_id + case_type + pass_fail`。
3. 回归 run 不占互斥槽、不参与 max_active_runs；对回归 run 设独立保留档（pinned/豁免 cleanup），清理先归档 pass_fail 终态。
4. error-only run 的 `pass_fail` = executor 技术判定 ∧ verifier no_fallback 合成，由 verifier 阶段落终值（不经 SCORING、不产 agent_score）——online 回查对 error 生效依赖此语义。

### 7.4 invalidated / rejected 重推（自愈闭环，online 侧落点）

| 驳回来源 | 重推执行方 | online 侧动作 |
|---|---|---|
| offline 能力缺（adapter/判定器未注册等，reason 属 offline） | **offline 重扫自愈**：配置变更后周期重跑结构自检 → 通过回写 active（复用 payload_id） | 只被动收 `active` 回写；不设 online 时钟 |
| online 现场内容缺（payload 字段不全，reason 指明缺项） | online admin 在聚类详情「重新组装/重推」 | `requeue_job`：`invalidated → assembled` 复位（复用 payload_id + 重填 payload_json 修正现场）→ **刷新 `assembled_ts=now()`**（「已待 N 天」归零、增量拉取可见，§7.2）→ 重新进入 pull 范围；记 conversion_record（detail 含 reason 码） |

**requeue 守卫**：仅 `offline_status=invalidated` 且 cluster 未 inactive 可复位；复位不改 `verify_status`（保持 pending → 仍占现行位，§5.1 注）。防抖限流：同一 link 人工重推间隔 ≥【实现约定】5 分钟。

**invalidate reason 结构化码（驳回与人工统一）**：`offline_cap_gap`（offline adapter/判定器缺）→ 归 offline 重扫自愈（本表上行）；`online_content_gap`（payload 内容缺，reason 指明缺项）→ 归 online admin 重推（本表下行）；`manual_invalidate`（admin 人工判无效，可附补充理由）。code 随 §8.7 ack/聚类详情透出，前端按码出文案（§9.3）。

### 7.5 reentry：线上观察哨位（worker/reentry_job.py）

- 观察键 = error 去重键（agent+interface+error_type+input_hash，与 §6.2 同源）。
- 触发：cluster 已 claim/fixed 后，同键错误**线上再现**（judged 为 L1/L2 的新事件）。**版本门控（v1.1）**：仅当新现事件 `agent_version ≥ cluster.fix_version`（修复确已上线、回归有据）才开 reentry；修复上线中/未上线再现 → 只按 §6.2 窗口 `count+1`，不开新 cluster（防修复落地前反复抖 cluster、空转回归）。
- 动作：新开 cluster（generation 独立计数沿用 §6.2 复发规则）；`conversion_record(action=reentry, detail="线上仍复发，claim 或回归失守，请核对 fix_version 是否覆盖线上路径")`。offline 侧对应回到待修复集（Task #4）。
- online = 观察事实权威，offline = 验证事实权威；二者互不替代、互相反馈。

### 7.6 状态机矩阵与人工处置

**cluster.status × link 状态迁移总表**（CAS 条件更新，`WHERE status=期望旧值`）：

| 状态 | 触发 | 可迁移 | 约束 |
|---|---|---|---|
| `open` | 新候选 / 复发 / 归档反悔 | → claim / inactive / needs_review | 有现行 link 时同键只计数（§6.2） |
| `claim` | viewer 认领，**必填 fix_version** + 说明 | → fixed（auto_regression：该 fix_version 回归 run 中 case passed）/ fixed（admin_review）/ open（回归 failed 或 TTL 超窗回退）/ needs_review（回归 infra-error 无法判定） | TTL 复核窗口默认 14d；超窗自动回退 open 记 conversion_record（`claim_ttl_job` 执行，§1.2；防认领驻车抑制告警）。**再 claim 新 fix_version → 同 cluster 生成新 link（新 payload_id 绑定新版本）**：旧 link 已终态自动让位（§5.1 注），见文末 reopen 条 |
| `needs_review` | v1 仅 claim 回归 infra-error 边缘触发 | → open（补充证据/升级） | 常态触发源均二期/D18 不回流 |
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
- **单错级回查规则（§10.5）**：回查锚定 = **claim 填的 fix_version** 对应回归 run 的 `run_results.pass_fail` 逐条判；**不取"最新 run"**（防多版本先后触发拿错 run）；该 case pass → verify passed → cluster fixed（闭环）；run 内他错仍红不阻塞本错 closed。
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

> **metrics 四端点默认护栏（O-1 已裁定，§10.1/§12.2）**：`agent` 缺省=全站 1h/24h 实时 agg **强制结果缓存** `metric_agg_cache_ttl_s=60` + agg 查询超时 `metric_agg_timeout_ms=3000`；`window=24h` 全站档另提供「按 agent 维度」下钻缩小扫描面；缺桶回退实时口径时响应带标记（§5.3）。overview/interfaces/anomalies/llm-failures 同套。

### 8.4 回流-聚类/用例（backflow，§7.6 状态机）

| Method & Path | 权限 | 说明 |
|---|---|---|
| `GET /backflow/overview` | viewer | 复验总览：open+claim 错误数、关联回归用例 verify 分布、**待修复集规模**（本地镜像推导 = offline_status=active ∧ verify∈{pending,failed}，标注「近似 offline 权威集」）、按 agent/接口/层分布 |
| `GET /backflow/clusters` | viewer | 列表/筛选：`agent interface layer status`（status 含 open/claim/fixed/inactive/needs_review + `watch=assembled/draft` 待拉取/确认筛选）；返回代表 trace、input_hash、去重/生成计数、关联 link 摘要 |
| `GET /backflow/clusters/{id}` | viewer | 详情：cluster 元数据 + links（case_id/case_type/offline_status/verify_status/source/payload_id）+ 该 case 历次回归 run **版本×pass/fail 时间线**（verify_run_record）+ conversion_record 审计时间线 + 「已待 N 天」与 requeue 状态 |
| `POST /backflow/clusters/{id}/ignore` | viewer | ignore → cluster inactive（link 若现行 → superseded 后再停回查） |
| `POST /backflow/clusters/{id}/claim` | viewer | **必填** `{fix_version, note}` → status=claim（fix_version 为 R5 回查锚定；CAS + 审计）；返回复核窗截止（TTL 默认 14d） |
| `POST /backflow/clusters/{id}/reopen` | viewer | reopen → open（复发/误判） |
| `POST /backflow/clusters/{id}/needs-review-resolve` | viewer | needs_review 处置：补证据回 open / 升级（v1 边缘触发语义） |
| `POST /backflow/clusters/{id}/fixed-review` | admin | admin 复核置 fixed：`{approve:true}` → fixed(closed_by=admin_review)；`approve:false` → reopen |
| `POST /backflow/links/{id}/invalidate` | admin | **仅 offline_status∈{assembled,draft}** 可人工 invalidate（`{reason}`；active 后不提供——废弃走 superseded+reopen） |
| `POST /backflow/links/{id}/requeue` | admin | invalidated→assembled 复位重推（复用 payload_id；§7.4 守卫 + 防抖） |

### 8.5 Agent 与接口字典（admin；solution §12.1 Agent 管理 → 本文件 §9.2）

| Method & Path | 说明 |
|---|---|
| `GET /agents` | agent 清单（enable、route_source、维度3 白名单） |
| `POST /agents/{id}/toggle` | 启停 agent（停用=停止该 agent 回流/指标入口？——**仅停回流生成与展示，消费不停**【实现约定】，防数据黑洞） |
| `GET /agents/{id}/interfaces` | 接口字典清单（自动发现、llm/llm_source/llm_suspect/body_search、first/last_seen） |
| `PUT /interfaces/{id}` | admin 补标：`{llm?, llm_source?, body_search?}`（归一化核对 = 修改 interface 串需记 conversion 审计【实现约定】）；疑似漏标告警处理（§8.5.1） |
| `GET /agents/{id}/credential` | Kafka 凭证查看（secret 脱敏 + 轮换入口；admin） |
| `POST /agents/{id}/credential/rotate` | 凭证轮换（版本化、吊销即时生效=撤 ACL+断连接，§13.2） |
| `GET /agents/{id}/health` | agent 上报健康小卡：最近 1min/5min 上报事件量、dropped、spool_pending、last_seen_ts（读自监控心跳 `obs.selfmonitor`，§3.6/§13.2）；agent 未接入=无 last_seen，前端据此出「未接入 SDK」文案（§9.1） |

**8.5.1 疑似漏标自动补标（§10.1 观察窗，v3.4.5 裁定）**：接口观测到 llm_call 且 `llm=false` → `llm_suspect=1`；连续观测达阈值（【实现约定】窗口 24h 内 ≥ 10 次）→ 自动 `llm=true`（source=auto_observed）不再疑似；观察窗内存疑 → `llm_suspect=1` 进 admin 复核列表 + 看板/Agent 管理「疑似漏标告警」。

### 8.6 配置与用户（admin）

| Method & Path | 说明 |
|---|---|
| `GET /configs?agent=` | dict_config 全量；**分「v1 生效 / 二期规划（灰置）」两组渲染**（§10.4 前端规则；后端只返回 v1 键，二期键不建） |
| `PUT /configs` | body `{agent_id?, key, value}` → 写 dict_config，`version+1`、记审计（admin-only；detail 记到 **config_key 粒度 + 旧/新值摘要**，§13.5；词表键变更特别提示 §10） |
| `GET /users` `POST /users` `PUT /users/{id}` | 账号 CRUD：角色 admin/viewer、启停（禁用即吊销会话，token version+1，§13.2） |

### 8.7 平台间（D20；offline 服务凭证，独立最小面）

**offline → online（pull 侧，v1）**：

| Method & Path | 说明 |
|---|---|
| `POST /pull/payloads` | 拉取 assembled payload：请求 `{schema_version:"1.0", case_type:"regression_error", agent?, limit≤100, since_ts?}`。**case_type 白名单校验：非白名单返回空集而非全量**（§12 加固）。响应 `{payloads:[信封全文(§7.1)], next_token?}` |
| `POST /pull/ack` | 拉取/状态回写：`{payload_id, action∈{draft,active,invalidated}, case_id?, reason?}` → 按 §7.3 表更新（payload_id upsert 幂等；**已知** payload_id 重复 ack=200）。**ack 前置矩阵（v1.1）**：draft 前置 `assembled`；active 前置 ∈{assembled,draft} 且**必带 case_id**；invalidated 前置 ∈{assembled,draft} 且必带结构化 reason（码见 §7.4）；前置不符→`ERR_CLUSTER_0003`、未知 payload_id→`ERR_PULL_0003` |

**online → offline（回查侧，v1；offline 实现，online 侧 client 契约）**：

| Method & Path | 说明 |
|---|---|
| `GET {offline_base}/api/v1/runs?agent=&version=&status=&case_id=` | 按 agent+version+status 过滤回归 run 且**支持按含 case_id 过滤**（offline 补强，Task #4） |
| `GET {offline_base}/api/v1/runs/{run_id}/results?case_id=` | run_results：`case_id + case_type + pass_fail`（case_type 需 join，offline 补强） |

> online 消费规则：回查只读、不写 offline；连续失败退避重试、超上限在聚类详情提示「回查失败待人工」（§7.6/§16）。online `http.py` 客户端持 offline 服务凭证、双向认证（§13.5）。

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
| `ERR_CLUSTER_0003` | 400 | 非法迁移（如 active case 人工 invalidate；claim 缺 fix_version） |
| `ERR_CONFIG_0001` | 403 | 词表等 admin-only 键变更被拒 |
| `ERR_PULL_0001` | 401 | evaluator 凭证无效 |
| `ERR_PULL_0002` | 400 | case_type 非白名单 / schema_version 不识别（返回空集约定在 8.7，强校验失败 400） |
| `ERR_PULL_0003` | 404 | payload_id 不存在（对**已知** payload_id 的重复 ack = 200 幂等成功；对**未知** payload_id = 404；§7.3 ack 矩阵） |

---

---

## 9. 前端页面规格（React；依据 solution.md §12.1 + §9.3）

### 9.1 全局约定

- 路由/菜单树见 §1.2/§12.1（solution）；**viewer/admin 按角色渲染菜单，admin-only 路由前端隐藏 + 后端二次鉴权**。
- 默认落点 = 指标看板 `/dashboard`（全站纵览 tab）。
- 空态与误读防呆（v3.5.1 易用性规则，实现为统一 `<EmptyState type=.../>` 组件）：
  - `needs_review` 状态筛选**保留但缺省为空**，附文案「v1 通常不出现（仅回归判定异常边缘触发）」，不误读为功能缺失。
  - 二期物（L3 质量出口 tab、弃留墙入口、trace quality 过滤/标记）**整条隐藏不可达、不灰置**；仅原始事件 JSON 不可避免暴露 `quality:null` 时行内提示「quality 观测为二期规划（v1 未采集），为空属预期，非采集故障」。
  - 配置管理「二期规划」组灰置 + 角标 + tooltip（键清单 §10.2）。
  - **看板「无数据」区分（防空报「采集故障」）**：`EmptyState.type` 细分——`no_agent`（该 agent 无 last_seen，未接入 SDK，数据源 §8.5 health）／`no_traffic`（有心跳但窗口无请求量）／`no_rollup`（7d 档缺桶，回退实时口径标注 §5.3）／`second_phase`（二期物，隐藏不可达）；接口/tab 按各自数据源落 type 与文案。

### 9.2 页面功能点 → 数据源（API §8）

| 页面（路由） | 功能点 | 数据源 |
|---|---|---|
| 登录 `/login` | 登录、会话维持、角色归属 | §8.1 |
| 指标看板 `/dashboard` | 全站纵览 tab（跨 agent QPS 时序 + 失败率/超时率叠加，agent 缺省=全站，可下钻单 agent）；概览卡；接口明细（双指标 tab）；异常聚焦；『LLM 调用失败』下钻段 | §8.3 overview/interfaces/anomalies/llm-failures |
| 链路查询 `/traces` | traceId/关键字自由输入（可任一）；命中列表 + agent/接口过滤 → trace 详情 | §8.2 traces |
| trace 详情（共享抽屉） | `(ts,parent,seq)` 树时间轴；异常节点红显；日志行分页懒加载；input/output/error_msg 脱敏展示；llm_call 高亮；正文查看受 `body_search` | §8.2 traces + logs |
| 回流-错误聚类 `/backflow` | cluster 列表/筛选；代表 trace 与 input_hash；复验总览 + 待修复集规模（标注"近似 offline 权威集"）；待 offline 拉取/确认 筛选 | §8.4 backflow/clusters + overview |
| 回流-聚类详情 | links（case_type/offline_status/verify_status/source）、版本×pass/fail 时间线、conversion_record 时间线、人工操作区（ignore/claim/needs_review/fixed-review/case invalidate/requeue） | §8.4 cluster/{id} + link 操作 |
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
| claim 行 | 展示复核窗口剩余时间；超窗回退提示 | §7.6 |
| assembled 已待 N 天超阈值 | 提示性标记「offline 疑似停摆，人工核查」（非告警、不设时钟） | §7.2/§13.5 |
| link invalidated 驳回（reason 码区分） | `offline_cap_gap`→「offline 能力补齐后自动恢复（重扫自愈）」；`online_content_gap`→「现场已修正，待 admin 重推」；`manual_invalidate`→「已人工判无效，可重推或弃用」 | §7.4/§8.7 |
| cluster status=needs_review | 「回归判定异常（v1 边缘触发）：补充证据回 open / 升级」 | §7.6 |
| 词表空 | 配置页/组装提示「空词库守卫不生效（fail-closed）」 | §10.1/§7.1 |
| 历史通过被 superseded | 展示「历史通过于 V_x / 现又复发」 | §6.2 |

### 9.4 viewer 可操作集（不含测试集确认）

ignore / claim（必填 fix_version+说明）/ needs_review 处置 / reopen；**不能单方置 fixed**（需回归 passed 或 admin 复核，R4）。case 级 invalidate 仅 admin（§8.4）。

**动作 × 状态门控（后端同规则，前端据此置灰/禁用，防点后被 409/400 拒）**：
- claim：仅 `cluster.status=open`；claim 中 → 置灰；
- ignore：`status∈{open,claim}`（claim 中先回退 open 再 ignore，需二次确认）；
- reopen：`status∈{fixed,inactive}`；
- needs-review-resolve：`status=needs_review`；
- fixed-review(admin)：`status=claim`；
- link invalidate(admin)：仅 `link.offline_status∈{assembled,draft}`（§8.4）；
- link requeue(admin)：仅 `offline_status=invalidated` 且 cluster 非 inactive（§7.4 守卫 + 防抖）。

---

## 10. 配置项清单（dict_config；admin-only 维护 + 审计）

> 键分「v1 生效」与「二期规划（不建键，前端灰置占位）」。`version` 字段：任何变更 +1；`fallback_utterance` 的 version 即 `wordlist_version`（随 D19 `no_fallback_config` 快照固化，§7.1）。

### 10.1 v1 生效键

| key | 作用域 | 默认 | 校验/说明 |
|---|---|---|---|
| `fallback_utterance` | per-agent | 空表 | JSON 数组（词条）。**no_fallback 断言唯一词源**；词条仅子串/关键词匹配（不按正则）；变更 admin-only + 审计；**空表=守卫 fail-closed**：信封照建→offline 结构自检不过→回写 invalidated（v1.1 语义收敛，`inconclusive` 属二期）→ 配置页提示 |
| `timeout_ms` | per-agent | 【实现约定】LLM 请求 30_000 | 上报打标阈值参考（SDK 按接入约定打标，平台不二次判；此键供看板"疑似超时"标签与接入约定单源） |
| `cluster_window_days` | 全局 | 7 | error 去重窗口（§6.2） |
| `claim_ttl_days` | 全局 | 14 | claim 复核窗（§7.6） |
| `backflow_enabled` | per-agent | true | 回流总开关（gq/cs/sp；cc 恒 false） |
| `llm_call_observe_window_min` / `llm_call_observe_threshold` | 全局 | 24h / 10 次 | 疑似漏标自动补标窗口（§8.5.1） |
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
| needs_review | 常态触发源（快照不足/判分 na/cc 文件型） | §7.6 边缘触发 |

### 12.2 open 清单（开发前需明确；O-1~O-3 已于 v1.1 裁定落稿，O-6/O-7 为部署约束派生项；余项不阻塞 P0/P1）

| # | 项 | 现状 | 建议 |
|---|---|---|---|
| O-1 | 全站 1h/24h 实时档无 agent 过滤的全量扫描护栏（性能评审 F-2） | **已裁定（v1.1）**：默认护栏 = agent 缺省「全站」档实时 agg 强制走结果缓存 `metric_agg_cache_ttl_s=60` + agg 查询超时 `metric_agg_timeout_ms=3000`（§8.3/§10.1/§14.4）；24h 档另提供「按 agent 维度」切换缩小扫描面 | P1 看板实现即落地，勿再拖（§12.2 不再视为开放） |
| O-2 | `fix_version` 组装时序（组装先于 claim 时 link 不含 fix_version） | **已裁定（v1.1）**：组装（§6.3）不写 fix_version；claim 后回查锚定 `cluster.fix_version`（§7.6 recheck_job + §5.1 verify_run_record.bound_version）；requeue 重推复用 payload_id | 与 Task #4 对账仅剩 offline 侧 run 绑定版本解析 |
| O-3 | 现行 link 唯一索引对「终态后再生成」的支持 | **已裁定（v1.1）**：改生成列 `cur_key`（仅 `verify_status='pending'` 占位），终态自动释放 → reopen / 回归 failed 后再 claim 可在同 cluster 生成新 link（新 payload_id，§5.1 注/§7.6） | — |
| O-4 | 7d 小时级 rollup 的 t-digest 库选型（`tdigest` 包序列化格式） | 【实现约定】存 base64 | 引入前验证跨小时合并正确性（§14.4 用例） |
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

### 14.3 阶段验收对齐（solution §15 P0~P2 → 用例映射）

- P0：S-1 通过（手工投事件按 trace 查回）。
- P1：S-4 通过；看板出现真实 P50/P95/P99 + 全站 QPS 趋势（gq/cs/sp 接入）。
- P2：E-1~E-22 通过 + §11.5 维度 3 开放验收（checklist #4/#8/#10，含兜底吸收埋点前提用例 S-4 在真实 agent 上复验）+ 词表覆盖度（对 §13.1 兜底逻辑盘点）。

### 14.4 性能与健壮性用例（护栏）

- rollup：迟到事件（≤6h）重算幂等不双计；缺桶回退实时 + 页面标注；**t-digest 跨小时合并 ≈ 全量重算 p95（误差 <1%）**（O-4 验证）。
- 检索/看板：慢查询熔断/限流 + 单 trace 日志懒加载分页（§8.2 大 trace 防护）。
- **O-1 护栏已裁定（§12.2，含数值判据）**：agent 缺省=全站 1h/24h 实时 agg 强制结果缓存 `metric_agg_cache_ttl_s=60` + agg 超时 `metric_agg_timeout_ms=3000`；全站 24h agg P95 ≤5s；trace 检索超时 `trace_query_timeout_ms=3000`、命中 ≤200 上限。
- **写侧/后台判据**：判定态表单行 upsert P95 ≤10ms；rollup 每小时任务完成 ≤2min；judge_scan/cluster/assemble/claim_ttl/recheck 各时间驱动 job 单飞无重复执行（§1.3）；requeue 防抖 ≥5min 生效。

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

