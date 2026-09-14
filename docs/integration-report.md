# 集成测试报告（阶段 4 登记载体）

> **本文件是什么**：`task.md` 阶段 4 约定「每任务出口 = 该组用例全绿 + 对应缺陷单清零 + **在集成报告登记**」（`task.md:138`）中的那个「集成报告」。新建于 2026-09-11。
>
> **当前状态（2026-09-13）**：**已开工**。§1/§2 仍是盘点口径（「已覆 / 未覆」**不等于验收结论**）；**唯一一条已执行的验收 = T-4.5 双实例单飞**（见 §1 末行与 §6 F-2 的分档结论）。执行期发现登记于 §6。
>
> **权威口径**：用例编号以 `solution_detail.md` §14.1~§14.5 为准；本文件只登记**覆盖状态**与**证据出处**，不重述用例定义。

---

## 0. 口径声明（先说清本文件能信到什么程度）

1. **「已覆」的判据 = 存在具名探针场景在真库/真机跑过**，证据列到「探针名#场景号」，可 `docker exec obs-backend python /app/tests/integration/<probe>.py` 复跑复核。
2. **「已覆」≠「已验收」**。探针是**独立进程直调 job/端点函数**，证明的是「该路径行为正确」；task.md 每任务的「**验证目标**」（含性能档位、双实例、真 offline、网关）是**另一层要求**，本表不与「已覆」混同。
3. **⚠️ 命名撞车，务必注意**：`task.md` 里的 **S-1~S-5** 是 detail §14.1 的**冒烟用例编号**；而 `cluster_probe.py` / `push_probe.py` / `d6_probe.py` **各自内部**也有一套 `S-x` 编号——**同名不同物**。本文件引用探针场景时一律写成 `探针名#场景号`，不裸写 `S-x`。
4. **标 ⚠️ 的条目未经实测**，属推断或未查（例如「公共 API 网关是否已存在」）。**不得当结论引用**。
5. 阶段 4 已开工（2026-09-13 起），**执行期发现登记于 §6**。§6 的 **F-x 是「待处置发现」而非「已定性缺陷」**——定性需先拍板缺陷处置口径（待定项②）。

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
| **T-4.5** 双实例单飞（detail §14.4 写侧判据） | **cluster / assemble / claim_ttl 三 job 并发无重复**（真机双实例，2026-09-13）；judge_scan 同轮有真数据但判据弱；rejudge 判据最弱 | **真机双实例实测，非探针资产**（脚本未落仓） |
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
| **T-4.7** 故障注入（**三条**） | **E-19 ES 不可用 / E-18 Kafka 不可用 / E-20 MySQL 不可用**——判据均为「投唯一 trace → 注入 → 恢复 → 断言判定态行」 | **真机注入实测，非探针资产**；dev 库已回基线 70 行（2026-09-13）。详见 §6 F-4 |
| **T-4.9** 部署/网络（**非网关半边五条**） | 交付物边界 / 凭证不入镜像 / `{env}.` 前缀全链路 / backend 零宿主端口映射 / 中间件走网络内服务名 | **真机取证**（`docker run --rm` 无 bind mount 取镜像本体 + 运行时 `select database()` + `NetworkSettings.Ports`），2026-09-13。详见 §6 F-6 |
| **T-4.10** 鉴权边界（**online 四条**） | 角色矩阵越权被拒 / 吊销即时生效（`status` + session 行**两半**）/ `case_type` 白名单返空集 / 未授权 topic 丢弃计数 | **探针 21/21 PASS**，2026-09-13（A/B/E/C1-C2/D 真机 HTTP + Kafka/ES；**C3~C6 为进程内 ASGI**，边界已标注）。详见 §6 F-8 |
| **T-4.8** 结构型四条 | 缓存 TTL 生效（观测面 = ES `search.query_total` 增量）/ trace 检索 `page_size≤200` 与深翻页守卫 / 判定态单行写 P95 ≤10ms / rollup **真重算轮**耗时 | **探针 16/16 PASS**，2026-09-13（真库直驱 + 真机 HTTP + 真 ES）；**容量型下移 T-5.3**。详见 §6 F-9 |
| **T-4.13** ②④⑥ + **T-4.14** ①②⑥ ⚠️ | 脱敏死角（`find_sensitive_leak`）/ 检索注入与转义（真机 `/traces?keyword=`）/ 大对象边界（`snapshot_input` 8K）/ 时间边界（`iso_week` ISO 跨年归属）/ 窗口边界（`late_k` 扫描集与窗口外不回填）/ 词表边界死角（`parse_words` 保真 + 缺 agent 行降级） | 探针 **33/33 PASS**，2026-09-13（真实现函数直驱 + 真机 HTTP + 真 ES + 真 rollup 轮）；**但当日独立复核揭出六处漏验 ⇒ 覆盖不全，见 §6 F-11**。**X-13 保留期下移 T-5.3、X-10 数量级半边下移**（两条下移均已由复核**原文级确认**） |

---

## 2. 真剩余（**online 单侧可开工**，按建议优先级）

| 优先 | 任务 | 剩余内容 | 备注 |
|---|---|---|---|
| 1 | **T-4.7**（**E-18~E-20 三条**） | ~~Kafka broker 停 / ES 不可用 / MySQL 不可用~~ **三条已于 2026-09-13 真机注入全部通过**（见 §1 与 §6 F-4）；残留 = E-19 的「该小时 rollup 缺口标注」**未验** | **E-21 的「网关不可达」注入半边不可做**——网关不在本阶段（见 §4.1），其**判定逻辑**已覆（§1） |
| 2 | **T-4.9**（**仅非网关半边**） | ~~交付物边界 / 凭证不入镜像 / `{env}.` 前缀全链路 / 不映射 3306·9200·9092 / 走内网~~ **五条已于 2026-09-13 全部验证通过**（见 §1 与 §6 F-6） | **网关与 SSO 半边已于 2026-09-11 裁定下移 T-5.3 上线门、文档订正已落**（见 §4.1） |
| 3 | **T-4.10** | ~~角色矩阵 / token version 吊销 / pull-API case_type 白名单 / 未授权 topic 丢弃计数~~ **四条已于 2026-09-13 全部验证通过**（探针 21/21，见 §1 与 §6 F-8）；**速率闸 / 凭证轮换 / Kafka ACL 已于同日裁定下移 T-5.3** | 残留边界 = `case_type` 白名单**只在实现层验过**（本环境未配 `EVALUATOR_SERVICE_SECRET` ⇒ `/pull/*` 整面 401），**部署层待 T-5.3 复验** |
| 4 | **T-4.8** | ~~判定态写 P95 ≤10ms~~ / ~~rollup 单轮耗时~~ / ~~`metric_agg_*` 生效~~ / ~~trace 检索上限~~ **四条结构型已于 2026-09-13 实测通过**（探针 16/16，见 §1 与 §6 F-9）；残留 = 全站 24h agg P95 ≤5s / t-digest 合并误差 <1% / 500 事件·s⁻¹ **三条容量型下移 T-5.3** | **「零覆盖」已订正**：`test_tdigest`/`test_metrics` 是单测属实，但四条结构型本地可验；**`metric_agg_*` 是 dict_config 键、不是 MySQL 表**（本库 13 表无该族），真机制 = 进程内 `_cache` |
| 5 | **T-4.5** 残留 | **E-14 SSE/分批到达窗口补全** | 「多实例并行消费幂等 / job 单飞双实例」= T-3.6 结清时延期到本阶段的那一项，**已于 2026-09-13 真机双实例执行（见 §1 与 §6）**，不再计为剩余 |
| 6 | **T-4.13** ②④⑥ | **② 六处漏验已于 2026-09-14 补测完毕 = 25/25**（探针 §6 F-11 ⑥；五处补测 + X-8 前半经 F-12 裁定不可验）；**④ 文档口径裁定已于 2026-09-14 收口**（4 条真错已改：三条尾锚 / `search_after` 旧口径 / X-10「超 200 截断」措辞 / X-8「24h+1s」；X-12 口径明确化——见 §6 F-11 ④，落 `solution_detail.md` **v1.24**） | ①③⑤ 早已覆；**F-10 的「33/33」与 F-11 ⑥ 的「25/25」均不得单独作为验收证据引用** |
| 7 | **T-4.14** ①②⑥ | **①⑥ 已于 2026-09-14 随 ② 补测完毕（X-2 五条 / X-12 四条，见 §6 F-11 ⑥）**；**④ 文档口径裁定已于 2026-09-14 收口**（§6 F-11 ④，落 detail v1.24）。**另有一条已定性的发现**：X-8 前半「同键恰 7d 聚类窗边缘（第 7 vs 8 天）」**在实现层无判别对象**——候选查询 `cluster.py:173-184` 零时间谓词、`pick_merge_target` 不接收时间输入、`latest_ts` 只有展示读、`inactive` 唯一赋值点 = 人工 `ignore`（详见 **§6 F-12**，**已定性为「本仓未实现」**；**⑦ 保留期下移 T-5.3**（detail §14.5 X-13 逐字「衔接 T-5.2」，T-5.2 属阶段 5；且 ILM 本体不在本仓） | ③⑤ 已覆；**④ 数量级边界**折半——已由复核**原文级确认**指 `MAX_LIST_RESULTS=200` 这同一处守卫（`trace.py:111` + `113-117`），与 T-4.8 J3 同源，容量半边下移 T-5.3。**F-12 已于 2026-09-14 拍板 = A（登记 + 并入待定项②，本阶段不补实现）** ⇒ **X-8 前半永久记「无判别对象」** |
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

