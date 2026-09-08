"""rollup（T-2.3）单测：store 确定性/映射 + job 纯函数（跳过真实 ES 编排，留 #129 集成）。

- store：mapping dynamic:false + doc_type 判别、确定性 _id（重跑同 id、跨组异 id）、
  hour 对齐助手、build_*_doc 形状（sketch 仅在有时序样本时落）、merge_digests 跨小时求和。
- job 纯函数：_late_hour_starts 对齐已完成小时、_decide_recompute 迟到探测、
  _accumulate 分组计数（node 白名单/status 红显/tokens 嵌套/duration 去重）、_fold_docs 确定性。
- 真实 ES rollup 行为（search_after 翻页/覆写/meta 探测）留集成阶段 judge_scan/DB shell 验证。
"""
from app.store import metrics_rollup as store
from app.store.tdigest import TDigest
from app.worker import rollup_job as job

_AGENT = "good-question"
_HOUR = "2026-09-08T01:00"
_HOUR_START_MS = 1_788_829_200_000  # 2026-09-08T01:00:00Z（UTC）


def _settings():
    from app.core.config import Settings

    return Settings(app_env="test", resource_env="dev", jwt_secret="mock-secret-" * 8)


def _src(**kw):
    base = {"agent": _AGENT, "interface": "POST /chat", "node": "request",
            "model": None, "status": "ok", "duration_ms": 100, "ts": _HOUR_START_MS + 1000,
            "trace_key": f"{_AGENT}#tr-x", "seq": 1,
            "usage": {"prompt_tokens": 100, "completion_tokens": 20}}
    base.update({k: v for k, v in kw.items() if v is not None})
    return base


# ---------- store：映射 / 确定性 _id / hour 助手 / doc 形状 ----------


class TestStoreIdsAndHelpers:
    def test_mapping_is_dynamic_false_with_doc_type(self):
        assert store.ROLLUP_MAPPING["dynamic"] is False
        props = store.ROLLUP_MAPPING["properties"]
        assert props["doc_type"]["type"] == "keyword"
        assert props["sketch"]["type"] == "keyword"
        assert props["total"]["type"] == "long"
        # rollup 组 doc 是扁平长整型计数，不声明嵌套 usage（token 已摊平成 prompt/completion）
        assert "usage" not in props

    def test_doc_id_deterministic_and_distinguishing(self):
        a = store.rollup_doc_id(_AGENT, "POST /chat", "request", "", _HOUR)
        assert a == store.rollup_doc_id(_AGENT, "POST /chat", "request", "", _HOUR)
        assert a != store.rollup_doc_id(_AGENT, "POST /chat", "request", "sonnet", _HOUR)
        assert a != store.rollup_doc_id(_AGENT, "POST /chat", "llm_call", "", _HOUR)
        assert store.rollup_meta_id(_HOUR) != a  # meta _id 与组 _id 空间不冲突

    def test_hour_helpers_align_and_roundtrip(self):
        assert store.floor_hour_ms(_HOUR_START_MS) == _HOUR_START_MS
        assert store.floor_hour_ms(_HOUR_START_MS + 3_599_999) == _HOUR_START_MS
        assert store.hour_key_of(_HOUR_START_MS) == _HOUR
        assert store.hour_key_of(_HOUR_START_MS + 3_600_000) == "2026-09-08T02:00"
        assert store.hour_key_of(store.floor_hour_ms(_HOUR_START_MS - 1)) == "2026-09-08T00:00"

    def test_rollup_index_name_uses_resource_env(self):
        assert store.rollup_index_name(_settings()) == "dev.obs-metrics-rollup"

    def test_build_rollup_doc_shape_and_sketch_gating(self):
        d = TDigest()
        d.update(50, 3)
        d.update(500, 1)
        d.compress()
        doc = store.build_rollup_doc(
            agent=_AGENT, interface="POST /chat", node="request", model="",
            hour=_HOUR, hour_start_ms=_HOUR_START_MS,
            total=4, error=1, timeout=0, prompt_tokens=0, completion_tokens=0,
            digest=d, updated_ts=_HOUR_START_MS + 3600_000,
        )
        assert doc["doc_type"] == "group" and doc["schema_version"] == "1"
        assert doc["total"] == 4 and doc["error"] == 1 and doc["sketch"]
        # 无 duration 样本（digest 空）→ 不落 sketch，percentiles 读侧显 '-'
        doc2 = store.build_rollup_doc(
            agent=_AGENT, interface="POST /chat", node="llm_call", model="sonnet",
            hour=_HOUR, hour_start_ms=_HOUR_START_MS, total=2, error=1, timeout=0,
            prompt_tokens=100, completion_tokens=20, digest=None,
            updated_ts=_HOUR_START_MS + 3600_000,
        )
        assert "sketch" not in doc2 and doc2["prompt_tokens"] == 100

    def test_meta_doc_marker(self):
        meta = store.build_meta_doc(hour=_HOUR, source_count=55, updated_ts=1)
        assert meta["doc_type"] == "meta" and meta["source_count"] == 55


