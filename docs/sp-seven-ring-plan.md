# sp 七环回流「B 方案」改造方案（2026-09-17）

> **状态（2026-09-17 收口）**：改动点 A（根事件硬失败标记）**已实施、已真机验收**，实施提交 = sp `382dc82`；
> **改动点 B（观测入参透传）已撤出本批、单开「环③ 批」** —— 执行时因镜像内 obs_sdk 为旧版而炸掉全 agent 观测，
> 根因与处置见 **§3.4**（该节已整节改写，**勿引旧版**）。其余节次未随此变更改写处，以 §3.4 与 online `task.md` T-5.9b 为准。
> 目标 = **smart-procurement（sp）的七环回流闭环真机跑通**，与已跑通的 good-question（gq）同形、可比。
> 本方案为 **A 级改动**（动核心代码、动观测出口判定），**须先经确认再动手**。
> 取证方式 = 只读读码 + 探索代理全仓核实（未改任何文件）；不含推断，凡未取证项在 §8 单列。

---

## §1 本批命题的精确边界（与 gq 同）

- **修的是**：「LLM 硬失败被业务吞成 SSE error 帧 ⇒ HTTP 200 ⇒ root 记 ok ⇒ 平台按『故障已被业务吸收』把回流候选切掉」。
- **不修**：「让所有子节点 error 都回流」（那是 L3 二期，规格划的界）。
- 判据来源 = 平台 `analyzer/classify.py:156` 子节点候选**仅在 `root_status != "ok"`** 时收集（T-3.10 兜底吸收门控）。

## §2 断口（sp 实测形态，与 gq **不**同形）

| 环节 | 位置 | 实测语义 |
|---|---|---|
| 吞点 ① | `app/ai/agent/agent_loop.py:200-206` | round1 `CircuitOpenError` / 其他异常 → `yield {"type":"error"}` 后 `return` |
| 吞点 ② | `app/ai/agent/agent_loop.py:263-267` | round2 同上 |
| 路由层②层吞 | `app/api/v1/reviews.py:239-241` / `:309-311` | catch-all → SSE `error` 帧（注释写「不吞」，但从观测角度异常确已被消化） |
| 熔断降级 | `app/services/review_service.py:416-420` | `except CircuitOpenError` → `thinking:LLM_DOWN` + `done:{content:""}`；**该路径无任何 llm_call 打点**（熔断在 `:158` acquire 处抛，早于 `:161` 的 `_obs_started`）⇒ **账面全干净** |
| 出口判定 | `app/core/middleware.py:26 _obs_finish(response, aborted=False)` | 优先级 = 断连 > **HTTP 状态码** > ok ⇒ 200 的 error 帧被判 ok |

⇒ 与 gq 的差异：gq 是**一个**吞点汇入**一个** LLM 咽喉；sp 是**三个** LLM 通道方法（`chat_stream` / `chat_stream_agent` / `chat`）**各一份**同构重试环，共 **9 处** `_obs_llm_error`。

## §3 改动清单（**6 个文件面** —— `app/obs.py` 载体 + A 组 `app/ai/llm/deepseek_client.py`（6 处）+ B 组 `app/ai/agent/agent_loop.py`（2 处）、`app/services/review_service.py`（1 处）+ 出口 `app/core/middleware.py` + 入参 `app/api/v1/reviews.py`；均为 `app/` 下 ⇒ `docker restart sp-app` 即可，**不需重建镜像**；**置位点共 9 处** = A 组 6 + B 组 3）

> 订正（2026-09-17 落码当刻）：本节原写「**4 个文件面**」，那是**决策 C（纳入熔断降级出口）之前**的数字。
> 决策 C 把 B 组三处置位落到 `agent_loop.py` / `review_service.py`，加上出口 `middleware.py` 与入参
> `reviews.py`，实际 **6 个文件面 + 2 个测试文件**（`tests/unit/test_llm_hard_fail_marker.py` 新增、
> `test_obs_wiring.py` 随出口契约改断言）。

### 3.1 新增请求级标记载体（对应 gq 的 `utils/trace.py`）

新建 `app/obs_health.py`（或不新增文件、并入 `app/obs.py`——**取「并入 `app/obs.py`」**，见 §4 决策 B）：

