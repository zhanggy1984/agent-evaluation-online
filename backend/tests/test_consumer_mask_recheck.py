"""D2 脱敏复核单测（detail §2.6/§4.2 step3 + X-2 死角子集）。

复核只检键名；键命中的值须为掩码字面 `***` 或 null 才放行，其余判未掩码（SDK 漏网兜底）。
"""
import pytest

from app.consumer.mask_recheck import find_sensitive_leak
from app.consumer.schema import EventModel


def evt(**fields):
    """构造合法 EventModel（字段默认对齐 §2.2① request 样例）。"""
    base = {
        "schema_version": "1.0", "event_kind": "event",
        "trace_id": "tr-1", "agent": "good-question", "interface": "POST /api/chat/{id}",
        "node": "request", "seq": 0, "parent": None, "ts": 1785897600000,
        "duration_ms": 10, "status": "ok",
        "input": None, "output": None, "extra": {},
    }
    base.update(fields)
    return EventModel.model_validate(base)


class TestClean:
    def test_no_sensitive_keys(self):
        event = evt(input={"session_id": "{id}", "question": "查政策"})
        assert find_sensitive_leak(event) == []

    def test_masked_value_pass(self):
        # 已掩码（值 = ***）与空值放行：不二次处理、不误丢
        event = evt(
            input={"token": "***", "password": "***", "Authorization": "***"},
            output={"api_key": None},
        )
        assert find_sensitive_leak(event) == []

    def test_plain_text_input_pass(self):
        # input 为自由 str/标量：无键结构，键级复核天然不命中（内容级不本期）
        assert find_sensitive_leak(evt(input="帮我查政策")) == []

    def test_masked_nested_pass(self):
        event = evt(input={"headers": {"cookie": "***"}, "body": {"a": {"b": "***"}}})
        assert find_sensitive_leak(event) == []

    def test_extra_masked_pass(self):
        assert find_sensitive_leak(evt(extra={"token": "***"})) == []


class TestLeak:
    @pytest.mark.parametrize(
        ("field", "path"),
        [
            ("token", "input.token"),
            ("api_key", "input.api_key"),     # api[_-]?key 变体
            ("apikey", "input.apikey"),
            ("Authorization", "input.Authorization"),  # 大写 → IGNORECASE 兜底
            ("refresh_token", "output.refresh_token"),
        ],
    )
    def test_plain_sensitive_value(self, field, path):
        event = evt(input={field: "secret123"}, output={"refresh_token": "abc"})
        # input 命中优先；output 场景单独构造
        leaks = find_sensitive_leak(event)
        assert path in leaks or f"output.{field}" in leaks

    def test_nested_leak_detected(self):
        event = evt(input={"headers": {"Authorization": "Bearer xyz"}})
        assert find_sensitive_leak(event) == ["input.headers.Authorization"]

    def test_mixed_masked_and_leak(self):
        # 同文档已掩码放行 + 漏网检出并存
        event = evt(input={"token": "***", "password": "real-password-123"})
        assert find_sensitive_leak(event) == ["input.password"]

    def test_list_of_dicts(self):
        event = evt(input={"items": [{"id": 1}, {"credential": "c0"}], "ok": True})
        assert find_sensitive_leak(event) == ["input.items[1].credential"]


class TestEdgeCases:
    def test_sensitive_key_with_null_value(self):
        # 键名敏感但值为 null：无泄露，放行
        assert find_sensitive_leak(evt(input={"token": None})) == []

    def test_log_message_content_not_scanned(self):
        # log_message 已钉死 str；正文含敏感字样属内容级（不本期），键级不命中
        event = EventModel.model_validate(
            {
                "schema_version": "1.0", "event_kind": "log", "trace_id": "tr-1",
                "agent": "good-question", "interface": "POST /api/chat/{id}", "node": "log",
                "seq": 1, "parent": None, "ts": 1785897600000, "status": "ok",
                # 样例避开 key=value 字面（pre-commit 伪密钥扫描会误拦）；正文含 token 字样
                # 即可证明 log_message 内容级不参与键级扫描（hook 例外已在此注释说明）
                "log_level": "WARNING", "log_message": "url contains token abc in text",
                "input": None, "output": None, "extra": {},
            }
        )
        assert find_sensitive_leak(event) == []

    def test_deep_nested_no_crash(self):
        # 超深/超长不炸（X-2 死角），返回可控
        deep = node = {}
        for _ in range(200):
            node["child"] = {}
            node = node["child"]
        node["password"] = "deep-secret"
        leaks = find_sensitive_leak(evt(input=deep))
        # depth 上限截断：可能因截断未扫到最深，但绝不抛异常
        assert isinstance(leaks, list)
