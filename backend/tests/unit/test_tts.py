"""Unit tests for TTS provider abstraction."""

import pytest

from app.capabilities.tts.base import BaseTTSProvider
from app.capabilities.tts.mock import MockTTSProvider
from app.capabilities.tts.factory import create_tts_provider
from app.core.config import TtsSettings


# ── Mock provider ─────────────────────────────────────────────────────

class TestMockTTSProvider:
    @pytest.mark.asyncio
    async def test_stream_returns_bytes(self):
        """Mock provider returns binary audio-like data."""
        provider = MockTTSProvider()
        chunks = []
        async for chunk in provider.stream("你好世界"):
            chunks.append(chunk)

        assert len(chunks) > 0
        for chunk in chunks:
            assert isinstance(chunk, bytes)
            assert len(chunk) > 0

    @pytest.mark.asyncio
    async def test_stream_chunk_count_depends_on_text(self):
        """Longer text should produce more chunks."""
        provider = MockTTSProvider()

        short_chunks = []
        async for c in provider.stream("你好"):
            short_chunks.append(c)

        long_chunks = []
        async for c in provider.stream("这是一段比较长的文本，用来测试TTS合成。" * 10):
            long_chunks.append(c)

        assert len(long_chunks) > len(short_chunks)

    @pytest.mark.asyncio
    async def test_stream_empty_text(self):
        """Empty text should still produce minimal output."""
        provider = MockTTSProvider()
        chunks = []
        async for chunk in provider.stream(""):
            chunks.append(chunk)

        # Should produce at least 1 chunk (minimal audio)
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_different_voices_work(self):
        """All voice options should work."""
        provider = MockTTSProvider()
        for voice in ("default", "zh_female", "zh_male"):
            chunks = []
            async for chunk in provider.stream("测试", voice=voice):
                chunks.append(chunk)
            assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_close_does_not_raise(self):
        """close() should be idempotent and safe."""
        provider = MockTTSProvider()
        await provider.close()
        await provider.close()  # Double close safe


# ── Factory ───────────────────────────────────────────────────────────

class TestTtsFactory:
    def test_create_mock_provider(self):
        settings = TtsSettings(provider="mock")
        provider = create_tts_provider(settings)
        assert isinstance(provider, MockTTSProvider)

    def test_fallback_to_mock_when_no_key(self):
        settings = TtsSettings(provider="azure", api_key="")
        provider = create_tts_provider(settings)
        assert isinstance(provider, MockTTSProvider)


# ── Config ────────────────────────────────────────────────────────────

class TestTtsSettings:
    def test_defaults(self):
        s = TtsSettings()
        assert s.provider == "mock"
        assert s.voice == "default"
        assert s.sample_rate == 24000
        assert s.format == "opus"

    def test_custom_settings(self):
        s = TtsSettings(
            provider="azure",
            api_key="test-key",
            voice="zh-CN-XiaoxiaoNeural",
            sample_rate=16000,
        )
        assert s.provider == "azure"
        assert s.voice == "zh-CN-XiaoxiaoNeural"
        assert s.sample_rate == 16000