1. ~~⚠️ 公共 API 网关是否存在、以何形态存在~~ → **已核清并已裁定（2026-09-11 用户拍板 = 下移）：网关 + SSO 属 `T-5.3 上线门`，不在阶段 4，本地 dev 亦不经网关。**文档订正已落 = `task.md` 5 处（**阶段 4 出口行 / T-4.1 / T-4.7 / T-4.9 / T-5.3 接收项**）+ `solution_detail.md` §14.2 **E-21 行**。**（不记行号——按本仓行号引用规范，改记任务号与章节号；裸行号会随上游插行即飘。）** 证据 = `docs/infra-access-matrix.md:49`「本地 dev 直连不经网关」+ `:51`「网关/SSO（§17 #14）与生产公共 infra 租户 = 上线门（T-5.3），不阻塞本地 dev 联调」；**⚠️ 二次订正（2026-09-11，原句错）**：初版写「仓库内亦无任何网关实现产物」并据此推出「环境物理上无网关」——**错**，只查了 online 仓、**未查 infra 仓**。真相 = shared infra **已有**公共 API 网关运行时（`../infra/api-gateway`，nginx `listen 8099` / `{name}.local`，服务 gq·cs·cc·sp·eval 五个被测 agent），**但无 online 的 server 块与 upstream**（online 接入尚未发生）。**故裁定理由收窄为一条**：阶段 4 的联调形态（**环 2**）设计上即「内网直连不经公共网关」，要验网关必须先改环 2 定义，而改联调形态不属于「只验收、不新增功能」。**❗显式声明：这不是能力限制，是边界划分**——网关运行时已存在、加一个 server 块即可验，**日后不得拿本条当「做不了」的证据**。
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

---

## 6. 缺陷与发现登记（阶段 4 执行期）

> 命名沿用既有约定：**F-x** = 待处置发现（尚未定性为缺陷）；**缺陷**需在处置口径（待定项②）拍板后另行编号。

> **⛔ 处置口径已拍板（2026-09-14，待定项② = 按类分流）** —— 阶段 4 全程共登记 F-1~F-12 **十二条**，按类分流如下（**这个分类本身就是本项的结论**：它证明「十二条缺陷」是个被夸大约 4 倍的说法）：
>
> | 类 | 含义 | 条目 | 数 |
> |---|---|---|---|
> | **甲 真待处置** | 有对象要动（数据/schema/代码/文档/判据） | **F-1、F-2、F-5、F-12** | 4 |
> | **乙 已闭合** | 记录验证结论或已订正事实，动作已完成，**无需再动** | F-3、F-4、F-6、F-7、F-8、F-9、F-10、F-11 | 8 |
>
> **处置结果（甲类四条，2026-09-14 全部落地）**：**F-1** 三拆（1a 已删 2 行 / 1b 已修兜底扫描 + 负对照取证 / 1c 升格挂阶段 5）；**F-2** 降格声明（§14.4 五 job = **3 强 / 2 未验**，非 5/5）；**F-5** 已改 `_backoff` docstring（措辞订正，**行为未变**）；**F-12** 已于同日拍板 A（登记 + 并入本项，不补实现）。
> **乙类不是待办、是资产**：F-7/F-9/F-10/F-11 的价值全在**方法论**（取证会骗人 / 容量型不算结构型 / 全绿≠验完），作用是**约束未来的判据写法**，处置方式 = **留在登记里，别删**。
> **无需新编「缺陷」号**：拍板后回看，F-1~F-12 **没有一条够得上「缺陷」**——甲类四条全是**发现**级（数据残留 / 判据未达标 / 措辞偏差 / 权威未实现），且均已落地或已挂账。原「缺陷另行编号」的预留**本阶段不启用**。

### F-1（2026-09-13）：dev 库存有 2 条 push_probe 清理残留，且两子表无 FK 级联

**现象** —— `error_cluster` 表为空，但两张子表各留 1 条指向**已不存在**的 `cluster_id=1086` 的孤儿行：

| 表 | 行 | 关键字段 |
|---|---|---|
| `error_case_link` | `#730` | `cluster_id=1086`、`source_trace_id='push-trace-4841cdd5'`、`verify_status='pending'`、`assembled_ts=2026-09-10 08:26` |
| `conversion_record` | `#1274` | `cluster_id=1086`、`action='regression_result'` |

**归属** —— 两行同指 cluster 1086，时间戳与 `push-trace-` 前缀均落在 **2026-09-10 补测批 `push_probe` 执行窗口**内 ⇒ 判定为 `push_probe` 清理残留：**删了 cluster，漏删了它的 link 与 conv**。

**连带事实（比残留本身更值得记）** —— 簇已删而子行仍在，说明 `error_case_link` / `conversion_record` **无 `ON DELETE CASCADE`**（或清理走的是绕过约束的路径）。这解释了为何「按 cluster 清理」的写法会留下孤儿。

**与既有记录矛盾** —— memory 记「dev 库已清且幂等（六表回 0）」。实为**五表回 0 + 2 条孤儿**。⚠️ **该矛盾不等同于 `push_probe` 探针本身有问题**：本文件 §5 表列的探针是**可复跑资产**，其清理逻辑未在本轮复核；本轮只据残留推断，**未取证到清理代码本身**。

**状态（2026-09-14 已处置，按待定项①「按类分流」口径拍板）** —— 本条拆成三条**独立**事实，**其中一条推翻了初版的因果判断**：

| | 内容 | 处置 |
|---|---|---|
| **F-1a** | 2 条悬空行 | **已删**：`DELETE FROM conversion_record WHERE cluster_id=1086` / `DELETE FROM error_case_link WHERE cluster_id=1086`，`row_count` 各 1；删后**六表回 0**、`trace_judge_state=70` 未动、`orphan_link/orphan_conv` 均 0 |
| **F-1b** | 清理以簇为锚 ⇒ 对「锚已消失」的行**单向不可达**（簇一旦删掉，任何后续 run 都扫不到它） | **已修**：`push_probe._cleanup` 加按 `push-trace-` 前缀的悬空行兜底扫描。**刻意不静默删——命中即打印**，否则将来真有新漏删时，兜底会把它抹平、反而让缺口隐身 |
| **F-1c** | 子表无 `ON DELETE CASCADE` | **升格**：若有级联，F-1a 的孤儿行**根本不会存在** ⇒ 它不是学术问题，是这起残留的**唯一充分条件**。属 DDL 变更（A 级），**本阶段不动**，挂阶段 5 |

**⚠️ 初版因果判断被推翻（留痕，勿沿用）** —— 初版写「删了 cluster，漏删了子行」，隐含「清理谓词写错」，并据此主张「删了症状留着病因」。2026-09-14 实测**证伪**：跑完整一轮 `push_probe`（**22/22 全绿**）后**零新增悬空行**、残留行 id 一字未变（仍为 730/1274）⇒ **清理本身工作正常**，那 2 行只是「锚先消失、此后永久扫不到」的历史存活者，**不复发**。故「病因」不存在，**删除才是正解**。

**⚠️ 成因仍无解释（不掩饰）** —— 「2026-09-10 08:26 那 2 行当初怎么变成孤儿的」**查不出**。中途我曾提出一版「live `assemble_job` 与清理 TOCTOU 竞争」的解释，**随后自我证伪**：`push_probe.py:256` 写的是 `assembled_ts=assembled_ts if assembled_ts is not None else NOW`，**永远非空**，故「`assembled_ts` 非空」**不能**证明是 live 组装写的；且 `push-trace-` 前缀本来就只由 `_seed_link` 生成。⇒ 该解释作废。**它是对一次历史事件的问题，且不影响处置结论。**

**F-1b 的判别力已用负对照取证（不是「跑绿了」）** —— 植入 `id=2068 / cluster_id=999999`（不存在）的悬空 link → 跑探针 → 输出 `[cleanup] 兜底扫到 1 条悬空 link（簇已删）：[2068]`，该行被清、表回 0、22/22 仍全绿 ⇒ **指名报出目标**，而非「恰好没报错」。

### F-2（2026-09-13）：T-4.5 双实例单飞——判据强度按 job 分层，勿笼统称「已验」

**背景** —— detail §14.4 写侧判据是「judge_scan / cluster / assemble / claim_ttl / rejudge **五 job** 单飞无重复执行」。2026-09-13 真机双实例实测（同一镜像起两个一次性容器、相隔 1s 相继启动，四族隔离种子）结果**按 job 分成三档**：

| job | 乘法性副作用 | 观测指标 | 结论 |
|---|---|---|---|
| **cluster** | 有（`count+1`、建簇） | `count` 精确 = 种子数（4000，**非 8000**）、单簇、无丢失 | **强** |
| **assemble** | 有（建 link + `conv(assemble)`） | 200 簇 → **恰好 200 条 link**（每簇 1.00 条）、`conv(assemble)` 精确 200 | **强** |
| **claim_ttl** | 有（`conv(claim_ttl_expire)`） | `conv(claim_ttl_expire)` 精确 200、200 簇全部 claim→open | **强** |
| **judge_scan** | **无**（布尔置位 `judged=1`） | `judged=1` 精确 3000 —— 但双跑本就只有 N 行 | **弱** |
| **rejudge** | 走 `judge_link`（SAVEPOINT 包裹） | 50 条 link 无双建、零异常；但种子未达终态 ⇒ 无终态迁移可观测 | **弱** |

**争用取证（这条是上述「强」档的命门）** —— 若两实例只是先后跑，结果与单实例跑完**完全无法区分**。故以 MySQL 全局计数取证：受控轮 `Innodb_row_lock_waits` **+38**、`Innodb_row_lock_time` **+40s**，另两轮旁证 +27 / +29 ⇒ 两实例**确实在同批行上争用**，非时序错开。全部轮次两实例日志**零 `Traceback` / 零 `ERROR` / 零 `WARNING`**。

**⚠️ 未取证的前提（不得当结论引用）** —— 锁等待增量归因于「两实例争用同一批行」，依据是「窗口内无其他写者」（当时 `obs-worker` 已停、`obs-backend` 无流量）。此为**推断，未独立取证**。

