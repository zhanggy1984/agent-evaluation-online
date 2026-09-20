"""`link_gap_version`（详情读面 result_gap_suspected 的唯一判据来源）单测。

本文件因一次**真实逃逸**而建：批 35-A 删掉了 `fv` 的定义与「只看 ≥ fv」边界，却漏改本
函数 `candidates` 推导式里的 `_ver_key(fv)` ⇒ 只要某 run 行带 `prev_terminal_version`
就 NameError，**详情页 500**。当时的单测没有覆盖这条分支，504 全绿把它盖了过去，是 ruff
的 F821 在批 35-B1 里抓出来的。这条用例把该分支钉住。
"""
import asyncio

from _fakes import ns

from app.backflow.verify import link_gap_version


class _Rows:
    def __init__(self, items):
        self.items = list(items)

    def all(self):
        return self.items


class _Session:
    """最小替身：按调用次序吐出预设行集（第 1 次 = 本 link 的行，第 2 次 = agent 版本全集）。"""

    def __init__(self, batches):
        self.batches = list(batches)
        self.calls = 0

    async def scalars(self, stmt):
        self.calls += 1
        return _Rows(self.batches.pop(0) if self.batches else [])

    async def execute(self, stmt):
        # `_agent_versions` 走 execute（两跳 join 取 bound_version 列），行形状 = 单元素元组
        self.calls += 1
        return _Rows(self.batches.pop(0) if self.batches else [])


_LINK = ns(id=30, case_id="c-1")
_CLUSTER = ns(id=10, agent="agent-x")


def _rec(version, raw):
    return ns(id=1, link_id=30, bound_version=version, raw_json=raw)


def test_gap_version_with_prev_terminal_row_does_not_name_error():
    """带 `prev_terminal_version` 的行 → 返回缺失版本，且**不得**引用已删除的 `fv`。

    35-A 之后本函数已无版本下界：任何 prev 终态版本都是候选，不含「≥ fv」的过滤。
    """
    session = _Session([
        [_rec("1.0.0", {"prev_terminal_version": "0.9.0"})],  # 本 link 行
        [],  # _agent_versions → 空集（该版本从未被观测到）
    ])
    got = asyncio.run(link_gap_version(session, cluster=_CLUSTER, link=_LINK))
    assert got == "0.9.0", got
    assert session.calls == 2  # 走到 candidates 非空 → 才会查 agent 全集


def test_gap_version_seen_prev_version_is_not_a_gap():
    """反假绿对照：prev 版本已在「已收结果全集」里 ⇒ 不是缺行，返回 None。

    没有这条，上一条用例在「恒返回首个候选」的实现下也会绿。
    """
    session = _Session([
        [_rec("1.0.0", {"prev_terminal_version": "0.9.0"})],
        [("0.9.0",)],  # agent 已收 0.9.0（版本全集列）
    ])
    assert asyncio.run(link_gap_version(session, cluster=_CLUSTER, link=_LINK)) is None


def test_gap_version_row_without_prev_terminal_is_none():
    """无 prev_terminal_version 的行不产候选（首版/断链起点）。"""
    session = _Session([[_rec("1.0.0", {})], []])
    assert asyncio.run(link_gap_version(session, cluster=_CLUSTER, link=_LINK)) is None