class TestMergeDigests:
    def test_merge_three_hour_docs_counts_and_pct(self):
        docs = []
        for offset, n in ((0, 3), (1, 4), (2, 5)):
            d = TDigest()
            for _ in range(n):
                d.update(10 * offset + 1, 1)  # 同 offset 小时同均值 → 各小时 distinct=1
            d.compress()
            docs.append(store.build_rollup_doc(
                agent=_AGENT, interface="POST /chat", node="request", model="",
                hour=store.hour_key_of(_HOUR_START_MS + offset * 3_600_000),
                hour_start_ms=_HOUR_START_MS + offset * 3_600_000,
                total=n, error=1, timeout=0, prompt_tokens=0, completion_tokens=0,
                digest=d, updated_ts=1,
            ))
        out = store.merge_digests(docs, pcts=(0.5, 0.95))
        assert out["total"] == 12 and out["error"] == 3 and out["timeout"] == 0
        assert out["p50"] is not None and out["p95"] is not None

    def test_merge_skips_hours_without_sketch(self):
        doc_noske = store.build_rollup_doc(
            agent=_AGENT, interface="POST /chat", node="request", model="",
            hour=_HOUR, hour_start_ms=_HOUR_START_MS, total=2, error=2, timeout=0,
            prompt_tokens=0, completion_tokens=0, digest=None, updated_ts=1,
        )
        out = store.merge_digests([doc_noske], pcts=(0.5,))
        assert out["total"] == 2 and out["p50"] is None  # 计数照算，无分位样本不贡献


# ---------- rollup_job：小时窗口 / 迟到探测 / 分组折叠 ----------


class TestJobPure:
    def test_late_hour_starts_aligned_completed_oldest_first(self):
        now = _HOUR_START_MS + 3_600_000 * 3 + 12_345  # now 在 T03 小时中段
        starts = job._late_hour_starts(now, 6)
        assert len(starts) == 6
        assert all(s % 3_600_000 == 0 for s in starts)  # 全部整点对齐
        assert starts == sorted(starts)  # 旧 → 新
        # 最旧 = now 所在小时起 −6h；最新 = now 所在小时起 −1h（进行中小时不含）
        assert starts[-1] == _HOUR_START_MS + 3_600_000 * 2
        assert starts[0] == _HOUR_START_MS - 3_600_000 * 3
        assert job._late_hour_starts(now, 0) == []  # late_k<=0 → 无小时可处理

    def test_decide_recompute(self):
        assert job._decide_recompute(None, 10) is True        # 未 rollup → 重算
        assert job._decide_recompute(10, 10) is False         # 一致 → 跳过
        assert job._decide_recompute(9, 10) is True           # 迟到新增 → 重算

    def test_accumulate_groups_and_counts(self):
        def drop_dur(s: dict) -> dict:  # 模拟源事件本就不带 duration_ms（llm/边界）
            s.pop("duration_ms", None)
            return s

        def drop_usage(s: dict) -> dict:  # 该事件无 token 计费信息
            s.pop("usage", None)
            return s

        accs = {}
        no_dur_req = drop_dur(_src(node="request", trace_key=f"{_AGENT}#tr-n", seq=6))
        llm_err = drop_dur(_src(node="llm_call", model="claude-sonnet", status="error",
                                usage={"prompt_tokens": 500, "completion_tokens": 100}, seq=5))
        srcs = [
            _src(node="request", status="ok", duration_ms=100, seq=0),
            _src(node="request", status="error", duration_ms=500,
                 trace_key=f"{_AGENT}#tr-y", seq=1),
            _src(node="request", status="timeout", duration_ms=300,
                 trace_key=f"{_AGENT}#tr-z", seq=2),
            drop_usage(_src(node="llm_call", model="claude-sonnet", status="ok",
                            duration_ms=80, seq=3)),
            llm_err,
            _src(node="heartbeat"),  # node 白名单外 → 不计
            no_dur_req,  # 无 duration → 计入 total，不计入 digest
        ]
        consumed = sum(job._accumulate(s, accs) for s in srcs)
        assert consumed == 6  # 心跳不计
        req_key = (_AGENT, "POST /chat", "request", "")
        llm_key = (_AGENT, "POST /chat", "llm_call", "claude-sonnet")
        assert set(accs) == {req_key, llm_key}
        req = accs[req_key]
        assert req["total"] == 4 and req["error"] == 1 and req["timeout"] == 1
        assert dict(req["dur"]) == {100: 1, 500: 1, 300: 1}  # 无 duration 的 request 不进 digest
        llm = accs[llm_key]
        assert llm["total"] == 2 and llm["error"] == 1
        assert llm["pt"] == 500 and llm["ct"] == 100  # usage.* 嵌套路径累计
        assert dict(llm["dur"]) == {80: 1}

    def test_fold_docs_deterministic_and_sketch_written(self):
        srcs = [
            _src(node="request", status="ok", duration_ms=100, seq=0),
            _src(node="llm_call", model="claude-sonnet", status="ok", duration_ms=80, seq=1),
        ]
        accs = {}
        for s in srcs:
            job._accumulate(s, accs)
        docs = job._fold_docs(accs, hour_start_ms=_HOUR_START_MS, updated_ts=1)
        assert len(docs) == 2 and docs[0]["doc_type"] == "group"
        assert all(d["sketch"] for d in docs)  # 各小时组均有 duration 样本
        # 确定性：同输入重折叠 → 同 doc 序列（含 sketch 字节一致）
        accs2 = {}
        for s in srcs:
            job._accumulate(s, accs2)
        assert job._fold_docs(accs2, hour_start_ms=_HOUR_START_MS, updated_ts=1) == docs
