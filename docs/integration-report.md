# 集成测试报告（阶段 4 登记载体）

> **本文件是什么**：`task.md` 阶段 4 约定「每任务出口 = 该组用例全绿 + 对应缺陷单清零 + **在集成报告登记**」（`task.md:138`）中的那个「集成报告」。新建于 2026-09-11。
>
> **当前状态**：**仅完成盘点，未执行任何 T-4.x 的正式验收**。本文件此刻登记的是「阶段 4 已覆 / 未覆」，不是验收结果。
>
> **权威口径**：用例编号以 `solution_detail.md` §14.1~§14.5 为准；本文件只登记**覆盖状态**与**证据出处**，不重述用例定义。

---

## 0. 口径声明（先说清本文件能信到什么程度）

1. **「已覆」的判据 = 存在具名探针场景在真库/真机跑过**，证据列到「探针名#场景号」，可 `docker exec obs-backend python /app/tests/integration/<probe>.py` 复跑复核。
2. **「已覆」≠「已验收」**。探针是**独立进程直调 job/端点函数**，证明的是「该路径行为正确」；task.md 每任务的「**验证目标**」（含性能档位、双实例、真 offline、网关）是**另一层要求**，本表不与「已覆」混同。
3. **⚠️ 命名撞车，务必注意**：`task.md` 里的 **S-1~S-5** 是 detail §14.1 的**冒烟用例编号**；而 `cluster_probe.py` / `push_probe.py` / `d6_probe.py` **各自内部**也有一套 `S-x` 编号——**同名不同物**。本文件引用探针场景时一律写成 `探针名#场景号`，不裸写 `S-x`。
4. **标 ⚠️ 的条目未经实测**，属推断或未查（例如「公共 API 网关是否已存在」）。**不得当结论引用**。
5. 本文件**不含任何代码缺陷结论**——阶段 4 尚未开工，无缺陷单可登。

---

## 1. 已覆（来自既有探针与补测批，可复跑取证）

| 阶段 4 任务 | 已覆的部分 | 证据（探针#场景） |
|---|---|---|
| **T-4.2** E-1~E-4 | **online 接收半边全覆**（v1.23 契约反转后的结果推送接收面） | `push_probe#S-1`~`#S-20`（20 场景，含 E-4 窗口抑制） |
| **T-4.2** E-4 窗口内不重复 | 组装侧窗口抑制 | `assemble_probe#A-2`、`#A-9` |
| **T-4.3** E-5 词表空 fail-closed | 词表缺 → 空表 fail-closed | `assemble_probe#W-1` |
| **T-4.3** E-6/E-22 requeue 防抖与重推 | 防抖 <5min 拒、批量 requeue、旧水位重拉可见 | `pull_probe#P-10`、`#P-11`、`#P-12` |
| **T-4.3** 驳回 → online 展示重推状态 | offline 调 pull-API 报拒（**探针模拟，非真实 offline 进程**） | `pull_probe#P-6` |
| **T-4.4** E-7 回归通过 | 单错级判定 → fixed(closed_by=auto_regression) | `claim_probe#C-3` |
| **T-4.4** E-8 TTL 超窗回退 | open + 处置字段清空 + conv(claim_ttl_expire) | `claim_probe#C-8` |
| **T-4.4** E-10 终态守卫 | 守卫 no_progress + 迟到 run 落孤儿 + 保持 fixed | `claim_probe#C-14` |
| **T-4.4** E-10 回归护栏（两向反证） | fixed/inactive 簇停摆判定必为 false | `push_probe#S-10`、`#S-11` |
| **T-4.4** E-17 生产路径 | 有终态 link 的 open cluster **在**扫描候选 + 新 payload_id | `assemble_probe#A-8`、`#A-9` |
| **T-4.4** CAS 并发（claim 面） | 先手成功 + 后到者 409 | `claim_probe#C-10` |
| **T-4.5** E-13 残 trace 按子节点判定 | L1/evidence=subnode；缺 input 实文只计数 | `cluster_probe#S-13`、`#S-1` |
| **T-4.5** E-16 judge_scan 到期补判不重判 | judged=0 ∧ ttl≤now → classify → judged=1 | `cluster_probe#S-11`~`#S-13` + `test_worker_judge_scan.py` |
| **T-4.6** E-11 assembled 超阈提示性标记 | **v1.23 改被动探测后的判据**（hit=true kind=assembled） | `push_probe#S-9` |
| **T-4.6** E-11 四个抑制条件 | 有效 claim 期内不误报 / 陈旧回退 / 新 link 到货 | `push_probe#S-7`、`#S-8`、`#S-12` |
| **T-4.6** E-15 ack 幂等重放 | 双 active ack 均 200（首 apply / 次幂等） | `pull_probe#P-13` |
| **T-4.7** E-21 判定逻辑 | 「超时未收到结果推送」的判据本身（**仅判据，非注入**） | `push_probe#S-7`~`#S-12` |
| **T-4.13** ① 消费侧 schema 异常 | 预检 schema/mismatch/mask + 丢弃计数可见 | `d6_probe#S-2`（**d6 排除在 CI 外**） |
| **T-4.13** ③ 埋点前提（§4.2/§5.1） | request ok + llm_call error → 先记后传、零候选 | `cluster_probe#S-11`（含 `gate 快照=放行` 反证） |
| **T-4.13** ⑤ 平台间契约异常 | 非白名单丢行 / schema_version 拒单 / 重复 case_id 整单拒 / 未知 payload 404 | `push_probe#S-4`、`#S-5`、`#S-13`、`pull_probe#P-5`、`#P-7`、`#P-8` |
| **T-4.14** ③ 判定时序边界 | 到期瞬间补判、重复到期不重判 | 同 T-4.5 E-16 |
| **T-4.14** ⑤ 并发/竞态（部分） | claim CAS、ack 幂等重放、requeue 防抖边界 | `claim_probe#C-10`、`pull_probe#P-13`、`#P-11` |
| **T-4.11** 前端端到端（大部分）⚠️ | 登录 / 回流列表与详情 / viewer 与 admin 权限 / 状态文案 / claim 倒计时 / 空态 | **补测批浏览器 e2e（2026-09-10 当次会话结论，非可复跑资产）** |

