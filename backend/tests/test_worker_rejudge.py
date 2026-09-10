"""worker rejudge_job（本地补判安全网）单测（本批 (a)/(d)）。

判定触发改「推送到达一次性事件」后，三类「事件到达时未就绪」现场需要有人再判一次 —— 本 job
只做本地重放（零 outbound），DB 壳（扫 claim 簇 ∧ pending link → judge_link）留集成探针
push_probe（真库语义：判定的写回、savepoint、终态守卫都在那里验）。本文件测：
- `_rejudge_loop` 生命周期（照抄本仓 4+1 个 loop 的测法）：正常一轮 / 异常自愈 / 取消干净；
- `run_rejudge` 的**收敛判据**（「零终态迁移」而非「空批」）：候选不自清时必须返回，
  有进展时才继续取批（真实踩过的空转 bug，见该用例 docstring）；
- job 注册回归护栏：6 个 loop 全在 create_task 里 + REJUDGE_INTERVAL_S（防删 recheck 时
  把 rejudge 一起当「多出来的 job」删掉）；
- `judge_link` 对**老格式行**（无 `cases` 键）的 (d) 判据：不可判 → 保持 pending，**不判
  missing**（真实 K 序列里那条 old 行若按 missing 处理会被当成「断链」而被后续纯净 pass
  跨过 → k=1 时直接误判 fixed，本用例正是钉这一条）。
"""
import asyncio
import inspect

from _fakes import ns

from app.backflow.verify import judge_link

# ---------- worker/main：_rejudge_loop 生命周期（另五个 loop 见各自 job 的测试文件） ----------


def test_rejudge_loop_runs_until_stop_and_self_heals(monkeypatch):
    from app.worker import main as worker_main

    calls: list[int] = []

    async def fake_run_rejudge(engine, *, logger, batch):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("DB 抖动模拟")  # 首轮异常 → 下轮自愈
        return 0

    monkeypatch.setattr(worker_main, "run_rejudge", fake_run_rejudge)
    monkeypatch.setattr(worker_main, "REJUDGE_INTERVAL_S", 0)

    app = worker_main.WorkerApp(worker_main.get_settings())

    async def main():
        async def stopper():
            while len(calls) < 3:
                await asyncio.sleep(0)
            app._stop.set()

        await asyncio.gather(app._rejudge_loop(), stopper())

    asyncio.run(main())
    assert len(calls) >= 3  # 异常轮不退出，正常轮继续直到 stop
    assert app._stop.is_set()


def test_rejudge_loop_cancel_stops_cleanly(monkeypatch):
    from app.worker import main as worker_main

    async def fake_run_rejudge(engine, *, logger, batch):
        await asyncio.sleep(3600)  # 模拟长跑

    monkeypatch.setattr(worker_main, "run_rejudge", fake_run_rejudge)
    app = worker_main.WorkerApp(worker_main.get_settings())

    async def main():
        task = asyncio.create_task(app._rejudge_loop())
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return True
        return False

    assert asyncio.run(main()) is True


def test_worker_registers_six_loops_including_rejudge():
    """job 注册回归护栏：6 个 loop 全在 start() 里，且 rejudge 常量在场。

    为什么留一条：第 3 刀删 recheck 时 job 数 6 → 5，本批补 rejudge 后 5 → 6 —— 两处数字
    变动最容易漏改 create_task 注册（loop 方法写了但没注册 = 安全网根本不在跑），故直接
    对 start() 源码做结构断言（比跑真 start() 便宜且不受 DB/ES 影响）。
    """
    from app.worker import main as worker_main

    src = inspect.getsource(worker_main.WorkerApp.start)
    for name in ("_judge_loop", "_cluster_loop", "_assemble_loop",
                 "_claim_ttl_loop", "_rejudge_loop", "_rollup_loop"):
        assert f"create_task(self.{name}())" in src, name
    assert worker_main.REJUDGE_INTERVAL_S == 60
    # 启动日志须带该字段（漏了等于线上看不出补判在跑）
    assert "rejudge_interval_s" in src


def test_run_rejudge_stops_when_batch_makes_no_progress(monkeypatch):
    """收敛判据回归护栏：候选**不自清**时（判定完仍是候选）一轮 run 必须返回，不能空转。

    本 job 的候选谓词 = claim ∧ 有 pending link，而 gap/未达 K/不可判的簇判定完**仍满足**
    该谓词 —— 照抄 assemble/claim_ttl 的「批循环直到空批」会让空批永不出现、run_rejudge
    永不返回（worker 该 loop 从此不 sleep，整轮打库不空转停止）。**实测踩过**：真库探针
    直接跑一轮 run_rejudge 挂死。本用例用「永远返回同一批、零终态迁移」的批函数把它钉住。
    """
    from app.worker import rejudge_job

    calls: list[int] = []

    async def fake_batch(engine, *, batch):
        calls.append(1)
        if len(calls) > 5:  # 没有本判据就会走到这里 → 断言失败（而不是真挂死）
            raise AssertionError("零进展仍继续循环 = 空转 bug 复现")
        return 3, 0, 0  # 3 条判定、0 终态迁移（候选永远不自清）

    monkeypatch.setattr(rejudge_job, "_rejudge_batch", fake_batch)
    total = asyncio.run(rejudge_job.run_rejudge(object()))
    assert total == 3 and len(calls) == 1, (total, len(calls))


