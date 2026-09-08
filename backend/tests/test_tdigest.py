"""t-digest（自研纯 Python）单测：精度（O-4 跨小时 merge p95<1%）/roundtrip/确定性。

裁定记录（供 detail v1.12 回填）：原拍板引 PyPI tdigest，其 C 依赖在无 MSVC 的 Windows
上不可编译 → 改自研纯 Python（见 tdigest.py 模块 docstring）。O-4 判据钉在 merge 误差。
"""
import random

from app.store.tdigest import TDigest


def _sample_pct(sorted_vals: list[float], q: float) -> float:
    """ground truth 分位（nearest-rank，供误差对比；与 digest 插值定义同量级口径）。"""
    n = len(sorted_vals)
    if n == 0:
        return float("nan")
    if q <= 0.0:
        return sorted_vals[0]
    if q >= 1.0:
        return sorted_vals[-1]
    return sorted_vals[min(int(q * n), n - 1)]


def _rel_err(est: float | None, exact: float) -> float:
    assert est is not None and exact != 0
    return abs(est - exact) / exact


def _make_hour_values(rng: random.Random, n: int) -> list[int]:
    """一小时模拟 request duration（ms 整数）：中段主体 + 右尾离群 → 喂饱 p95/p99。"""
    vals = []
    for _ in range(n):
        r = rng.random()
        if r < 0.7:
            base = max(1, int(rng.gauss(100, 40)))
        elif r < 0.9:
            base = max(1, int(rng.gauss(300, 80)))
        else:
            base = max(1, int(rng.expovariate(1 / 2000)))  # 长尾：p95/p99 敏感区
        vals.append(min(base, 60_000))
    return vals


def _digest_of(vals: list[int], seed=0) -> TDigest:
    """按 rollup 口径建 digest：distinct × 次数（去重后带权喂入，成本可控）。"""
    d = TDigest()
    counter = {}
    for v in vals:
        counter[v] = counter.get(v, 0) + 1
    for v, c in sorted(counter.items()):
        d.update(v, c)
    d.compress()
    return d


class TestAccuracy:
    def test_merge_vs_full_p95_within_one_percent(self):
        # O-4：三个"小时 digest" merge 后 p95 误差 <1%（跨小时 merge 口径）
        rng = random.Random(42)
        hours = [_make_hour_values(rng, 3000) for _ in range(3)]
        merged = TDigest()
        for vals in hours:
            merged.merge(_digest_of(vals))
        merged.compress()

        full = sorted(v for vals in hours for v in vals)
        for q, tol in ((0.5, 0.06), (0.95, 0.01), (0.99, 0.02)):
            err = _rel_err(merged.percentile(q), _sample_pct(full, q))
            assert err < tol, f"q={q} err={err:.4f}"

    def test_single_pass_accuracy_after_compress(self):
        rng = random.Random(7)
        vals = _make_hour_values(rng, 5000)
        d = _digest_of(vals)
        assert len(d.centroids()) <= 1000  # K=1000 压得住
        full = sorted(vals)
        assert _rel_err(d.percentile(0.95), _sample_pct(full, 0.95)) < 0.01
        assert _rel_err(d.percentile(0.99), _sample_pct(full, 0.99)) < 0.02


class TestRoundtrip:
    def test_serialize_deserialize_preserves_percentiles(self):
        d = _digest_of([50, 60, 70, 80, 90, 100, 200, 300, 400, 500])
        raw = d.serialize()
        assert isinstance(raw, str)
        d2 = TDigest.deserialize(raw)
        for q in (0.5, 0.95, 0.99):
            assert d2.percentile(q) == d.percentile(q)

    def test_empty_digest_returns_none_and_sketch_roundtrip(self):
        d = TDigest()
        assert d.percentile(0.5) is None
        assert d.serialize()  # 空 sketch 可序列化（payload 有 version/[]，不 None）
        assert TDigest.deserialize("").total() == 0.0  # 空串反序列化为空 digest

    def test_merge_of_equal_and_deterministic(self):
        d1, d2 = _digest_of([1, 2, 3, 100]), _digest_of([2, 3, 4, 200])
        before = d1.percentile(0.95)
        d1.merge(d2)
        d1.compress()
        assert d1.total() == 8.0
        assert d1.percentile(0.95) is not None
        # 同输入重建 → 同输出（无随机）
        d3, d4 = _digest_of([1, 2, 3, 100]), _digest_of([2, 3, 4, 200])
        d3.merge(d4)
        d3.compress()
        assert d3.serialize() == d1.serialize()
        assert d1.percentile(0.5) is not None and before is not None

    def test_same_mean_merges_into_existing_centroid(self):
        d = TDigest()
        d.update(5, 1)
        d.update(5, 2)  # 同 mean 合并（去重喂样语义）
        assert len(d.centroids()) == 1
        assert d.centroids()[0] == (5.0, 3.0)


class TestConvergence:
    def test_integer_granularity_no_hang_and_bounded(self):
        # 早先死循环回归：distinct 少、单 centroid 权重大 → compress 必须单调收敛
        d = TDigest()
        vals = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        counter = {}
        for i in range(10):
            for _ in range(1000):
                counter[vals[i]] = counter.get(vals[i], 0) + 1
        for v, c in sorted(counter.items()):
            d.update(v, c)
        d.compress()
        assert len(d.centroids()) <= 1000
        assert d.total() == 10_000.0
        assert d.percentile(0.5) is not None
