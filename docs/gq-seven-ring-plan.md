# gq 七环回流「B 方案」实施方案（v3 · **已实施并验收**，2026-09-17；实施提交 = gq `1945ac9`）

- **日期**：2026-09-17　**状态**：待审、**未动手**（代码改动面 = 0）
- **范围**：**仅 good-question（gq）**。sp 另行一批（§7 **不可照抄**）
- **上游台账**：online `task.md` T-5.9（批次 = gq 先行，已拍板）
- **已独立评审两轮**（subagent 全程只读）：v1→v2 见 §9，v2→v3 见 §10。
  ⚠️ 两轮**都打在「覆盖范围」这一处**（我两次都把「逐行查过的点」外推成「全部」）——这是本方案最薄弱的失效面，后续任何「全覆盖」措辞都须先证明**入口已穷尽**。

---

## 1. 断口（已读码 + 独立复核）

七环的 ① 观测 → ② 聚类判定 → ③ 组装 在 gq 断掉，**两处独立原因，缺一不可**：

**断口 1（环②）**：`online backend/app/analyzer/classify.py:156`
子节点候选**仅在 root 终态非 ok 时**收集（T-3.10 兜底吸收门控，`classify.py:17-19` 有论证）。
gq 的 LLM 异常被吞成 SSE error 帧后**生成器正常结束** ⇒ HTTP 200 ⇒ `end_request("ok")`
⇒ root=ok ⇒ 子节点那条 `llm_timeout` **永远进不了候选**。

**断口 2（环③）**：`online backend/app/converter/envelope.py:97`
「快照缺 input 实文 → **只计数不组装返回 False**」。
**消费链已核实完整**：`consumer/state.py:136-139`（`event.input is not None` →
`input_snapshot_clean`）→ `cluster_job.py:71` → `assemble_job.py:41-42` → `envelope.py:71`。
**唯一缺环就是 gq 从不发 `input`**（`main.py:90/94/96` 三处 `end_request` 均无 `input=`）。

---

## 2. 方案总览

| 改动点 | 作用 | 落点 | 量 |
|---|---|---|---|
| A 请求级 LLM 硬失败标记 | 修断口 1 | `utils/trace.py` 加变量与标记 + **`llm_service` 2 处**（置位 / 撤销）+ 出口读 | ~20 行 |
| B 观测入参透传 | 修断口 2 | `api/chat.py` 一行 + `_obs_end` 四条出口 | ~6 行 |

**二者必须同批**：只做 A ⇒ 环③ 断；只做 B ⇒ 环② 断。

**⚠️ 本批命题的精确边界（v3 补，防被读成 L3）**：本批修的是「**本该 root=error 却记成 ok**」——
用户明明拿到兜底话术/失败交付，root 的如实性缺失。它**不是**「让所有子节点 error 都回流」：
规格对「request ok + 子节点 error」的口径是**已被业务吸收、v1 不回流（L3 二期）**
（`classify.py:17-19`、`:128-131`，均引 §6.1 L826；root 的量程 = **「请求是否成功返回答」**）。
⇒ 凡「用户交付未受影响」的内部失败（如 §6.7 的压缩）**本批一律不动** —— 这是**规格划的界**，
不是本批的取舍，不得在汇报里说成「本批暂未覆盖」。

---

## 3. 改动点 A：请求级 LLM 硬失败标记

### 3.1 落点 = **单点 + 撤销**（v1 曾写「6 个吞点」，已证伪，见 §9.1）

**为什么不能「只标记不撤销」**：`llm_service.py:200-202` 自陈该处 error **每次尝试都记**
（「每次重试都是完整付费调用 → 各记 1 条」），而 `stream_round1_with_retry:422-423` 对
**429/5xx 且尚未 yield 事件**的情况**会退避重试**。若只置位不撤销，「第一次 429 → 重试
成功 → 用户拿到完整回答」会被标成 root=error ⇒ **假红**。

