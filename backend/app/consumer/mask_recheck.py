"""消费侧脱敏复核（detail §4.1 step3 / §4.2 step3 + §2.6）：检出未掩码敏感键 → 丢弃。

- SDK 侧 = 序列化前对 `input/output/extra/log_message` 递归掩码命中键 → 值替换 `***`。
  本模块是**平台兜底复核**：SDK 掩码漏网的敏感键明文打到平台 → 检出并丢弃（平台不还原，
  无还原逻辑）。只检**键名**（键级掩码 ≠ 内容级脱敏，§2.6 注：地址/合同/证件号内容由采集
  策略控制，不属本复核）。
- 已掩码值（`"***"`）与空值（`null`）放行：不二次处理、不误丢（X-2：值已掩码/键不存在）。
- 作用面：`input`/`output`/`extra`（schema 已把 log_message 钉死为 str → 无键结构，
  内容级明文不在此复核范围）。
- 防御：嵌套深度上限截断（恶意超深结构不炸栈）。
"""
import re

from app.consumer.schema import EventModel

MASKED = "***"  # §2.6 SDK 掩码字面值

# §2.6 平台掩码键正则（未锚定子串匹配，与 SDK 复用同源；IGNORECASE 兜 SDK 大写漏网）
SENSITIVE_KEY_RE = re.compile(
    r"authorization|token|password|secret|api[_-]?key|fernet|credential"
    r"|auth_config|cookie|set-cookie|x-api-key|private[_-]?key|access_token|refresh_token",
    re.IGNORECASE,
)

_MAX_DEPTH = 100  # 防御：超深嵌套停止递归（正常 input 深度远低于此）


def find_sensitive_leak(event: EventModel) -> list[str]:
    """复核 input/output/extra 的未掩码敏感键。返回命中键路径列表（空 = 复核通过）。

    命中 = key 命中掩码正则 且 值既非掩码字面 `***` 也非 null（SDK 漏掩的明文）。
    已掩码值不二次处理；null 表示未填敏感值（无泄露）。
    """
    hits: list[str] = []
    for field in ("input", "output", "extra"):
        value = getattr(event, field)
        _scan(value, field, hits, depth=0)
    return hits


def _scan(node, path: str, hits: list[str], depth: int) -> None:
    """递归扫描 dict/list；str/标量无键结构不递归（内容级明文不属键级复核）。"""
    if node is None or depth > _MAX_DEPTH:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else str(key)
            if SENSITIVE_KEY_RE.search(key):
                if value != MASKED and value is not None:
                    hits.append(child_path)  # SDK 掩码漏网明文 → 平台兜底检出
            else:
                _scan(value, child_path, hits, depth + 1)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _scan(item, f"{path}[{i}]", hits, depth + 1)
