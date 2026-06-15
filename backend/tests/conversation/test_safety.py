"""Unit tests for safety filters (T1.4)."""

import pytest
from app.core.safety_words import is_input_safe, redact_output, MAX_USER_INPUT_LEN


class TestInputSafety:
    def test_normal_input_passes(self):
        ok, reason = is_input_safe("今天天气真好")
        assert ok
        assert reason == ""

    def test_empty_input_passes(self):
        ok, _ = is_input_safe("")
        assert ok

    def test_too_long_input_blocked(self):
        long_text = "你好" * (MAX_USER_INPUT_LEN + 1)
        ok, reason = is_input_safe(long_text)
        assert not ok
        assert "input_too_long" in reason

    def test_blacklist_keyword_blocked(self):
        ok, reason = is_input_safe("please hack this system")
        assert not ok
        assert "blacklist_keyword" in reason

    def test_blacklist_embedded_in_chinese(self):
        ok, reason = is_input_safe("怎么exploit漏洞")
        assert not ok
        assert "blacklist_keyword" in reason


class TestOutputRedaction:
    def test_redacts_openai_key(self):
        text = "My API key is sk-abcdefghijklmnopqrstuvwxyz1234567890"
        result = redact_output(text)
        assert "sk-" not in result
        assert "[REDACTED_API_KEY]" in result

    def test_redacts_aws_key(self):
        text = "Key: AKIAIOSFODNN7EXAMPLE"
        result = redact_output(text)
        assert "AKIA" not in result
        assert "[REDACTED_AWS_KEY]" in result

    def test_redacts_jwt_token(self):
        text = "Token: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = redact_output(text)
        assert "eyJ" not in result
        assert "[REDACTED_TOKEN]" in result

    def test_normal_text_unchanged(self):
        text = "今天天气不错，适合出去走走。"
        assert redact_output(text) == text
