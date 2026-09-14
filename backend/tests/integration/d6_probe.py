"""D6 集成验证 probe（detail §14.1 S-1~S-5 + T-4.1 残留大 trace 懒加载）。容器内跑。

前置：obs-backend 已 up（consumer 由 lifespan 拉起，app_env=dev）；probe 在容器内用
compose 注入的 env（DB_HOST=mysql/ES_URL/KAFKA_BOOTSTRAP 容器内 alias）建连，与
backend 同网络同 Settings 值域。

S-2：投 3 类非法事件（schema 缺字段 / agent≠topic / 未掩码敏感键）到 good-question
topic → 断言 form A 心跳 doc（node=heartbeat & agent=good-question）的 dropped 计数
含 schema/agent_mismatch/mask ≥1（selfmonitor 可见，§14.1 S-2）。
  心跳周期 60s（模块常量，D6 接受等待）：投递后轮询 ≤90s。
S-3：同一合法 trace（request ok + llm_call error + log）投 2 遍 → 断言 ES 同 _id 幂等
（跨 event/log 周 index 检索 trace_id 恰 3 doc、无重复行）+ MySQL trace_judge_state 恰
1 行（uk_trace 吸收重放，判定不重复）。已判定冻结前的重放会让 err_summary 内
llm_timeout count 变 2——**有意且有界**（judge/classify 只发生一次、ES _id 幂等、下游靠
judged bit + cluster 唯一性），故本断言只验"行数与 doc 数"，不验 err_summary 计数值。

S-1/S-4：**走真机 HTTP**（`127.0.0.1:8000/api/v1`，登录 → 取 auth，auth 不打印）读
S-3 那条 trace → 断言「详情可查 + event 面 seq 升序 + llm_call 节点原样 + 日志行懒加载 +
两面 seq 值域可合并」与「llm_call 子节点 status∈{error,timeout}（红显依据）+ `/metrics/
llm-failures` 可下钻到本 trace」。**CSS 级高亮/红显/穿插渲染不在本层**（归 T-4.11 浏览器 e2e），
本层只证「后端按契约把判据字段原样给出」。

S-5：`/traces` 检索面四条——命中 `error_msg`（+ 无关关键字对照）、偏移翻页第 1/2 页不重叠、
`offset ≥ 200` → 400 `ERR_TRACE_0002`、**限 7d 的正反对照**（投一条 8 天前同形 trace：默认窗口
裁掉、显式放宽 `start_ts` 命中 ⇒ 证裁剪真发生，而非只读常量）。该 trace 由本节自清（ES + MySQL）。
**「超时」不记作已验**：本环境无「慢 ES」注入手段，只登记接线事实。

T-4.1 残留「大 trace 懒加载」（task.md T-1.4）：判据**定性为结构型**——证的是「首屏上界与
trace 总行数**无关**」，而非「1000 行时够快」，故可用 N=200 证明（6 断言，含 1 条前置）；
残留的容量尾巴
（500 个 event 行的首屏算不算不拉爆）需真实量级 ⇒ 归 T-5.3。

退出码：全绿 0，任一断言失败非 0。
"""
import asyncio
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, "/app")  # docker exec 默认 cwd=/app，但脚本目录先入 sys.path，显式补

from aiokafka import AIOKafkaProducer  # noqa: E402
from elasticsearch import AsyncElasticsearch  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.consumer.main import classify  # noqa: E402  (预检本地判定，与消费链同源)
from app.core.config import Settings  # noqa: E402
from app.worker.judge_scan_job import run_judge_scan  # noqa: E402  (S-6 判定侧，进程内调 job)

AGENT = "good-question"
FAILURES: list[str] = []
TS_BASE = int(time.time() * 1000)  # 本周归属当前周 index；S-2/S-3 各 trace 时间戳下探避撞
API_BASE = "http://127.0.0.1:8000/api/v1"  # 容器内 loopback：验收面是 HTTP 契约，非 store 直查


CHECKED = 0  # 断言**执行**条数（由 check 自计，不靠人手工数输出行/调用点）


def check(name: str, ok: bool, detail: str) -> None:
    global CHECKED
    CHECKED += 1
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        FAILURES.append(name)


