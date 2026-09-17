"""七环真机验收：造故障**前**的基线水位快照。容器内 `docker exec obs-backend` 运行：

    docker exec obs-backend python /app/tests/integration/ring_baseline_probe.py > baseline.json

为什么要有这一步（不是可选的仪式）：为造对照而人为注入的故障，会在共享观测面留下与真缺陷
**逐字同形**的红（见 memory `self-injected-fault-looks-like-real-defect`）。事后唯一能区分
「这批红是我造的」与「真缺陷」的手段，就是事先记下的水位差 —— 没有基线，「新增了几行」这个
问题当场无法回答。

产出：一份 JSON 快照（四张主表的水位 + agent 表全量），供 `ring_state_probe.py --baseline`
做差。快照**落在调用方指定的路径**（通常 .tmp-probe/ 或容器 /tmp），不写进仓 —— 它是某一次
验收的现场记录，不是仓的资产。

⚠️ 基线是**当时**的水位：跨请求复用旧快照会让「新增」算错，故快照带 `ts`，`ring_state_probe`
会把它打印出来供核对。
"""
import json
import os
import sys
from datetime import datetime, timezone

import pymysql

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 四张主表 = 七环的落点面（环① trace_judge_state 另有独立水位，见下）
TABLES = ("error_cluster", "error_case_link", "verify_run_record", "conversion_record")


def main() -> None:
    conn = pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT") or 3306),
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        database=os.environ.get("DB_NAME") or "dev.obs", charset="utf8mb4")
    cur = conn.cursor()
    snap = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    for t in TABLES:
        cur.execute(f"SELECT COUNT(*), COALESCE(MAX(id),0) FROM {t}")
        n, mx = cur.fetchone()
        snap[t] = {"n": int(n), "max_id": int(mx)}
    # 环① 的水位（trace_judge_state 无 agent 过滤时也给全量，便于事后按 agent 取子集）
    cur.execute("SELECT COUNT(*), COALESCE(MAX(id),0) FROM trace_judge_state")
    n, mx = cur.fetchone()
    snap["trace_judge_state"] = {"n": int(n), "max_id": int(mx)}
    # agent 名→id 映射：探针反复踩过「把数字 id 当 agent 名传」⇒ 四个 agent 全返 0
    cur.execute("SELECT id, name FROM agent ORDER BY id")
    snap["agents"] = [{"id": i, "name": n} for i, n in cur.fetchall()]
    print(json.dumps(snap, ensure_ascii=False, indent=2, default=str))


main()