**未验部分** —— `rejudge` 的种子（`claim` ∧ pending link）始终未达终态（50 条恒 `pending`），故该 job 只验到「无双建 + 无异常」，**未验到终态迁移的并发正确性**；
  **⛔ 降格声明（2026-09-14，按待定项①「按类分流」口径拍板）** —— `judge_scan` / `rejudge` 两 job 的「单飞」在本阶段**未获强判据**，此后引用**必须带此限定**，不得笼统写「五 job 单飞已验」。本阶段**不补测**：要拿到强判据需把临界区拉长到远超实例启动偏移、并另造**乘法性**观测指标（布尔置位无判别力，见 [[concurrency-test-needs-contention-proof]]），属**重做一轮**而非补一条断言 ⇒ 要补须单独立项。**故 §14.4 的验收状态 = 3 强 / 2 未验，不是 5/5。**`judge_scan` 的 CAS 因无乘法副作用，**原理上不可由外部观测证伪**。

**方法论留痕（勿重蹈）** —— 首轮用 200 行种子判「通过」，**系假绿**：两实例 tick 相隔 1s 而临界区不足 1s，且 `worker` 日志 formatter 只打 `message`、`extra={"merged": n}` 字段**根本不输出** ⇒ 无法区分「真争用」与「一个跑完另一个见空集」。**判「并发测试通过」前必须先证「争用真的发生过」**。

### F-3（2026-09-13）：环境事实订正——阶段 4 环境并非「无网关」

详见 §4.1 的二次订正。此处只挂索引，不重复。

### F-4（2026-09-13）：T-4.7 三条故障注入**全部通过**（E-19 → E-18 → E-20）

真机注入，非探针资产。判据均为「投唯一标识 trace → 注入 → 恢复 → 断言该 trace 的 `trace_judge_state` 行」，**不是只读日志**。

| 注入 | 形态与时长 | 判据 | 取证 | 结论 |
|---|---|---|---|---|
| **E-19** ES 不可用 | `stop shared-elasticsearch`，03:46:5x–03:52:33 | 判定/聚类/回流不受影响；ES 侧并「显式丢弃 + 计数」 | 注入期间 `t47-es-b1` 完成 `judged 0→1`（03:51:29）；`t47-es-i1` = `judged=1, processed=1`（**聚类亦跑**）；心跳 doc `dropped={'es_fail': 2, 'schema': 3}` | **通过** |
| **E-18** Kafka 不可用 | `stop shared-kafka`，11:58:00–11:58:59 | 消费侧退避挂起不崩；**不提交空推进**；恢复续拉不丢 | 库层 `Marking the coordinator dead` / `Will retry` 循环；CONSUMER-ID 停机前后**完全相同** ⇒ 同一实例重入组；offset **8→11** 恰为停机后新投 3 条，无跳号 | **通过** |
| **E-20** MySQL 不可用 | `stop shared-mysql`，12:01:11–12:02:17 | **不提交 offset**（禁「丢弃并提交」）；恢复后判定不丢 | 注入期 offset **停留 11** / LOG-END 14 / **LAG 3**；日志 `step4 落库失败退避重试（不提交 offset）` WARNING；恢复后 **14/14 LAG=0** 且 `t47-mysql-i1` 判定行落库 | **通过** |

**E-20 是三条中信息量最大的一条**：它是 E-19 的**反向分支**——E-19 允许「丢弃 + 计数」（ES 非判定源），E-20 **明令禁止**同类处置。两者同时成立，才说明「处置口径按依赖的重要性分级」而非一刀切。

**共性环境事实（三条同源，值得单列）** —— `docker stop <容器>` 造成的不是「端口拒绝」而是 **DNS 名字消失**：三条注入的应用侧报错一律为 `Name or service not known`（E-19 `ClientConnectorDNSError` / E-18 `[Errno -2]`）。⇒ 本环境用 `stop` 注入，模拟的是**服务发现层不可达**；若要模拟「进程崩但容器在」，须改为容器内 kill 进程。

**E-19 的结构性观察（登记，非缺陷）** —— form A 的 dropped 计数**唯一持久化出口是写 ES 自身**（`consumer/main.py:322` ⇒ `_es.index`），且 `DroppedCounter.per_agent()` 文档明写「写完不清零 = 累计口径」、纯进程内。故：**注入期间「计数可见」根本不可验**，只能在 ES 恢复后、且以「进程未重启」为前提取证。若 ES 长期不可用且进程重启，**丢弃计数会静默归零**——这是自监控面的固有盲区，spool 归二期。

**未验（不得当结论引用）** —— detail §14.2 E-19 另有一条判据「**该小时 rollup 缺口标注**」，本轮**未覆盖**（ES 停机期未观察 `rollup_job` 侧的缺口登记行为）。

**顺带取证的探针事实（勿再试错）** —— ① **残缺 trace 不落判定态**：只投一条 `node=request`（无终态/无 error 子节点）时 `trace_judge_state` **零行**，必须投完整三事件（`request` + `llm_call` error + `log`）才落行；② TTL 实测 **300s**（`ttl_until` − 投递时刻）；③ `dev.obs.agent.good-question` 消费组下 `schema` 计数只按**被拒事件**累加，可反推投递次数。

### F-5（2026-09-13）：`_backoff` 的「共用」措辞与实现不符——step4 实为非递进重试（**仅登记，不改码**）

`consumer/main.py:332` `_backoff(attempt)` 是真指数退避（1/2/4/8…cap 30s），docstring 称「**step4 重试与 ES 重试共用**」。但调用处：ES 路径（`:264`）传 `attempt` ⇒ 真退避；**step4 落库路径（`:245`）传常量 `_backoff(1)`** ⇒ 固定 1s，**不递进**。

实测吻合：MySQL 停机 66s 内重试 13 次（观测间隔约 4.3s ≈ 1s sleep + 3.3s DNS 解析失败），**非指数拉开**。同 `:203` 亦为常量 `_backoff(3)`=4s。

⇒ 措辞偏差（日志亦称「退避重试」），**非缺陷**——固定间隔对恢复时延反而更有利。按阶段 4「发现即登记、不顺手改」口径处理。

**✅ 处置（2026-09-14，按待定项①「按类分流」）** —— 已改 `app/consumer/main.py` 的 `_backoff` docstring：删去误导性的「step4 重试与 ES 重试共用」，改为**显式列出两处调用档位不一致**（ES 传递进 `attempt` 真指数；**step4 固定传 1 ⇒ 实为 1s 定长退避**）并标注本条编号。**仅订正措辞，行为一字未改**（返回值逻辑未动）；ruff 干净、453 passed 无回归。

### F-6（2026-09-13）：T-4.9 **非网关半边五条断言全部通过**

| 断言 | 结论 | 取证（均为真机） |
|---|---|---|
| 交付物边界（仅 backend + frontend） | ✅ | `docker-compose.yml` 头注释明写「仅 backend + frontend，不含任何中间件」；`services` 实为 backend / worker / frontend（worker 与 backend **同镜像同 env**，不构成第三份交付物）。宿主 `backend/` 下的 6 个一次性脚本（`gen_demo_trace.py` / `metrics_s5_probe.py` / `run_rollup_once.py` / `verify_7d_backfill.py` / `verify_s5_agents_probe.py` / `s5out.txt`）**均被 `.gitignore` 覆盖**（`backend/gen_*.py` / `backend/metrics_s5_*.py` / `backend/s5out.txt`）⇒ 不入交付物 |
| `.env` 注入 + 凭证不入镜像 | ✅ | **取镜像本体**：`docker run --rm --entrypoint sh agent-evaluation-online-backend -c 'ls /app/.env'` → **No such file**；镜像 `/app` 仅 `alembic`/`alembic.ini`/`app`/`pyproject.toml`/`build`/`egg-info`。Dockerfile 只 `COPY pyproject.toml ./` + `COPY app ./app` + `COPY alembic ./alembic` + `COPY alembic.ini ./`；`.dockerignore` 含 `.env`；本仓 `ENV` 仅 `PYTHONDONTWRITEBYTECODE=1`；`docker history` 无应用密钥（命中项全属 `python:3.11-slim` 基础层，如 `GPG_KEY`） |
| `{env}.` 前缀在库·index·topic·group 全链路一致 | ✅ | 运行时实测：`select database()` = **`dev.obs`**；`consumer_group` = **`dev.obs.consumer`**（Kafka `--describe` 复核同名）；`agent_topic` = `dev.obs.agent.<name>`、`selfmonitor_topic` = **`dev.obs.selfmonitor`**（Kafka topic 列表复核）；`event_index_prefix` = `dev.obs-event`（ES 实测索引 `dev.obs-event-202637`）、`log_index_prefix` = `dev.obs-log`。**单点来源 = `config.py:25` `resource_env="dev"`** |
| backend 容器不映射 3306/9200/9092 | ✅ | `NetworkSettings.Ports` = **`map[8000/tcp:[]]`**（仅镜像 `EXPOSE`、**零宿主绑定**；`ports:` 段被注释掉，注释原文即「需要宿主直连调试时临时加，用后移除」）。`obs-worker` 同 |
| offline↔online 走内网不经公网网关 | ✅ | 中间件寻址全为**网络内服务名**：`db_host:db_port` = `mysql:3306`、`es_url` = `http://elasticsearch:9200`、`kafka_bootstrap` = `kafka:19092`；compose 网络 = `external: true` / `shared-infra_shared-infra` |

**下移项（不在本条）** —— 「终止 TLS / `{env}` 子域路径 / 前端登录走网关 / SSO 透传 / 绕过网关直连 backend 被拒」整块已于 2026-09-11 下移 **T-5.3 上线门**（见 §4.1）。

### F-8（2026-09-13）：T-4.10 边界调研 —— 裁定「非网关项整体下移 T-5.3」；**速率闸「未实现」的判断被取证推翻**

**裁定（2026-09-13 拍板）**：T-4.10 本次**只验 online 侧已实现的四条**；**速率闸 / agent_credential 轮换 / Kafka SASL·TLS + topic ACL 三项整体下移 T-5.3 上线门**（与网关同口径）。