**做法**（共 2 处改动；⚠️ 二轮评审**证伪**了 v2 写的「未来新增调用点自动覆盖」—— **现存的就没覆盖**，见 §6.7）：

- **置位**：`services/llm_service.py` 的 `stream_chat` except 块（`:219-224`，`recorded = True`
  之后、`raise` 之前）加一行 `mark_llm_hard_fail(llm_error_type(exc))`。
- **撤销**：`stream_round1_with_retry` 的**「将要重试」分支**（`:423` 的 `raise` 判据**未**命中
  之后、`:428` `time.sleep(backoff)` 之前）加一行 `unmark_llm_hard_fail()`。

**语义等价性（评审已逐路径核过）**：round2 调用点（`:743/:849/:885/:952/:978`）**无重试**，
失败直落吞点；round1 的唯一最终失败点是 `:423` 的 `raise`；被撤销的只可能是「确定要重试」
的那次 ⇒ 全部路径结果与「逐吞点标记」**相同**。

**为什么单点优于逐吞点**：① 与 cs 一致 —— cs 的 3 个标注点**全在基础设施层**
（`deepseek_gateway.py:229/244/261`），**一个吞点都没碰**，其重试在标注点**之下**
（`_call` 内部），故根本不存在上述假红；② 逐吞点依赖「吞点当时穷尽」这个**会腐**的前提，
将来多一个调用点就静默变**假绿**（正是本方案要治的病）；③ 「更精确」在 gq 当前代码上
**收益为零** —— 6 个 except 全是 `yield ("error")` 后 `return`，不存在「失败但仍给好答案」的路径。

**已知边界（v3 按二轮评审订正）**：`stream_chat` 在 `obs is None` 时于 `:205-208` **提前 return**，
永不进入 except ⇒ 标记不置。⚠️ 二轮评审**证伪了 v2 在此写的「两处判据同源」**：`main._obs()`
（`main.py:71-78`）只查 settings + import，**无 `is_initialized()`**；`llm_service._obs_sdk()`
（`llm_service.py:240-246`）**有**。故存在一档：`OBS_ENABLED=true` 但 `obs.init()` 抛异常
（`main.py:170-171` 被 catch）⇒ 中间件**照常包 body**，而 `stream_chat` **早退、永不置位**。
结论（整条 trace 不产）仍成立，但真正的机制是 **`obs_sdk.end_request` 在 `sink is None` 时直接
return**，不是「同源」。⇒ **照「核对同源」去核会核过、却核错了地方**；实施时核的是「两处
`is_initialized()` 语义差」，不是「同源」。

### 3.2 标记模块放哪

**放 `backend/utils/trace.py`**，与已有的 `trace_id_var`（`utils/trace.py:9`）并列 ——
该文件与 cs 的 `app/utils/trace.py` **完全同构**，是参照实现的原位。
⚠️ v1 曾写 `services/obs_health.py`（新增文件），**已订正**：gq 有 `utils/`，无需新建模块。

```python
# 请求级 LLM 健康标记。⚠️ 持可变 dict 而非标量：写入发生在深层调用里，
# 标量赋值传不回中间件持有的那个上下文。
llm_health_var: ContextVar[dict | None] = ContextVar("llm_health", default=None)

def mark_llm_hard_fail(error_type): ...    # 只取首次
def unmark_llm_hard_fail(): ...            # 重试前撤销
```

⚠️ **写侧必须 fail-loud**（二轮评审 A2）：`llm_health_var` 的 default 是 `None`，若置位时所在上下文
与中间件 `set` 的**不是同一个**（换中间件形态 / 后台任务 / 新线程），`get()` 返 `None` ⇒ 置位
**静默 no-op、无日志、无断言** —— 那正是 §3.3 用「当参数传」在**读侧**消灭的病，不能又从
**写侧**长回来。故 `mark_llm_hard_fail` 内 `health = llm_health_var.get()`；`health is None` 时
`logger.error` 后返回。（对照：`sdk/obs_sdk/__init__.py:110-112` 的 `_require_span` 缺失时至少打 warning。）

