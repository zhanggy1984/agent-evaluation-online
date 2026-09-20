"""批 37 自动重推出口单测：守卫链 + auto_requeue_stuck 的候选/上限/CAS/审计。

替身（`_AutoRequeueSession`）三件事：喂候选行、按注册的 conversion_record 行真算
历史次数（复用 `_fakes.aggregate_requeue_counts`）、CAS update 的 rowcount 可控。

⚠️ **本文件证不了什么**（别把这里的绿读成「功能验过了」）：
- 替身**不解释 SQL** ⇒ 候选的 `where`（invalidate_reason='online_content_gap' /
  assembled_ts <= cutoff / cluster.status IN …）**未被覆盖**，测的是「喂进来的行会被怎么处理」。
  真库谓词由 integration 探针覆盖。
- `resolve_fallback_wordlist` / `build_envelope` 被 monkeypatch ⇒ **「按现 cluster+现词表
  重算」的语义（§6.5 内容已刷新的判据）不在判据内**，只断言「重填过 payload_json」。
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone

from _fakes import FakeAsyncSession, FakeRows, aggregate_requeue_counts, ns, requeue_count_link_ids

from app.backflow import requeue as R
from app.backflow.requeue import (
    AUTO_REQUEUE_MAX_KEY,
    auto_requeue_stuck,
    requeue_guard_errors,
)


def _run(coro):
    return asyncio.run(coro)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _link(**over):
    base = dict(id=30, cluster_id=10, payload_id="pl-abc", case_id="c-1",
                case_type="regression_error", offline_status="invalidated",
                verify_status="pending", assembled_ts=_now() - timedelta(minutes=6),
                invalidate_reason="online_content_gap", payload_json='{"old": 1}')
    return ns(**{**base, **over})


def _cluster(**over):
    base = dict(id=10, agent="good-question", interface="POST /api/chat/{id}",
                first_trace_id="tr-9f2c1a", generation=1,
                trigger_version="2026.08.31-r47", fix_version=None,
                input_snapshot='{"question": "q"}', status="open")
    return ns(**{**base, **over})


class _AutoRequeueSession(FakeAsyncSession):
    """候选 select 喂给定行；计数按注册行真算；CAS rowcount 可控。"""

    def __init__(self, candidates=(), conv_rows=(), cas_rowcount=1):
        super().__init__()
        self._candidates = list(candidates)
        self._conv_rows = list(conv_rows)
        self._cas_rowcount = cas_rowcount
        self.cas_count = 0
        self.last_update_values: dict = {}   # 替身不执行 update ⇒ 把 SET 值捞出来供断言

    async def execute(self, stmt, params=None, execution_options=None):
        if getattr(stmt, "is_update", False):        # CAS 复位
            self.cas_count += 1
            self.last_update_values = {
                # SQLAlchemy 把 SET 值包成 BindParameter，取 .value 才是原值
                col.key: getattr(val, "value", val)
                for col, val in getattr(stmt, "_values", {}).items()
            }
            return ns(rowcount=self._cas_rowcount)
        ids = requeue_count_link_ids(stmt)           # 成批计数
        if ids is not None:
            return FakeRows(aggregate_requeue_counts(self._conv_rows, ids))
        # 候选 join select：成对返回
        return FakeRows(list(self._candidates))


def _patch_envelope(monkeypatch, *, marker="REBUILT"):
    """替掉词表读取与信封渲染（两者都要 IO），返回可识别的信封便于断言「重填过」。"""
    async def _words(session, *, agent_name):
        return ["嗯", "啊"], 7

    monkeypatch.setattr(R, "resolve_fallback_wordlist", _words)
    # 只回可 JSON 序列化的载荷（真 envelope 含 ORM 对象，替身不解释结构）
    monkeypatch.setattr(
        R, "build_envelope",
        lambda **kw: {"marker": marker, "payload_id": kw.get("payload_id"), "words": kw.get("words")},
    )


# ---------- 守卫链：四个否定维度（纯函数，无 IO） ----------


def test_guard_rejects_non_invalidated():
    assert requeue_guard_errors(_link(offline_status="active"), _cluster(), now=_now())


def test_guard_rejects_cap_gap_reason():
    why = requeue_guard_errors(_link(invalidate_reason="offline_cap_gap"), _cluster(), now=_now())
    assert why and "offline_cap_gap" in why


def test_guard_rejects_non_pending_verify():
    why = requeue_guard_errors(_link(verify_status="passed"), _cluster(), now=_now())
    assert why and "verify" in why


def test_guard_rejects_closed_cluster():
    why = requeue_guard_errors(_link(), _cluster(status="fixed"), now=_now())
    assert why and "closed" in why


def test_guard_rejects_within_debounce_window():
    lk = _link(assembled_ts=_now() - timedelta(minutes=1))
    why = requeue_guard_errors(lk, _cluster(), now=_now())
    assert why and "防抖" in why


def test_guard_passes_on_happy_path():
    assert requeue_guard_errors(_link(), _cluster(), now=_now()) is None


# ---------- 自动出口 ----------


def test_happy_path_resets_link_and_writes_audit(monkeypatch):
    _patch_envelope(monkeypatch)
    sess = _AutoRequeueSession(candidates=[(_link(id=30), _cluster(id=10))])
    n = _run(auto_requeue_stuck(sess, now=_now(), cap=2))

    assert n == 1 and sess.cas_count == 1
    conv = [o for o in sess.added if getattr(o, "action", None) == "requeue"]
    assert len(conv) == 1
    assert conv[0].actor_user_id is None            # 系统动作记 NULL
    assert "上限 2" in conv[0].detail                # 记**当时生效的上限**（可改，须可复原）
    assert "#1" in conv[0].detail                    # 本次是第 1 次（历史 0 条）


def test_rebuilds_payload_and_refreshes_assembled_ts(monkeypatch):
    """复位必须**重填 payload_json**（内容缺愈），不是重发旧载荷；assembled_ts 前进。"""
    _patch_envelope(monkeypatch, marker="REBUILT")
    old_ts = _now() - timedelta(minutes=30)
    lk = _link(id=30, assembled_ts=old_ts)
    sess = _AutoRequeueSession(candidates=[(lk, _cluster())])
    _run(auto_requeue_stuck(sess, now=_now(), cap=2))
    # 替身不执行 update，故断言 update 语句携带的值（真实落库由探针覆盖）
    stmt_values = sess.last_update_values
    assert stmt_values["offline_status"] == "assembled"
    assert stmt_values["invalidate_reason"] is None and stmt_values["invalidated_by"] is None
    assert json.loads(stmt_values["payload_json"])["marker"] == "REBUILT"
    assert stmt_values["payload_json"] != lk.payload_json   # 真的重算了，非原样回写
    assert stmt_values["assembled_ts"] > old_ts             # 离线据此判「内容已刷新」


def test_at_cap_skips_without_cas_or_audit(monkeypatch):
    """已达上限 ⇒ 停手转人工：不 CAS、不写审计（R-7「疑似不可自愈」）。"""
    _patch_envelope(monkeypatch)
    sess = _AutoRequeueSession(
        candidates=[(_link(id=30), _cluster())],
        conv_rows=[ns(link_id=30, action="requeue"), ns(link_id=30, action="requeue")],
    )
    assert _run(auto_requeue_stuck(sess, now=_now(), cap=2)) == 0
    assert sess.cas_count == 0 and sess.added == []


def test_cap_read_from_history_including_non_requeue_rows(monkeypatch):
    """计数口径 = 只数 action=requeue：同 link 的 invalidate 行不该把上限提前用掉。"""
    _patch_envelope(monkeypatch)
    sess = _AutoRequeueSession(
        candidates=[(_link(id=30), _cluster())],
        conv_rows=[ns(link_id=30, action="requeue"), ns(link_id=30, action="invalidate")],
    )
    assert _run(auto_requeue_stuck(sess, now=_now(), cap=2)) == 1
    conv = [o for o in sess.added if o.action == "requeue"]
    assert "#2" in conv[0].detail                    # 历史 1 条 ⇒ 本次是第 2 次


def test_cap_zero_disables_auto_requeue(monkeypatch):
    """cap=0 ⇒ 全停（配置化后的「关掉自动重推」语义）。"""
    _patch_envelope(monkeypatch)
    sess = _AutoRequeueSession(candidates=[(_link(id=30), _cluster())])
    assert _run(auto_requeue_stuck(sess, now=_now(), cap=0)) == 0
    assert sess.cas_count == 0


def test_cap_gap_candidate_is_skipped_by_guard(monkeypatch):
    """守备兜底：即使 cap_gap 行漏进候选（where 理应已排除），也必须被守卫挡下。"""
    _patch_envelope(monkeypatch)
    sess = _AutoRequeueSession(
        candidates=[(_link(id=31, invalidate_reason="offline_cap_gap"), _cluster())])
    assert _run(auto_requeue_stuck(sess, now=_now(), cap=2)) == 0
    assert sess.cas_count == 0 and sess.added == []


def test_cas_miss_skips_silently(monkeypatch):
    """CAS 落空（竞态：与 offline ack 交错）⇒ 跳过不抛、不写审计（无 HTTP 层可报错）。"""
    _patch_envelope(monkeypatch)
    sess = _AutoRequeueSession(candidates=[(_link(id=30), _cluster())], cas_rowcount=0)
    assert _run(auto_requeue_stuck(sess, now=_now(), cap=2)) == 0
    assert sess.cas_count == 1 and sess.added == []


def test_empty_candidates_returns_zero_without_count_query(monkeypatch):
    _patch_envelope(monkeypatch)
    sess = _AutoRequeueSession(candidates=[])
    assert _run(auto_requeue_stuck(sess, now=_now(), cap=2)) == 0


def test_batch_mixed_only_eligible_reset(monkeypatch):
    """一批里只复位够格的，其余原样留 invalidated（不误伤、不整批停）。"""
    _patch_envelope(monkeypatch)
    sess = _AutoRequeueSession(candidates=[
        (_link(id=30), _cluster()),                                  # 够格
        (_link(id=31, verify_status="passed"), _cluster()),           # verify 非 pending
        (_link(id=32, assembled_ts=_now() - timedelta(minutes=1)), _cluster()),  # 防抖内
    ])
    assert _run(auto_requeue_stuck(sess, now=_now(), cap=2)) == 1
    assert sess.cas_count == 1
    assert [o.link_id for o in sess.added if o.action == "requeue"] == [30]


def test_config_key_name_is_stable():
    # 键名是**对外契约**（admin 页 / 前端 configLabels / seed 三处靠它对齐），改名即破坏
    assert AUTO_REQUEUE_MAX_KEY == "auto_requeue_max_default"