| 要求 | 实现形态 | 状态 |
|---|---|---|
| 角色矩阵越权被拒 | `api/deps.py` `require_viewer`/`require_admin`，且**查库保 role/status 最新**（非纯 claims 信任） | ✅ 可验 |
| **token version 吊销** | **全仓无 `token_version` 字段**——但 `api/auth.py:7` 注释**明写它就是「refresh 轮换 + 旧 session 吊销」的别名**；实体 = `UserSession.revoked_at` + `User.status`（禁用即吊销）+ `auth.py:115` 轮换即吊销旧会话 | ✅ 可验（**形态不同 ≠ 未实现**） |
| pull-API `case_type` 白名单 | `api/pull.py:94` 非白名单**返 200 空集而非全量泄漏** | ✅ 可验 |
| 未授权 topic 丢弃并计数 | `DropCode.AGENT_MISMATCH` + `DroppedCounter` | ✅ 可验 |
| **每 agent 上报/回流量级速率闸** | ⚠️ **见下「更正」**——网关侧有限流，但**按 agent 维度**的上报/回流速率闸**未见** | 下移 T-5.3 |
| agent_credential 加密轮换 | 表结构支持（`secret_cipher` / `rotated_at` / `active` 齐备），**无应用侧执行逻辑** ⇒ 属性上是**运维动作**（脚本/人工轮换后置 `rotated_at`），不是应用功能 | 下移 T-5.3 |
| Kafka SASL·TLS + topic ACL | infra 侧 | 下移 T-5.3 |

**⚠️ 更正（2026-09-13，本条目初判把「未实现」写错了）** —— 我最初据「app 全仓 grep `rate_limit` 零命中」判「速率闸未实现」；补查 infra 时**又一次**得到零命中，遂加固了该判断。**两次零命中都是假证据**：第二次的直接成因是**路径错位**——shell 的 cwd 停在 `backend/`，而我搜的是 `../infra`（= `agent-evaluation-online/infra`，**不存在**）⇒ grep 静默返回空，我却把「空」读成了「无」。改用绝对路径后真相 = `/d/study/aiprojcet/infra/api-gateway/conf.d/gateway.conf` **有 7 个 `limit_req_zone`**（global 30r/s、gq_chat 2r/s、cs_chat 2r/s、cs_auth 5r/m、cc_api 10r/s、sp_api 10r/s、eval_api 10r/s），并在 `nginx.conf:45` 应用 `limit_req zone=global burst=50 nodelay`。

**但两者不是同一件事**：网关限流按**来源 IP × 端点**（面向 chat/业务 API），T-4.10 要求的是「**每 agent 上报/回流量级**」的速率闸——**后者仍未证实存在**。故本项的准确表述是「**未见按 agent 维度的速率闸**」，**不是「未实现」**；定论需在 T-5.3 连同网关一并做。

**执行结果（2026-09-13，探针 21/21 PASS）** —— 上表四条已于本笔**跑完**（原「尚未执行」声明作废）：

| # | 断言 | 结果 | 备注 |
|---|---|---|---|
| A1 | 无 token 打 `/auth/me` | ✅ 401 | — |
| A2 | viewer 登录 | ✅ 200 | — |
| A3 | viewer 打 `/auth/me` | ✅ 200 且 `role=viewer` | — |
| A4 | **viewer 打 admin-only**（`POST /backflow/links/{id}/requeue`） | ✅ **403 `ERR_AUTH_0002`**「角色不足（需要 admin）」 | `deps.py:44` |
| A5 | admin 登录 | ✅ 200 | — |
| A6 | **admin 打同一端点** | ✅ **404 `ERR_CLUSTER_0001` link 不存在** | 对照组：证明 A4 的 403 来自**角色**而非路由/载荷 |
| B1 | `status=0` 后**同一 access token** | ✅ 401 `ERR_AUTH_0001`「账号不存在或已停用」 | `deps.py:33` 查库 |
| B2 | `status=0` 后重新登录 | ✅ 401 | `auth.py:75` |
| B3 | 恢复 `status=1` 后**同一 token** 又 200 | ✅ 200 | **B 组命门**：同一串 token ①停用前 200 ②停用中 401 ③恢复后 200 ⇒ 该 401 只可能来自**服务端查库**，与 token 自身有效期无关（access 15min 窗内） |
| E1 | refresh 轮换 | ✅ 200 且发新 refresh | `auth.py:115` |
| E2 | **旧 refresh 二次使用** | ✅ 401「refresh token 无效或已过期」 | 轮换即吊销旧 session 行 |
| E3 | logout | ✅ 204 | — |
| E4 | **登出后原 refresh** | ✅ 401 | session 行吊销**即时生效** |
| E5 | 登出后**该 access** 仍 200 | ✅ 200 | **设计内残窗**：access 为无状态 JWT，登出只吊销 session 行，access 存活至过期（≤15min）。`auth.py:4-6` 已显式声明「access 15min 短效覆盖最小闭环」，**非缺陷** |
| C1 | 真机 · 无 evaluator 凭证打 `/pull/payloads` | ✅ 401 `ERR_PULL_0001` | fail-closed（`config.py:53`） |
| C2 | 真机 · **平台 JWT** 打 `/pull/payloads` | ✅ 401 `ERR_PULL_0001` | `/pull/*` 不接平台 JWT（`deps.py:8`） |
| C3 | 非白名单 `case_type` | ✅ **200 且 `payloads=[]`** | 非 4xx、非全量 |
| C4 | 非白名单 + **垃圾游标** | ✅ 仍 200 空集 | **可判别对照**：证空集是**提前 return**，不是「查询返空」 |
| C5 | 对照 · 白名单 + 同一垃圾游标 | ✅ **400 `ERR_PULL_0002`** 游标解析失败 | 与 C4 同入参、仅 `case_type` 不同 ⇒ 分支差异被隔离到 `pull.py:94` |
| C6 | 对照 · `schema_version='9.9'` | ✅ 400 `ERR_PULL_0002` | 校验链确实在跑 |
| D1 | 跨 agent 伪报事件 → 心跳 `dropped.agent_mismatch` | ✅ **增量恰 +1**（base 0 → after 1） | 心跳全量 `{agent_mismatch:1, es_fail:2, schema:5}` |

**「吊销即时生效」的口径补充** —— F-8 原表把该项记作「refresh 轮换 + 旧 session 吊销」的别名，而 **B 组只覆盖了 `User.status` 半边**（账号禁用）。故本笔**补 E 组 5 条**覆盖 session 行级半边（轮换吊销 / 登出吊销）。**两半合起来才是该项的完整验证**——只跑 B 就报「吊销已验证」是不成立的。E5 另记下一条**设计内残窗**（登出后 access 仍有效至过期）。

**A 组的覆盖边界** —— admin-only 端点共 4 个（`backflow.py:776/796/820/846`），A4/A6 只打了其中 `links/{id}/requeue`。四条**共用同一个 `AdminUser` 依赖**（`deps.py:44`），故该依赖是真判据、逐条打属冗余；但仍**如实记为「按依赖覆盖，非按端点穷举」**。

**C 组的取证边界（显式标注，否则易被读成「全真机验过」）** —— 本环境 `backend/.env` **未配 `EVALUATOR_SERVICE_SECRET`**（实测值长 0）⇒ `/pull/*` **整面 401**，故 **C3~C6 是进程内 ASGI** 跑的（`create_app(Settings(app_env="test", evaluator_service_secret=<临时值>))` + `httpx.ASGITransport`）：**真 app 对象、真依赖链、真 DB，仅凭证取临时值**，且**不走 lifespan**（避免在探针进程里另起一个 Kafka 消费者）。**C1/C2 是真机网络路径**。⇒ 「白名单返空集」的结论强度 = **实现层已验、部署层未验**。

**D 组的基线注（兼证累计口径）** —— 首次运行基线 = `{es_fail:2, schema:5}`（**无 `agent_mismatch` 键** = 0）→ after 1；补跑 E 组后**第二次**运行基线 = `{agent_mismatch:1, es_fail:2, schema:5}` → after 2。**两次增量都恰 +1，且基线随上次结果平移** ⇒ ①该计数确为 **`DroppedCounter` 进程内累计口径**（与 `per_agent()` docstring 相符）；②判据取**增量**而非绝对值是必要且充分的。`es_fail`/`schema` 两项**非本探针产生**（来源未追；较 E-19 时的 `schema:3` 多 2——本探针不投非法事件，仅投 1 条 `agent_mismatch`）。

**顺带浮出的部署侧事实（登记，非缺陷）** —— `evaluator_service_secret` 未配置 = **设计内的 fail-closed**（`config.py:53` 原文：「未配置 = fail-closed（`/pull/*` 全 ERR_PULL_0001 401），不进 `_validate_secrets` 强校验」），offline 侧「部署时同持」是既有约定。故 **dev 环境平台间拉取链路整条不可达属预期**。对阶段 4 的直接影响：**任何依赖 `/pull/*` 真机链路的验收条目（T-4.13/T-4.14 中涉拉取者）在本环境只能验到 401**，须待 T-5.3 配置该凭证后真机复验。**登记，不改码、不改 `.env`。**

**方法论留痕（同族第三次）** —— ① `token_version` grep 零命中 → 差点报「已实现项为缺口」；② 速率闸两次 grep 零命中 → 据「空」下「不存在」。**共同根因 = 把「搜索返回空」当成「对象不存在」，而没先证明「我的搜索确实能命中」**。⇒ 规则：**任何「未找到」结论，必须先跑一个「已知存在的对照样本」验证搜索路径本身有效**（本例对照样本 = 先 `ls` 确认目录存在）；路径含 `..` 时尤其要 `pwd` 核对。这是 [[existence-is-not-reachability]] 的**取证侧镜像**：前两形态管「对象是否可达/归属」，本条管「我的观测手段是否真的触到了它」。