### 3.3 绑定与出口

- **绑定**：`main.py` 的 `obs_request_middleware`（`async def` :233）在 `call_next` **之前**：
  `health = {"hard_fail": False, "error_type": None}` + `llm_health_var.set(health)`。
  **必须放在 `obs is None` 早退之前**（cs 即如此，`:153-154` 早于 `:156-158`）。
- **出口**：`main.py:_obs_end`（:81）。**health 当参数传下去，不在出口 `get()`** ——
  与 cs 同构（cs `main.py:44` 签名里就有 `health: dict`），cs 注释原话即「**不依赖**子任务里的
  写能传回中间件上下文」。
  ⚠️ v1 写成在出口 `llm_health_var.get()`（**已订正**）：那样若上下文边界变化，`get()` 返 None
  ⇒ **静默退回原 bug、无日志、无断言失败**。
- **分支顺序** = 断连 > LLM 硬失败 > HTTP 码 > ok（插在现有 :89 断连与 :93 HTTP 之间）。
  `error_type` 直接用白名单词，**不另造词**。

---

## 4. 改动点 B：观测入参透传

1. `backend/api/chat.py` 路由 `chat()`（`request: Request` 已在 :47）内加：
   `request.state.obs_input = body.model_dump()`（cs 同形：`routes.py:56`）。
   **本仓已有先例**：`api/chat.py:36` 的 `request.state.obs_aborted` 就是「业务置位 → 中间件读出」，
   且有单测（`tests/test_api_chat_disconnect.py`）——比引外部仓更有力。
2. `_obs_end` 的出口带 `input=obs_input`（`getattr(request.state, "obs_input", None)`）。
   error 路径同样要带，否则失败 trace 建不出簇。
   **边界**：中间件内 `main.py:253` 的 `UNHANDLED_EXCEPTION` 出口**不在此列**（它值域外、不产候选）。

---

## 5. 验收判据（含反例，且已按评审补上四条）

**注入手段**：把 gq 的 LLM 指向黑洞。⚠️ **先确认注入产生的是连接/超时异常**——
`_is_transient_http_error`（`:391-401`）**只认 `HTTPStatusError` 的 429/5xx**，
连接超时/拒连**不可重试、立刻抛**，正好走我们要验的路径。

| 环 | 判据 | 反例（不可省） |
|---|---|---|
| ① | trace request 事件 `status=error` ∧ `error_type` ∈ 白名单 ∧ **`input` 非空** | **正常请求** ⇒ 仍 `ok`（防误标） |
| ② | 该 trace 被 judge，layer≠none（**必须用新 trace**，见下 B5） | — |
| ③ | 建簇后组装出 envelope，`evidence.input` **有实文** ∧ 该 envelope 的 `input_hash` **== 本 trace 的 `root_input_hash`** | — |
| ④ | 生成 case；`check_input_wiring` 通过 | — |
| ⑤⑥⑦ | error run 判定 → 回归回推 → 收口 | — |

**三条必守的验收纪律（评审新增，缺一条验收结论就可能反向）**：

1. **入参必须唯一化** —— gq 命中 Redis 缓存即 `_replay_cached` 回放、**0 次 LLM 调用**
   （`chat_service.py:619-626`）。先跑正常请求落缓存、再用**同一 question** 注入 ⇒ 命中缓存
   回放成功答案 ⇒ 结论被读成「方案没生效」。**「连跑两遍」必须换成「两遍不同问题」。**
2. **必须用新 trace** —— `consumer/state.py:147-150` 的 `judged` 位防重放，A+B 上线前已入库的
   gq error trace **永久 layer=none**，拿旧 trace 验必假红。
3. **重试后成功必须仍为 ok**（防 §3.1 那个假红的**唯一**直接判据）：真机构造 429 成本高，
   **用单测覆盖** `stream_round1_with_retry` 重试成功路径，断言撤销后标记未生效。
   ⚠️ **mock 边界必须下沉到 `_stream_chat_http`**（二轮评审 B2）：既有做法是 mock
   `cs.llm_stream_chat`（`tests/test_chat_service.py:352-356`），那样**根本进不到 `stream_chat` 的
   except** ⇒ 只验了撤销、**没验置位**，判据形同虚设。
