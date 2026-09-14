# 运营手册与交接清单（T-5.4 交付物）

> **本文件是什么**：`task.md` **T-5.4** 要求的「运营清单与交接」成品件。**它不是设计文档**——设计口径以 `solution.md` / `solution_detail.md` 为准，本文件只回答**「运营期照这份能不能做」**。
>
> **写作原则（最重要的约定）**：**每一节必须带「实现现状」栏**。凡是运营动作**当前没有执行载体**的，**照实写明**并指向缺口登记——**不许把设计意图写成已有能力**。理由 = T-5.4 的验证目标是「**运营手册与实现行为一致**」；若手册描述的实现不存在，该目标在写出来的一刻就假了。
>
> **创建 2026-09-14**（阶段 5 首轮）。状态断言均带日期与证据出处，**引用前请回查**。

---

## 0. 归口一览（owner 归属）

| 事项 | owner | 依据 | 现状 |
|---|---|---|---|
| offline 的**拉取**（pull-API）与**结果确认** | **offline** | `task.md:185`（T-5.4 原文） | 设计已定；**offline 侧实现零落地**（该仓冻结中，见 `#217`） |
| 「已待 N 天」**展示** | online | `task.md:185`：online **仅展示、不设时钟** | ✅ 已实现（`api/backflow.py:559-561` → 详情页 `BackflowClusterDetailView.vue:310`） |
| TTL 超窗**回退**（claim → open） | online（自动） | `worker/claim_ttl_job.py:31-84` | ✅ 已实现，60s tick，写 `claim_ttl_expire` 审计 |
| **告警发出**（webhook / 邮件 / 外部通知） | — | — | ❌ **无通道**：`core/config.py` 无任何 webhook/smtp 字段；仅有进程日志 |

> **⚠️ 两条必须一起读的口径**：① **「不设 online 时钟」是刻意的**，不是遗漏——`api/backflow.py:320/421` 逐字「MySQL 现算，零 DDL、不落列、**不设 online 时钟**」，`solution_detail.md:1266`「非告警、不设时钟」。② 因此**「已待 N 天」是展示值**（`waiting_days = (now - anchor)//86400`，anchor = claim 态取 `claimed_at`、否则取 `first_ts`），**它不触发任何动作**。运营期**不得**把它当告警用。

---

## 1. 回流积压的观察与处置

**看什么**：回流详情页的「已待 N 天」（`waiting_days`）与「回查结果未达」类提示。

| 提示 | 后端字段 | 前端现状 | 语义 |
|---|---|---|---|
| 已待 N 天 | `waiting_days` | ✅ 渲染（`BackflowClusterDetailView.vue:310`） | 距锚点天数，**展示值** |
| 结果缺口疑似 | `result_gap_suspected` | ✅ 渲染（`:328`，文案 `backflowLabels.ts:98`） | claim 侧派生警示（**零 DDL**），抑制集见 `solution_detail` §10.4 |
| 回查结果未达 | `result_overdue` | ❌ **前端整条不消费** | 后端已算（`api/backflow.py:399-407` / `:334-397`），**登记 = `integration-report.md` §6 F-18** |

**⚠️ 运营动作的现实**：F-18 未闭合前，**「回查结果未达」这条在界面上看不到**——运营期若需观测此态，只能查库或等 F-18 处置（F-18 已挂 T-4.11 残留，阶段 4 未补实现）。

**超窗自动回退**：claim 超 `claim_ttl_days`（默认 14，`core/seed.py:47`）→ `claim_ttl_job` 清回 `open` 并写 `claim_ttl_expire` 审计。**这是自动的，运营无需介入**；介入场景 = 需要人工复核为何长期未被拉取时，查 `conversion_record` 的 `claim_ttl_expire` 行。

---

## 2. 词表（`fallback_utterance`）维护流程 —— ⚠️ **当前无执行载体**

**设计要求**：`task.md:185` 「新增兜底话术即补词表、**admin-only 留审计**」；代码注释同口径——`converter/no_fallback_cfg.py:4-5`「`fallback_utterance` 的 version 即 D19 `wordlist_version`，**变更 +1，admin-only**」。

