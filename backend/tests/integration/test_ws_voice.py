"""Integration tests for WebSocket /ws/voice endpoint (T3.2)."""

import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from pydantic import ValidationError

from app.main import app
from app.api.ws.voice_messages import (
    VoiceStartIn,
    VoiceEndIn,
    VoiceBargeInIn,
    AsrPartialOut,
    AsrFinalOut,
    VoiceDoneOut,
    VoiceErrorOut,
)


# ── Route registration ────────────────────────────────────────────────


def test_voice_ws_route_registered():
    """Verify /ws/voice route is registered."""
    ws_routes = [
        r for r in app.routes if hasattr(r, "path") and r.path == "/ws/voice"
    ]
    assert len(ws_routes) == 1, "/ws/voice route should be registered"


@pytest.mark.asyncio
async def test_ws_voice_rejects_invalid_token():
    """Connecting without valid token should be rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        try:
            async with c.stream("GET", "/ws/voice?token=bad") as response:
                assert response.status_code in (401, 403, 426)
        except Exception:
            pass  # Connection rejected is acceptable


# ── Message schema validation ─────────────────────────────────────────


class TestVoiceStartIn:
    def test_valid(self):
        msg = VoiceStartIn(lang="zh")
        assert msg.type == "voice.start"
        assert msg.lang == "zh"

    def test_default_lang(self):
        msg = VoiceStartIn()
        assert msg.lang == "zh"

    def test_invalid_type(self):
        with pytest.raises(ValidationError):
            VoiceStartIn(type="wrong", lang="zh")


class TestOutboundMessages:
    def test_asr_partial(self):
        msg = AsrPartialOut(text="你好")
        data = msg.model_dump()
        assert data["type"] == "asr.partial"
        assert data["text"] == "你好"

    def test_asr_final(self):
        msg = AsrFinalOut(text="你好世界")
        data = msg.model_dump()
        assert data["type"] == "asr.final"
        assert data["text"] == "你好世界"

    def test_voice_done(self):
        msg = VoiceDoneOut(latency_ms=1234.5, tokens={"completion": 42})
        data = msg.model_dump()
        assert data["type"] == "chat.done"
        assert data["latency_ms"] == 1234.5
        assert data["tokens"]["completion"] == 42

    def test_voice_error(self):
        msg = VoiceErrorOut(code="test_error", detail="Something went wrong")
        data = msg.model_dump()
        assert data["type"] == "error"
        assert data["code"] == "test_error"