4. **判据③ 必须绑定到本 trace**（二轮评审 B1）：`evidence.input 有实文` 在**全局组装面**上成立即可，
   而 §6.2 自己预警「新旧簇并存」⇒ **任意别的 gq 簇带实文就能把它蒙绿**。故断言里必须带
   `input_hash == 本 trace 的 root_input_hash`，不能只查「有 envelope」。

**前置**：验收前先确认 gq 容器 `OBS_ENABLED` 生效且 `obs_sdk` 已 init —— 否则
`main.py:244-246` 直接 `return await call_next(request)`，**整条 trace 不产**，判据①会以
「没有 trace」失败，与 A/B 无关。

**查询口径（实查所得，别用 manifest 的串）**：过滤 gq 的行用
`agent='good-question'` ∧ `interface='POST /api/chat/{id}'`。

**对照基线（A+B 上线前，库内实测 2026-09-17）**：gq 共 **151 行、全部 `judged=1`**；其中
`POST /api/chat/{id}` **51 行 = 48 ok + 3 个 `HTTP_400`（无一条 `llm_*`）**。
⇒ **gq 至今没有任何一条 LLM 类 root error 进过库** —— 这是断口的**直接证据**，
也是验收时要被「新 trace 出现 `llm_*` root error」打破的那组数字。

---

## 6. 已知副作用 / 边界（评审新增，须在汇报里如实声明）

1. **非异常降级不在本批覆盖内 —— 这会限制「七环跑通」的说服力**：三处**不抛异常**的用户可见降级
   （`chat_service.py:1026-1030` 空返回兜底、`:1031-1038` tool_call markup → 未找到、
   `:770-777` 工具轮次耗尽 → 未找到）**不会置位** ⇒ root 仍 `ok` ⇒ 环② 仍断。
   佐证：平台 L1 白名单**本来就有 `llm_empty_response`**（`classify.py:44`），而**四个仓无人产出该词**
   —— 那个词就是给这类降级预留的位置。
   **本批的结论必须限定为「对抛异常那一类 LLM 故障成立」**；而验收用的黑洞注入**结构性地**
   只覆盖这一类，缺口不会在验收里暴露。⇒ **空返回另立待办**（用户已拍板不纳入本批），
   但**必须在验收汇报里写明这条限度**，不得让整批的绿把它盖过去。
2. **`root_input_hash` 维度变化**：gq 此前 `input=None` ⇒ 该 hash 恒 NULL；改动 B 后新 trace 带 hash
   （`core/input_hash.py:30-32`）。部署前后同因故障**会形成新簇 + 旧簇并存**，count/优先级会失真。
3. **已判定 trace 不重判**（同 §5 第 2 条）。
4. **第 5 处出口**：`main.py:253` 不属改动 B 范围（见 §4 边界）。
5. **`interface` 串对不上 —— 已库内实查，结案：当前无实际影响**：gq 真实串经 `normalize_route`
   归一为 **`POST /api/chat/{id}`**（库内实测 51 行取该值），而 offline manifest 声明的是
   `/api/chat/{session_id}` —— **确实不同串**。但 `interface` 字典表**实测 0 行**
   ⇒ 字典侧**根本没有 gq 的行可命中**，且 L2 的 `interface.llm==1` 支对**四个 agent 全部**恒不满足
   （皆只靠 `llm_fact` 支；既有事实，非本批引入）。L1 本就不看 interface ⇒ **本批无影响**。
   ⚠️ **这是「现在没影响」，不是「串对了」**：一旦 interface 字典被填充，该串差异**立刻**变成真影响。