**实现现状（2026-09-14 实测）**：

| 环节 | 现状 | 证据 |
|---|---|---|
| 读取（组装瞬间） | ✅ 有 | `converter/no_fallback_cfg.py:47`（`parse_words(row.config_value), row.version`） |
| **写入端点** | ❌ **无** | `api/router.py:13-20` 只挂 auth/backflow/metrics/pull/trace 五个 router，**无 config/admin 写面** |
| **admin 角色门控** | ❌ 无（无端点可挂） | `deps.py:44-47` `require_admin` 存在，但**无路由使用它写 `dict_config`** |
| **审计落点** | ❌ 无 | 审计表 `conversion_record` 仅被回流链路写，**词表变更无写入路径** |
| **version 自增** | ❌ 无实现 | `models/config.py:23-24` 仅有字段默认值与注释；全仓无 `version = version + 1` |

**⇒ 结论（写清楚，避免误读）**：**「新增兜底话术即补词表」这条流程，运营期无法执行**——唯一的生产侧写入是 seed 落初始空表（`core/seed.py:154-177`，且 `ON DUPLICATE KEY UPDATE updated_ts = updated_ts`，**只补缺省、不覆盖人工值**）。

**归口 = `task.md` T-3.12**（「系统管理面（admin）补实现」，其范围**明写含 `dict_config` 配置**）——**已在册，无需新立**；本条把「词表写入 + version 自增 + 审计」**显式列为 T-3.12 的验收内容**，防它在实现时被漏掉。

**过渡期建议**：在 T-3.12 落地前，词表变更**只能由开发直接改库**（无 UI、无审计、无 version 自增）——**这会造成 `wordlist_version` 失真**，而该 version 是 D19 信封的组成部分。**故过渡期应避免改词表**；确需变更时，须同步手工维护 `version`，并知悉该操作**不留审计**。

---

## 3. 保留期与审计

| 事项 | 现状 | 证据 |
|---|---|---|
| ES 事件/日志保留 | ✅ **ILM 30 天已登记**（delete `min_age: 30d`），两个 template 均已挂载 | `es-template/obs-ilm-policy.json:15-20`、`obs-event-template.json:13`、`obs-log-template.json:13` |
| 审计表 | ✅ `conversion_record` | `models/error_flow.py:143-162` |
| 审计**读面** | ⚠️ **仅 cluster 详情内嵌**，无独立列表/检索端点 | `api/backflow.py:555-558/590-596/608`（仅 `GET /backflow/clusters/{id}` 返回 `conversions`） |
| 审计**导出** | ❌ **无** | 全仓 grep `csv\|export\|StreamingResponse\|FileResponse\|Content-Disposition` **零命中** |

**⚠️ 运营含义**：**跨 cluster 的审计检索与导出当前做不到**——只能逐个 cluster 打开详情看。这在「统计某时间段内人工处置了多少条」这类运营诉求下**不可用**。

**归口 = `T-3.13 审计读面与导出补实现`**（**2026-09-14 立**，用户拍板）。**⚠️ 性质须读写清楚**：该项在 **T-5.4 原文**中提出，但**上游设计零命中「导出」**（2026-09-14 实测 grep：`solution.md`/`solution_detail.md` 对「导出」**无任何命中**，仅 `task.md` T-5.4 自身一行）⇒ 它是「**运营需求驱动的补实现**」，**不是** T-3.12 那种「文档承诺过、实现没做」的欠债。**`T-3.13` 条目内已显式标注该区别**，引用时勿把两条并成同类。

---

## 4. 看板口径（双指标 · rollup 缺口语义）

### 4.1 双指标

**语义**：请求级（`request` 事件）与 LLM 调用级（`llm_call` 事件）**分别统计**，`error/timeout/ok` 互斥（`solution.md:51` D4、`:350`）。

**实现**：前端 `components/InterfacesSection.vue` 双 tab（`:11-16` `type Tab = 'request'|'llm'`，`:37-45` 两个按钮）；后端 `api/metrics.py:150-156`（`MetricsInterfaces.request[]` / `.llm[]`）。