---

## 2. 真剩余（**online 单侧可开工**，按建议优先级）

| 优先 | 任务 | 剩余内容 | 备注 |
|---|---|---|---|
| 1 | **T-4.7**（**E-18~E-20 三条**） | Kafka broker 停 / ES 不可用 / MySQL 不可用 + selfmonitor 计数可见 + 恢复自愈 | **零覆盖**，detail §14.2 明文；故障注入以本地 share-infra 编排层注入优先。**E-21 的「网关不可达」注入半边不可做**——网关不在本阶段（见 §4.1），其**判定逻辑**已覆（§1） |
| 2 | **T-4.9**（**仅非网关半边**） | 交付物边界 / 凭证不入镜像 / `{env}.` 前缀在库·index·topic·consumer group 全链路一致 / 容器不映射 3306·9200·9092 / offline↔online 走内网不经公网网关 | **网关与 SSO 半边已于 2026-09-11 裁定下移 T-5.3 上线门、文档订正已落**（见 §4.1） |
| 3 | **T-4.10** | 角色矩阵 / token version 吊销 / Kafka SASL·TLS + topic ACL / 凭证轮换 / 速率闸 / pull-API case_type 白名单 | 现仅零星碎片（`claim_probe#C-2`、`pull_probe#P-9` 的 403） |
| 4 | **T-4.8** | 全站 24h agg P95 ≤5s / `metric_agg_*` 生效 / 判定态 upsert P95 ≤10ms / rollup 每小时 ≤2min / **t-digest 合并误差 <1%** / 500 事件·s⁻¹ | **零覆盖**（现有 `test_tdigest`/`test_metrics` 是单测，非集成档位） |
| 5 | **T-4.5** 残留 | **E-14 SSE/分批到达窗口补全** + **多实例并行消费幂等 / job 单飞双实例** | 后者 = **T-3.6 结清时明确延期到本阶段的那一项**，纯 online |
| 6 | **T-4.13** 残留 | ② 脱敏死角 / ④ 检索注入与转义 / ⑥ 大对象边界 | ①③⑤ 已覆 |
| 7 | **T-4.14** 残留 | ① 时间边界 / ② 窗口边界 / ④ 数量级边界 / ⑥ 词表边界死角 / ⑦ 保留期边界 | ③⑤ 已覆 |
| 8 | **T-4.11** 残留 | `needs_review` v1 三 reason（na / unclean_run / reentry_same_version）前端呈现 / 菜单按角色渲染 / 看板类页 | 其余已覆 |
| 9 | **T-4.1** 残留 | detail §14.1 冒烟 S-1~S-5 逐条复验（S-2/S-3 的 d6 部分已覆）/ 大 trace 懒加载 | ⚠️ S-1~S-5 原文口径需回 detail §14.1 逐条核对。**「检索限 7d·超时·上限在网关侧生效」不可验**——网关不在本阶段（见 §4.1）；7d/超时/上限本身可在后端侧验 |