```python
llm_health_var: contextvars.ContextVar[dict | None] = contextvars.ContextVar("llm_health", default=None)

def mark_llm_hard_fail(error_type: str) -> None:
    """置位本请求的 LLM 硬失败（只取首次）。上下文缺失时 fail-loud，不静默空转。"""

def mark_llm_hard_fail_from_exc(exc: Exception) -> None:
    """按异常分型置位（error_type 复用平台白名单分类器，不引入新词）。"""
```

> **`set_obs_input` 已删除（2026-09-17）**：它随 `input=` 透传一并撤销，见 §3.4 —— 曾因镜像内 sdk 无此形参而令**全 agent 观测哑掉**。**勿据本节旧版重建它**；环③ 批须先对齐 sdk 版本。

- **必须持可变 dict**（不是标量）：dict 按引用跨 context 拷贝共享，子任务写入对中间件可见；标量赋值传不回来（cs 注释已写明，两家口径一致）。
- `mark_llm_hard_fail` 在上下文缺失时**打 ERROR 日志**，不静默返回——静默空转的症状正是「trace 记 ok」这个要治的病。

### 3.2 置位点 A 组 = **6 个「异常最终上抛」点**（`app/ai/llm/deepseek_client.py`）

| 行号 | 所属方法 | 语义 | 是否置位 |
|---|---|---|---|
| `:203` / `:318` / `:381` | `chat_stream` / `chat_stream_agent` / `chat` | 配置错误（Auth/Permission）**不重试** → 上抛 | ✅ 置位 |
| `:207` / `:322` / `:385` | 同上 | **重试耗尽 / 最终失败** → 上抛 | ✅ 置位 |
| `:220` / `:330` / `:397` | 同上 | 退避期被取消（`GeneratorExit`/`CancelledError`）→ 兜底记 error 后冲出 | ❌ **不置位** |

**为什么不需要 gq 那样的「撤销」**：gq 的重试在**更外层**（`stream_round1_with_retry`），所以要先标后撤；sp 的重试在 `deepseek_client` **内部 while 环**，`attempts >= len(schedule)` 判在 `:207/:322/:385`，**只有最终失败才走上抛**。⇒ **「只在最终上抛前置位」等价于 gq 的「咽喉置位 + 撤销」，且少一个可错点**。
⚠️ 这正是台账 `:600` 预警的「sp 侧不可照搬 gq 结论」——**gq 的 `unmark_llm_hard_fail()` 在 sp 没有对应位置，不应为对称而硬造一个**。

`error_type` 取值 = 既有分类器 `app/obs.py:114 llm_error_type(exc)`（复用值域折叠，落平台白名单词）。

### 3.2b 置位点 B 组 = **3 个「熔断降级出口」**（A 组**覆盖不到**，见挑战 ①）

A 组只覆盖「异常从 `deepseek_client` 上抛」的路径。但 `CircuitOpenError` 在 **acquire 处**（`deepseek_client.py:80`）抛出，早于 `:161` 的 `_obs_started` ⇒ **不记 llm_call、也不经 A 组任何一点**。它的活路径共 3 处（实测 grep，全仓 `CircuitOpenError` 落点已穷尽）：

| 位置 | 形态 | 用户实际拿到 |
|---|---|---|
| `app/ai/agent/agent_loop.py:200-202` | round1 熔断 → `yield {"type":"error","message":"AI 服务不可用，请稍后重试"}` 后 `return` | **error 帧，HTTP 200** |
| `app/ai/agent/agent_loop.py:263-264` | round2 熔断 → 同上 | **error 帧，HTTP 200** |
| `app/services/review_service.py:416-420` | 评分流熔断 → `thinking:LLM_DOWN` + `usage` + `done:{content: full_text}` 后 `return` | **降级/空答案 + 200，且账面全干净** |

⇒ 三处**都为 error / 降级出口，响应均为 200** ⇒ `_obs_finish` 记 ok ⇒ 环② 断。
**处置 = 置位（推荐，见 §4 决策 C）**，`error_type` 由 `llm_error_type(CircuitOpenError)` 得 **`llm_other`**（类名无 timeout/connect/rate 关键词；`obs.py:132` 兜底），属平台白名单值域内、能产候选。

### 3.3 出口判定（`app/core/middleware.py`）

- `_obs_finish` 增 `health` 形参（当前 `:26` 签名 = `(response, aborted=False)`，**既无 request 也无 health**）：
  优先级 = **断连 > LLM 硬失败 > HTTP 状态码 > ok**（与 gq 逐字同序）。