**运营要点**：**「LLM 调用失败」≠「请求失败」**——`request ok + 子节点 llm_call error/timeout` 是**降级/兜底现场**，v1 **不回流**、L3 二期接入（`solution.md:373`）。运营期看到 LLM 级失败率毛刺**不要**当成 request 级故障。

### 4.2 rollup 缺口语义（**易误读，重点**）

**实现口径 = 读侧现算，非写侧持久标记**：
- 缺口字段 `fallback_hours`（`api/metrics.py:116`，Interfaces 侧 `:154`），判定 = 已闭合 UTC 整点小时集合 **减去** rollup meta 已覆盖小时（`:362-367`，`_rollup_covered_hours` 在 `:294-303`）。
- 前端呈现：`OverviewView.vue:85-86`「部分时段回退实时口径（N 个整点小时无 rollup 覆盖）」；`:98` `covered_hours`。
- **覆盖小时含「处理过但零流量」的小时**（`api/metrics.py:12`），故缺口 = **真缺口**而非「无数据」。

**⚠️ 与 `consumer/es.py:18-19` 注释的关系（勿混读）**：该注释说「rollup 缺口标记归属主循环与 rollup job、rollup 建成后标缺口才落得下」——**写侧的持久化标记并未实现**（主循环 `consumer/main.py` 无缺口逻辑、`worker/rollup_job.py` 与 `store/metrics_rollup.py:105-109` 的 meta doc 只有 `source_count`）。**登记 = `integration-report.md` §6 F-13**。⇒ 运营期看板上的缺口**是读侧实时算出来的**，**没有**「缺口事件」可查、可审计。

**运营动作**：看到缺口 → 判定该时段看板分位基于**实时口径**（覆盖小时数由 `covered_hours` 给出）→ **不要**把该时段的分位数当 rollup 口径引用。

---

## 5. 已知边界与挂账（交接必读）

| # | 边界 | 性质 | 登记 |
|---|---|---|---|
| 1 | 「回查结果未达」前端不呈现 | 实现缺口 | F-18（挂 T-4.11 残留） |
| 2 | 词表变更无写入面/无审计/无 version 自增 | 实现缺口 | T-3.12（范围内） |
| 3 | 审计跨 cluster 检索与导出不可用 | 缺实现（**运营需求驱动，非文档欠债**） | **`T-3.13`**（未开工，不阻塞放量） |
| 4 | rollup 缺口**写侧**无持久标记 | 设计要求有、实现无对象 | F-13 |
| 5 | 无任何外部告警通道 | 设计如此（不设时钟、非告警） | `api/backflow.py:320/421` |
| 6 | 维度 3 开放验收在**真实 agent** 上复验 | **卡输入**：需真实 agent 接入 | T-2.5 / S-4，**阶段 5 内无法完成** |
| 7 | 网关/SSO 上线门 | `#14b` 待 infra 回执 | F-22（`docs/infra-access-matrix.md` §4） |

---

## 6. 交接清单

| 交付物 | 状态 |
|---|---|
| 运营手册（本文件） | ✅ 本轮交付（**带 7 条边界对照**） |
| 看板口径文档（双指标 + 缺口语义） | ✅ §4 |
| 归口一览（owner） | ✅ §0 |
| 回归假绿残余承认 + 词表维护流程 写入 SOP | ⚠️ **流程已写（§2），但无执行载体** ⇒ 随 T-3.12 落地方可执行 |
| TTL 告警 owner 明确 | ✅ §0（含「无告警通道、不设时钟」两条否定口径） |
| 保留期与审计导出 | ⚠️ 保留期 ✅ / **导出缺实现 → 已立 `T-3.13`**（§3；不阻塞放量） |
| **验证目标：维度 3 开放验收在真实 agent 上最终复验** | ❌ **未达成**——需真实 agent，卡 T-2.5 |

---

*创建：2026-09-14（阶段 5 首轮，T-5.4）。本文件的「实现现状」栏一律以实测为准；若与设计文档冲突，以本栏 + 对应 F-x 登记为准，并回头订正设计文档。*
