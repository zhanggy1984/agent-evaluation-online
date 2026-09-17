"""七环真机验收：按 agent 报「环①②③」各环的落点行（可与基线做差）。容器内运行：

    docker exec obs-backend python /app/tests/integration/ring_state_probe.py [agent 名] \
        [--baseline /tmp/baseline.json]

不给 `--baseline` 则只打**绝对水位**、不打差 —— 这是刻意的：原版把 2026-09-16 那次验收的
基线**写死成常量**，换个 agent（gq）或隔几天再跑，`新增≤` 一栏就算错，而输出仍像正常结果。
差必须由**调用方当次**的快照（`ring_baseline_probe.py` 的产出）提供，不做任何默认。

agent 名默认报全部四家（good-question / customer-service / contract-check /
smart-procurement）。

⚠️ `trace_judge_state.agent` / `error_cluster.agent` 存的是**字符串名、不是数字 id**。
2026-09-16 首版按 id 传入，四个 agent 全返 0，差点读成「环① 无数据」（见 memory
`shape-mismatch-yields-silent-zero`：任何「0 条」结论落笔前先 dump 原始值）。

本探针是**观测面**、不做断言（与同目录 `*_probe.py` 那些自建自清、跑完给 pass/fail 的不同）：
七环的判据是「台账里的结论」，本探针只负责把现场摊开给人看。
"""
import argparse
import json
import os
import sys

import pymysql

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ALL_AGENTS = ("good-question", "customer-service", "contract-check", "smart-procurement")
TABLES = ("trace_judge_state", "error_cluster", "error_case_link",
          "verify_run_record", "conversion_record")


def cols(cur, t):
    cur.execute(f"SHOW COLUMNS FROM {t}")
    return [r[0] for r in cur.fetchall()]


def show_ring1(cur, name):
    """环① 观测：trace_judge_state 最近 5 行。"""
    cur.execute("SELECT COUNT(*), COALESCE(MAX(id),0) FROM trace_judge_state WHERE agent=%s",
                (name,))
    n, mx = cur.fetchone()
    print(f"  环① trace_judge_state: n={n} max_id={mx}")
    cur.execute("SELECT id, trace_id, interface, root_status, root_error_type, judged, "
                "llm_fact_ok, updated_ts FROM trace_judge_state WHERE agent=%s "
                "ORDER BY id DESC LIMIT 5", (name,))
    for r in cur.fetchall():
        print(f"     id={r[0]} iface={r[2]} root_status={r[3]} root_err={r[4]} "
              f"judged={r[5]} llm_fact={r[6]} ts={r[7]}")


def show_rings(cur, name):
    show_ring1(cur, name)
    # 环② 聚类
    cur.execute("SELECT id, interface, layer, error_type, status, count, created_at "
                "FROM error_cluster WHERE agent=%s ORDER BY id DESC LIMIT 5", (name,))
    print("  环② error_cluster 最近 5 行（id|iface|layer|err|status|count|ts）:")
    for r in cur.fetchall():
        print(f"     {r}")
    # 环③ 组装（link）
    cur.execute("SELECT l.id, l.cluster_id, l.payload_id, l.offline_status, l.verify_status, "
                "l.created_at FROM error_case_link l JOIN error_cluster c ON c.id=l.cluster_id "
                "WHERE c.agent=%s ORDER BY l.id DESC LIMIT 5", (name,))
    print("  环③ error_case_link 最近 5 行（id|cluster|payload|offline|verify|ts）:")
    for r in cur.fetchall():
        print(f"     {r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("agent", nargs="?", help="agent 名；不给则报全部四家")
    ap.add_argument("--baseline", help="基线快照 JSON（ring_baseline_probe.py 的产出）")
    args = ap.parse_args()

    base = None
    if args.baseline:
        with open(args.baseline, encoding="utf-8") as f:
            base = json.load(f)
        print(f"=== 基线快照 ts={base.get('ts')} ===")
        print("（⚠️ 快照越旧，「新增」越不准；确认 ts 是你这次验收之前取的）\n")

    conn = pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT") or 3306),
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        database=os.environ.get("DB_NAME") or "dev.obs", charset="utf8mb4", autocommit=True)
    cur = conn.cursor()

    print("=== 相关表结构 ===")
    for t in TABLES:
        try:
            print(f"  {t}: {cols(cur, t)}")
        except Exception as e:  # noqa: BLE001  探针：表名不符就直说，别静默
            print(f"  {t}: 查不到（{e.args[0]}）")

    print("\n=== 各表水位" + ("（对基线做差）" if base else "（无基线，仅绝对值）") + " ===")
    for t in TABLES:
        cur.execute(f"SELECT COUNT(*), COALESCE(MAX(id),0) FROM {t}")
        n, mx = cur.fetchone()
        # ⚠️ COALESCE(MAX(id),0) 在 pymysql 下回 **Decimal**（不是 int），JSON 往返后又可能
        # 是 str ⇒ 相减会 TypeError。两处都显式 int()，别指望驱动替你归一。
        n, mx = int(n), int(mx)
        if base and t in base:
            print(f"  {t:<20} n={n:<5}(基线 {base[t]['n']})  max_id={mx:<6} "
                  f"新增≤{mx - int(base[t]['max_id'])}")
        else:
            print(f"  {t:<20} n={n:<5}  max_id={mx:<6}")

    for name in (args.agent,) if args.agent else ALL_AGENTS:
        print(f"\n===== {name} =====")
        show_rings(cur, name)


main()
