"""D6 集成验证 probe（detail §14.1 S-2/S-3）。容器内 `docker exec obs-backend` 运行。

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

退出码：全绿 0，任一断言失败非 0。
"""
import asyncio
import json
import sys
import time

sys.path.insert(0, "/app")  # docker exec 默认 cwd=/app，但脚本目录先入 sys.path，显式补

from aiokafka import AIOKafkaProducer  # noqa: E402
from elasticsearch import AsyncElasticsearch  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.consumer.main import classify  # noqa: E402  (预检本地判定，与消费链同源)
from app.core.config import Settings  # noqa: E402

AGENT = "good-question"
FAILURES: list[str] = []
TS_BASE = int(time.time() * 1000)  # 本周归属当前周 index；S-2/S-3 各 trace 时间戳下探避撞


def check(name: str, ok: bool, detail: str) -> None:
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


async def main() -> None:
    settings = Settings()
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap,
                                max_request_size=1_048_576)
    try:
        await producer.start()
        await s2(producer, settings)
        await s3(producer, settings)
    finally:
        await producer.stop()

    verdict = "全部通过" if not FAILURES else f"{len(FAILURES)} 项失败"
    print(f"\n===== D6 probe 结果：{verdict} =====")
    for name in FAILURES:
        print(f"  - {name}")
    sys.exit(0 if not FAILURES else 1)


if __name__ == "__main__":
    asyncio.run(main())
