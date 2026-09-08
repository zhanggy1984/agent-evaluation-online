"""D3 累积态单测（detail §4.1 step4 / §4.3 / §4.4 + R-18/R-21 落点）。

只测纯函数 merge_trace_state（db 无关）；ORM 壳 apply_event 属薄接线，留 D6 集成 S-3
（同 trace 重放 → uk_trace 唯一行）实库验证。落行触发 = root 到达 / llm_call 到达 /
子节点 error（§4.1 step4）；log 与普通 ok 子节点不触达。
"""
from datetime import datetime, timezone

from app.consumer.schema import EventModel
from app.consumer.state import StateEffects, merge_trace_state
from app.core.input_hash import compute_input_hash, snapshot_input

WINDOW_S = 60  # 完成窗口（§4.3，D5 由 dict_config 注入）
GRACE_S = 300  # 宽限
TS = 1785897600000  # ms，UTC 近 2026-08 真实锚
CHILD_TS = TS + 10  # 子节点默认晚 root 10ms


def _ts_utc(ms: int) -> datetime:
    """int ms → naive UTC datetime（与 state._ms_to_utc 同换算，独立复算防同源 bug）。"""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(tzinfo=None)


def _ttl(ms: int) -> datetime:
    """期望 ttl_until = 触发行事件 ts + (窗口+宽限)。"""
    return _ts_utc(ms + (WINDOW_S + GRACE_S) * 1000)


def req(agent="good-question", trace_id="tr-1", status="error", ts=TS, **over):
    """root 请求事件（可带 input）。status=error/timeout → 携带 error_type。"""
    data = {
        "schema_version": "1.0", "event_kind": "event", "trace_id": trace_id, "agent": agent,
        "agent_version": "2026.08.31-r47", "interface": "POST /api/chat/{id}", "node": "request",
        "seq": 0, "parent": None, "ts": ts, "duration_ms": 1200, "status": status,
        "error_type": None if status == "ok" else "llm_timeout",
        "error_msg": None if status == "ok" else "provider timeout (masked)",
        "input": {"q": "政策?"}, "output": None, "extra": {},
    }
    data.update(over)
    return EventModel.model_validate(data)


def child(agent="good-question", trace_id="tr-1", node="llm_call", status="ok",
          seq=1, ts=CHILD_TS, error_type="llm_timeout", **over):
    """子节点事件。llm_call 必填 model/usage；非 llm 子节点不填。"""
    data = {
        "schema_version": "1.0", "event_kind": "event", "trace_id": trace_id, "agent": agent,
        "agent_version": "2026.08.31-r47", "interface": "POST /api/chat/{id}", "node": node,
        "seq": seq, "parent": 0, "ts": ts, "duration_ms": 40, "status": status,
        "error_type": error_type if status == "error" else None,
        "error_msg": "tool dead" if status == "error" else None,
        "usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10}
        if node == "llm_call" else None,
        "model": "deepseek-v3" if node == "llm_call" else None,
        "input": None, "output": None, "extra": {},
    }
    data.update(over)
    return EventModel.model_validate(data)


def log_event(ts=CHILD_TS, trace_id="tr-1"):
    """合法 log 事件（event_kind=log，§2.2③）。"""
    return EventModel.model_validate({
        "schema_version": "1.0", "event_kind": "log", "trace_id": trace_id,
        "agent": "good-question", "agent_version": "2026.08.31-r47",
        "interface": "POST /api/chat/{id}", "node": "log", "seq": 2, "parent": None,
        "ts": ts, "status": "ok", "log_level": "WARNING",
        "log_message": "retry attempt=2", "input": None, "output": None, "extra": {},
    })


def assert_counts(state, expected):
    """err_summary_json.entries 聚合形态断言：{error_type: count}。"""
    counts = {e["error_type"]: e["count"] for e in state["err_summary_json"]["entries"]}
    assert counts == expected