### F-7（2026-09-13）：T-4.9 执行期两个发现——**取证方法本身会骗人**

**(1) `obs-frontend` 容器已 `Exited (0)` 42 小时——「前端在跑」是过期前提。**
早前会话记录「前端 `localhost:18080` 可达」（`docker ps` 当时确为 Up）**已是旧状态**；现 `docker ps` 只有 `obs-worker`/`obs-backend`，`docker ps -a` 显示 `obs-frontend | Exited (0) 42 hours ago | ports=`。`.env` 里 `FRONT_HOST_PORT=18080` 仍在，一旦拉起即恢复映射。**影响**：§1 中 T-4.11 的浏览器 e2e 结论是「2026-09-10 当次会话」的，**当前环境前端未运行**，任何浏览器类复验须先 `docker start obs-frontend`；且不得据「容器存在」推断「服务在跑」——`docker inspect` 对已退出容器同样成功。

**(2) 「运行中容器里有 `.env`」≠「凭证入了镜像」——本次差点误判为缺陷。**
`docker exec obs-backend ls /app/.env` **返回存在**（581B，时间戳 = 宿主文件时间），初判「凭证入镜像」**是错的**：compose 对 backend 有 `./backend:/app` 开发热挂载，该 `.env` 是**宿主文件被挂进去的**。**正确取证 = 绕过 bind mount 取镜像本体**（`docker run --rm --entrypoint sh <image>`，或 `docker create` 后 `docker cp`）。⇒ 泛化：**凡是「运行时观测到的文件/端口/环境变量」，都要先问一句「它是镜像内容，还是编排层注入/挂载进来的」**——前者是交付物缺陷，后者是部署形态，两者结论相反。此为 [[existence-is-not-reachability]] 在交付物取证上的同族形态：**存在性证据必须先定位「这份存在由谁提供」**。

---

### F-9（2026-09-13）：T-4.8 结构型四条**实测通过（16/16）**——附一次**自我划线订正**（J5 实为容量型）

探针 `t48_probe.py`（**临时资产、未落仓**，`docker cp` 进 `obs-backend` 执行）；真机 HTTP + 真 ES + 真库直驱。原表「**零覆盖**」措辞此处订正：`test_tdigest`/`test_metrics` 是单测属实，但结构型四条本地可验。

**① J2 `metric_agg_*` 生效（缓存 TTL）** — 观测面 = ES `search.query_total` 增量（乘法型观测量，非布尔置位）。
冷请求 +2、同参第二次 **+0**（命中缓存、未触 ES）、TTL=60s 到期后再 +2。
- **坑（首轮真栽）**：缓存是**进程级共享**的，上一轮 J2.3 刚把条目焐热 ⇒ 本轮「冷请求」根本不冷（实测 `q0=q1=106`，FAIL）。修法 = 测冷请求前先 `sleep 62`。
- 顺带：一次 `/metrics/overview` 打 **2** 次 ES，故增量是 2 非 1 ⇒ 断言写 `>0` / `==0`，不写 `+1`。

**② J3 trace 检索上限** — `page_size=201` → 422；`=200` → 200（cap 值本身放行）；`page=2&page_size=200`（offset=200）→ 400 `ERR_TRACE_0002`。

**③ J4 判定态单行写 P95** — 真库直驱 `apply_event`，`N=150` × 两条路径：INSERT **p95=6.85ms** / UPDATE **p95=5.23ms**，均 ≤10ms；且 `fx.affected` **150/150 全覆盖**——这条是防「快了但根本没写」的假绿。前缀 `t48-bench-` 隔离，跑完残留 **0**。
- **措辞订正**：task.md 写「判定态 **upsert**」，实现实为 **ORM 读-改-写**（`state.apply_event`）+ `uk_trace`（`agent`+`trace_id`，`error_flow.py:226`）唯一键兜底，**不是** `INSERT ... ON DUPLICATE KEY UPDATE`；探针区分 INSERT/UPDATE 双路径即此形态的证据。

**④ J5 rollup 单轮耗时 —— 必须逼出 `rebuilt_hours>0`，否则整条判据是空的。**
`run_rollup` 先做**廉价探测**（`_decide_recompute`：meta 源计数未变即 skip），不逼的话全 6 小时 skip、耗时 **≈0.05s**——那是**探测耗时不是 rollup 耗时**（首轮实测即 `rebuilt=0 / skipped=6 / 0.05s`，**假绿**）。
逼法 = **删窗口内一小时 meta doc** → 下轮见 `meta is None` → 真重算 → **重算即把 meta 写回**（自愈）。实测 `rebuilt=1 / skipped=5`，且 meta 计数一致、该小时组 doc 条数不变、全库 meta 数复原（**幂等零残留**）。三个坑：
- **删窗口外**的 meta 不触发重算（只扫最近 `late_k=6` 个已完成小时）⇒ 照样 `rebuilt=0`；
- meta 的 `hour` 是**字符串** `hour_key_of(ms)`，与 `_late_hour_starts` 返回的 **epoch ms 不同型**，直接比对永不命中；
- **测量假象**：`es.get` 是 realtime、`es.count` 走 search 视图受 refresh 影响 ⇒ 不 refresh 会把「刚写回但未 refresh 的 meta」量成**假残留**（224→223）。

**⑤ 自我划线订正（本轮最该记的一条）**：我把 J5 划进「结构型四条」**是错的**——`≤2min` 是**容量阈值**。本库 224 个小时的源事件**最大仅 68 条、均值 14.4**，重算轮实测 **0.06s** ⇒ 与已下移 T-5.3 的容量型三条（1/6/7）**同类、同属无判别力**。
J5 真挣到的是**四条结构型事实**：真重算轮确实会发生 / meta 自愈 / 组 doc 幂等 / 零残留；**阈值本身下移 T-5.3**。
⇒ 泛化：**「结构型形状 + 容量型语义」的判据要按语义归类**，不能因为「能在本地跑」就当成结构型——本地数据量不够时，跑绿只是把无判别力包装成了有判据。

**残留（下移 T-5.3）**：全站 24h agg P95 ≤5s、t-digest 合并误差 <1%、500 事件·s⁻¹、rollup 单轮 ≤2min 的**容量含义**。
`metric_agg_timeout_ms=3000` 的超时半边**已由单测覆盖**，非集成档位。

### F-10（2026-09-13）：T-4.13 ②④⑥ + T-4.14 ①②⑥ 边界/死角探针**实测通过（33/33）**——含一次**假红**与一次**破坏性取证被拦**

> ⚠️ **订正（同日，见 F-11）**：「33/33 通过」的**唯一含义 = 我写的 33 条断言都成立**，
> **不等于**「这 6 条边界验完了」。经**独立复核**（另起 agent，只读 detail §14.5 原文、不看本文件与探针）
> 查出**六处真实漏验**（含原文点名「E-13 集成复验」的一条），以及**一条实质性发现**（X-8 前半的
> 「7d 聚类窗」在实现层无判别对象）。**本节不得单独作为「T-4.13 ②④⑥ / T-4.14 ①②⑥ 已验收」的证据引用。**

| 编号 | 断言内容 | 结果 |
|---|---|---|
| X-2 脱敏死角（6） | 干净 input 零命中 / 已掩码 `***` 放行 / `null` 放行 / 对照·明文命中且可追踪 / 嵌套 >`_MAX_DEPTH`(100) 不炸栈 / 100k 超长值正常检出 | 全 PASS |
| X-4 检索注入（6） | 对照样本有命中 / 保留字符串零命中 / 引号串归因 / 撇号零命中 / 中文分词边界不 5xx / **`keyword=*` 零命中（决定性）** | 全 PASS（修正后） |
| X-6 大对象边界（4） | 恰 8192 不截断 / 8193 截断且标位 / `None` → `(None,0)` / 超限 dict 序列化后截断 | 全 PASS |
| X-7 时间边界（5） | epoch 0 → 1970-W1 / **2021-01-01 UTC → 2020-W53（ISO 跨年）** / index 名 `{prefix}-yyyyWW` 补零 / 周边界 UTC 两侧分属不同周 / 未来 ts 不抛异常 | 全 PASS |
| X-8 窗口边界（6） | `1h`/`24h` → realtime 且 `fallback_hours=[]` / `7d` → `mixed` 形状不破 / 窗口外老小时不在 `_late_hour_starts` 扫描集 / **整轮 rollup 前后老小时 `updated_ts` 未变** / 扫描小时数 == `late_k` | 全 PASS |
| X-12 词表死角（5） | 前缀·空白·大小写·换行·超长·重复原样保真进快照 / `str`/`None` 脏列值降级 `[]` / 单元素极短表照建 / **缺 agent 行 → `([], 0)`** | 全 PASS |

**① 假红：我最初的 X-4 判据是错的，不是代码有缺陷。**
原判据 `200 且 items==0`（要求注入串零命中）把 `it's a "quote"` 判 FAIL（实测 1 条）。
逐 token 归因（`x4probe.py` → `x4d.py`）后定音：

| keyword | 命中 |
|---|---|
| `it's a "quote"` | 1（`t1-checkout-0001`）|
| `s` / `3` / `3s` / `超时` | 1，**均为同一条 `t1-checkout-0001`** |
| `it` / `its` / `quote` / `a` / `t1` / `checkout` | 0 |
| `'` / `*` / `OR` / `--` | 0 |
| 无关键字全量 | 200（= `page_size` 上限）|

