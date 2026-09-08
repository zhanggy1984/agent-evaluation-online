"""#89 4 仓冒烟探针（detail §14.1 S-1 前提 / S-4 前提数据解锁）。容器内 `docker exec obs-backend` 运行。

前置：obs-backend 已 up（consumer 由 lifespan 拉起，app_env=dev）；probe 在容器内用
compose 注入 env（DB_HOST=mysql / ES_URL / KAFKA_BOOTSTRAP 容器内 alias）建连，与
backend 同网络同 Settings 值域。

用法（宿主编排，逐 agent）：
    # 1) 触发业务请求前拍一次基线（累积计数快照 → /tmp/smoke_<agent>.json）
    docker exec obs-backend python /app/tests/integration/smoke_4agents_probe.py \
        --mode snapshot --agent contract-check
    # 2) 宿主侧触发该 agent 真实业务请求（curl/脚本，产 request + llm_call）
    # 3) 轮询断言新事件落库（ES 事件 + MySQL trace_judge_state）+ dropped 增量为 0
    docker exec obs-backend python /app/tests/integration/smoke_4agents_probe.py \
        --mode poll --agent contract-check --expect-llm 1 --timeout 180

断言口径（时间窗 = 计数增量，非 ts 过滤；基线累积值相减）：
- ES `{env}.obs-event-*` / `{env}.obs-log-*`：该 agent request doc +1（必有）、
  llm_call doc +1（--expect-llm 1 的仓）；重放无关（只验增量）。
- MySQL `trace_judge_state`：该 agent 新增 ≥1 行（step4 落库）。
- 无丢弃（零注入冒烟的 dropped 守卫）：form A 心跳 doc 仅在进程内 dropped 计数非空时写
  （consumer/main.py `_heartbeat_loop`）——正常事件被丢弃会立即使该 agent 出现带 dropped 的
  心跳 doc。故「无任何带 dropped 心跳 doc 新增」= 本轮真实事件零 schema/脱敏/agent 丢弃；
  一旦出现即 FAIL（真实丢包告警）。主落库 gate（request/llm/step4 齐到）本身已兜底：任一
  事件被丢弃 → poll 超时 FAIL，此检查是对「非预期 node 丢弃」的二次 tripwire。
- consumer 若在两拍之间重启，累积计数回零 → 增量按 max(0, now-base) 计算。

退出码：全绿 0，任一断言失败非 0（供编排串行短路）。
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, "/app")  # docker exec 默认 cwd=/app，但脚本目录先入 sys.path，显式补

from elasticsearch import AsyncElasticsearch  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.core.config import Settings  # noqa: E402

# 允许 env 覆盖（宿主直连 dev 调试）；容器内默认读 compose 注入 alias
FAILURES: list[str] = []
DROP_KEYS = ("schema", "agent_mismatch", "mask")


def check(name: str, ok: bool, detail: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        FAILURES.append(name)


async def _es_agent_stats(es: AsyncElasticsearch, agent: str) -> dict | None:
    """ES 全量（跨周 index）该 agent 的 doc 总量 + node 计数。异常/无 index → None。"""
    index = [f"{Settings().event_index_prefix}-*", f"{Settings().log_index_prefix}-*"]
    try:
        resp = await es.search(
            index=index,
            query={"term": {"agent": agent}},
            size=0,
            aggs={"nodes": {"terms": {"field": "node", "size": 20}}},
        )
    except Exception:
        return None
    total = int(resp["hits"]["total"]["value"])
    nodes: dict[str, int] = {}
    for b in resp["aggregations"]["nodes"]["buckets"]:
        nodes[b["key"]] = int(b["doc_count"])
    return {"total": total, "request": nodes.get("request", 0), "llm": nodes.get("llm_call", 0)}


async def _db_rows(engine, agent: str) -> int:
    """MySQL trace_judge_state 该 agent 行数（step4 落库）。异常 → -1。"""
    try:
        async with engine.connect() as conn:
            res = await conn.execute(
                text("SELECT COUNT(*) FROM trace_judge_state WHERE agent=:a"), {"a": agent}
            )
            return int(res.scalar())
    except Exception:
        return -1


async def _heartbeat_dropped(es: AsyncElasticsearch, agent: str) -> dict[str, int] | None:
    """最新 form A 心跳 doc 的 dropped 计数（consumer 进程内累积）。无 → None。"""
    index = [f"{Settings().event_index_prefix}-*"]
    try:
        resp = await es.search(
            index=index,
            query={"bool": {"filter": [{"term": {"node": "heartbeat"}}, {"term": {"agent": agent}}]}},
            sort=[{"ts": "desc"}],
            size=1,
        )
    except Exception:
        return None
    hits = resp["hits"]["hits"]
    if not hits:
        return None
    dropped = (hits[0].get("_source") or {}).get("dropped") or {}
    return {k: int(dropped.get(k, 0)) for k in DROP_KEYS}


async def snapshot(agent: str) -> None:
    settings = Settings()
    es = AsyncElasticsearch(settings.es_url)
    engine = create_async_engine(settings.sqlalchemy_url)
    try:
        stats = await _es_agent_stats(es, agent)
        rows = await _db_rows(engine, agent)
        dropped = await _heartbeat_dropped(es, agent)
        base = {
            "agent": agent,
            "ts_ms": int(time.time() * 1000),
            "es_total": stats["total"] if stats else -1,
            "es_request": stats["request"] if stats else -1,
            "es_llm": stats["llm"] if stats else -1,
            "db_rows": rows,
            "dropped": dropped,
        }
        path = f"/tmp/smoke_{agent}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(base, f, ensure_ascii=False)
        print(f"snapshot {agent}: {json.dumps(base, ensure_ascii=False)} -> {path}")
        # 说明：form A 心跳 doc 仅在 dropped 非空时写（main.py _heartbeat_loop），
        # 未见心跳 = 该 agent 迄今零丢弃 = 健康基线常态（dropped 按全 0 参与比较）。
    finally:
        await es.close()
        await engine.dispose()


async def poll(agent: str, expect_llm: bool, timeout_s: float) -> None:
    settings = Settings()
    es = AsyncElasticsearch(settings.es_url)
    engine = create_async_engine(settings.sqlalchemy_url)
    path = f"/tmp/smoke_{agent}.json"
    if not os.path.exists(path):
        print(f"[FAIL] 缺基线 {path}，先跑 --mode snapshot")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        base = json.load(f)

    def delta(cur: int, prev: int) -> int:
        # consumer 重启 → 累积计数回零/下降 → 按 0 增量处理，避免负值误报
        return max(int(cur) - int(prev), 0) if cur >= 0 and prev >= 0 else -1

    # 心跳 dropped 增量：无 doc（None）视同全 0——健康零丢弃时心跳 doc 不写，None 即全零。
    def dropped_delta(cur: dict | None, prev: dict | None) -> dict[str, int]:
        cur = cur or {}
        prev = prev or {}
        return {k: delta(cur.get(k, 0), prev.get(k, 0)) for k in DROP_KEYS}

    deadline = time.time() + timeout_s
    result = None
    while time.time() < deadline:
        stats = await _es_agent_stats(es, agent)
        rows = await _db_rows(engine, agent)
        dropped = await _heartbeat_dropped(es, agent)
        if stats is None or rows < 0:
            await asyncio.sleep(2)
            continue
        req_d = delta(stats["request"], base["es_request"])
        llm_d = delta(stats["llm"], base["es_llm"])
        db_d = delta(rows, base["db_rows"])
        dd = dropped_delta(dropped, base["dropped"])
        if req_d >= 1 and db_d >= 1 and (not expect_llm or llm_d >= 1):
            result = {"req_d": req_d, "llm_d": llm_d, "db_d": db_d, "dropped_delta": dd,
                      "es_total_delta": delta(stats["total"], base["es_total"])}
            break
        await asyncio.sleep(2)

    if result is None:
        stats = await _es_agent_stats(es, agent)
        rows = await _db_rows(engine, agent)
        dropped = await _heartbeat_dropped(es, agent)
        print(f"[FAIL] {agent} 轮询 {int(timeout_s)}s 超时：新事件未按预期落库")
        print(f"  基线 {base}")
        print(f"  现值 es_total={stats}, db_rows={rows}, dropped={dropped}")
        sys.exit(1)

    req_d = result["req_d"]
    llm_d = result["llm_d"]
    db_d = result["db_d"]
    check(f"{agent} 新 request 事件落 ES", req_d >= 1, f"+{req_d} request doc")
    if expect_llm:
        check(f"{agent} 新 llm_call 事件落 ES", llm_d >= 1, f"+{llm_d} llm_call doc")
    check(f"{agent} step4 落 MySQL trace_judge_state", db_d >= 1, f"+{db_d} 行")
    dd = result["dropped_delta"]
    bad = {k: v for k, v in dd.items() if v > 0}
    check(f"{agent} 本轮零丢弃（无新增 form A dropped 心跳）", not bad,
          f"delta={dd}：真实事件全部合法通过，无 schema/脱敏/agent 丢弃"
          if not bad else f"delta={dd} 含丢弃：{bad} —— 上抛真实丢包")
    print(f"\n===== {agent} probe 结果：{'全部通过' if not FAILURES else f'{len(FAILURES)} 项失败'} =====")
    for name in FAILURES:
        print(f"  - {name}")
    sys.exit(0 if not FAILURES else 1)


def main() -> None:
    p = argparse.ArgumentParser(description="#89 4 仓冒烟探针")
    p.add_argument("--mode", required=True, choices=["snapshot", "poll"])
    p.add_argument("--agent", required=True)
    p.add_argument("--expect-llm", type=int, default=1, help="期望本次触发含 llm_call 事件")
    p.add_argument("--timeout", type=float, default=120.0)
    args = p.parse_args()
    asyncio.run(
        snapshot(args.agent) if args.mode == "snapshot" else
        poll(args.agent, bool(args.expect_llm), args.timeout)
    )


if __name__ == "__main__":
    main()
