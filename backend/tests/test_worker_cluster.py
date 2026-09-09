"""worker cluster_job 纯分支 + analyzer.cluster 归并决策 + worker/main cluster loop（P2-1）。

cluster/consumer 的 DB 壳（扫批→归并开簇/count/generation/R-13 回填/E-12 吸收/CAS）
留集成探针（仿 judge_scan「DB 壳留集成探针」先例）：tests/integration/cluster_probe.py
容器内 `docker exec obs-backend` 跑真库断言。本文件测：
- analyzer.cluster 纯决策：pick_merge_target（count/skip/open）、error_msg_for、
  build_cluster_row 字段装载；
- worker/cluster_job 纯拆解：_judgement/_candidate_error_sets（脏数据防崩）；
- worker/main：_cluster_loop 单 job 异常自愈 + _stop 取消（monkeypatch run_cluster_merge）。
真 MySQL/ES 链不连。
"""
import asyncio
from datetime import datetime

import pytest

import app.worker.main as worker_main
from app.analyzer.cluster import (
    ERROR_MSG_MAX,
    build_cluster_row,
    error_msg_for,
    pick_merge_target,
    reentry_gate_allows,
)
from app.worker.cluster_job import _candidate_error_sets, _judgement


def ns(**kw):
    from types import SimpleNamespace

    return SimpleNamespace(**kw)


NOW = datetime(2026, 9, 9, 3, 30, 0)


def _cluster(status="open", generation=1):
    return ns(status=status, generation=generation)


# ---- pick_merge_target：归并动作决策（analyzer.cluster 纯函数） ------------------

class TestPickMergeTarget:
    def test_open_cluster_is_count_target(self):
        mode, target, gen = pick_merge_target(
            [_cluster(status="fixed", generation=1), _cluster(status="open", generation=2)],
            reopen_after_terminal=True,
        )
        assert mode == "count" and target is not None and target.status == "open"
        assert gen is None

    def test_claim_and_needs_review_also_non_terminal(self):
        for st in ("claim", "needs_review"):
            mode, target, _ = pick_merge_target([_cluster(status=st)], reopen_after_terminal=True)
            assert mode == "count" and target.status == st

    def test_normal_candidate_reopens_after_closed_with_gen_plus_one(self):
        # 同键 fixed 终态后正常复发（cluster_job reopen_after_terminal=True）→ 新开代数
        mode, target, gen = pick_merge_target(
            [_cluster(status="fixed", generation=1)], reopen_after_terminal=True
        )
        assert mode == "open" and target is None and gen == 2

    def test_never_seen_opens_gen_one(self):
        mode, _, gen = pick_merge_target([], reopen_after_terminal=True)
        assert mode == "open" and gen == 1

    def test_rootlate_closed_not_reopened_skips(self):
        # §4.3④/E-28：root-late 同键 closed（fixed/inactive）→ 跳过不翻案
        for st in ("fixed", "inactive"):
            mode, target, gen = pick_merge_target(
                [_cluster(status=st, generation=1)], reopen_after_terminal=False
            )
            assert mode == "skip" and target is None and gen is None

    def test_rootlate_never_seen_still_opens(self):
        # root-late 同键从未出现 → 仍开簇（异键开新簇）
        mode, _, gen = pick_merge_target([], reopen_after_terminal=False)
        assert mode == "open" and gen == 1


# ---- error_msg_for：err_summary entries 取代表 msg ---------------------------------

class TestErrorMsgFor:
    def test_match_returns_latest_msg_truncated(self):
        entries = [{"error_type": "db_error", "error_msg": "conn refused", "count": 2}]
        assert error_msg_for(entries, "db_error") == "conn refused"

    def test_msg_over_512_truncated(self):
        entries = [{"error_type": "llm_timeout", "error_msg": "x" * 600, "count": 1}]
        assert len(error_msg_for(entries, "llm_timeout")) == ERROR_MSG_MAX

    def test_no_match_or_empty_msg_yields_empty(self):
        assert error_msg_for([{"error_type": "db_error", "error_msg": "c", "count": 1}], "x") == ""
        assert error_msg_for([{"error_type": "x", "error_msg": "", "count": 1}], "x") == ""
        assert error_msg_for([{"error_type": "x", "error_msg": None, "count": 1}], "x") == ""

    def test_non_dict_entries_tolerated(self):
        entries = ["junk", None, {"error_type": "y", "error_msg": "m", "count": 1}]
        assert error_msg_for(entries, "y") == "m"


# ---- build_cluster_row：新簇字段装载 ------------------------------------------------

class TestBuildClusterRow:
    def test_field_mapping(self):
        row = build_cluster_row(
            agent="good-question", interface="POST /api/chat/{id}", layer="L1",
            error_type="llm_timeout", input_hash="a" * 64, input_snapshot="snap",
            input_truncated=1, error_msg="timeout after 10s", trace_id="tr-1",
            trigger_version="2026.08.31-r47", generation=2, now=NOW,
        )
        assert row.agent == "good-question"
        assert row.interface == "POST /api/chat/{id}"
        assert row.layer == "L1" and row.error_type == "llm_timeout"
        assert row.input_hash == "a" * 64
        assert row.input_snapshot == "snap" and row.input_truncated == 1
        assert row.error_msg == "timeout after 10s"
        assert row.first_trace_id == "tr-1" and row.trigger_version == "2026.08.31-r47"
        assert row.first_ts == NOW and row.latest_ts == NOW
        assert row.count == 1 and row.generation == 2 and row.status == "open"

    def test_empty_error_msg_falls_back_to_error_type(self):
        row = build_cluster_row(
            agent="a", interface="i", layer="L2", error_type="db_error",
            input_hash="b" * 64, input_snapshot=None, input_truncated=0,
            error_msg="", trace_id="t", trigger_version=None, generation=1, now=NOW,
        )
        assert row.error_msg == "db_error"  # 无可读 msg 时以 error_type 兜底
        assert row.input_snapshot is None and row.trigger_version is None