- `RequestIDMiddleware.dispatch`（`:45`）在 `obs_begin`（`:54`）**之前**置入 `health: dict = {"hard_fail": False, "error_type": None}` 并 `set`；三个调用点（`:69` 非流式 / `:77` aborted / `:80` 正常流末）回填 `health`。
- `:57-61` 的 `UNHANDLED_EXCEPTION` 分支**不动**（与 gq 的 `main.py:275` 处置一致）。

### 3.4 入参透传（**②不可省，否则环③断**）—— **⚠️ 2026-09-17 已撤出本批，改单开一批（下称「环③ 批」）**

> **订正（2026-09-17，同日）**：本节原方案**本体正确，但前提写错了**，且实际执行时**炸了**，故整节改判为「已撤出」。

**原前提错在哪**：本节写「底层 sdk 接受 `input=`（`sdk/obs_sdk/__init__.py:130`）」—— 引的是**宿主仓源码**。而 **sp 镜像烤入的 obs_sdk 是旧版，`end_request` 形参为 `['status','error_type','error_msg','output','duration_ms','extra']`，根本没有 `input`**（`additional_contexts` 构建期注入 ⇒ 镜像内 sdk 与宿主仓源码**不是同一份**）。按宿主源码改门 + 中间件 ⇒ 每次请求出口 `TypeError`，被 `app/obs.py` 的 `except Exception: logger.debug` 吞掉 ⇒ **sp 全 agent 观测哑掉**（详见 online `task.md` T-5.9b）。

**因此环③ 批的**第一件事**不是写透传，而是**先把 sdk 版本对齐**（重建镜像，使镜像内 `end_request` 与宿主仓同形），否则同一坑必然复现。

- ~~`app/obs.py:93 end_request` **当前不接受 `input=`**……~~（**已实现过，已连根去除**：`set_obs_input`、`end_request` 的 `input` 形参、中间件四处传值、`reviews.py` 两处调用**全部删除**；`reviews.py` 回到 HEAD 同形。**不留无人读的写入方**。）
- 写入点（**待环③ 批重做**）：两个 SSE 路由 `app/api/v1/reviews.py` 的 `stream_score` / `stream_chat` 各加一行置位（**在进入流之前**，与 gq「放在归属校验之前」同理：校验失败也是要归因的 trace）。
- **不用 `request.state` 路线**：sp 两个 SSE 端点**均无 `request` 参数**，且写入点在 `agent_loop` 深处 ⇒ **只能 contextvar**（本条与故障无关，仍然成立）。
- **必要性已由真机钉死**：`worker/cluster_job.py` 的 **Fork A** —— `root_input_hash` 为 NULL 的行**候选不建簇不计数**。sp 的 `root_input_hash` 恒为 NULL ⇒ **即使环② 判出 `root_status='error'`，环③ 仍不出候选**。环③ 批 = sp 七环的必要条件，不是可选项。

## §4 两处需拍板的判断点

### 决策 A（**已拍板 2026-09-17：不纳入，只登记缺口**）——「流开始前熔断直接 503」这一支

- 形态：`reviews.py:211-215`（score）/ `:258-262`（chat）熔断 OPEN ⇒ `raise HTTPException(503)`，**不走 SSE** ⇒ 出口记 `HTTP_503`，属**平台值域外、不产候选**。
- 现状即「同一个『AI 不可用』，流前 503 不能回流、流中途能回流」。
- **推荐不纳入**，理由：① `HTTP_503` 是**忠实的** HTTP 语义表达，为回流而改状态码会破坏「状态码」这条通用判据；② 纳入需**动平台 `classify` 值域**（跨服务、面向所有 agent），代价与风险远超本批；③ 纳入后 sp 与 gq **不可比**（gq 无此形态）。
- 处置 = **登记为已知缺口**（台账 `:629` ① 已记），不在本批。**但见 §6.2 的验收前置**——它会在验收时反过来卡我们。

### 决策 B（**我推荐：并入 `app/obs.py`，不新建文件**）——载体放哪

