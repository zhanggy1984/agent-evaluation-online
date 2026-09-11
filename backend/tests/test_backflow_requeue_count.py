"""R-7「可愈性标注」换判据 = 行为数据的读/写口径单测（requeue.py 计数三件套）。

- requeue_counts：成批口径（只数 action=requeue 行、按 link_id 分组）+ 空入参短路不发查询；
- requeue_count：单点便捷（未命中 → 0）；
- requeue_link：返回体 requeue_count **不含本次**——用操作序断言「计数查在 add 本次审计行之前」。

替身按注册的 ConversionRecord 行真算计数（见 _fakes.aggregate_requeue_counts），故测的是
与真库 SQL 同义的过滤/分组语义，而非 canned 值；真库 COUNT/GROUP BY 由 pull_probe 覆盖。
"""
import asyncio
from datetime import datetime, timedelta, timezone

from _fakes import (
    FakeAsyncSession,
    FakeRows,
    aggregate_requeue_counts,
    ns,
    requeue_count_link_ids,
)

from app.backflow.requeue import (
    SUSPECT_REQUEUE_THRESHOLD,
    requeue_count,
    requeue_counts,
    requeue_link,
)
from app.models.error_flow import ConversionRecord


def _run(coro):
    return asyncio.run(coro)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class _RequeueSession(FakeAsyncSession):
    """requeue_link 最小替身：CAS update 恒命中；成批计数按注册行真算。

    ops = 操作序（cas / count / add:<action>），用于钉计数与本次审计行的先后（口径不含本次）。
    """

    def __init__(self, conv_rows=()):
        super().__init__()
        self._conv_rows = list(conv_rows)
        self.ops: list[str] = []
        self.count_queries = 0

    async def execute(self, stmt, params=None, execution_options=None):
        if getattr(stmt, "is_update", False):        # CAS 复位
            self.ops.append("cas")
            return ns(rowcount=1)
        ids = requeue_count_link_ids(stmt)           # 成批计数
        if ids is not None:
            self.ops.append("count")
            self.count_queries += 1
            return FakeRows(aggregate_requeue_counts(self._conv_rows, ids))
        raise AssertionError(f"_RequeueSession 不支持的查询形态: {stmt}")

    def add(self, obj):
        self.ops.append(f"add:{obj.action}")
        super().add(obj)


# ---------- requeue_counts：成批口径 ----------


def test_requeue_counts_empty_ids_short_circuits_without_query():
    class _Boom:
        async def execute(self, *a, **k):
            raise AssertionError("空 link_ids 不应发查询")

    assert _run(requeue_counts(_Boom(), [])) == {}


def test_requeue_counts_groups_per_link_and_counts_requeue_rows_only():
    sess = _RequeueSession([
        ns(link_id=1, action="requeue"), ns(link_id=1, action="requeue"),
        ns(link_id=2, action="requeue"),
        ns(link_id=1, action="invalidate"),   # 非 requeue 不计
        ns(link_id=3, action="requeue"),      # 不在入参 link_ids 内 → 不计
    ])
    out = _run(requeue_counts(sess, [1, 2]))
    assert out == {1: 2, 2: 1}                # 未命中的 link 不入 dict（调用方取 0）
    assert 3 not in out


def test_requeue_counts_zero_rows_is_empty_dict():
    assert _run(requeue_counts(_RequeueSession([]), [7, 8])) == {}


def test_requeue_count_single_link_zero_and_hit():
    sess = _RequeueSession([ns(link_id=5, action="requeue")])
    assert _run(requeue_count(sess, 5)) == 1
    assert _run(requeue_count(sess, 6)) == 0   # 无历史 → 0（边界）


# ---------- requeue_link：返回体口径 = 历史次数（不含本次） ----------


def _link(**over):
    now = _now()
    base = dict(id=30, cluster_id=10, payload_id="pl-abc", case_id="c-1",
                case_type="regression_error", offline_status="invalidated",
                verify_status="pending", assembled_ts=now - timedelta(minutes=6),
                invalidate_reason="online_content_gap")
    return ns(**{**base, **over})


def _cluster(**over):
    base = dict(id=10, agent="good-question", interface="POST /api/chat/{id}",
                first_trace_id="tr-9f2c1a", generation=1,
                trigger_version="2026.08.31-r47", fix_version=None,
                input_snapshot='{"question": "q"}', status="open")
    return ns(**{**base, **over})


def test_requeue_link_returns_historical_count_excluding_this_call():
    # 已有 2 条历史 requeue 行 → 本次重推返回 2（不含本次；含本次则应为 3）
    sess = _RequeueSession([ns(link_id=30, action="requeue"),
                            ns(link_id=30, action="requeue")])
    out = _run(requeue_link(sess, _link(), _cluster(), actor_id=1, now=_now()))
    assert out["requeue_count"] == 2
    assert out["offline_status"] == "assembled"
    # 口径保证靠操作序：计数查在 add 本次审计行之前
    assert sess.ops.index("count") < sess.ops.index("add:requeue")
    assert [r.action for r in sess.added] == ["requeue"]   # 本次审计行确已写入


def test_requeue_link_first_ever_requeue_is_zero():
    sess = _RequeueSession([])
    out = _run(requeue_link(sess, _link(), _cluster(), actor_id=1, now=_now()))
    assert out["requeue_count"] == 0
    assert sess.count_queries == 1


def test_requeue_link_ignores_other_links_requeues():
    # 计数按 link 隔离：别的 link 的历史重推不算进本 link
    sess = _RequeueSession([ns(link_id=31, action="requeue")])
    out = _run(requeue_link(sess, _link(), _cluster(), actor_id=1, now=_now()))
    assert out["requeue_count"] == 0


def test_suspect_requeue_threshold_value():
    # 拍定值（无数据支撑，上线后按真实 conversion_record 分布调）：前端有同值常量
    assert SUSPECT_REQUEUE_THRESHOLD == 2


def test_conversion_record_added_is_the_requeue_audit_row():
    sess = _RequeueSession([])
    _run(requeue_link(sess, _link(), _cluster(), actor_id=7, now=_now()))
    rec = sess.added[0]
    assert isinstance(rec, ConversionRecord)
    assert rec.action == "requeue" and rec.link_id == 30 and rec.actor_user_id == 7