async def poll(desc: str, timeout_s: float, step: float, pred) -> bool:
    """轮询直到 pred() 真或超时（step 秒一跳）。"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if await pred():
            return True
        await asyncio.sleep(step)
    return False


# ---- 事件构造（dict → classify 预检 → JSON 投递；raw 与消费链同形，§2.2 ①） ----

def _request(agent: str, trace_id: str, ts: int, status: str = "ok",
             error_type: str | None = None, input_: dict | None = None) -> dict:
    return {
        "schema_version": "1.0", "event_kind": "event", "trace_id": trace_id,
        "agent": agent, "agent_version": "2026.08.31-r47",
        "interface": "POST /api/chat/{id}", "node": "request", "seq": 0,
        "parent": None, "ts": ts, "duration_ms": 1200, "status": status,
        "error_type": error_type, "error_msg": None, "input": input_,
        "output": None, "usage": None, "model": None, "extra": {},
    }


def _llm_error(trace_id: str, ts: int) -> dict:
    return {
        "schema_version": "1.0", "event_kind": "event", "trace_id": trace_id,
        "agent": AGENT, "agent_version": "2026.08.31-r47",
        "interface": "POST /api/chat/{id}", "node": "llm_call", "seq": 1,
        "parent": 0, "ts": ts, "duration_ms": 3000, "status": "error",
        "error_type": "llm_timeout", "error_msg": "provider timeout",
        "input": None, "output": None,
        "usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
        "model": "deepseek-v3", "extra": {},
    }


def _llm_ok(trace_id: str, ts: int) -> dict:
    """S-4 负对照用：与 `_llm_error` 同形，**只差 status**（llm_call 成功）。"""
    ev = _llm_error(trace_id, ts)
    return {**ev, "status": "ok", "error_type": None, "error_msg": None}


def _log(trace_id: str, ts: int) -> dict:
    return {
        "schema_version": "1.0", "event_kind": "log", "trace_id": trace_id,
        "agent": AGENT, "agent_version": "2026.08.31-r47",
        "interface": "POST /api/chat/{id}", "node": "log", "seq": 2,
        "parent": None, "ts": ts, "status": "ok",
        "log_level": "WARNING", "log_message": "retry attempt=2", "extra": {},
    }


# ---- S-2：三类非法事件（构造后本地预检分型，与消费链 classify 同源） ----

def build_s2_events():
    ts = TS_BASE + 1
    schema_bad = {"schema_version": "1.0"}  # 缺必填字段 → pydantic 拒绝
    mismatch = _request("customer-service", f"d6-s2-mis-{TS_BASE}", ts)  # topic 属 good-question
    leak = _request(AGENT, f"d6-s2-mask-{TS_BASE}", ts, input_={"token": "secret-123"})
    return ts, schema_bad, mismatch, leak


# ---- 主流程 ----

async def s2(producer, settings: Settings) -> None:
    print("\n===== S-2 三类非法事件丢弃 + form A 心跳计数可见 =====")
    topic = settings.agent_topic(AGENT)
    ts, schema_bad, mismatch, leak = build_s2_events()
    # 预检：分型与预期一致再投（防止自己造的事件语义漂移误报）
    check("S-2 预检 schema→SCHEMA", classify(schema_bad, AGENT)[0].value == "schema",
          f"classify 期望 schema，实际 {classify(schema_bad, AGENT)[0]}")
    check("S-2 预检 mismatch→AGENT_MISMATCH",
          classify(mismatch, AGENT)[0].value == "agent_mismatch",
          f"classify 期望 agent_mismatch，实际 {classify(mismatch, AGENT)[0]}")
    check("S-2 预检 mask→MASK", classify(leak, AGENT)[0].value == "mask",
          f"classify 期望 mask，实际 {classify(leak, AGENT)[0]}")
    for raw in (schema_bad, mismatch, leak):
        await producer.send(topic, json.dumps(raw, ensure_ascii=False).encode("utf-8"))
    await producer.flush()
    print("已投 3 类非法事件，轮询 form A 心跳 doc（≤90s，心跳周期 60s）…")

    es = AsyncElasticsearch(settings.es_url)
    week_prefix = f"{settings.event_index_prefix}-*"

    async def hb_visible() -> bool:
        try:
            resp = await es.search(
                index=week_prefix,
                query={
                    "bool": {
                        "filter": [
                            {"term": {"node": "heartbeat"}},
                            {"term": {"agent": AGENT}},
                        ]
                    }
                },
                sort=[{"ts": "desc"}], size=5,
            )
        except Exception:
            return False
        for hit in resp["hits"]["hits"]:
            dropped = (hit.get("_source") or {}).get("dropped") or {}
            if (dropped.get("schema", 0) >= 1 and dropped.get("agent_mismatch", 0) >= 1
                    and dropped.get("mask", 0) >= 1):
                return True
        return False

    ok = await poll("S-2 心跳含三类计数", 90, 5, hb_visible)
    detail = "轮询超时：heartbeat doc 未见 dropped{schema,agent_mismatch,mask}≥1"
    if ok:
        detail = "heartbeat doc 已见 dropped 计数含三类 ≥1（schema/agent_mismatch/mask）"
    check("S-2 非法事件丢弃计数 selfmonitor 可见", ok, detail)
    await es.close()


async def s3(producer, settings: Settings) -> None:
    print("\n===== S-3 同 trace 重放幂等（ES _id 无重复行 + MySQL 单行） =====")
    topic = settings.agent_topic(AGENT)
    trace_id = f"d6-s3-{TS_BASE}"
    ts = TS_BASE + 2
    trace = [_request(AGENT, trace_id, ts), _llm_error(trace_id, ts), _log(trace_id, ts)]
    for ev in trace:
        drop, _ = classify(ev, AGENT)
        check(f"S-3 预检合法（{ev['node']}）", drop is None,
              f"classify 应通过，实际 {drop}")

    # 投 2 遍（Kafka at-least-once 重投语义）
    for _ in range(2):
        for ev in trace:
            await producer.send(topic, json.dumps(ev, ensure_ascii=False).encode("utf-8"))
    await producer.flush()
    print(f"已投同 trace（{trace_id}）2 遍，轮询 ES/MySQL 幂等断言…")

    es = AsyncElasticsearch(settings.es_url)
    engine = create_async_engine(settings.sqlalchemy_url)

    async def es_docs() -> int:
        try:
            resp = await es.search(
                index=["dev.obs-event-*", "dev.obs-log-*"],
                query={"term": {"trace_id": trace_id}}, size=10,
            )
            return int(resp["hits"]["total"]["value"])
        except Exception:
            return -1

    async def mysql_rows() -> int:
        try:
            async with engine.connect() as conn:
                res = await conn.execute(
                    text("SELECT COUNT(*) FROM trace_judge_state "
                         "WHERE agent=:a AND trace_id=:t"),
                    {"a": AGENT, "t": trace_id},
                )
                return int(res.scalar())
        except Exception:
            return -1

    async def first_landed() -> bool:   # poll 谓词须为 async（await es_docs 再比较）
        return await es_docs() == 3

    # 第一阶段：第一遍完整落地（root+llm+log 全入 ES = 3 doc，MySQL 建 1 行）
    await poll("S-3 首遍落地", 40, 2, first_landed)

    # 第二阶段：等待第二遍（重放）也被消费后，幂等仍成立——ES 仍 3 doc、MySQL 仍 1 行
    # 无法从外部数"重放已消费"：给足消费窗口后断言终态（若重放产生第二行/重复 doc 则破）
    await asyncio.sleep(8)
    docs = await es_docs()
    rows = await mysql_rows()
    es_detail = f"跨 event/log 检索 {trace_id} = {docs} doc（期望 3）"
    check("S-3 ES 同 _id 幂等无重复行", docs == 3, es_detail)
    check("S-3 MySQL trace_judge_state 恰 1 行", rows == 1,
          f"SELECT COUNT = {rows}（期望 1，uk_trace 吸收重放）")
    await es.close()
    await engine.dispose()
    return trace_id


# ---- S-1 / S-4：走真机 HTTP（trace 详情 / 日志懒加载 / llm-failures 下钻） ----

def _http(method: str, path: str, auth: str | None = None,
          body: dict | None = None) -> tuple[int, object]:
    """同步 HTTP 调用（urllib，零新依赖）；由 to_thread 包进 async。auth 绝不打印。"""
    req = urllib.request.Request(API_BASE + path, method=method)
    if auth:
        req.add_header("Authorization", f"Bearer {auth}")
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # 4xx 也要**按声明形状解析**（AppError → 扁平 {code, message}，errors.py:30）——
        # 早先此处塞 "_raw" 字符串，导致「断言因取不到 code 而永不可通过」（判据不可达）。
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"_raw": raw}


async def _api(method: str, path: str, auth: str | None = None,
               body: dict | None = None) -> tuple[int, object]:
    return await asyncio.to_thread(_http, method, path, auth, body)


async def s1_s4(producer, settings: Settings, trace_id: str) -> None:
    """S-1（trace 可查 / 日志穿插 / llm_call 高亮）+ S-4（子节点红显 / llm-failures 可下钻）。

    **输入 = S-3 已投的同一 trace**（request ok + llm_call error + log，正是 S-1/S-4 的场景），
    不另投一份：省一次投递，且顺带证「重放后的 trace 读面仍正确」。

    **口径说明（勿读成更强）**：S-1 的「日志穿插」在本实现里**不是后端合并列表**——
    详情端点只返 event 行、日志行走 `/{trace_id}/logs` 懒加载（`trace.py:79/96`），
    穿插发生在**前端渲染层**（归 T-4.11）。故本处可验的形态 = 「两个面各自可查、seq 值域
    互不重叠且并集恰为 [0,1,2]」⇒ 前端按 seq 合并即得穿插。此断言**弱于**「渲染已穿插」，
    后者需浏览器 e2e。
    """
    print("\n===== S-1 trace 可查 + 日志懒加载 + llm_call 高亮 =====")
    # S-4 负对照：同形但 **llm_call 成功** 的 trace（只差一个字段取值的最小差异对）
    ctl_trace = f"d6-ctl-{TS_BASE}"
    topic = settings.agent_topic(AGENT)
    await producer.send(topic, json.dumps(_request(AGENT, ctl_trace, TS_BASE + 3),
                                          ensure_ascii=False).encode("utf-8"))
    await producer.send(topic, json.dumps(_llm_ok(ctl_trace, TS_BASE + 4),
                                          ensure_ascii=False).encode("utf-8"))
    await producer.flush()
    status, tok = await _api("POST", "/auth/login",
                             body={"username": settings.admin_username,
                                   "password": settings.admin_password})
    auth = (tok or {}).get("access_token") if isinstance(tok, dict) else None
    check("S-1 登录取得 access_token", status == 200 and bool(auth),
          f"POST /auth/login → {status}（凭证不入日志）")
    if not auth:
        return None

    status, detail = await _api("GET", f"/traces/{AGENT}/{trace_id}", auth)
    if not isinstance(detail, dict):
        detail = {}
    events = detail.get("events") or []
    check("S-1 trace 详情可查", status == 200 and bool(events),
          f"GET /traces/{AGENT}/{trace_id} → {status}，events={len(events)} 条")
    nodes = [e.get("node") for e in events]
    seqs = [e.get("seq") for e in events]
    check("S-1 event 面按 seq 升序还原拓扑序", seqs == sorted(s for s in seqs if s is not None),
          f"seq 序列 = {seqs}")
    check("S-1 llm_call 高亮依据（node 字段原样返回）", "llm_call" in nodes,
          f"node 序列 = {nodes}（前端高亮判据 = node=='llm_call'，CSS 级归 T-4.11）")

    status, logs = await _api("GET", f"/traces/{AGENT}/{trace_id}/logs", auth)
    if not isinstance(logs, dict):
        logs = {}
    items = logs.get("items") or []
    check("S-1 日志行懒加载可查", status == 200 and bool(items),
          f"GET .../logs → {status}，items={len(items)} 条")
    log_seq = [i.get("seq") for i in items]
    merged = sorted([s for s in seqs if s is not None] + [s for s in log_seq if s is not None])
    check("S-1 日志穿插的**值域条件**（两面 seq 并集连续无重叠）",
          bool(log_seq) and merged == list(range(len(merged))) and len(set(merged)) == len(merged),
          f"event seq={seqs} + log seq={log_seq} → 并集 {merged}"
          "（前端按 seq 合并即穿插；渲染本体归 T-4.11）")
    check("S-1 日志字段带 log_level", all(i.get("log_level") for i in items),
          f"log_level = {[i.get('log_level') for i in items]}")

    print("\n===== S-4 子节点红显 + llm-failures 可下钻 =====")
    llm = next((e for e in events if e.get("node") == "llm_call"), {})
    root = next((e for e in events if e.get("node") == "request"), {})
    check("S-4 红显依据（llm_call 子节点 status∈{error,timeout}）",
          llm.get("status") in ("error", "timeout") and root.get("status") == "ok",
          f"llm_call.status={llm.get('status')!r} / request.status={root.get('status')!r}"
          "（红显判据 = status∈{error,timeout}，CSS 归 T-4.11）")
    check("S-4 子节点错因字段可读", llm.get("error_type") == "llm_timeout",
          f"llm_call.error_type={llm.get('error_type')!r}")

    # llm-failures 有 60s 进程级缓存（metric_agg_cache_ttl_s 默认 60）⇒ 轮询 ≤ TTL+30s
    async def drillable() -> bool:
        st, resp = await _api("GET", f"/metrics/llm-failures?agent={AGENT}&window=1h", auth)
        if st != 200 or not isinstance(resp, dict):
            return False
        rows = resp.get("items") or resp.get("failures") or []
        return any((r.get("trace_id") == trace_id) for r in rows if isinstance(r, dict))

    ok = await poll("S-4 llm-failures 含本 trace", 90, 10, drillable)
    check("S-4 /metrics/llm-failures 可下钻到本 trace", ok,
          "命中本 trace_id" if ok else "轮询 90s（>TTL 60s）仍未见，可能窗口/聚合口径不符")

    # 负对照：否则「命中本 trace」与「命中任何 trace」观测等价，上一条无判别力。
    # 对照 trace 须**先确认已落地**，否则「不在列表」可能只是「还没进 ES」。
    # 落地须**轮询等待**：投完即查会撞上消费链未落地（实测 404）——前置条的意义正在于此，
    # 它把这情况判成 FAIL 而不是让下面的「不在列表」假绿。
    async def ctl_landed() -> bool:
        st, _ = await _api("GET", f"/traces/{AGENT}/{ctl_trace}", auth)
        return st == 200

    ctl_ok = await poll("S-4 对照 trace 落地", 120, 5, ctl_landed)
    check("S-4 对照 trace 已落地（前置）", ctl_ok,
          (f"对照 {ctl_trace} 已可查（轮询等待消费链落地）" if ctl_ok
           else f"对照 {ctl_trace} 轮询 120s 仍不可查 ⇒ 数据不足，判 FAIL 不静默通过"))
    if ctl_ok:
        st_f, resp_f = await _api("GET", f"/metrics/llm-failures?agent={AGENT}&window=1h", auth)
        rows_f = (resp_f.get("items") or []) if isinstance(resp_f, dict) else []
        ids = [r.get("trace_id") for r in rows_f if isinstance(r, dict)]
        check("S-4 负对照：同形但 llm_call 成功的 trace **不在**失败列表",
              st_f == 200 and trace_id in ids and ctl_trace not in ids,
              f"st={st_f}、本 trace 在={trace_id in ids}、对照在={ctl_trace in ids}"
              f"（期望 st=200/True/False；谓词 node='llm_call' ∧ "
              f"status∈{{error,timeout}}，es.py:349）")

    es = AsyncElasticsearch(settings.es_url)
    engine = create_async_engine(settings.sqlalchemy_url)
    try:
        await es.delete_by_query(index=["dev.obs-event-*", "dev.obs-log-*"],
                                 query={"term": {"trace_id": ctl_trace}},
                                 conflicts="proceed", refresh=True)
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM trace_judge_state WHERE agent=:a AND trace_id=:t"),
                               {"a": AGENT, "t": ctl_trace})
        print(f"已清理 S-4 对照 trace {ctl_trace}（MySQL 判定行 + ES doc）")
    except Exception as exc:
        print(f"清理 {ctl_trace} 失败（残留，需人工确认）：{exc}")
    finally:
        await es.close()
        await engine.dispose()
    return auth


async def s5(producer, settings: Settings, auth: str, fresh_trace: str) -> None:
    """S-5（命中 error_msg / 深翻页 / 限 7d / 上限）——走真机 HTTP `/traces` 检索面。

    **归因式判据（勿读成「不为 0」）**：每条正向断言都写「**等于谁**」，并配一条对照，
    防「keyword 被整条忽略」这类假绿——同族教训见 X-4 假红（OR 语义把注入串拆出单字符）。

    「限 7d」取**正反对照**而非读常量：同一关键字下，默认窗口**不含** 8 天前的同形 trace、
    显式放宽 `start_ts` 后**含**它 ⇒ 窗口裁剪真的发生了（读常量只能证「配置是 7」）。
    「超时」**不做故障注入**——本环境无「慢 ES」注入手段，只登记接线事实（见下），
    不假装验过（同 E-19/F-13 的记账纪律）。
    """
    print("\n===== S-5 关键字检索：命中 error_msg / 深翻页 / 限 7d / 上限 =====")
    kw = "provider timeout"          # = _llm_error 的 error_msg，故命中即证 error_msg 在检索面
    miss_kw = "d6-no-such-keyword-zzz"  # 对照：不存在的串必须查不到本 trace
    old_trace = f"d6-s5-old-{TS_BASE}"
    old_ts = TS_BASE - 8 * 24 * 3600 * 1000   # 8 天前（超出默认 7d 窗口）

    async def qs(query: str, **extra) -> tuple[int, dict]:
        q = f"?keyword={urllib.parse.quote(query)}&agent={AGENT}"
        for k, v in extra.items():
            q += f"&{k}={v}"
        st, resp = await _api("GET", f"/traces{q}", auth)
        return st, resp if isinstance(resp, dict) else {}

    st, resp = await qs(kw)
    ids = [i.get("trace_id") for i in (resp.get("items") or [])]
    check("S-5 命中 error_msg（本 trace 在结果内）", st == 200 and fresh_trace in ids,
          f"keyword={kw!r} → {st}，total={resp.get('total')}，含本 trace={fresh_trace in ids}")
    st_m, resp_m = await qs(miss_kw)
    ids_m = [i.get("trace_id") for i in (resp_m.get("items") or [])]
    check("S-5 对照：无关关键字查不到本 trace（排除 keyword 被忽略）",
          st_m == 200 and fresh_trace not in ids_m,
          f"keyword={miss_kw!r} → {st_m}，items={len(ids_m)}，含本 trace={fresh_trace in ids_m}")

    # 深翻页：同页宽下第 1/2 页无重叠（§8.2 collapse(trace_key)+from/size 偏移）
    st1, r1 = await qs(kw, page=1, page_size=1)
    st2, r2 = await qs(kw, page=2, page_size=1)
    i1 = [i.get("trace_id") for i in (r1.get("items") or [])]
    i2 = [i.get("trace_id") for i in (r2.get("items") or [])]
    total = r1.get("total")
    if isinstance(total, int) and total >= 2 and st1 == 200 and st2 == 200:
        check("S-5 偏移翻页第 1/2 页不重叠", bool(i1) and bool(i2) and not set(i1) & set(i2),
              f"page1={i1} / page2={i2}（total={total}）")
    else:
        check("S-5 偏移翻页第 1/2 页不重叠", False,
              f"前置不足：total={total} st1={st1} st2={st2}（数据不足以判别 ⇒ 判 FAIL 不静默通过）")

    # 上限：offset ≥ MAX_LIST_RESULTS(200) → 400 ERR_TRACE_0002
    st_ok, _ = await qs(kw, page_size=2, page=100)   # offset = 198 < 200
    st_bad, body = await qs(kw, page_size=2, page=101)  # offset = 200 → 越界
    code = body.get("code") if isinstance(body, dict) else None
    msg = body.get("message") if isinstance(body, dict) else None
    check("S-5 上限：offset<200 放行 / offset≥200 → 400 ERR_TRACE_0002",
          st_ok == 200 and st_bad == 400 and code == "ERR_TRACE_0002" and bool(msg),
          f"page*2=198 → {st_ok}；page*2=200 → {st_bad} code={code!r} message={msg!r}"
          "（形状取声明源 errors.py:30 = 扁平 {code,message}）")

    # 限 7d：投一条 8 天前的同形 trace（同 error_msg），默认窗口应排除、显式放宽应命中
    old_trace_events = [_request(AGENT, old_trace, old_ts, input_={"q": "s5-window"}),
                        _llm_error(old_trace, old_ts)]
    topic = settings.agent_topic(AGENT)
    for ev in old_trace_events:
        await producer.send(topic, json.dumps(ev, ensure_ascii=False).encode("utf-8"))
    await producer.flush()
    print(f"已投 8 天前同形 trace（{old_trace}，ts={old_ts}），等待落地后验窗口裁剪…")

    async def old_landed() -> bool:
        st_, r_ = await qs(kw, start_ts=old_ts - 3600_000, end_ts=old_ts + 3600_000)
        return st_ == 200 and old_trace in [i.get("trace_id") for i in (r_.get("items") or [])]

    landed = await poll("S-5 旧 trace 落地", 60, 5, old_landed)
    st_def, r_def = await qs(kw)   # 默认窗口（不传 start_ts）
    in_def = old_trace in [i.get("trace_id") for i in (r_def.get("items") or [])]
    in_fresh_def = fresh_trace in [i.get("trace_id") for i in (r_def.get("items") or [])]
    check("S-5 限 7d：8 天前 trace 被默认窗口裁掉（同关键字、同 agent）",
          landed and not in_def,
          f"落地={landed}；默认窗口含旧 trace={in_def}（期望 False）")
    check("S-5 同一次默认窗口查询仍含今天的新 trace（证裁剪非「整条查不到」）",
          in_fresh_def, f"默认窗口含 {fresh_trace}={in_fresh_def}（期望 True）")

    # 收尾：清掉本节自造的旧 trace（ES 两 index + MySQL 判定行），幂等
    es = AsyncElasticsearch(settings.es_url)
    engine = create_async_engine(settings.sqlalchemy_url)
    try:
        await es.delete_by_query(index=["dev.obs-event-*", "dev.obs-log-*"],
                                 query={"term": {"trace_id": old_trace}},
                                 conflicts="proceed", refresh=True)
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM trace_judge_state "
                                    "WHERE agent=:a AND trace_id=:t"),
                               {"a": AGENT, "t": old_trace})
        print(f"已清理本节自造 trace {old_trace}（MySQL 判定行 + ES doc）")
    except Exception as exc:  # 清理失败不掩盖主断言结论
        print(f"清理 {old_trace} 失败（残留，需人工确认）：{exc}")
    finally:
        await es.close()
        await engine.dispose()
    print("S-5 「超时」口径：本环境**未做故障注入**（无「慢 ES」手段）⇒ 只登记接线事实"
          "（`trace_query_timeout_ms` → `request_timeout_s=max(ms/1000,1.0)`，trace.py 三处），"
          "**不记作已验通过**。")


async def s1_lazy(producer, settings: Settings, auth: str) -> None:
    """T-4.1 残留「大 trace 懒加载」（task.md T-1.4「单 trace 上千日志行首屏不拉爆」）。

    **判据定性 = 结构型**（不是容量型）：被验的不是「1000 行时跑得够快」，而是
    「**首屏上界与 trace 总行数无关**」——该命题由两个实现层硬上界承载：
      - 详情面 `size=MAX_DETAIL_EVENTS(500)` + `truncated = total > limit`（`es.py:23/166/174`）；
      - 日志**不在详情面**（`trace.py:79` 只返 event 行），走独立分页端点，默认
        `page_size=50`、硬上界 `le=200`（`trace.py:204-205`）、默认 `body_search=false`
        （正文置空）。
    ⇒ **可用 N > page_size 的少量数据证明**（本处 N=200），**不需要真造上千行**。
    残留的**容量尾巴**（「500 个 event 行的首屏算不算不拉爆」）仍需真实量级 + 时延测量 ⇒ 归 T-5.3。
    """
    print("\n===== T-4.1 残留：大 trace 懒加载（首屏上界与总数无关） =====")
    trace_id = f"d6-lazy-{TS_BASE}"
    n_log = 200
    ts = TS_BASE + 3
    topic = settings.agent_topic(AGENT)
    await producer.send(topic, json.dumps(_request(AGENT, trace_id, ts), ensure_ascii=False)
                        .encode("utf-8"))
    for i in range(n_log):   # seq 3..202：doc_id=none(agent|trace|seq) ⇒ 200 个不同 doc，不互覆
        await producer.send(topic, json.dumps(
            {"schema_version": "1.0", "event_kind": "log", "trace_id": trace_id,
             "agent": AGENT, "agent_version": "2026.08.31-r47",
             "interface": "POST /api/chat/{id}", "node": "log", "seq": 3 + i,
             "parent": None, "ts": ts + i, "status": "ok",
             "log_level": "INFO", "log_message": f"lazy line {i}", "extra": {}},
            ensure_ascii=False).encode("utf-8"))
    await producer.flush()
    print(f"已投 1 event + {n_log} log（trace={trace_id}），等待落地后验首屏上界…")

    async def logs_page(page: int, size: int) -> tuple[int, list, object]:
        st, resp = await _api("GET",
                              f"/traces/{AGENT}/{trace_id}/logs?page={page}&page_size={size}", auth)
        if st != 200 or not isinstance(resp, dict):
            return st, [], None
        return st, resp.get("items") or [], resp.get("total")

    async def landed() -> bool:
        st, items, total = await logs_page(1, 50)
        return st == 200 and total == n_log

    ok = await poll("大 trace 日志落地", 120, 5, landed)
    if not ok:
        check("大 trace 懒加载：前置（200 条日志全部落地）", False,
              f"轮询 120s 未达 total={n_log} ⇒ 数据不足，**判 FAIL 不静默通过**")
        return

    st_d, detail = await _api("GET", f"/traces/{AGENT}/{trace_id}", auth)
    events = (detail.get("events") or []) if isinstance(detail, dict) else []
    check("大 trace 懒加载：日志**不在**详情面（首屏只含 event 行）",
          st_d == 200 and len(events) == 1 and all(e.get("node") != "log" for e in events),
          f"详情 events={len(events)} 条、node={[e.get('node') for e in events]}"
          f"（期望恰 1 条 request）")

    st, items50, total = await logs_page(1, 50)
    check("大 trace 懒加载：首屏有界（库里 200 条、默认一页只回 50）",
          st == 200 and len(items50) == 50 and total == n_log,
          f"page_size=50 → items={len(items50)}，total={total}（上界与总数无关的正证）")

    st_ok, items200, _ = await logs_page(1, 200)
    st_bad, resp_bad = await _api("GET",
                                  f"/traces/{AGENT}/{trace_id}/logs?page=1&page_size=201", auth)
    check("大 trace 懒加载：page_size 硬上界 200（201 → 422，声明源 trace.py:205）",
          len(items200) == n_log and st_bad == 422,
          f"page_size=200 → {len(items200)} 条；page_size=201 → {st_bad}"
          f"（FastAPI 校验错误形状无 code 键，detail="
          f"{bool(isinstance(resp_bad, dict) and resp_bad.get('detail'))}）")

    body_none = bool(items50) and all(i.get("log_message") is None for i in items50)
    check("大 trace 懒加载：默认 body_search=false 不下发日志正文",
          body_none, f"首屏 log_message 全为 None = {body_none}")

    # 正对照（否则「默认不下发」与「永远不下发」观测等价，该断言无判别力）：
    # body_search=true 时正文必须回传，且**逐字等于**投递原文（归因式断言，非只判非空）。
    st_b, resp_b = await _api(
        "GET", f"/traces/{AGENT}/{trace_id}/logs?page=1&page_size=50&body_search=true", auth)
    items_b = (resp_b.get("items") or []) if isinstance(resp_b, dict) else []
    msgs = [i.get("log_message") for i in items_b]
    check("大 trace 懒加载：body_search=true 正文逐字回传（上一条的正对照）",
          st_b == 200 and "lazy line 0" in msgs and msgs.count(None) == 0,
          f"st={st_b}、命中 'lazy line 0' = {'lazy line 0' in msgs}、"
          f"None 数 = {msgs.count(None)}（共 {len(msgs)} 行）")

    es = AsyncElasticsearch(settings.es_url)
    engine = create_async_engine(settings.sqlalchemy_url)
    try:
        await es.delete_by_query(index=["dev.obs-event-*", "dev.obs-log-*"],
                                 query={"term": {"trace_id": trace_id}},
                                 conflicts="proceed", refresh=True)
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM trace_judge_state "
                                    "WHERE agent=:a AND trace_id=:t"),
                               {"a": AGENT, "t": trace_id})
        print(f"已清理本节自造 trace {trace_id}（MySQL 判定行 + ES doc）")
    except Exception as exc:
        print(f"清理 {trace_id} 失败（残留，需人工确认）：{exc}")
    finally:
        await es.close()
        await engine.dispose()


# ---- S-6：E-14 分批到达「窗口补全后判定」（detail §14.3 E-14） ----

async def s6_e14(producer, settings: Settings) -> None:
    """E-14 判据原文 =「长 SSE 分批到达仍等窗口补全后判定（root 到达标记）」。

    机制（`consumer/state.py:118/167-168`）：`ttl_until = 触发行事件 ts + window(60)+grace(300)s`，
    `judged=0` 时**每来一个触发行事件即顺延**；扫描位点 = `judged=0 ∧ ttl_until<=now`
    （`judge_scan_job.py:84`）⇒ **窗口内不判**。故本步**不必等 360s**，用三条断言代替：

      A 到达侧（真机 Kafka 消费链）：只投 root ⇒ 建档、`root_ok=1`、**`judged=0`**（窗口内不判）；
      B 到达侧：窗口内补投**错误子节点** ⇒ `ttl_until` **恰顺延该事件的 ts 差**（= 后续批次被
        纳入同一窗口，**非丢弃、非另建行**）+ 累积集含该错误；
      C 判定侧（进程内调 job 函数，与 cluster_probe 同法，**非** Kafka 链）：**夹具动作 =
        把 `ttl_until` 拨到过去**以模拟窗口到期 ⇒ `run_judge_scan` 判掉 ⇒ 防「永远不判」的假绿。

    期望值取自声明源而非推测：B 用**差值**断言（对时区/epoch 换算约定免疫），
    A/C 的 `judged` 位取自 `state.py` 与 `judge_scan_job.py` 的谓词原文。
    """
    print("\n===== S-6 E-14 分批到达：窗口内不判 / 后续批次纳入同窗 / 到期才判 =====")
    topic = settings.agent_topic(AGENT)
    trace_id = f"d6-e14-{TS_BASE}"
    ts1 = TS_BASE + 20        # 第 1 批：root
    ts2 = ts1 + 3_000         # 第 2 批：迟到的错误子节点（ts 晚 3s）
    engine = create_async_engine(settings.sqlalchemy_url)

    async def send(ev: dict) -> None:
        await producer.send(topic, json.dumps(ev, ensure_ascii=False).encode("utf-8"))
        await producer.flush()

    async def fetch():
        async with engine.connect() as conn:
            res = await conn.execute(text(
                "SELECT judged, root_ok, ttl_until, err_summary_json "
                "FROM trace_judge_state WHERE agent=:a AND trace_id=:t"),
                {"a": AGENT, "t": trace_id})
            return res.first()

    def entries_of(row) -> list:
        """err_summary_json 在 MySQL 是 JSON 列：驱动可能回 dict 或 str，两种都认。"""
        raw = row[3]
        if raw is None:
            return []
        obj = raw if isinstance(raw, dict) else json.loads(raw)
        return list(obj.get("entries") or [])

    # ---- A 第 1 批（仅 root）----
    ev1 = _request(AGENT, trace_id, ts1)
    drop, _ = classify(ev1, AGENT)
    check("S-6 第 1 批（仅 root）预检合法", drop is None, f"classify 应通过，实际 {drop}")
    await send(ev1)

    async def row_exists() -> bool:
        return (await fetch()) is not None

    got1 = await poll("S-6 第 1 批落地", 40, 2, row_exists)
    row1 = await fetch() if got1 else None
    check("S-6 A 仅 root 也已建档（前置：不建档则后续断言无对象）",
          got1 and row1 is not None,
          (f"judged={row1[0]} root_ok={row1[1]}（残/半程 trace 也落行，state.py:150-155）"
           if got1 else "轮询 40s 仍未建档 ⇒ 数据不足，判 FAIL 不静默通过"))
    if row1 is None:
        await engine.dispose()
        return
    check("S-6 A 窗口内不判：第 1 批落地后 judged 仍为 0",
          int(row1[0]) == 0,
          f"judged={row1[0]}、ttl_until={row1[2]}（判为 1 则说明未等窗口就用残缺集下了判定）")
    ttl1 = row1[2]

    # ---- B 窗口内补投第 2 批（错误子节点）----
    ev2 = _llm_error(trace_id, ts2)
    drop, _ = classify(ev2, AGENT)
    check("S-6 第 2 批（llm_call error）预检合法", drop is None,
          f"classify 应通过，实际 {drop}")
    await send(ev2)

    async def batch2_landed() -> bool:
        row = await fetch()
        return row is not None and any(e.get("error_type") == "llm_timeout"
                                       for e in entries_of(row))

    got2 = await poll("S-6 第 2 批纳入累积集", 40, 2, batch2_landed)
    row2 = await fetch()
    check("S-6 B 窗口内到达的后续批次被纳入累积集（同窗、同行的 err_summary）",
          got2,
          (f"entries={[e.get('error_type') for e in entries_of(row2)]}"
           if got2 else "轮询 40s 累积集仍无 llm_timeout ⇒ 后续批次未纳入"))
    delta = (row2[2] - ttl1) if (row2 is not None and ttl1 is not None) else None
    check("S-6 B 窗口随触发行事件顺延，且顺延量**恰等于该事件的 ts 差**（3s）",
          delta is not None and abs(delta.total_seconds() - 3.0) < 0.005,
          f"ttl1={ttl1} → ttl2={row2[2] if row2 else None}（差 {delta}，期望 3s）"
          "⇒ 顺延则说明窗口尚未关闭、该批次仍计入同一判定集")

    # ---- C 到期才判（把 ttl 拨到过去 = 模拟窗口到期；唯一夹具动作）----
    async with engine.begin() as conn:
        await conn.execute(text(
            "UPDATE trace_judge_state SET ttl_until = :past "
            "WHERE agent=:a AND trace_id=:t"),
            {"past": dt.datetime.now() - dt.timedelta(minutes=1),
             "a": AGENT, "t": trace_id})
    judged_n = await run_judge_scan(engine)
    row3 = await fetch()
    check("S-6 C 窗口到期后才被判（对照：防「永远不判」的假绿）",
          row3 is not None and int(row3[0]) == 1,
          f"run_judge_scan 置 judged=1 行数={judged_n}、"
          f"本行 judged={row3[0] if row3 else None}")
    # judgement_json 单独取（列较多，避免 fetch 里塞满）
    async with engine.connect() as conn:
        res = await conn.execute(text(
            "SELECT judgement_json FROM trace_judge_state WHERE agent=:a AND trace_id=:t"),
            {"a": AGENT, "t": trace_id})
        raw = res.scalar()
    if raw is not None:
        layer = (raw if isinstance(raw, dict) else json.loads(raw)).get("layer")
    check("S-6 C 判定层 = none（root_status='ok' ⇒ _collect_candidates 门控不建候选 = 兜底吸收）",
          layer == "none",
          f"layer={layer}（T-3.10 门控：root 已 ok 的子节点错误走兜底吸收，不作候选）")

    # ---- 自清（幂等：本 trace 的 ES 事件 + MySQL 行）----
    es = AsyncElasticsearch(settings.es_url)
    try:
        await es.delete_by_query(
            index=["dev.obs-event-*", "dev.obs-log-*"],
            query={"term": {"trace_id": trace_id}}, refresh=True)
        await es.close()
    except Exception as exc:  # noqa: BLE001
        print(f"[S-6] ES 自清异常（不判 FAIL）：{exc}")
    async with engine.begin() as conn:
        await conn.execute(text(
            "DELETE FROM trace_judge_state WHERE agent=:a AND trace_id=:t"),
            {"a": AGENT, "t": trace_id})
    await engine.dispose()
    print(f"[S-6] 已自清 {trace_id}（ES 文档 + MySQL 判定行）")


async def main() -> None:
    settings = Settings()
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap,
                                max_request_size=1_048_576)
    try:
        await producer.start()
        await s2(producer, settings)
        s3_trace_id = await s3(producer, settings)
        await s6_e14(producer, settings)
        auth = await s1_s4(producer, settings, s3_trace_id)
        if auth:
            await s5(producer, settings, auth, s3_trace_id)
            await s1_lazy(producer, settings, auth)
    finally:
        await producer.stop()

    verdict = "全部通过" if not FAILURES else f"{len(FAILURES)} 项失败"
    print(f"\n===== D6 probe 结果：{verdict} =====")
    print(f"断言 {CHECKED} 条：PASS {CHECKED - len(FAILURES)} / FAIL {len(FAILURES)}"
          "（**由 check 自计**，勿按输出行数或调用点手工数——见 report §6 F-15 ⑧）")
    for name in FAILURES:
        print(f"  - {name}")
    sys.exit(0 if not FAILURES else 1)


if __name__ == "__main__":
    asyncio.run(main())