---

## 3. 卡 offline（**本阶段不可开工**）

| 任务 | 卡点 |
|---|---|
| **T-4.2** 的 offline 半边 | 需**真实 offline 仓**定时 pull → 回归 run → 结果推送。online 接收半边已覆（见 §1） |
| **T-4.3** 的「真实 offline 驳回（能力缺）」 | 探针只能模拟调用，验不了真实 offline 行为 |
| **T-4.6** 的「offline 恢复继续拉取不丢 / 恢复积压限速 / 按序拉取」 | 需 offline 侧真实恢复动作 |
| **T-4.12** 全条 | 明写「在 **offline 集成环境**验证」 |
| **阶段出口** E-23~E-29 修订包端到端 | 明写「于**环 2** 串」 |
| **T-4.13** ⑤ 的真实对端 | 探针已覆判据，但真实对端未验 |

> **注**：offline 侧结果推送面（`POST /backflow/regression-results` 按 `solution_detail.md` §8.7 载荷表投递，含必填 `prev_terminal_version`）online 侧接收面**已就位并已覆**（`push_probe` 20 场景）；R-4/R-5 只读面已随 v1.23 整体作废，**不得再作为依赖项**。

---

## 4. 待核项（**未实测，不得当结论引用**）

1. ~~⚠️ 公共 API 网关是否存在、以何形态存在~~ → **已核清并已裁定（2026-09-11 用户拍板 = 下移）：网关 + SSO 属 `T-5.3 上线门`，不在阶段 4，本地 dev 亦不经网关。文档订正已落 = `task.md` 5 处（**阶段 4 出口行 / T-4.1 / T-4.7 / T-4.9 / T-5.3 接收项**）+ `solution_detail.md` §14.2 **E-21 行**。**（不记行号——按本仓行号引用规范，改记任务号与章节号；裸行号会随上游插行即飘。）** 证据 = `docs/infra-access-matrix.md:49`「本地 dev 直连不经网关」+ `:51`「网关/SSO（§17 #14）与生产公共 infra 租户 = 上线门（T-5.3），不阻塞本地 dev 联调」；仓库内亦无任何网关实现产物（仅有 `docker-compose.yml` 与 `frontend/nginx.conf` 静态服务）。
   **连带影响**：T-4.1「网关侧同样生效」、T-4.9「公共 API 网关」、T-4.7 E-21「网关不可达」三条任务的**网关半边在本阶段不可执行**（已回填 §2 标注）。三条的**非网关半边仍可做**。**若日后网关提前落地，此三条需重开。**
2. ⚠️ **detail §14.1 的 S-1~S-5 逐条原文**——本表对 T-4.1 的覆盖判定系按探针场景反推，未逐条比对 §14.1。
3. ⚠️ **补测批浏览器 e2e 的逐项结论**——系 2026-09-10 当次会话快照，**无落盘资产**，回归时须重跑（chrome-devtools MCP 不留可复跑产物）。
4. ⚠️ **`docs/infra-access-matrix.md` 与阶段 4 环境前提的关系**——未逐条比对。

---

## 5. 探针资产索引（复跑入口）

| 探针 | 场景数 | 复跑命令 | CI |
|---|---|---|---|
| `cluster_probe.py` | #S-1~#S-13 | `docker exec obs-backend python /app/tests/integration/cluster_probe.py` | ✅ |
| `claim_probe.py` | #C-1~#C-15 | 同上换文件名 | ✅ |
| `pull_probe.py` | #P-1~#P-13 | 同上 | ✅ |
| `assemble_probe.py` | #A-1~#A-9、#W-1 | 同上 | ✅ |
| `push_probe.py` | #S-1~#S-20 | 同上 | ✅ |
| `d6_probe.py` | #S-1~#S-3 | 同上 | ❌ 排除 |
| `smoke_4agents_probe.py` | — | 同上 | ❌ 排除 |
| `e2e_seed.py` / `tick_rejudge_seed.py` | 种子，非断言 | 同上 | ❌ 排除 |

> 场景数为**本次盘点时点**计数；新增场景请同步本表。真库探针只需 MySQL（不用 ES/Kafka/Redis/进程），空库可跑通。