⇒ 真因：**`multi_match` 默认 OR 语义**下，`it's` 被 standard analyzer 拆出单字符 token **`s`**，
与库内样本 `'意图识别接口 3s 无响应（重试分支）'` 的 `3s` 逐字命中——**引号零语法贡献**
（`'` 单独零命中、`"quote"` 零命中、`*` 零命中已证无 `query_string` 语义）。
⇒ 判据修正为**归因式**：`引号串命中数 == 其拆出的库内 token('s') 命中数 且 < 全量`，
并补 `X-4.6 单独撇号零命中`、`X-4.7 中文分词边界不 5xx`。
**教训**：**注入类判据不能只写「不为 0」，要写「等于谁」**——不为 0 既可能是缺陷，也可能是 OR 语义的合法结果，两者用同一条断言区分不开。

**② X-8 原取证法被自动分类器拦下，且拦得对。**
初版 X-8.4/X-8.5 靠「**删掉窗口外老小时的 meta doc**，跑整轮 rollup，断言它没被重建」取证——
特征版**在共享 `dev.obs-metrics-rollup` 索引上留永久空洞**，且该删除**非必要**（`updated_ts` 零变更即可证同一件事）。
已按零变更重写：读老小时 meta 的 `updated_ts` → 跑一整轮 → 断言**未变**，另补 `rebuilt+skipped == late_k` 证无窗口外小时被顺带扫描。**全程零写入。**

**③ 范围调整（本轮口径，与 §2 一致）**
- **X-13 保留期下移 T-5.3**：detail §14.5 该条**原文自写「衔接 T-5.2 保留期」**，本阶段无保留期策略可验。
- **X-10 数量级边界折半下移**：其 `page_size≤200` / 深翻页守卫半边**已由 T-4.8 J3 覆盖**（同一守卫复用），容量半边归 T-5.3。
- 本轮实做 6 条结构型：X-2 / X-4 / X-6 / X-7 / X-8 / X-12。

**探针**：容器内 `/tmp/t41314.py`（临时资产，**不入仓**），复跑：`docker cp` 进 `obs-backend` 后 `python /tmp/t41314.py`。

### F-11（2026-09-13）：**独立复核揭出 F-10 的覆盖缺口**——「N/N 全绿」不构成「该条已验完」

**方法（信息边界是这次复核的全部价值）**：另起 agent，**只允许读** `solution_detail.md` §14.5 原文（+ 为理解判据必需的其它章节）+ 产品代码 `backend/app/**`（用于确定观测面）；
**禁止读** `docs/integration-report.md` 与 `backend/tests/integration/**`。要求它**独立推导「应该断言什么」**，并禁止给出通过/失败结论。
⇒ 得到一条**与我推导过程无交集**的对照。**差异本身就是复核输出**，无论谁对。

**① 两条自我怀疑被否证（复核的正面产出）**

- **X-13 / X-10 的下移理由成立（原文级）**：
  - Q2 取出 `solution_detail.md:1509` 期望列**逐字原文** = 「`ILM 30 天删除后检索与看板缺口标注行为（衔接 T-5.2）`」；`task.md:163` 定义 **T-5.2 属阶段 5**。复核另指出 **ILM 本体不在本仓**（§5.2 逐字「index template/ILM 由平台提交、infra 建」），且**「看板缺口标注」与 ILM 无因果连接**（缺口由 rollup meta 缺失派生，源 index 被删不影响已落的小时桶）——下移的正当性比我的原理由更强。
  - Q1 判定 X-10 的「数量级边界」**就是** `MAX_LIST_RESULTS = 200`（`backend/app/store/es.py:22`）这同一个上限，由**同一个端点**两处衔接实施：入参上界 `trace.py:111`（`le=MAX_LIST_RESULTS`）+ 深翻页守卫 `trace.py:113-117`（`offset >= 200` → 400 `ERR_TRACE_0002`）。**与 T-4.8 J3 验的是同一处守卫** ⇒ 「守卫半边已覆」成立。
    复核另补一条我从没注意的**不同源同名值**：`/logs` 端点 `trace.py:205` 的 `le=200` 是**硬编码字面量**，**不受 `MAX_LIST_RESULTS` 约束**；单 trace 详情上限是 **500**（`es.py:23`），与 200 无关。

- **X-4 的「归因式判据」被独立复现**：复核在**没看过我的修正**的前提下自行推导出——
  「『不误命』必须写成归因式：期望命中集合 = 由该串拆分出的各 token 单独查询结果集合的**并集**；
  不能只断言『命中数 ≠ 0』（`multi_match` 默认 OR + 分词会把串拆成 token，与库内已有文本合法命中，
  **无法与「注入穿透」区分**）」。
  ⇒ **两条独立路径收敛到同一条判据**，比我在同一套查询链上反复自证强得多。此前「归因是否属自证」的自我怀疑就此否证。

**② 六处真实漏验（F-10 的 33 条没覆盖原文要求的这些）**

| 用例 | F-10 已验 | **原文要求但我未验** |
|---|---|---|
| X-4 | 不 5xx / 不全量 / `*` 零命中 / 引号归因 | **「不返回错误 scope」**——keyword 与 `agent`/`interface`/`ts` 组合时返回行 `agent` 必须**全等于**传入值。**这是注入的真风险面（filter 被破坏），我只验了查询体本身** |
| X-6 | `snapshot_input` 纯函数 4 条 | **「缺 input 残现场只计数」的组装侧**（`assemble_cluster` 返回 False、**不建 link**）——原文**点名「（E-13 集成复验）」**，我只验了纯函数返 `(None, 0)`；**`truncated` 一路复制到 `payload.verify_status` 的链路**（state→cluster→link→envelope→verify） |
| X-7 | 纯函数索引归属 5 条 | **「跨周检索去重不重不漏」**（原文明确写的）；**`date_histogram` 分桶** |
| X-8 | 仅 rollup 窗口那半 | **前半整块**：「同键恰 7d 聚类窗边缘（第 7 天 vs 第 8 天）→ count+1 vs 新开代」；以及「缺桶回退实时 **+ 页面标注**」「**尾小时实时补齐**」（我只验了 `7d` 的 `source=mixed` 形状，没验 `fallback_hours` 的**内容语义**） |
| X-2 | 6 条（顶层键） | **大小写变体**（`Authorization`，`IGNORECASE`）；**列表内嵌套键路径**（`input.a[0].password`，我只验了顶层键）；**「可追踪」= 丢弃计数落库**（`dropped.mask` 自监控心跳，需真 Kafka+ES） |
| X-12 | 5 条 | **版本同源断言**：`assert.no_fallback.config_ref.wordlist_version == no_fallback_config.wordlist_version` |

**③ 一条实质性发现：X-8 前半的「7d 聚类窗」在实现层无判别对象**（**我已自行 grep 复核确认**）

- `cluster_window_days` 全仓仅 **2 个**命中：`backend/app/core/seed.py:46`（写库默认值）+ `solution_detail.md:1285`（口径表）。**零读取点。**
- `pick_merge_target`（`backend/app/analyzer/cluster.py:49-69`）签名只收 `reopen_after_terminal`，**不接收任何时间输入**；分支只看 `status` / `generation`。其 docstring 第 56 行把「**窗内**同键新现」与「root-late 同键 open」**并列在同一个 `count` 分支** ⇒ **时间对该分支根本不参与判断**。

⇒ 「第 7 天 vs 第 8 天」这个用例，按现状写出来只能验到「**无论隔多久，只要簇仍 open 就仍 count+1**」——**与 §6.2 表的意图（超窗静默转 inactive）不符**。

> **边界声明（勿读成更强）**：仅核了该纯函数及其调用链上的这一处，**未穷举**是否有别处按 `latest_ts` 预过滤候选集。
> 按既有教训，「grep 未命中读取点」比「不可达」证据强，但**不等于「整条链上都不存在」**——**定性前需再走一遍 `merge_candidate` 全文**。

**④ 复核顺带报出的文档问题 —— 逐条复核后 2026-09-14 收口（定音 = 4 条真错 + 1 条口径模糊）**

> **收口结论**：五条全部已处置，落 `solution_detail.md` **v1.24 修订记录** + 表内 6 处订正。**零代码改动、零判据实质变更**。下为逐条裁定（★ = 复核所说属实）。

- **三条尾锚指错**：X-2 尾锚 `§4.5`（本文件 §4.5 是「顺序与还原」，脱敏正文在 §2.6/§4.2/§13.4）；X-7 尾锚 `§2.1`（周滚动正文在 §5.2）；X-13 尾锚 `§7.1`（存疑：可能是跨文件锚指 `solution.md` §7.1）。
  - **裁定 = ★ 三条全属实**，且**「跨文件锚」之存疑被否证**。判据 = 本表 `§x.y` 一律为 `solution_detail.md` **内部锚**：同表 X-5 `§7.3/§7.4`、X-4 `§8.2`、X-11 `§1.3/§7.4` 经逐条核对**全部指本文件自身**；跨文件时文中**显式写文件名**（X-5 的「solution §16」）。⇒ X-13 的 `§7.1` 是**指错的本文件锚**，非跨文件引用。已改：`§4.5`→`§2.6 脱敏`、`§2.1`→`§5.2 周滚动`、`§7.1`→`§5.2 ILM/保留期`。
- **X-4 与 X-10 都残留 `search_after` / 「末页后翻稳定返回空」旧口径**，与 §8.2 已 v1.23 订正为「`collapse(trace_key)` + `from/size` 偏移翻页 + `offset ≥ 200` → 400」冲突。
  - **裁定 = ★ 属实（真错）。** `search_after` 属 v1.23 前旧实现口径。X-4 期望列已改为「末页后再翻**稳定返回空 items**（v1.23 口径：`collapse(trace_key)` + `from/size` 偏移翻页，非 search_after）」。
- **X-10「命中恰 200 与超 200 截断」措辞与实现不符**：列表端点**无截断语义**，`Page` 响应只有 `{items,total,page,page_size}`（`schemas.py:44-50`），超 200 是 **400 而**非截断（真正带 `truncated` 的是详情 ≤500 与 anomalies/llm-failures/agents 的 size≤100）。
  - **裁定 = ★ 属实（真错，措辞级）。** X-10 期望列已改为「`page_size` 恰 200 为**入参上界**（`le=MAX_LIST_RESULTS`），`offset ≥ 200` 返 400 `ERR_TRACE_0002` **而非截断**」。