- sp 的 `app/obs.py` 已是「中央观测门」，`llm_health_var` + `mark_llm_hard_fail`/`mark_llm_hard_fail_from_exc` 并入其中，**不新建 `obs_health.py`**（**已落实**；`set_obs_input` 曾一并并入，现已删除，见 §3.4）。
- 理由：符合「能不加的就不加」；且 `tests/unit/test_obs_wiring.py` 的既有 monkeypatch 惯例就是**打 `app.obs` 门**（`:40-70`），并入后新增测试可直接复用该惯例。

### 决策 C（**已拍板 2026-09-17：纳入**，即 §3.2b 三处置位）——「熔断降级出口」要不要标

- **它不是「有意设计放过」**：`app/obs.py:120` 明写「CircuitOpenError（熔断前置拒绝）不打点，由 request **HTTP_503** 反映（对齐 cs）」—— 该论据的**前提是响应为 503**。而 §3.2b 那三处响应均是 **200**（error 帧 / 降级 content）⇒ **前提不成立**，规格并未覆盖这三处。（判据依 memory `implementation-odd-is-not-defect`：先回读规格，确认「有意」还是「缺口」——此处是缺口。）
- **不纳入的后果与验收直接冲突**：黑洞注入会让断路器累积失败而 OPEN，之后**同一次评测 run 内的后续请求**极可能走 `:263` 或 `:416` 这条 ⇒ root 仍记 ok ⇒ **验收当场误判成「修复无效」**。§6.2 的前置门禁只能保证「第一个请求不撞 503」，**保证不了「run 中途熔断不出现」**。
- **代价（已核实，2026-09-17 读 cs 源码）**：**确实与 cs 偏离**。cs 的标记点在 `customer-service/backend/app/infrastructure/deepseek_gateway.py:226-229`（`except LLMUnavailableError` → `mark_llm_hard_fail`），而**熔断入口快速拒绝的 `raise LLMUnavailableError` 在 `:196-200`，位于 `:201` 的 `try:` 之外** ⇒ 不会走到 `:226`。
  ⇒ sp `app/obs.py:120` 那句「对齐 cs：熔断拒绝非 LLM 调用」**是对 cs 的准确描述**（此处先前的怀疑不成立，录以备考）。也即：**cs 有同一个缺口**（熔断时用户拿规则引擎兜底 + HTTP 200 + root 记 ok），本批让 sp 比 cs 更完整。
  ⚠️ 边界：以上仅证到「cs 的 `raise` 在 `try` 之外」与标记点位置；**cs 全链（兜底装饰器是否另行标记）未核实**，故不据此断言 cs 是缺陷，只作为「sp 纳入不会造成口径倒退」的依据。memory `contract-claims-need-both-sides` 已遵守：两侧都取了证。
- **与决策 A 不矛盾**：A 拒的是「把 503 改成 error」（破坏 HTTP 语义）；C 标的是「已经是 200 的降级出口」（不碰状态码）。两者都在「不篡改 HTTP 语义」的前提下。

### 判据澄清（回应挑战 ③：我在两处用了同一把尺子、方向相反）

本方案里「与 gq 可比」是**验收口径**层面的要求 —— 两家能用同一套判据回答「七环是否跑通」，**不是代码形状必须一致**。所以：
- 决策 A 说「纳入后与 gq 不可比」= 若为回流而改 HTTP 语义，则两家的「root 为什么是 error」不再是同一件事，验收无法并置结论；
- §3.2 说「偏离 gq 形状」= 实现结构本就不同（重试在内层环、无 `request`、无独立 trace 模块），照搬形状反而会引入不需要的「撤销」。
两者判据不同、并不打架；但**必须写明**，否则评审时会读成前后矛盾。

## §5 显式不纳入项（避免「为文档写了而实现」）

1. **「LLM 正常结束但返回空」兜底**（`app/ai/agent/agent_loop.py:114`「AI 未生成有效回复」）—— **不纳入**，与 gq 已拍板口径一致（`:602`）。理由同批：黑洞注入产的是**超时/连接异常**、产不出空返回，写了就是「无消费方的实现」。另立待办。
2. **`app/services/fraud_detection_service.py:511-513` / `tag_translation_service.py:60-65`** 的降级文案 —— **不纳入**。取证发现 `generate_report` / `translate_tags` **在 `app/api/` 下无任何路由调用方**（仅定义与 `tests/`）⇒ 当前 HTTP 面的死路径，标记即「造无人调用的实现」。
3. **`app/services/conversation_service.py:202-205`**（摘要失败吞异常返 None）—— **不纳入**。用户不受影响（继续正常回答），标了会把健康请求记成 error（假红）。
4. ~~**不改 obs-sdk**（`end_request` 已支持 `input=`）。改 sdk 须重建镜像，本批不动。~~
   **↳ 订正（2026-09-17，本批最大的错）**：「`end_request` 已支持 `input=`」是照**宿主仓源码**得出的 —— **镜像内那份 sdk 不支持**（`additional_contexts` 构建期注入 ⇒ 两者不是同一份）。本批据此改了门并传参，**当场炸掉全 agent 观测**（§3.4）。**环③ 批必须改 sdk / 重建镜像**，不再是「可不动」。