class TestRootArrival:
    def test_first_root_creates_full_state(self):
        state, fx = merge_trace_state(None, req(ts=TS), window_s=WINDOW_S, grace_s=GRACE_S)
        assert fx == StateEffects(affected=True, created=True)
        assert state["root_ok"] == 1
        assert state["root_ts"] == _ts_utc(TS)
        assert state["interface"] == "POST /api/chat/{id}"
        assert state["root_status"] == "error"
        assert state["root_error_type"] == "llm_timeout"
        assert state["judged"] == 0 and state["processed"] == 0
        assert state["llm_fact_ok"] == 0
        assert state["ttl_until"] == _ttl(TS)

    def test_root_input_hash_and_snapshot(self):
        # input 非空：hash + 明文快照 + 未截断标；hash 与 snapshot 各自同源（§6.2）
        state, _ = merge_trace_state(None, req(), window_s=WINDOW_S, grace_s=GRACE_S)
        clean, truncated = snapshot_input({"q": "政策?"})
        assert state["root_input_hash"] == compute_input_hash({"q": "政策?"})
        assert state["input_snapshot_clean"] == clean
        assert state["input_truncated"] == truncated == 0

    def test_root_without_input_no_hash(self):
        # input=null：无 input 现场，hash/快照留空（只计数不组装路径，§6.2/§10.2）
        state, fx = merge_trace_state(None, req(input=None), window_s=WINDOW_S, grace_s=GRACE_S)
        assert fx.affected
        assert state["root_input_hash"] is None
        assert state["input_snapshot_clean"] is None
        assert state["input_truncated"] == 0

    def test_root_long_input_truncated(self):
        state, _ = merge_trace_state(None, req(input="长" * 9000),
                                     window_s=WINDOW_S, grace_s=GRACE_S)
        assert state["input_truncated"] == 1
        assert len(state["input_snapshot_clean"]) == 8192

    def test_root_replay_idempotent(self):
        # root 重放：不重复建行（created=False）、err_summary 无重复累积、root 字段幂等覆盖
        first, fx1 = merge_trace_state(None, req(ts=TS), window_s=WINDOW_S, grace_s=GRACE_S)
        assert fx1.created
        second, fx2 = merge_trace_state(first, req(ts=TS + 5), window_s=WINDOW_S, grace_s=GRACE_S)
        assert not fx2.created
        assert second["root_ts"] == _ts_utc(TS + 5)  # 最新 root 到达时间（幂等覆盖）
        assert_counts(second, {})
        assert second["judged"] == 0
        assert second["ttl_until"] == _ttl(TS + 5)

    def test_root_ok_status_recorded(self):
        state, _ = merge_trace_state(None, req(status="ok"), window_s=WINDOW_S, grace_s=GRACE_S)
        assert state["root_status"] == "ok"
        assert state["root_error_type"] is None


class TestResidualTrace:
    """无 root 的残 trace：子节点 error / llm_call 先到，建行累积（§4.3 残现场）。"""

    def test_error_child_creates_residual_row(self):
        state, fx = merge_trace_state(
            None, child(node="tool_call", status="error", error_type="tool_timeout"),
            window_s=WINDOW_S, grace_s=GRACE_S,
        )
        assert fx == StateEffects(affected=True, created=True)
        assert state["root_ok"] == 0
        assert state["root_status"] is None
        assert state["root_input_hash"] is None
        assert state["llm_fact_ok"] == 0  # tool_call 非 llm_call，不动 llm 事实
        assert_counts(state, {"tool_timeout": 1})
        assert state["ttl_until"] == _ttl(CHILD_TS)

    def test_errors_aggregate_by_error_type(self):
        first, _ = merge_trace_state(
            None, child(node="tool_call", status="error", error_type="tool_timeout"),
            window_s=WINDOW_S, grace_s=GRACE_S,
        )
        # 同 error_type → count+1；error_msg 保留最新非空
        second, _ = merge_trace_state(
            first, child(node="tool_call", status="error", error_type="tool_timeout",
                         error_msg="retry dead"),
            window_s=WINDOW_S, grace_s=GRACE_S,
        )
        assert_counts(second, {"tool_timeout": 2})
        msgs = {e["error_type"]: e["error_msg"] for e in second["err_summary_json"]["entries"]}
        assert msgs["tool_timeout"] == "retry dead"
        # 新 error_type → 追加独立条目
        third, _ = merge_trace_state(
            second, child(node="tool_call", status="error", error_type="db_error"),
            window_s=WINDOW_S, grace_s=GRACE_S,
        )
        assert_counts(third, {"tool_timeout": 2, "db_error": 1})

    def test_llm_error_child_sets_llm_fact_and_summary(self):
        state, _ = merge_trace_state(
            None, child(node="llm_call", status="error", error_type="llm_timeout"),
            window_s=WINDOW_S, grace_s=GRACE_S,
        )
        assert state["llm_fact_ok"] == 1
        assert_counts(state, {"llm_timeout": 1})

    def test_llm_call_ok_sets_llm_fact(self):
        # llm_call status=ok 也落 llm_fact_ok（动态事实证据，§6.1 step2），不产生 err 条目
        state, _ = merge_trace_state(None, child(node="llm_call", status="ok"),
                                     window_s=WINDOW_S, grace_s=GRACE_S)
        assert state["llm_fact_ok"] == 1
        assert_counts(state, {})

    def test_root_after_residual_children(self):
        # 残行先累积 error，root 后到 → root 字段补齐、err 条目保留、不新建第二行
        residual, _ = merge_trace_state(
            None, child(node="tool_call", status="error", error_type="tool_timeout"),
            window_s=WINDOW_S, grace_s=GRACE_S,
        )
        full, fx = merge_trace_state(residual, req(status="ok"), window_s=WINDOW_S, grace_s=GRACE_S)
        assert not fx.created  # 同 trace 同键 → 覆盖同一行
        assert full["root_ok"] == 1
        assert full["root_status"] == "ok"
        assert_counts(full, {"tool_timeout": 1})