- **X-8 的「指标 24h 实时 vs 24h+1s rollup 路由切换」不可表达**：`window` 是离散枚举 `{1h, 24h, 7d}`，`24h+1s` 会 400 `ERR_METRICS_0001`。
  - **裁定 = ★ 属实（真错）。** X-8 期望列已改为「指标 **1h/24h 实时 vs 7d rollup** 路由切换（`window` 为离散枚举 `{1h,24h,7d}`，不存在 `24h+1s`——越界值直接 400 `ERR_METRICS_0001`）」。
- **X-12 的「动态前缀/拼接/多语言模板改写」判分在 offline**：online 只做固化与透传、不做匹配 ⇒ 该半条**在本阶段环境不可验**。
  - **裁定 = ⚠️ 事实属实，但\*\*不构成判据错误\*\*——属「口径模糊」而非「表述与代码不符」**（与上面四条性质不同）。区分依据 = 该条**从未声称 online 侧做判分**，「行为可观测」是可立的；问题只在**没写明观测面落在哪一层**，导致读的人误以为整个判据在本阶段可验。**处置 = 用户拍板 A：补一句口径明确化、不改判据**（改动大于「改错」小于「下移」，因为「词表固化保真 + 信封透传」这半边在本阶段**确实可验且已验**）。已追加：「**观测面口径**：online 侧可验的是**词表固化保真与信封透传**（`parse_words` 原样进 `no_fallback_config.words`、`resolve_fallback_wordlist` 取 per-agent 版本），**判分/抽查归 offline**——本阶段验前者，后者由 offline 侧承担」。
  - **余下留白（不改）**：X-12 尚未像 X-13/X-10 那样**显式下移 T-5.3**。理由 = 它的判分半边**本就不在 online 仓**（不是「本仓未配环境」，是**职责在另一仓**）⇒ 挂到 online 的哪个阶段都不对，写「归 offline」比写「下移 T-5.3」准确。

**⑤ 本轮结论**

**「N/N 全绿」这句话本身没有判别力**——它只说明「我写的断言都成立」。要回答「这条边界验完了吗」，必须**另有一条不经过我的推导路径**去独立回答「应该验什么」。这两件事看起来都在「测」，**测的对象完全不同**：前者测实现，后者测**我的判据**。

**⑥ ② 的六处漏验补测（2026-09-14 执行完毕 = 25/25 PASS）**

探针 = `%TEMP%\f11gap.py`（临时资产，**不入仓**；`docker cp` 进 `obs-backend` 跑，收尾三表核过**零残留**）。
**六处中补了五处**——X-8 前半已由 F-12 裁定为「实现层无判别对象」（拍板 A），故**不补**、如实记为不可验。

| 原文要求 | 补测断言 | 结果 |
|---|---|---|
| X-4「不返回错误 scope」 | 前置确有 6 个 agent 的 trace；`keyword+agent`（逐 agent）、`keyword+interface`、`keyword+ts` 三组组合下，**每一返回行的过滤字段全等于传入值** + 对照「无过滤命中数 ≥ 各 agent 分别命中之和」 | ✅ 5 条（越界行 0） |
| X-6「缺 input 不建 link」（**原文点名 E-13**） | `input_snapshot=NULL` → `assemble_cluster` 返 `False` ∧ **link 数 = 0**；**对照组**有快照 → `True` ∧ link 1 条 | ✅ 2 条（对照成立） |
| X-6 `truncated` 复制链 | `cluster.input_truncated=1` → `link.input_truncated=1`（随 link 透传）∧ 信封 `evidence.input` 已解析出 `{'q':'hello'}` ∧ `case_type`/`source.cluster_id` 对位 | ✅ 3 条 |
| X-7 跨周去重不重不漏 | 200 条返回的 `trace_id` 无重复 ∧ 无空 `trace_id`（`collapse(trace_key)` 跨周生效） | ✅ 2 条 |
| X-7 `date_histogram` 分桶 | 桶 ts 递增且**对齐声明桶宽** ∧ 相邻间隔 == 声明桶宽 ∧ 各桶 `count` 之和 == `cards.total`（3） | ✅ 3 条 |
| X-2 大小写变体 / 列表内嵌套键 | 大写 `Authorization` 命中（+ 值为 `***` 的**对照**放行）；`input.a[1].password` / `extra.nested.api_key` / `output.list[0].cookie` 三作用面路径全对 | ✅ 5 条 |
| X-12 版本同源 | 同一信封内 `assert.no_fallback.config_ref.wordlist_version == no_fallback_config.wordlist_version`（v=0/7/12345 三取值均等）∧ **决定性**：换入参时**两处一起变**（证同源，非各自独立常量）∧ 空词表 fail-closed 载体 ∧ 真库 agent 缺失 → `([], 0)` | ✅ 4 条 |
| **X-8 前半「第 7 vs 8 天」** | **不补**——见 F-12，实现层无判别对象 | — 不可验 |
| **X-12 保真半边（2026-09-14 追加）** | `parse_words` → `no_fallback_config.words` **逐字保真**（八形态：空串·纯空白·大小写·含换行·5000 超长·重复元素·单字符）∧ 版本 `12345` 两侧同源 | ✅ 1 条（`tests/test_converter_envelope.py::test_words_verbatim_into_envelope`） |

> **X-12 保真半边这笔是 F-11 ④ 收口时的副产品，值得单记**：我在 v1.24 里写下「online 侧可验的是**词表固化保真与信封透传**」后，按惯例回查这句的**取证来源**，结果发现——**它没有可复跑的资产**。F-11 ⑥ 的 X-12 四条（上表）验的是 **版本同源**（`wordlist_version` 两侧相等），**根本没验 `words` 逐字**；唯一声称验过逐字保真的是 F-10 §⑥ 表格里那句「原样保真进快照」，而**那批探针是临时文件、已不存在**，且该表本身挂着「不得单独作为验收证据引用」。
> ⇒ **这正是 F-11 的同构再现**：一个「N/N 全绿」背后，判据里**最强的那半条**恰好是**没有证据**的那半条。区别在于这次是我**主动回查搬运**抓到的（不是独立复核抓的），且**成本足够低**——补一条单测即可永久闭合，故未另立 F 项。
> **判别力已否证式取证**：把 `parse_words` 换成归一化实现（`[w.strip() ...]`）后该断言**转红**（`AssertionError` 落在我新写的第 166 行），证其非恒真。
> **代码级事实**（故「online 侧可验」不是推测）：`no_fallback_cfg.py:21-23` 原样返回入参 list；`envelope.py:83` `"words": list(words)` 浅拷贝不加工；`envelope.py:79/84` 两处 `wordlist_version` **同源同一入参**（非二次读取）。

**⚠️ 本轮抓到两个判据自身的问题（都不是代码缺陷，**两个都是我的判据错**）**

1. **又一次假红（同日内第二次，与 X-4 引号同族）**：X-7 分桶初版**硬编码桶宽 1h**（`ts % 3600000 == 0`），实测窗口 `24h` 用的是 **30 分钟桶** ⇒ 判 FAIL。
   归因：`_WINDOWS["24h"]` 的 interval 本就是 30min（`app/api/metrics.py:346/373`），7d 才钉 `1h`。
   **修法 = 从实现常量取声明桶宽**（`_WINDOWS` + `_BUCKET_WIDTH_S`），不再硬编码 ⇒ **判据的期望值必须来自被验对象自己的声明源**，这也是归因式判据的另一种形态。
2. **一次真空通过（假绿的另一种形态）**：初版对 `window=1h` 取桶，实测**桶数 = 0**（该窗无流量），而 `all(...)` 在**空集上恒真** ⇒ 「桶对齐」「间隔无畸变」两条**真空 PASS**。
   修法 = 加**前置断言**：窗口集合里必须存在 `cards.total > 0` 的窗，选不出即判 **FAIL**（数据不足 ⇒ 不可验，**不得静默通过**）。加前置后桶数=2，两条才成为真判据。

⇒ **两条合起来是一条可复用的判据规则**：**全称量词断言必须先证非空**，**期望值必须取自被验对象的声明源**。二者与 X-4 的归因式判据同族（都在问「我这个判据本身站得住吗」）。

> **待办（未开工）**：④ 的文档口径裁定（三条尾锚指错 / X-4 与 X-10 残留 `search_after` 旧口径 / X-10「超 200 截断」措辞 / X-8「24h+1s」不可表达 / X-12 判分在 offline）。
> **F-10 中「33/33」不得单独作为验收证据引用**；本节的 25/25 **同样不得单独引用**——它的口径见上表（五处补测 + 一处明确不可验）。（③ 已于同日定性，见 F-12。）

### F-12（2026-09-13）：X-8 前半「7d 聚类窗」**定性为未实现**——**权威文档 `solution.md:404` 要求、实现缺失**（非 detail 笔误）

**定性方法**：走代码全链 + 与文档逐条对表。**判据事先定死**（见 F-11）：只要能找到一个按事件时间过滤/归档的点 ⇒ F-11 ③ 不成立。

**① 实现层：零时间过滤（证据是穷举式的，非 grep 未命中）**

| 检查点 | 事实 | 强度 |
|---|---|---|
| 判定入口的候选查询 | `analyzer/cluster.py:173-184` 的 `select(ErrorCluster).where(...)` **只有四个谓词** = `agent` / `interface` / `error_type` / `input_hash`。**无任何时间谓词** | **强**——这是「count+1 vs 新开代」的唯一判据产生处，我读的是该查询语句本身 |
| 判据纯函数 | `pick_merge_target`（`:49-69`）签名只收 `reopen_after_terminal`，**不接收时间输入**；分支只看 `status` / `generation` | 强 |
| `latest_ts` 全部读写点 | 写 **2** 处（`:124` 建簇、`:254` `_apply_count` 刷新）；读 **1** 处（`api/backflow.py:245`，仅为展示转 ISO）。**无任何时间比较** | 强 |
| `inactive` 全部命中 | 全仓命中中**唯一的赋值点 = 人工 `ignore`**（`backflow/claim.py:154-174` 的 `.values(status="inactive")`）；另有 `reopen` 反向。**无自动归档代码** | 强——`inactive` 的全部命中已逐条过目 |
| `cluster_window_days` | 全仓 **2** 命中：`core/seed.py:46`（写库默认值）+ 文档口径表。**零读取点** | 强（限本仓） |