# ---- cluster_job 候选拆解 -------------------------------------------------------------

class TestJudgementParsing:
    def test_candidate_error_sets_filters_valid(self):
        row = ns(judgement_json={
            "candidate_error_sets": [
                {"layer": "L1", "error_type": "llm_timeout"},
                {"layer": "L2", "error_type": "db_error"},
                {"layer": "L2"},                      # 缺 error_type → 弃
                {"layer": "none", "error_type": "x"},  # 层非 L1/L2 → 弃
                {"error_type": "y"},                   # 缺 layer → 弃
                "junk", None,
            ],
        })
        got = _candidate_error_sets(row)
        assert got == [{"layer": "L1", "error_type": "llm_timeout"},
                       {"layer": "L2", "error_type": "db_error"}]

    def test_none_judgement_json_yields_empty(self):
        assert _candidate_error_sets(ns(judgement_json=None)) == []
        assert _candidate_error_sets(ns(judgement_json="not-a-dict")) == []
        assert _judgement(ns(judgement_json=None)) == {}


# ---- reentry_gate_allows：§7.5 版本门控（B-5 等值+日期前缀序，P2-5 纯函数） ----------

class TestReentryGate:
    def test_same_day_same_value_allows(self):
        assert reentry_gate_allows("2026.09.03-r47", "2026.09.03-r47") is True

    def test_same_day_different_value_blocks(self):
        # 同日不等值按"修复上线中/未上线"处理——防 r100<r47 类字典序把同日已上线误判
        for v in ("2026.09.03-r48", "2026.09.03-r100", "2026.09.03"):
            assert reentry_gate_allows(v, "2026.09.03-r47") is False

    def test_cross_day_later_allows(self):
        assert reentry_gate_allows("2026.09.04-rc1", "2026.09.03-r47") is True
        assert reentry_gate_allows("2026.09.05", "2026.09.03-r47") is True

    def test_cross_day_earlier_blocks(self):
        assert reentry_gate_allows("2026.09.02-r99", "2026.09.03-r47") is False

    def test_same_value_pure_date_allows(self):
        assert reentry_gate_allows("2026.09.03", "2026.09.03") is True

    def test_non_date_literal_equality_only(self):
        # 非 YYYY.MM.DD 形态 → 不透明字面量等值比较（构建标签不参与跨日）
        assert reentry_gate_allows("app-2.0", "app-2.0") is True
        assert reentry_gate_allows("app-1.9", "app-2.0") is False

    def test_one_side_non_date_uses_literal_equality(self):
        # 单侧非日期形态 → 整体按字面量等值（不截前缀比较）
        assert reentry_gate_allows("app-2.0", "app-2.0") is True
        assert reentry_gate_allows("app-1.9", "app-2.0") is False
        assert reentry_gate_allows("2026.09.04-r1", "app-2.0") is False

    def test_none_or_blank_versions_block(self):
        # 无版本证据 / 空串 → 不满足门控（人工 reopen 兜底）
        assert reentry_gate_allows(None, "2026.09.03-r47") is False
        assert reentry_gate_allows("2026.09.03-r47", None) is False
        assert reentry_gate_allows("", "2026.09.03-r47") is False
        assert reentry_gate_allows("  ", "2026.09.03-r47") is False

    def test_whitespace_stripped_before_compare(self):
        assert reentry_gate_allows(" 2026.09.04-r1 ", "2026.09.03-r47") is True

    def test_non_date_agent_vs_dated_fix_blocks(self):
        # agent 非日期形态 vs fix 日期形态 → 整体字面量不等 → False（日期前缀只对双侧同形态生效）
        assert reentry_gate_allows("app-2.0", "2026.09.03-r47") is False


# ---- worker/main：_cluster_loop 生命周期（monkeypatch job 函数，不连库） -------------

class TestClusterLoop:
    @pytest.mark.asyncio
    async def test_runs_until_stop_and_self_heals(self, monkeypatch):
        calls: list[int] = []

        async def fake_run_cluster_merge(engine, *, logger, batch):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("DB 抖动模拟")  # 首轮异常 → 下轮自愈
            return 0

        monkeypatch.setattr(worker_main, "run_cluster_merge", fake_run_cluster_merge)
        monkeypatch.setattr(worker_main, "CLUSTER_INTERVAL_S", 0)

        app = worker_main.WorkerApp(worker_main.get_settings())

        async def stopper():
            while len(calls) < 3:
                await asyncio.sleep(0)
            app._stop.set()

        await asyncio.gather(app._cluster_loop(), stopper())
        assert len(calls) >= 3  # 异常轮不退出，正常轮继续直到 stop

    @pytest.mark.asyncio
    async def test_cancel_stops_cleanly(self, monkeypatch):
        async def fake_run_cluster_merge(engine, *, logger, batch):
            await asyncio.sleep(3600)

        monkeypatch.setattr(worker_main, "run_cluster_merge", fake_run_cluster_merge)
        app = worker_main.WorkerApp(worker_main.get_settings())
        task = asyncio.create_task(app._cluster_loop())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
