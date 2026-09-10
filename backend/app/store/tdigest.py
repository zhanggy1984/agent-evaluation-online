"""极简确定性 t-digest（自研纯 Python，T-2.3 裁定落地）。

背景（2026-09-08 裁定，记录给文档收尾 v1.12 / O-4 回填）：原拍板引 PyPI `tdigest`，但其 C
依赖 accumulation-tree 在无 MSVC 的 Windows 上只能源码编译（pip 实测失败），且本环境索引无纯
Python 替包 → **改为自研纯 Python 实现**（用户确认）。语义与官方一致：centroid 压缩近似分布，
sketch 格式 = 自研但沿用 `{v:1, c:[[mean,weight],…]}` JSON → base64(utf-8)（§5.3 rollup）。

设计：
- 只喂**去重后带权样本**（distinct duration × 次数）——rollup 建 digest 前先 Counter 聚合，
  每小时去重后 distinct 量级远小于事件总量（duration 是 ms 整数，值域收敛），update 成本可控。
- centroid 列表按 mean 升序；同 mean 样本合并入已有 centroid（去重天然相邻）。
- 超 K 时**单遍压缩**（经典 Dunning 近似）：顺序归并，集群总量 ≤ allowed(q)=4·n·q(1-q)/K；
  尾部 q→0/1 时 allowed→≤1 → 极端离群各自独立成簇，右尾分辨率保住 → p95/p99 稳。
- 纯函数、无随机（同输入同输出），跨平台。

百分位估计：把每 centroid 视作累计分布上的点 (mean_i, cum_mid_i/n)，对 q 目标做分段线性
插值（端点外推到头尾均值）——centroid 数 ≥ K 时误差远小于 1%（O-4 单测实证）。
"""
from __future__ import annotations

import base64
import json

_K_DEFAULT = 1000  # 压缩目标 centroid 数（越大右尾越细、sketch 越大；O-4 调 K 的旋钮）
_MIN_ALLOWED_WEIGHT = 1.0


def _interp_q(q: float, means: list[float], weights: list[float], n: float) -> float:
    """q∈[0,1] 的线性插值估计：以 centroid 累计中点为锚点。空 digest 返回 NaN。"""
    if n <= 0 or not means:
        return float("nan")
    if q <= 0.0:
        return means[0]
    if q >= 1.0:
        return means[-1]
    target = q * n
    cum = 0.0
    prev_m = means[0]
    for m, w in zip(means, weights):
        hi = cum + w
        if target <= hi:
            # 落在当前 centroid 内：估计值在 prev_m..m 间按权重占比插值（首簇用 m）
            if cum <= 0.0 or prev_m == m:
                return m
            frac = (target - cum) / w if w > 0 else 0.0
            return prev_m + (m - prev_m) * frac
        prev_m = m
        cum = hi
    return means[-1]


