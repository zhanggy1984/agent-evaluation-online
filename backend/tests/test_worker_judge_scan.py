"""worker judge_scan_job 纯分支 + worker/main 生命周期单测（T-2.1，独立进程）。

judge_scan DB 壳（扫批→decide→CAS→purge 实库行为）留集成探针（任务 #129，仿
test_consumer_state「apply_event 留 D6 实库」先例）；**补测批起该壳已由 cluster_probe
S-11~S-13 经真实 `run_judge_scan` 入口端到端覆盖**（含兜底吸收门控），故此处不再扩
FakeAsyncSession 补一批弱化重复（FakeAsyncSession 无 scalars().all() / rowcount，
扩了也只是测替身）。本文件测：
- judge_scan_job 纯逻辑：_facts_from_row（行→TraceFacts）、_ctx_for（字典侧 gate 组装）；
- worker/main：_sleep_until_next_hour 对齐、_wait_db_ready 守卫（成功/超时）、
  _judge_loop 单 job 异常自愈 + _stop 取消、_rollup_loop 异常自愈（不拖垮进程）。
真 MySQL/ES 链不连（monkeypatch job 函数 + 伪 engine/session）。
"""
import asyncio

import pytest

import app.worker.main as worker_main
from app.worker.judge_scan_job import _ctx_for, _facts_from_row


def ns(**kw):
    from types import SimpleNamespace

    return SimpleNamespace(**kw)


def _row(root_ok=1, root_status="error", root_error_type="llm_timeout", interface="i",
         llm_fact=0, entries=None, judged=0):
    summary = None if entries is None else {"agent_version": None, "entries": entries}
    return ns(agent="good-question", trace_id="tr-1", root_ok=root_ok,
              root_status=root_status, root_error_type=root_error_type,
              interface=interface, llm_fact_ok=llm_fact,
              err_summary_json=summary, judged=judged)


def _agent(backflow_allow=1, enable=1, aid=7, name="good-question"):
    return ns(id=aid, name=name, backflow_allow=backflow_allow, enable=enable)


class TestFactsFromRow:
    def test_basic_row_to_facts(self):
        f = _facts_from_row(_row(root_error_type="db_error", interface="POST /chat",
                                 llm_fact=1))
        assert f.root_ok is True and f.root_status == "error"
        assert f.root_error_type == "db_error" and f.interface == "POST /chat"
        assert f.llm_fact_ok is True and f.err_entries == ()

    def test_err_summary_entries_passed_through(self):
        entries = [{"error_type": "db_error", "error_msg": "conn", "count": 3}]
        f = _facts_from_row(_row(entries=entries))
        assert f.err_entries == tuple(entries)

    def test_null_summary_and_non_dict_entries_tolerated(self):
        # 老行/异常行：err_summary_json=None 或 entries 混入非 dict → 不崩、丢弃非 dict
        f1 = _facts_from_row(_row(entries=None))
        assert f1.err_entries == ()
        f2 = _facts_from_row(_row(entries=[{"error_type": "x", "count": 1}, "junk", None]))
        assert f2.err_entries == ({"error_type": "x", "count": 1},)


class TestCtxFor:
    def test_gate_all_open(self):
        ctx = _ctx_for(_row(), {"good-question": _agent()}, {7: True},
                       {(7, "i")})
        assert ctx.agent_exists and ctx.backflow_allow and ctx.agent_enabled
        assert ctx.backflow_enabled and ctx.interface_llm is True

    def test_agent_missing_gate_all_closed(self):
        ctx = _ctx_for(_row(), {}, {}, set())
        assert ctx.agent_exists is False and ctx.backflow_allow is False
        assert ctx.backflow_enabled is False and ctx.interface_llm is None

    def test_cc_backflow_allow_off(self):
        ctx = _ctx_for(_row(), {"good-question": _agent(backflow_allow=0)}, {7: True},
                       {(7, "i")})
        assert ctx.backflow_allow is False  # cc 双保险一（agent 布尔位）

    def test_dict_flag_default_true_when_missing(self):
        # flags 缺 agent id 键 → 回退开启（context.loader 缺键回退同规）
        ctx = _ctx_for(_row(), {"good-question": _agent()}, {}, set())
        assert ctx.backflow_enabled is True

    def test_dict_flag_false_closes(self):
        ctx = _ctx_for(_row(), {"good-question": _agent()}, {7: False}, set())
        assert ctx.backflow_enabled is False

    def test_interface_not_in_llm_pair_false(self):
        ctx = _ctx_for(_row(), {"good-question": _agent()}, {7: True}, set())
        assert ctx.interface_llm is False

    def test_no_interface_yields_none(self):
        # 行无 interface → None（只靠 llm_fact 兜底，L2 dict 门不参与）
        ctx = _ctx_for(_row(interface=None), {"good-question": _agent()}, {7: True},
                       {(7, None)})
        assert ctx.interface_llm is None


