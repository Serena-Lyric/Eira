"""Unit tests for WS message schemas (T1.5)."""

import pytest
from app.api.ws.messages import (
    UserTextIn,
    StateOut,
    TokenOut,
    ActionOut,
    DoneOut,
    ErrorOut,
    extract_action_tags,
    strip_action_tags,
)


class TestInboundMessages:
    def test_user_text_in_valid(self):
        msg = UserTextIn(
            type="user_text", session_id="sess-1", text="你好", ts=123.0
        )
        assert msg.text == "你好"
        assert msg.session_id == "sess-1"

    def test_user_text_in_minimal(self):
        msg = UserTextIn(type="user_text", session_id="x", text="hi")
        assert msg.ts is None

    def test_user_text_in_empty_session_rejected(self):
        with pytest.raises(Exception):
            UserTextIn(type="user_text", session_id="", text="hi")

    def test_user_text_in_empty_text_rejected(self):
        with pytest.raises(Exception):
            UserTextIn(type="user_text", session_id="s", text="")


class TestOutboundMessages:
    def test_state_out(self):
        msg = StateOut(phase="thinking")
        data = msg.model_dump()
        assert data["type"] == "state"
        assert data["phase"] == "thinking"

    def test_token_out(self):
        msg = TokenOut(text="你好")
        data = msg.model_dump()
        assert data["type"] == "token"
        assert data["text"] == "你好"

    def test_action_out(self):
        msg = ActionOut(tag="Flick")
        data = msg.model_dump()
        assert data["type"] == "action"
        assert data["tag"] == "Flick"

    def test_done_out(self):
        msg = DoneOut(message_id=5, latency_ms=123.4, tokens={"completion": 10})
        data = msg.model_dump()
        assert data["message_id"] == 5

    def test_error_out(self):
        msg = ErrorOut(code="test_err", detail="something broke")
        data = msg.model_dump()
        assert data["code"] == "test_err"
        assert data["detail"] == "something broke"


class TestActionTags:
    def test_extract_wave_tag(self):
        assert extract_action_tags("[wave]你好") == ["wave"]

    def test_extract_multiple_tags(self):
        tags = extract_action_tags("[wave]你好[nod]")
        assert tags == ["wave", "nod"]

    def test_extract_no_tags(self):
        assert extract_action_tags("普通文本") == []

    def test_strip_tags_removes_all(self):
        result = strip_action_tags("[wave]你好[nod]再见")
        assert "[wave]" not in result
        assert "[nod]" not in result
        assert "你好" in result
        assert "再见" in result

    def test_strip_tags_no_tags(self):
        assert strip_action_tags("普通文本") == "普通文本"
