"""Unit tests for ASR provider abstraction."""

import asyncio

import pytest

from app.capabilities.asr.base import BaseASRProvider, AsrEvent
from app.capabilities.asr.mock import MockASRProvider
from app.capabilities.asr.factory import create_asr_provider
from app.core.config import AsrSettings


# ── Base interface contract ───────────────────────────────────────────

class TestAsrEvent:
    def test_partial_event(self):
        evt = AsrEvent(kind="partial", text="你好", is_final=False)
        assert evt.kind == "partial"
        assert evt.text == "你好"
        assert evt.is_final is False

    def test_final_event(self):
        evt = AsrEvent(kind="final", text="你好世界", is_final=True)
        assert evt.kind == "final"
        assert evt.text == "你好世界"
        assert evt.is_final is True


# ── Mock provider ─────────────────────────────────────────────────────

class TestMockASRProvider:
    @pytest.mark.asyncio
    async def test_stream_returns_text(self):
        """Mock provider echoes back text based on audio chunk count."""
        provider = MockASRProvider(latency_ms=0)

        # Simulate sending audio chunks
        async def audio_iter():
            for _ in range(10):
                yield b"\x00" * 1024

        events = []
        async for evt in provider.stream(audio_iter(), lang="zh"):
            events.append(evt)

        # Should have partial events + 1 final event
        assert len(events) >= 1
        assert events[-1].is_final is True
        assert len(events[-1].text) > 0
        # Partial events should not be final
        for evt in events[:-1]:
            assert evt.is_final is False

    @pytest.mark.asyncio
    async def test_stream_multiple_languages(self):
        """Mock provider accepts language parameter."""
        provider = MockASRProvider()

        async def audio_iter():
            for _ in range(5):
                yield b"\x00" * 512

        # Different languages should all work
        for lang in ("zh", "en", "ja"):
            events = []
            async for evt in provider.stream(audio_iter(), lang=lang):
                events.append(evt)
            assert len(events) > 0
            assert events[-1].is_final is True

    @pytest.mark.asyncio
    async def test_empty_audio_handled(self):
        """Empty audio stream should still return a final event."""
        provider = MockASRProvider(latency_ms=0)

        async def empty():
            if False:
                yield b""  # Never yields

        events = []
        async for evt in provider.stream(empty()):
            events.append(evt)

        assert events[-1].is_final is True

    @pytest.mark.asyncio
    async def test_close_does_not_raise(self):
        """close() should be idempotent and not raise."""
        provider = MockASRProvider()
        await provider.close()
        await provider.close()  # double close should be safe


# ── Factory ───────────────────────────────────────────────────────────

class TestAsrFactory:
    def test_create_mock_provider(self):
        settings = AsrSettings(provider="mock")
        provider = create_asr_provider(settings)
        assert isinstance(provider, MockASRProvider)

    def test_create_mock_provider_when_no_api_key(self):
        """Falls back to mock when no API key is set for real provider."""
        settings = AsrSettings(provider="aliyun_nls", api_key="")
        provider = create_asr_provider(settings)
        assert isinstance(provider, MockASRProvider)


# ── Config ────────────────────────────────────────────────────────────

class TestAsrSettings:
    def test_defaults(self):
        s = AsrSettings()
        assert s.provider == "mock"
        assert s.api_key == ""
        assert s.heartbeat_interval == 5
        assert s.request_timeout == 30

    def test_custom_provider(self):
        s = AsrSettings(provider="aliyun_nls", api_key="test-key", app_id="app-123")
        assert s.provider == "aliyun_nls"
        assert s.api_key == "test-key"
        assert s.app_id == "app-123"