6. **`obs` 未启用 ⇒ 整条 trace 不产**（§5 前置同条）。
7. **`_compress_memory` 等「非 `stream_chat` 入口」的失败 —— 本批不覆盖，且这是规格划的界（§10.6）**：
   它是 `stream_chat` **之外**的第二处 LLM 入口（`get_llm(streaming=False).invoke()`，
   `chat_service.py:412-413`），异常在 `:419-421` 被 `logger.warning` 后**丢弃、不重抛**
   ⇒ 永不进 `stream_chat` 的 except ⇒「单点」盖不到它。**但盖不到不等于该盖**：规格对
   「request ok + 子节点 error」的口径是**已被业务吸收、v1 不回流（L3 二期）**，而它正是这一档
   （实测失败时本轮回答**逐字一致**，见 §10.6）⇒ **现状正确，本批不动、也不新立待办。**
   `llm_service.py:60 rewrite_query` 为同类入口，当前已停用（`retrieval_service.py:60` 注释），同样只登记。
   附两项**真实但与本批正交**的登记（不在本批范围，不得写进本批验收结论）：
   ① `compress_prompt` 只增不减（`:390-401`）⇒ 长会话下压缩**永久失败、记忆冻结**（产品缺陷）；
   ② `:420` 的 `_record_mem_llm` 在 except 块内、其内部 `obs_sdk.record_llm` 未受保护 ⇒ 观测 sdk 抛错
   会逃出 `_compress_memory` 与 `stream_chat`，而 `api/chat.py:56-60` 无 try/except ⇒ 流被掐断
   （既无 error 帧也无 done）—— 属**观测边带的洞**。

---

## 7. sp 复制批的已知差异（**不可照抄 gq**）

1. sp 的 SSE 路由 `api/v1/reviews.py:201` / `:251` **没有 `request` 参数** ⇒ §4 的
   `request.state.obs_input` 写法**用不了**，须换别的入参携带方式（待设计）。
2. sp 的 `deepseek_client.py` 9 处 `_obs_llm_error` **同时含两类**：`:203/:318/:381`「配置错误不重试」、
   `:207/:322/:385`「重试耗尽：最终失败」⇒ 置位/撤销点须在 sp 侧**重新定位**。
   （另一支 `:220/:330/:397` 也须一并看。）
3. 另有 `conversation_service.py:203` 明写「**吞异常返 None**」—— 又一条吞路。
4. 断路器「同因不同果」：流开始前熔断 → 路由直接 503（`reviews.py:211`）⇒ root 记 `HTTP_503`
   （**值域外，不产候选**）；流中途 `CircuitOpenError` → error 帧 + 200。**待决定是否本批一并处理。**
5. ⚠️ sp 仓布局是 `smart-procurement/app/...`，与 gq 的 `backend/...` 不同。

---

## 8. 库内实查结果（v3：三条全部核实，2026-09-17 实测）

复核方式（借容器自己的连接串，**不回显凭据**）：
`MSYS_NO_PATHCONV=1 docker exec -i obs-backend python - <<'PY' … Settings().sqlalchemy_url … PY`

1. **运行期库态 —— 已确认，无阻塞**：`agent` 表 gq = `enable=1 / backflow_allow=1`；
   `dict_config` 四个 agent 的 `backflow_enabled` 全 = `'true'`。⇒ 白名单四闸全开，环② 不卡在这。
2. **`interface` 字典表实测 0 行**：gq 的 `chat` 行**不存在**（全表皆空）
   ⇒ §6.5 的串差异**当前无实际影响**；同时意味着 L2 的 `interface.llm==1` 支对四 agent 恒不满足
   （既有事实，登记不改）。
3. **gq 运行期真实串 = `POST /api/chat/{id}`**（51 行）：**本批验收的过滤口径就用这个串**，
   不是 manifest 的 `/api/chat/{session_id}`。另有一行 `POST /api/chat/`（尾斜杠未归一，量 1）忽略。
   **基线数字（断口的直接证据）**：gq 共 151 行、全部 `judged=1`；`POST /api/chat/{id}` 51 行
   = 48 ok + 3 个 `HTTP_400`，**无一条 `llm_*`** ⇒ gq 至今无任何 LLM 类 root error 进库。