⇒ **「同键静默超窗口 → cluster → inactive」整条未实现**；`cluster_window_days` 是一个**登记了默认值、无人读取**的配置键。

**② 文档侧：**上位权威文档也这么要求** ⇒ 是「权威要求未实现」，**不是**「detail 笔误」**

> ⚠️ **本节曾在校正前写过一版错误判断**（「大概率是 §6.2 表多写了一行」），根因 = **未先枚举站点全集、只读了 detail 就外推**。
> 枚举后才发现 `solution.md`（**权威**）里也有站点，读原文后结论反转。**这是同一天内第三次「只读单侧外推 ⇒ 假证据」**。

| 位置 | 原文 | 与实现 |
|---|---|---|
| **`solution.md:404`（§ 生命周期，权威）** | 「同键**持续静默超窗口 → cluster 转 inactive**（归档，保留最近 ts/计数供查）」 | ❌ **要求，未实现** |
| **`solution.md:744`（表 5）** | 「\| 5 \| **错误聚类窗口** \| 7 天 \| 可配 \|」 | ❌ 键存在但零读取点 |
| **`solution.md:457`** | 「→ **聚类窗口内**同类新错误并入该 cluster，不再生成新用例」 | ⚠️ 前半（「窗内」）恒真、无判别力；后半（并入不新开）已实现 |
| `solution.md:708`（风险表） | 「去重误判/漏判 \| 中 \| 归一化 + **聚类窗口** + per-trace 归并分层优先 + 人工 ignore 兜底」 | ❌ 把「聚类窗口」列为**缓解措施**，而它未实现 |
| `solution_detail.md:184`（§1.5） | 「时间窗口统一口径：错误聚类窗口 7 天、【实现约定】以「error_cluster 首现时间」滚动」 | ❌ 与 `:404` 一致 |
| `solution_detail.md:846`（§6.2 表） | 「**同键静默超窗口** \| cluster → inactive（归档，保留 count/最近 ts/快照） \| —」 | ❌ 与 `:404` 一致 |
| `solution_detail.md:1285`（dict_config 表） | 「`cluster_window_days` \| 全局 \| 7 \| error 去重窗口（§6.2）」 | ❌ 登记了却无人读 |
| **`solution_detail.md:973`（§7.6 状态机表）** | 「`inactive` \| **触发 = ignore** \| → open（反悔/复发重新开）」 | ✅ **与实现一致** |
| `solution_detail.md:1451`（E-4） | 「7d 窗口内同键再现 → 只 count+1，不重复生成 link」 | 前半恒真；后半已覆 |
| `solution_detail.md:1504`（X-8） | 「error 同键恰 7d 聚类窗边缘（第 7 vs 8 天）→ count+1 vs generation 新开（**E-4 补强**）」 | ❌ **无判别对象** |
| `solution_detail.md:1432`（§14 前言） | 「单测聚焦：…去重归一、**聚类窗口**…」 | ❌ 该聚焦项无对应实现 |
| `solution_detail.md:583`（DDL 注释） | 「`count` … -- **7d 窗口内**同键合并计数」 | 措辞误导（无窗） |
| `CONTRIBUTING.md:11` | 「时间窗口统一口径：错误聚类窗口 7d，以 error_cluster 首现时间滚动（detail §1.5）」 | ❌ 同 §1.5 |

**结论订正**：**权威文档（`solution.md`）与 detail §6.2 一致地要求该行为；只有 detail §7.6 这一处表跟着实现走。**
⇒ 真因**不是**「detail 多写一行」，而是 **`solution.md:404` 这条权威要求从未实现**，detail 内部的分歧只是这个事实的投影。
⇒ **处置性质随之升级**：这不是「改一处笔误级的口径同步」，而是「**一条权威要求 vs 一条实现，二选一**」——**必须由你重新拍板**。

**③ 边界声明（勿读成更强）**

- 已核范围 = **本仓实现层 + 本仓全部 `inactive` 命中 + 本仓 `cluster_window_days` 命中**。
- **未核**：`cluster_window_days` 是否被**仓外**（运维脚本 / DB 侧 / 手工 SQL）读取；亦未核是否存在**不经过 `cluster.py` 判定入口**的其它归档路径——但 `inactive` 的赋值点在本仓已穷举，若存在只能来自**直接改库**。
- 故本条定性为「**本仓实现层无此机制**」，**不是**「任何地方都没有」。

**④ 影响面**

- **X-8 前半**（「第 7 vs 8 天」）：**无判别对象**。按现状写用例，只会验到「无论隔多久，只要簇仍 open 就仍 count+1」——**与 §6.2 表意图相反**。
- **§14 前言**「单测聚焦：…聚类窗口…」（`:1432`）：该聚焦项**无对应实现** ⇒ 单测面也不存在。
- **E-4**「7d 窗口内同键再现 → 只 count+1」：**前半（「窗内」）恒真、无判别力**；后半（只 count+1）由 `cluster_probe` 已覆。

**⑤ 补充取证（2026-09-14）：这条**从未被撤销**，但**缺失有真实行为后果****

**a. 修订记录全量核**：全文 grep「归档 / 静默超窗 / 转 inactive」，命中的**唯一引入点 = 修订记录 `v3.4.2`**：

> `| v3.4.2 | 吸收六方向独立评审…cluster 生命周期**重写** 首现即开→静默→归档（§10.2）…`

随后 **v3.4.3 / v3.4.5 / v3.4.6 / v3.5.0 ~ v3.5.10 共 20 版修订，无一处改动、撤销或降格它**；§15 阶段划分也未把它排除在 P2 之外。
⇒ 它是**作为一次修正**（原文理由：「消除首现/静默语义死结」）引入的，**不是遗留笔误**。⇒ 原自我挑战「被 `generation+1` 事实上替代」**不成立**，无任何文档痕迹支持该替代。

**b. §16 那行**不是**独立证据**（原以为的第二来源，实为衍生）：`solution.md:724` 「判定不因 cluster 归档跳过在途 case（防 case pass 而 cluster 永不 fixed）；**仅人工 ignore**（link 已 superseded）的 cluster 停判定」——后半句**恰恰是在描述现状**（只有人工 `ignore` 才停判定）。故全部 15 处站点均为**文档内部自洽，零实现痕迹**。

**c. 但缺失有行为后果（这条推翻了我原挑战 #3 的「只是容量问题」）**：`pick_merge_target` 的 `count` 分支**只要簇是非终态就命中**，而 `inactive` **唯一**赋值点是人工 `ignore`。⇒ 一个**从未被人工处置过**的 `open` 簇，**永远吞并同键新错误、`generation` 永不推进、`first_seen` 永远停在最初那次**——§404「同键再现允许重新开 cluster（generation+1）」在「没人管过的簇」上**永远不触发**。这不是累积，是**行为偏差**。

**d. 未取到的证据（环境所限，如实声明）**：`Docker Desktop` 已停（`docker ps` 报 daemon 未运行），**无法统计 dev 库 `error_cluster` 的 `latest_ts` 分布**。若补实现，这是必须补的前置调研（存量 `open` 簇会被 job 立刻归档）。**本条现状无此数据，不得据 memory 里的「六表回 0」当结论**（那是历史快照）。

**⑥ 处置（2026-09-14 拍板 = A）**

**定性 = 「权威设计已要求、实现缺失」**（非 detail 笔误、非容量问题）。**处置 = 登记 + 并入待定项②（阶段 4 缺陷处置口径）一同拍板；阶段 4 不补实现。**

| 选项 | 内容 | 代价 / 收益 | 裁定 |
|---|---|---|---|
| **A** | 登记为「设计已要求、实现缺失」，处置随待定项② | 代价：§10.2 与 §7.6 的矛盾带进阶段 5，X-8 只能记成「无判别对象」；收益：**验收基线不被污染** | ✅ **选定** |
| B | 现在补实现（候选查询加时间谓词 + 超窗归档路径 + 派生，job 6→7） | 代价：阶段 4 前序全部绿色需重跑；且待定项②未拍板就做了产品行为决策 | ✗ |
| C | 改文档、按现状改写 `solution.md:404` 生命周期 | 代价：把**一个已被证实有行为后果的偏差合法化**（见 ⑤c），且该条 20 版未撤 | ✗ 三者中代价最大 |

**选 A 的核心理由**：本条是**验收阶段发现的范围外需求**，不是「待修缺陷」。补一个 worker job = 改运行时行为 = **验收基线作废**；而待定项②（缺陷处置口径）**本身未拍板**，此时补等于**用一个未定的口径做了产品决策**。

**A 的已知代价（如实记）**：X-8 前半将**永久只能记成「无判别对象」**——除非补实现，否则该用例永远验不到与 §6.2 意图一致的东西。这是选项 A 的真实成本，**不是零成本**。

**⑦ 可复用的流程缺口**：我在 F-12 初版里先下了「是 detail 笔误」的判断，之后才枚举站点，**顺序颠倒导致结论反转**。正确顺序 = **先 grep 定死站点全集（含权威文档），再下判断**。

> **本条与 F-1~F-11 的性质不同**：那十一条是「待处置缺陷」，本条是**已定性的「权威要求未实现」**——定性动作已完成，**剩下的是产品决策**（已于 2026-09-14 拍板 = A，见 ⑥）。