class TestSleepToNextHour:
    @pytest.mark.asyncio
    async def test_sleeps_positive_small_extra(self, monkeypatch):
        # 对齐下一 UTC 整点 + 抖动：sleep 时长 ∈ (0, 3605]，不 sleep 负值
        slept: list[float] = []

        async def fake_sleep(secs):
            slept.append(secs)

        monkeypatch.setattr(worker_main.asyncio, "sleep", fake_sleep)
        await worker_main._sleep_until_next_hour(5)
        assert len(slept) == 1
        assert 0 <= slept[0] <= 3605  # 距离下整点 ≤1h + 5s 抖动上限


class TestWaitDbReady:
    @pytest.mark.asyncio
    async def test_returns_once_table_visible(self, monkeypatch):
        class FakeEngine:
            def __init__(self, fail_times):
                self.fail_times, self.attempts = fail_times, 0

        class FakeAsyncSession:
            def __init__(self, engine):
                self.engine = engine

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def execute(self, stmt, *a, **k):
                self.engine.attempts += 1
                if self.engine.attempts <= self.engine.fail_times:
                    raise RuntimeError("agent 表未就绪")

        eng = FakeEngine(fail_times=2)
        monkeypatch.setattr(worker_main, "AsyncSession", FakeAsyncSession)
        monkeypatch.setattr(worker_main, "DB_READY_RETRY_S", 0.01)
        app = worker_main.WorkerApp(worker_main.get_settings())
        app._engine = eng  # 不建真连接

        await asyncio.wait_for(app._wait_db_ready(), timeout=5)
        assert eng.attempts == 3  # 2 次失败 + 第 3 次成功

    @pytest.mark.asyncio
    async def test_timeout_raises_runtime_error(self, monkeypatch):
        class FakeEngine:
            fail_times = 10 ** 9
            attempts = 0

        class FakeAsyncSession:
            def __init__(self, engine):
                self.engine = engine

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def execute(self, stmt, *a, **k):
                self.engine.attempts += 1
                raise RuntimeError("agent 表未就绪")

        monkeypatch.setattr(worker_main, "AsyncSession", FakeAsyncSession)
        monkeypatch.setattr(worker_main, "DB_READY_TIMEOUT_S", 0.3)
        monkeypatch.setattr(worker_main, "DB_READY_RETRY_S", 0.01)
        app = worker_main.WorkerApp(worker_main.get_settings())
        app._engine = FakeEngine()

        with pytest.raises(RuntimeError):
            await asyncio.wait_for(app._wait_db_ready(), timeout=5)


class TestJudgeLoop:
    @pytest.mark.asyncio
    async def test_runs_until_stop_and_self_heals(self, monkeypatch):
        calls: list[int] = []

        async def fake_run_judge_scan(engine, *, logger, batch):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("DB 抖动模拟")  # 首轮异常 → 下轮自愈
            return 0

        monkeypatch.setattr(worker_main, "run_judge_scan", fake_run_judge_scan)
        monkeypatch.setattr(worker_main, "JUDGE_INTERVAL_S", 0)  # 不 sleep，测循环行为

        app = worker_main.WorkerApp(worker_main.get_settings())

        async def stopper():
            # 让循环跑 3 轮后置 stop
            while len(calls) < 3:
                await asyncio.sleep(0)
            app._stop.set()

        await asyncio.gather(app._judge_loop(), stopper())
        assert len(calls) >= 3  # 异常轮不退出，正常轮继续，直到 stop
        assert app._stop.is_set()

    @pytest.mark.asyncio
    async def test_cancel_stops_cleanly(self, monkeypatch):
        async def fake_run_judge_scan(engine, *, logger, batch):
            await asyncio.sleep(3600)  # 模拟长跑

        monkeypatch.setattr(worker_main, "run_judge_scan", fake_run_judge_scan)
        app = worker_main.WorkerApp(worker_main.get_settings())
        task = asyncio.create_task(app._judge_loop())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


class TestRollupLoop:
    @pytest.mark.asyncio
    async def test_exception_does_not_kill_loop(self, monkeypatch):
        calls: list[int] = []

        async def boom(engine, es, settings, *, logger):
            calls.append(1)
            raise RuntimeError("rollup 失败模拟")

        # 延迟 import 走 `from app.worker import rollup_job` → patch 包属性（非 main 模块）
        import app.worker as worker_pkg

        monkeypatch.setattr(worker_pkg, "rollup_job", ns(run_rollup=boom), raising=False)
        monkeypatch.setattr(worker_main, "_sleep_until_next_hour", lambda *a: asyncio.sleep(0))

        app = worker_main.WorkerApp(worker_main.get_settings())

        async def stopper():
            while len(calls) < 2:
                await asyncio.sleep(0)
            app._stop.set()

        await asyncio.gather(app._rollup_loop(), stopper())
        assert len(calls) >= 2  # 首轮异常后循环继续到第二轮才 stop