class TDigest:
    """自研 t-digest：update 增量喂样本、centroid 超限单遍压缩、percentile/序列化。"""

    def __init__(self, compression: int = _K_DEFAULT) -> None:
        self._K = max(compression, 10)
        self._means: list[float] = []
        self._weights: list[float] = []
        self._n = 0.0

    # ---- 喂样 ---------------------------------------------------------

    def update(self, x: float, w: float = 1.0) -> None:
        """喂一个带权样本（x 建议先去重聚合，同 mean 合并进已有 centroid）。"""
        if w <= 0 or x is None:
            return
        x = float(x)
        self._n += float(w)
        lo = _bisect_left(self._means, x)
        if lo < len(self._means) and self._means[lo] == x:  # 同 mean 合并，控制 centroid 数
            self._weights[lo] += float(w)
            return
        self._means.insert(lo, x)
        self._weights.insert(lo, float(w))

    def merge(self, other: "TDigest") -> None:
        """合并另一 digest（读侧跨小时/跨 doc merge）：逐 centroid 带权喂入。"""
        for m, w in zip(other._means, other._weights):
            self.update(m, w)

    # ---- 压缩 ---------------------------------------------------------

    def compress(self) -> "TDigest":
        """压缩至 centroid ≤ K（幂等；≤K 时 no-op）。读侧 merge 完调用一次。

        收敛保证：经典单遍归并可能因**整数粒度**（distinct duration 少、单个 weight 大）停在
        >K 且不再减少（allowed 已到 1/权重上限）。故每轮无进展就把 k_eff 折半（allowed 按
        1/k_eff 放大）强制并簇 → 单调减少到 ≤K 必终止。k_eff→1 时 allowed≈4nq(1-q) 足以把
        中部质量并成少数簇，尾部分位数仍保（尾部 q→0/1 处 allowed→小，极端离群独立成簇）。
        """
        if len(self._means) <= self._K:
            return self
        n = self._n
        if n <= 0:
            return self
        k_eff = float(self._K)
        while len(self._means) > self._K:
            before = len(self._means)
            self._do_pass(n, k_eff)
            if len(self._means) >= before:
                if k_eff <= 1.0:  # allowed 已到上限仍超 K（极端尾部离群被 cap=1 卡住）
                    self._merge_closest_until_k()
                    break
                k_eff = max(k_eff / 2.0, 1.0)  # 无进展 → 放宽簇宽强制合并
        return self

    def _merge_closest_until_k(self) -> None:
        """兜底：反复并「加权距离最小」的相邻簇直到 ≤K（仅极端情形触发，迭代有界）。"""
        while len(self._means) > self._K:
            best_i, best_cost = -1, float("inf")
            for i in range(len(self._means) - 1):
                ww = self._weights[i] * self._weights[i + 1] / (
                    self._weights[i] + self._weights[i + 1])
                cost = ww * (self._means[i] - self._means[i + 1]) ** 2
                if cost < best_cost:
                    best_i, best_cost = i, cost
            m, w = self._means[best_i], self._weights[best_i]
            m2, w2 = self._means[best_i + 1], self._weights[best_i + 1]
            self._means[best_i] = (m * w + m2 * w2) / (w + w2)
            self._weights[best_i] = w + w2
            del self._means[best_i + 1]
            del self._weights[best_i + 1]

    def _do_pass(self, n: float, k_eff: float) -> None:
        """单遍顺序归并：集群总量 ≤ allowed(q)=max(4·n·q(1-q)/k_eff, 1)。"""
        def allowed(q: float) -> float:
            return max(4.0 * n * q * (1.0 - q) / k_eff, _MIN_ALLOWED_WEIGHT)

        out_m: list[float] = []
        out_w: list[float] = []
        cum = 0.0  # 已落盘集群的总权重（= 当前待归并簇的累计下界）
        cm = self._means[0]
        cw = self._weights[0]
        for m, w in zip(self._means[1:], self._weights[1:]):
            q = min(max((cum + (cw + w) / 2.0) / n, 1e-9), 1.0 - 1e-9)
            if (cw + w) <= allowed(q):  # 与下一 centroid 归并仍在允许簇宽内
                cm = (cm * cw + m * w) / (cw + w)
                cw += w
            else:  # 簇封口，新簇起
                out_m.append(cm)
                out_w.append(cw)
                cum += cw
                cm, cw = m, w
        out_m.append(cm)
        out_w.append(cw)
        self._means, self._weights = out_m, out_w

    # ---- 读取 ---------------------------------------------------------

    def percentile(self, q: float) -> float | None:
        """q∈[0,1] 分位；空 digest 返回 None（API 层显示 '-'）。"""
        if self._n <= 0 or not self._means:
            return None
        v = _interp_q(q, self._means, self._weights, self._n)
        return None if v != v else float(v)  # NaN → None

    def total(self) -> float:
        return self._n

    def centroids(self) -> list[tuple[float, float]]:
        """(mean, weight) 升序列表（序列化用）。"""
        return list(zip(self._means, self._weights))

    # ---- 序列化（sketch 字段：JSON base64，§5.3） -----------------------

    def serialize(self) -> str:
        """centroids → {"v":1,"c":[[mean,weight],…]} → base64(utf-8)。"""
        payload = {"v": 1, "c": [[m, w] for m, w in zip(self._means, self._weights)]}
        raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return base64.b64encode(raw.encode("utf-8")).decode("ascii")

    @classmethod
    def deserialize(cls, sketch: str | None, compression: int = _K_DEFAULT) -> "TDigest":
        """sketch(base64) → TDigest（逐 centroid 带权重建，等价 merge 语义）。"""
        d = cls(compression=compression)
        if not sketch:
            return d
        payload = json.loads(base64.b64decode(sketch.encode("ascii")).decode("utf-8"))
        for m, w in payload.get("c", []):
            d.update(m, w)
        return d


def _bisect_left(a: list[float], x: float) -> int:
    """手写二分（避免依赖 bisect 的 C 实现差异，保确定性；O(log len)）。"""
    lo, hi = 0, len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if a[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    return lo