def test_run_rejudge_drains_while_progress(monkeypatch):
    """反假绿对照：有终态迁移时**继续**取下一批（别把「取一批就停」当收敛）。"""
    from app.worker import rejudge_job

    batches = [(2, 1, 0), (2, 0, 0)]  # 首批有迁移 → 再取；次批零迁移 → 停

    async def fake_batch(engine, *, batch):
        return batches.pop(0)

    monkeypatch.setattr(rejudge_job, "_rejudge_batch", fake_batch)
    assert asyncio.run(rejudge_job.run_rejudge(object())) == 4
    assert batches == []


# ---------- judge_link：(d) 老格式行不可判（不判 missing） ----------


class _Rows:
    def __init__(self, items):
        self.items = list(items)

    def all(self):
        return self.items


class _WriteResult:
    def __init__(self, rowcount=1):
        self.rowcount = rowcount


class _RecSession:
    """judge_link 的最小替身：`scalars` 回 VerifyRunRecord 行，`execute` 记 CAS 调用。

    收窄点（诚实登记）：只够跑「本 link 行集 → 判据」这一段，`_agent_versions` 的两跳 join
    装不下 —— 故本文件的老格式用例都构造 `prev_terminal_version=None`（不触达缺行判据），
    agent 级判据的真库语义在 push_probe 覆盖。
    """

    def __init__(self, records=()):
        self.records = list(records)
        self.updates: list = []
        self.added: list = []

    async def scalars(self, stmt):
        return _Rows(self.records)

    async def execute(self, stmt):
        self.updates.append(stmt)
        return _WriteResult(1)

    def add(self, obj):
        self.added.append(obj)


def _rec(rid, version, raw):
    return ns(id=rid, link_id=30, run_id=f"run-{rid}", bound_version=version,
              case_pass=1, run_status="completed", raw_json=raw)


def _claim_cluster(k):
    return ns(id=10, agent="agent-old", status="claim", claim_k=k,
              input_truncated=0, fix_version="1.0.0")


_LINK = ns(id=30, case_id="c-1", verify_status="pending")


def test_judge_link_legacy_row_without_cases_is_unjudgeable_not_missing():
    """老格式行（无 `cases` 键）→ 不可判：保持 pending，且**不**被当成 missing 跨过。

    现场：v1.0.0 是第 2 刀期 writer 落的老格式行（raw 只有 case_pass），v2.0.0 是逐 case
    pass。k=1 下若把 v1 判 missing（= 断链，decide_k 不清零不累计）再走 v2 → seq=1 ≥ k
    → **直接判 fixed**：等于用「不知道 v1 结果」换来了「假修复」（v1 可能 fail）。
    判据必须显式识别该形态并停在原地。
    """
    session = _RecSession([
        _rec(1, "1.0.0", {"case_pass": 1, "agent_latest_version": "2.0.0"}),  # 老格式
        _rec(2, "2.0.0", {"cases": [{"case_id": "c-1", "pass_fail": "pass"}],
                          "agent_latest_version": "2.0.0", "prev_terminal_version": None}),
    ])
    summary = asyncio.run(
        judge_link(session, cluster=_claim_cluster(1), link=_LINK))
    assert summary["outcome"] == "pending", summary  # 不是 fixed_auto（也不触达写面）
    assert summary["unjudgeable_version"] == "1.0.0", summary
    assert "老格式" in summary["reason"], summary


def test_judge_link_legacy_row_records_below_fix_version_ignored():
    """反假绿对照：老格式行落在 `fix_version` **之前**（上一轮 claim 的残留）→ 不拦本轮。

    没有本对照，上一条可能只是「只要链上有老行就永不推进」——那会把正常 claim 也钉死。
    判据与缺行中断同规：只看 `≥ fix_version` 的版本（之前的终态 run 促成本次 claim、
    不属本轮 K 序列）。
    """
    session = _RecSession([
        _rec(1, "0.9.0", {"case_pass": 0}),  # 老格式，但在 fv=1.0.0 之前
        _rec(2, "1.0.0", {"cases": [{"case_id": "c-1", "pass_fail": "pass"}],
                          "agent_latest_version": "1.0.0", "prev_terminal_version": None}),
    ])
    summary = asyncio.run(
        judge_link(session, cluster=_claim_cluster(1), link=_LINK))
    assert summary["outcome"] == "fixed_auto", summary  # 与上一条只差「老行在 fv 之前」
    assert [getattr(c, "action", None) for c in session.added] == ["auto_fixed"]
