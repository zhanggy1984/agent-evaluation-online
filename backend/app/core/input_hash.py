"""input 归一与 hash（detail §6.2 R-10：input_hash = sha256(normalize(input))）。

normalize = strip + 折叠空白 + 截断 8192 字符（去重键粒度 ≥ 复现粒度，与 §5.1④ DDL 截断
上限一致）。本模块是消费侧（trace_judge_state.root_input_hash）与聚类侧
（error_cluster.input_hash）的**共用同源实现**——两处 hash 必须同算法才能可比（§6.2）。

- input 为 str → 直接按文本归一；obj/list/标量 → 稳定序列化（sort_keys，键序无关）后归一。
- 快照（input_snapshot_clean）走原序序列化（展示用，§4.3 R-18），截断 8192 字符。
- normalize 截断先于 sha256，截断只影响长 input 的去重粒度下限，不会破坏结构比对。
"""
import hashlib
import json
import re

INPUT_MAX = 8192  # R-10：normalize 与明文快照截断上限（与 DDL 一致）

_WS_RE = re.compile(r"\s+")


def normalize_input(raw) -> str:
    """输入语义归一为规范文本：折叠空白 + strip + 截断。dict 键排序保证同语义同 hash。"""
    if isinstance(raw, str):
        text = raw
    else:
        text = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    text = _WS_RE.sub(" ", text).strip()
    return text[:INPUT_MAX]


def compute_input_hash(raw) -> str:
    """input_hash：sha256(normalize(input))。raw 为 None 时由调用方跳过（不入 hash 键）。"""
    return hashlib.sha256(normalize_input(raw).encode("utf-8")).hexdigest()


def snapshot_input(raw) -> tuple[str | None, int]:
    """root 明文快照（§4.3 R-18 落 input_snapshot_clean/input_truncated）。

    返回 (截断文本, truncated 0/1)：raw=None → (None, 0)（无 input 现场，组装侧只计数，
    §6.2/§10.2）；超 8192 字符截断前 8192 并置截断标。快照走**原序**序列化（evidence 形态，
    §7.1 evidence.input 展示用），与 hash 的 sort_keys 稳定序列化分离。
    """
    if raw is None:
        return None, 0
    text = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    truncated = 1 if len(text) > INPUT_MAX else 0
    return (text[:INPUT_MAX], truncated)