class TestNoTouch:
    """log 与普通 ok 子节点不落行（§4.1 step4 两类态迁移之外）。"""

    def test_log_never_touches(self):
        state, fx = merge_trace_state(None, log_event(), window_s=WINDOW_S, grace_s=GRACE_S)
        assert fx == StateEffects()  # affected=False（不落行）
        assert not state["root_ok"] and state["judged"] == 0

    def test_ok_non_llm_child_no_touch(self):
        # retrieve ok / tool_call ok：非 error、非 llm → 非落行触发
        _, fx = merge_trace_state(None, child(node="retrieve", status="ok"),
                                  window_s=WINDOW_S, grace_s=GRACE_S)
        assert not fx.affected

    def test_existing_state_untouched_by_log(self):
        state, _ = merge_trace_state(None, req(ts=TS), window_s=WINDOW_S, grace_s=GRACE_S)
        snapshot = dict(state)
        after, fx = merge_trace_state(state, log_event(ts=TS + 30), window_s=WINDOW_S,
                                      grace_s=GRACE_S)
        assert not fx.affected
        assert after == snapshot  # 现态逐字段不变（含 ttl）


class TestJudgedFreeze:
    """judged=1 后冻结：迟到子节点不改累积；R-21 迟到 root CAS 例外（§4.4/§6.1）。"""

    def _judged_state(self):
        """已判定残行：root 缺席、err 累积在场、judged=1（T-3.6 judge_scan 产物）。"""
        state, _ = merge_trace_state(
            None, child(node="llm_call", status="error", error_type="llm_timeout"),
            window_s=WINDOW_S, grace_s=GRACE_S,
        )
        state["judged"] = 1
        state["processed"] = 0
        return state

    def test_late_child_after_judged_frozen(self):
        state = self._judged_state()
        before_entries = list(state["err_summary_json"]["entries"])
        before_ttl = state["ttl_until"]
        after, fx = merge_trace_state(
            state, child(node="llm_call", status="error", error_type="db_error", seq=2),
            window_s=WINDOW_S, grace_s=GRACE_S,
        )
        assert fx == StateEffects()  # 不写行不续窗
        assert after["err_summary_json"]["entries"] == before_entries  # 不汇入新 error
        assert after["ttl_until"] == before_ttl

    def test_r21_root_late_cas(self):
        # judged=1 无 root + 迟到 root(error) → CAS root_late_complement 0→1 + 触发信号
        state = self._judged_state()
        after, fx = merge_trace_state(state, req(status="error", ts=TS),
                                      window_s=WINDOW_S, grace_s=GRACE_S)
        assert fx.affected and fx.root_late and not fx.created
        assert after["root_ok"] == 1
        assert after["root_late_complement"] == 1
        assert after["judged"] == 1  # 不重判不推翻，只补判候选（T-3.6 classify 消费）
        assert after["ttl_until"] == state["ttl_until"]  # judged 行不续窗

    def test_r21_cas_once(self):
        # 补判位已置 1 后，再次迟到 root 不再触发（幂等柱，防重复补判）
        state = self._judged_state()
        first, fx1 = merge_trace_state(state, req(ts=TS + 10), window_s=WINDOW_S, grace_s=GRACE_S)
        assert fx1.root_late and first["root_late_complement"] == 1
        second, fx2 = merge_trace_state(first, req(ts=TS + 20), window_s=WINDOW_S, grace_s=GRACE_S)
        assert not fx2.root_late
        assert second["root_late_complement"] == 1

    def test_r21_ok_root_after_judged_no_cas(self):
        # 迟到 root status=ok：无补判面（R-21 仅 error/timeout），judged 位不动
        state = self._judged_state()
        after, fx = merge_trace_state(state, req(status="ok"), window_s=WINDOW_S, grace_s=GRACE_S)
        assert not fx.root_late
        assert after["root_late_complement"] == 0
        assert after["judged"] == 1
        assert after["root_ok"] == 1 and after["root_status"] == "ok"  # 证据照记
        assert after["ttl_until"] == state["ttl_until"]