4. **`_obs_end` 的 `exc` 形参**：确认当前函数体内未被引用（死形参）；删签名属 A 级范畴，
   本批**不顺手改**。

**顺带发现（不属本批，待定夺）**：`agent` 表有一行 `probe-unknown-agent`（id=853），
在 `trace_judge_state` 中 0 行 ⇒ 疑似探针残留的空壳行。**未删**，已列给用户决定。

> v1 曾列的另两项（online 侧消费链是否完整、cs 是否也有重试）**已结案**，见 §1 与 §3.1。

---

## 9. v2 相对 v1 改了什么（保留追溯）

1. **落点：6 个吞点 → 单点 + 撤销**（§3.1）。v1 的推论「标记必须落在吞点」是**过度外推**：
   它证伪的只是「放在记录出口**且不撤销**」，却漏了「撤销」这一维，也漏了 cs 的做法（cs 标注点
   全在基础设施层、重试在标注点之下）。
2. **标记模块位置：新增 `services/obs_health.py` → 并入 `utils/trace.py`**（§3.2）。
   v1 把「放哪」列为未核实，实为**一眼可核**。
3. **出口读法：`llm_health_var.get()` → 当参数传**（§3.3）。消除「标记静默丢失」的暴露面。
4. **验收补三条纪律**：入参唯一化 / 必须用新 trace / 「重试后成功仍为 ok」单测（§5）。
5. **新增 §6 副作用清单**，其中第 1 条把「本批只覆盖抛异常支」写成**明示限度**（§9 的 4 条均由评审提出）。

---

## 10. v3 相对 v2 改了什么（二轮评审后）

1. **【已落】§3.1 订正一处事实**：「`_obs_sdk()` 与 `main._obs()` 同源」**不成立**（后者无
   `is_initialized()`）；结论不变，机制改为「`end_request` 在 `sink is None` 时直接 return」。
   这是**唯一一处「写错了依据、但结论侥幸对」**的地方，最危险 —— 照它去核会核过。
2. **【已落】§3.2 补写侧 fail-loud**：`llm_health_var.get() is None` ⇒ `logger.error`（防置位静默 no-op）。
3. **【已落】§5 判据③ 绑定 `input_hash`**：防「任意别的 gq 簇带实文」把判据蒙绿。
4. **【已落】§5 纪律 3 钉死 mock 边界**：须下沉到 `_stream_chat_http`，否则进不到置位点。
5. **【已落】§3.1 删掉「未来新增调用点自动覆盖」**：与事实相反（现存的就没覆盖）。
6. **【已定 · 结论翻转】§6.7 `_compress_memory`**：二轮评审判它「同形同病」、是「本轮最重发现」，
   **经回读规格后证伪**。规格（`classify.py:17-19`、`:128-131`，均引 §6.1 L826）明写：
   **request ok + 子节点 error = 「已被业务吸收」，v1 不回流（L3 二期）**；
   **root 的量程 = 「请求是否成功返回答」**。实测 `_compress_memory` 在回答产出**之后**才收尾
   （`:1068` 在 token yield 之后），失败时本轮回答**逐字一致**、无 error 帧、无兜底话术
   ⇒ 标它 root=error 是**假红且违反规格**。**⇒ A1 不成立：不纳入本批，也不新立待办（L3 二期已在规格里）。**
   评审此处的错 = **按形状归类**（「子节点 error + root ok」同形）而非按语义，且**未回读规格**
   —— 与我方既有教训「判『该不该发生』前必须回读规格」完全同型。**同形 ≠ 同病。**
7. **二轮确认不变的部分**（逐路径核过，不再改动）：mark/unmark 与「只取首次」在 round1/round2
   分工下无假红/假绿路径；`ContextVar` 持可变 dict 是跨 `BaseHTTPMiddleware` 任务 + 线程池唯一
   能写回的形态，并发天然隔离；`utils/trace.py` 无循环 import（`main.py:15` 已 import 它，只依赖标准库）。