## §6 验收方案（口径 = 「这批的绿能证明什么、不能证明什么」）

### 6.1 正反例（缺一不可）

- **反例**：无注入 ⇒ `root_status` 必须仍为 **`ok`**（防「一律记 error」式的过度修）。gq 侧对应 trace `gqaccept1-220ab86ee8e1`。
- **正例**：注 LLM 黑洞（容器内 `/etc/hosts` 把 `api.deepseek.com` 指向 `127.0.0.1`）⇒ SSE 返 `event: error` **且 HTTP 200**（正是本批要治的病理）⇒ `root_status=error`、`error_type` 为白名单词。

### 6.2 熔断注意项（**已核实，2026-09-17**）

实测参数：阈值 = **5 次失败**（`config.py:72 deepseek_circuit_breaker_threshold=5`）；`CIRCUIT_OPEN_SECONDS = 30.0`（`deepseek_client.py:54`）；`record_failure()` 在 `:201/:316/:379`（每次失败尝试各计 1）；状态为**进程内存态**（`:61-70`）。

⇒ **OPEN 只锁 30 秒**，到期自动转 HALF_OPEN 放行（`:81-83`，且 HALF_OPEN 期间不拦截）⇒ **复位手段 = 等 30 秒，或 `docker restart sp-app`**。验收不会因熔断卡死，本条**不再是硬门禁**。

⚠️ 但**熔断期内请求走的是路由层 503**（`reviews.py:211/:258`，决策 A 不纳入）⇒ 那种请求**不产候选、建不出环②**。故给出诊断判据：

> **注入后若发现簇没建出来，先看该 trace 的 `root_error_type`。**
> 是 **`HTTP_503`** ⇒ 撞上熔断窗口，**等 30 秒重试**即可；
> 不是 503 却仍无簇 ⇒ 才轮到怀疑「修复无效」。

这条能把「环境撞车」与「改动无效」当场分开，避免误判。

### 6.3 七环 id 链（每环须留 id，跑完即落台账）

① trace（`root_status=error`）→ ② cluster id → ③ link id（`source_trace_id` = 该 trace，**非 `task-NNN` 桩**）→ ④ 离线 inbox / case id → ⑤ 信号 run + 自动派生的 error run → ⑥ `conversion_record(action=regression_result)` → ⑦ `claim` conv + `auto_fixed`(conv) + cluster `fixed` + link `passed`。

### 6.4 自造故障标注（**造完当场落台账**）

起止时刻 + 手法 + **撤销动作 + 回读确认** + 注入前基线水位 + 产出物 id 清单，全部写进 online `task.md`。区分手段只有人为标注——不写，这批红与真缺陷逐字同形。
（`/etc/hosts` 上 `sed -i` **不可用**，须 `grep -v … > /tmp/h.new && cat /tmp/h.new > /etc/hosts`，见 gq 本轮实测。）

### 6.5 单测

- 扩展 `tests/unit/test_obs_wiring.py`（既有唯一 obs 专项测试），**mock 边界必须落在 `deepseek_client` 重试环的真实上抛点**——否则置位点根本不执行，用例只验了反例、形同虚设（gq 侧踩过：mock 边界错了会「只验撤销、不验置位」）。
- 至少 4 例：**最终失败置位** / **重试后成功不置位**（反例，防假红）/ 上下文缺失 fail-loud / `_obs_finish` 的 health 分支（硬失败记 error、正常记 ok）。
- 跑法（仓内既有约定）：`poetry run pytest tests/unit -p no:html -p no:metadata`；CI 门禁 `-m "not external"`。

## §7 与 gq 的差异对照（不可外推项）

