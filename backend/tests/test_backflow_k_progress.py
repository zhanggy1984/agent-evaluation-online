"""`link_k_progress`（详情读面 K 进度 seq 的唯一判据来源）单测。

本文件守两件事：

1. **读面与内核同源** —— seq 由 `_replay_k` 算出，与 `judge_link` 判出的是同一个数。
   将来若有人在读面另抄一份判定（在前端数 pass 行、或在 API 层重写循环），这条会红。
2. **读面零写** —— 这是拆分 `judge_link` 的**硬前提**：unclean 的重放副作用
   （`batches.ensure_unclean_batch` 对非 open 批会**置回 open 并清 resolve 审计**）
   一旦被搬到读路径，就**每翻一次详情页重开一次人工已 resolve 的批**，且没有任何判据会红。

   ⚠️ 第 2 条用**成对**断言：写面（judge_link）必须调、读面（link_k_progress）必须不调。
   只写读面那半边时，谓词弄错（比如这组数据根本没触发 unclean）会让该断言**静默变绿**
   ——「没观察到调用」与「本来就不会调用」同形。
"""
import asyncio
from unittest.mock import AsyncMock, patch

from _fakes import ns

from app.backflow import batches as batches_mod
from app.backflow.verify import judge_link, link_k_progress


class _Rows:
    def __init__(self, items):
        self.items = list(items)

    def all(self):
        return self.items


class _Session:
    """最小替身：按调用次序吐出预设行集（第 1 次 = 本 link 的已收结果行）。

    本组用例刻意**不给** `prev_terminal_version` ⇒ 不触发 `_agent_versions`
    （那会走 execute 那条第二跳），故只实现 scalars 一条路径。
    """

    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = 0

    async def scalars(self, stmt):
        self.calls += 1
        return _Rows(self.rows)

    async def execute(self, stmt):  # pragma: no cover - 本组用例不触达
        self.calls += 1
        return _Rows([])


_LINK = ns(id=30, case_id="c-1", verify_status="pending")
_CLUSTER = ns(id=10, agent="agent-x", claim_k=5, input_truncated=False)


def _pure_pass(rec_id, version):
    """纯净 pass 行（本 link 的 case 通过、run 内无环境级 na）。"""
    return ns(id=rec_id, link_id=30, bound_version=version, run_id=f"r-{version}",
              raw_json={"cases": [{"case_id": "c-1", "pass_fail": "pass"}]})


def _unclean(rec_id, version):
    """同一 case pass，但**同 run 内另有环境级 na 行** ⇒ route_verdict 判 unclean_run。"""
    return ns(id=rec_id, link_id=30, bound_version=version, run_id=f"r-{version}",
              raw_json={"cases": [
                  {"case_id": "c-1", "pass_fail": "pass"},
                  {"case_id": "c-9", "pass_fail": "na", "error_type": "circuit_open"},
              ]})


def test_k_progress_is_the_kernel_seq():
    """两个相邻纯净 pass → seq=2（claim_k=5 故尚未收口）。"""
    s = _Session([_pure_pass(1, "1.0.0"), _pure_pass(2, "1.1.0")])
    assert asyncio.run(link_k_progress(s, _CLUSTER, _LINK)) == 2


def test_k_progress_broken_chain_restarts_at_one():
    """反假绿对照：pass, unclean, pass ⇒ 断链后重新计 1（不是 2、不是 3）。

    没有这条，上一条在「数 pass 行数」的错实现下也会绿 —— 而那正是本批要避免的
    「前端自己数一遍」。
    """
    s = _Session([_pure_pass(1, "1.0.0"), _unclean(2, "1.1.0"), _pure_pass(3, "1.2.0")])
    assert asyncio.run(link_k_progress(s, _CLUSTER, _LINK)) == 1


def test_k_progress_none_when_not_applicable():
    """三种「不适用」各有别的可见面，返回 None 而**不是 0**（0 是「跑过但没通过」）。"""
    s = _Session([])
    assert asyncio.run(link_k_progress(s, _CLUSTER, None)) is None
    # 终态只读：K 序列已结束，再报进度是假象
    done = ns(id=30, case_id="c-1", verify_status="passed")
    assert asyncio.run(link_k_progress(s, _CLUSTER, done)) is None
    # 无 case_id：assemble_job 待补 link，判定前提不成立
    no_case = ns(id=30, case_id=None, verify_status="pending")
    assert asyncio.run(link_k_progress(s, _CLUSTER, no_case)) is None
    assert s.calls == 0  # 三种都应在**查库之前**返回


def test_read_face_does_not_register_unclean_batch_but_writer_does():
    """成对判别：同一份 unclean 数据，写面调批、读面一次都不调。"""
    rows = [_pure_pass(1, "1.0.0"), _unclean(2, "1.1.0")]  # 最后一条 = 触发记录

    with patch.object(batches_mod, "ensure_unclean_batch",
                      new=AsyncMock(return_value=7)) as m:
        # 读面：详情页会反复调它
        assert asyncio.run(link_k_progress(_Session(rows), _CLUSTER, _LINK)) == 1
        m.assert_not_awaited()

        # 写面：同一数据必须入批（否则上一条断言是空转绿）
        out = asyncio.run(judge_link(_Session(rows), cluster=_CLUSTER, link=_LINK))
        m.assert_awaited_once()
        assert m.await_args.kwargs["bound_version"] == "1.1.0"
        assert out["outcome"] == "unclean_batch", out
