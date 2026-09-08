# infra 服务账号与权限矩阵（操作面契约交付物）

> **任务**：task.md T-0.2（公共 infra 接入申请与操作面契约）——交付物 = 本矩阵 + 回执核对；T-5.3 上线收口核销。
> **依据**：solution_detail §13（安全实现三域隔离）/ §3.3（Kafka 契约）/ §5.2（ES 索引）/ solution §14 部署边界 / §12.2 O-6/O-7。
> **分层**：① dev 底座 = 本地共享 infra（`D:/study/aiprojcet/infra`，本项目自控仓，本地可自控节奏）；② 生产 = 公共 infra 租户（上线门，T-5.3）。
> **本地安全态（重要）**：本地共享 infra 为 dev 简化——ES `xpack.security.enabled=false`、Kafka PLAINTEXT 无 SASL/ACL + `AUTO_CREATE_TOPICS_ENABLE=true`。SASL/TLS/ACL 等安全断言在**隔离安全实例**验证（task T-4.10），不污染共享实例。故下表中仅「生产公共 infra」列需严格落权，「本地 dev」列到 MySQL 建库 + 账号为止。

---

## 0. env 值域与命名登记（全部资源带 `{env}.` 前缀，无前缀 = 独立集群默认，§17 #15）

| 资源 | 命名 | 本次 env |
|---|---|---|
| MySQL 库 | `{env}.obs`（库内表全集 = detail §5.1，T-1.1 DDL） | `dev.obs` |
| ES index | `{env}.obs-event-yyyyWW`（event）/ `{env}.obs-log-yyyyWW`（log），周滚动 + ILM 30d delete；`{env}.obs-metrics-rollup` + t-digest 草图 | `dev.obs-*` |
| Kafka topic | `{env}.obs.agent.<name>`（name ∈ {gq, cs, sp, cc}，每 agent 一个）+ `{env}.obs.selfmonitor`；partition=1（同 trace 近似保序） | `dev.obs.*` |
| consumer group | backend 消费组 principal，带 `{env}.` 前缀，与 topic 同建同绑 | `dev.obs.*` |

> env 值域建议：本地联调 = `dev`；生产值域上线前与 infra 登记一致（§17 #15）。topic 白名单正则 = `^(?:[a-z0-9-]+\.)?obs\.(?:agent\.[a-z0-9-]+|selfmonitor)$`（§13.2）。

## 1. 服务账号权限矩阵 ①~⑤（生产公共 infra 申请形态；本地 dev 见 §3）

| # | 账号角色 | 依赖资源 | 权限面 | 凭证/隔离 | 归属与备注（锚） |
|---|---|---|---|---|---|
| ① | ES backend 写账号 | 事件/日志 index（`{env}.obs-event-*` / `{env}.obs-log-*`） | 写入 + 自建周 index | backend 专用最小账号 | 消费 worker ES 分派写入（detail §5.2/§13.3） |
| ② | **rollup 写账号** | rollup / t-digest index（`{env}.obs-metrics-rollup*`） | **每小时自建/写 rollup、t-digest index 的归属与配额**；含 rollup index 的 ILM 与容量是否纳入租户档 | backend 专用或独立写账号 | **v3.5.2 缺口补（task 显式要求）**：该每小时隐含写入从未成申请项，须显式落为申请条目（detail §5.3/§7.1、T-2.3） |
| ③ | ES 只读查询账号 | 7d rollup + 实时 agg（metrics/trace 查询） | 只读 agg/search | 查询专用 | 看板/链路查询侧（detail §8.2/§8.3、T-1.4/T-2.2） |
| ④ | Kafka producer 账号 | topic `{env}.obs.agent.<name>` ×4 + `{env}.obs.selfmonitor` | 每 agent 独立凭证、topic 级 ACL：仅对应 agent 可写、仅 backend consumer principal 可读；agent 间不可互写 | 每 agent 独立 SASL（`agent_credential` 加密映射，§5.1⑨） | 上报域（detail §3.3/§13.2、R3 首版即上）；轮换 = 新 SASL → 落密 → 撤销旧 ACL → 断线重连 |
| ⑤ | consumer group 管理操作面 | backend 消费组（`{env}.obs.*`） | **offset 提交/重平衡/增 partition 是 backend 日常动作——group 的创建/变更申请通道、是否含在首批落权内须确认** | group principal 同建同绑 | task 显式要求确认项（detail §3.3/§13.2） |

## 2. 变更通道 SLA 与失败兜底约定（task T-0.2 约定项）

- **申请回执 SLA**：账号/权限/template 申请回执时限、超时或被拒时的负责人——上线前与 infra 敲定，登记进 T-5.3 收口清单。
- **任一依赖未就绪时的平台降级路径**：
  - rollup 写失败 → 看板缺口标注而非静默写崩（衔接 solution §16 公共 infra 共享/多租户耦合风险行）；
  - ES 不可用 → 事件落待补写 spool 或显式丢弃 + 缺口标注，判定/聚类/回流不受影响（T-4.7）；
  - Kafka 不可用 → consumer 停拉退避挂起、不提交空推进（T-4.7）；
  - MySQL 不可用 → 判定态写失败不提交 offset + 退避自监控（禁"丢弃并提交"，T-4.7）。
- **先建 topic + 绑 ACL，后发凭证**；平台无 broker 建删权（§3.3/§13.2）。

## 3. 本地 dev 落权动作清单（本次 session，自控；执行需确认）

| 步 | 动作 | 说明 |
|---|---|---|
| 1 | 起本地共享 infra 三服务 | `docker compose -f D:/study/aiprojcet/infra/docker-compose.yml up -d mysql kafka elasticsearch`（MySQL/ES/Kafka 已在 compose 声明，当前零容器） |
| 2 | MySQL 建库 `dev.obs` + backend 最小账号 | 账号（含 alembic 迁移账号）由 backend .env 注入；不入镜像不入仓库 |
| 3 | Kafka topics | 本地 `AUTO_CREATE_TOPICS_ENABLE=true` → producer 首投自建即可，无需手动建（生产走 §2「先建后发」） |
| 4 | ES index template / ILM | **T-1.3（阶段 1）提交**（detail §5.2 mapping + §7.1 ILM），P0 前非必需 |
| 5 | .env 注入 | endpoint/账号/凭证仅 `.env`，本地 dev 直连不经网关（detail §1.6） |

> 网关/SSO（§17 #14）与生产公共 infra 租户 = 上线门（T-5.3），不阻塞本地 dev 联调（detail §1.6/§12.2 O-6/O-7）。

---

*创建：2026-09-08（online 阶段 0 T-0.2 编码推进首轮，材料面交付）*