| 维度 | gq（已跑通） | sp（本方案） |
|---|---|---|
| 后端根 | `backend/` | **`app/`**（无 `backend/` 目录） |
| 观测模块 | `backend/utils/trace.py` + `main.py` 中间件 | **无独立 trace 模块**；`app/obs.py`（中央门）+ `app/core/middleware.py` |
| 中间件形态 | `@app.middleware("http")` 函数 | `BaseHTTPMiddleware` 子类 `RequestIDMiddleware.dispatch` |
| 出口签名 | `_obs_end(obs, response, request, health, ...)` | `_obs_finish(response, aborted=False)` —— **窄一圈**，health/入参都要新增 |
| `end_request` 是否收 `input=` | 收 | **不收**（`app/obs.py` 中央门）；⚠️ 底下**镜像内 sdk 也不收**（宿主仓那份才收）—— 本表原写「宿主收、sp 门不收 ⇒ 改门即可」，**漏了底层这一层**，是本批事故的根源，见 §3.4 |
| LLM 记账 | 单点 `stream_chat` | **三个方法各一份拷贝，9 个 error 点** |
| 重试位置 | 外层 `stream_round1_with_retry` | **内层 while 环**（`attempts`）⇒ 无「撤销」需求 |
| SSE 路由是否带 `request` | 带 | **不带**（`reviews.py:201` / `:251`）⇒ 只能 contextvar |
| 熔断「流前 503」 | 无此形态 | **有**（`reviews.py:211/:258`）——见 §4 决策 A（不纳入） |
| 熔断「降级出口（200）」 | 无此形态 | **有 3 处**（`agent_loop.py:200/:263`、`review_service.py:416`）——见 §4 决策 C |
| 部署 | **无 bind mount ⇒ 必须重建镜像** | **有 `./app:/app/app:ro` ⇒ `docker restart sp-app` 即可** |
| 容器名 | `rag-backend` | **`sp-app`** |
| 回滚 | 重建镜像 | 改回文件 + `docker restart sp-app` |

## §8 未取证 / 待核项（开工前补齐，不凭印象）

1. ~~sp `llm_error_type` 的实际映射~~ **已核实（2026-09-17 读码 `app/obs.py:114-132`）**：有 `status_code` 时 429→`llm_rate_limit`、其余→`llm_other`；无状态码按**类名关键词**归并（`timeout`→`llm_timeout` / `connect`→`llm_connection` / `rate`→`llm_rate_limit`），全不中→`llm_other`。
   ⇒ **黑洞注入走的是 openai 的 connect/timeout 类异常**，预期落 `llm_timeout` 或 `llm_connection`（**与 gq 本轮实测 `llm_connection` 同族**）；`CircuitOpenError` 类名无关键词 ⇒ 落 **`llm_other`**（§3.2b）。三者均在白名单内、都能产候选。⚠️ 这是**读码推断**，验收时须以真机落库的 `error_type` 为准，**不据推断写断言**。
2. ~~熔断器参数与复位手段~~ **已核实（2026-09-17）**：阈值 5 / 冷却 30s / 进程内存态 / 复位 = 等 30s 或 `docker restart sp-app`。详见 §6.2。
3. ~~sp 观测开关现状~~ **已核实（2026-09-17，含实测）**：`OBS_ENABLED=true`、`OBS_KAFKA_TOPIC=dev.obs.agent.smart-procurement`、容器 `Up 2 hours (healthy)`；⚠️ 但历史 trace 停在 `2026-09-16 08:25:50 UTC` 而容器是 2h 前起的 ⇒ 「有过 trace」**证不了管道还通**，故补做**实测探针**：`GET :18002/api/v1/reviews` 无 token → `HTTP 401` → trace store 出现 **id 18970**（`root_status=error` / `root_error_type=HTTP_401` / `2026-09-17 02:20:22`）、sp 行数 **32 → 33** ⇒ **采集→Kafka→落库全链现在确实通，无需改配置**。
   ⚠️ **自造痕迹**：上述探针产生 1 行 trace（id 18970，非缺陷），与后续注入一并标注入台账。
4. sp 侧同名「空返回兜底」是否有**重试**（决定是否与 gq 完全一致地不纳入）—— 已按不纳入处置，此项仅登记。

---

**状态**：本方案**未开工、未改任何文件**。待确认后按 §3 落码 → §6 验收 → 落台账。
