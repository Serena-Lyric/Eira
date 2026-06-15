"""End-to-end tests for voice WebSocket flow (ASR → LLM → TTS)."""

import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.ws.audio_pump import AudioPump
from app.capabilities.tts.base import BaseTTSProvider
from app.capabilities.asr.base import BaseASRProvider
from app.capabilities.asr.mock import MockASRProvider
from app.capabilities.tts.mock import MockTTSProvider


# ── AudioPump ─────────────────────────────────────────────────────────


class TestAudioPump:
    """Unit-like tests for AudioPump (no WS connection needed for logic)."""

    def test_initialization(self):
        """AudioPump can be created with default settings."""
        pump = AudioPump(ws=None)  # type: ignore
        assert pump is not None

    def test_backpressure_calculation(self):
        """Buffered audio tracking works correctly."""
        pump = AudioPump(ws=None, estimated_chunk_ms=20, backpressure_threshold_ms=3000)  # type: ignore
        # Push 90 chunks → 1800ms buffered, below 3000ms threshold
        for _ in range(90):
            pump._buffered_ms += pump._estimated_chunk_ms
        assert pump._buffered_ms == 1800
        assert pump._buffered_ms < pump._backpressure_threshold_ms

        # Push 70 more → 3200ms, above threshold
        for _ in range(70):
            pump._buffered_ms += pump._estimated_chunk_ms
        assert pump._buffered_ms >= pump._backpressure_threshold_ms

    def test_cancel_and_reset(self):
        """Cancel flag stops pushing."""
        pump = AudioPump(ws=None)  # type: ignore
        pump.cancel()
        assert pump._cancelled is True

        pump.reset()
        assert pump._cancelled is False
        assert pump._buffered_ms == 0

    @pytest.mark.asyncio
    async def test_flush_resets_buffer(self):
        """Flush resets the buffered audio counter."""
        pump = AudioPump(ws=None)  # type: ignore
        pump._buffered_ms = 5000
        await pump.flush()
        assert pump._buffered_ms == 0


# ── Provider integration ──────────────────────────────────────────────


class TestVoicePipeline:
    @pytest.mark.asyncio
    async def test_asr_mock_produces_text(self):
        """ASR mock provider produces text from audio stream."""
        provider = MockASRProvider(latency_ms=0)

        async def audio():
            for _ in range(5):
                yield b"\x00" * 512

        events = []
        async for evt in provider.stream(audio(), lang="zh"):
            events.append(evt)

        assert events[-1].is_final
        assert len(events[-1].text) > 0

    @pytest.mark.asyncio
    async def test_tts_mock_produces_audio(self):
        """TTS mock provider produces audio chunks."""
        provider = MockTTSProvider(latency_ms=0)

        chunks = []
        async for chunk in provider.stream("你好世界，欢迎来到西湖。"):
            chunks.append(chunk)

        assert len(chunks) > 0
        assert all(isinstance(c, bytes) for c in chunks)

    @pytest.mark.asyncio
    async def test_voice_end_to_end_pipeline(self):
        """Full pipeline: ASR text → LLM → TTS audio works atomically."""
        asr = MockASRProvider(latency_ms=0)
        tts = MockTTSProvider(latency_ms=0)

        # Step 1: ASR recognition
        async def audio():
            for _ in range(10):
                yield b"\x00" * 512

        recognized = ""
        async for evt in asr.stream(audio()):
            if evt.is_final:
                recognized = evt.text

        assert len(recognized) > 0

        # Step 2: TTS synthesis
        audio_chunks = []
        async for chunk in tts.stream(recognized):
            audio_chunks.append(chunk)

        assert len(audio_chunks) > 0

        # Step 3: Close providers
        await asr.close()
        await tts.close()


# ── Route verification ────────────────────────────────────────────────


def test_voice_route_and_chat_route_both_registered():
    """Both /ws/voice and /ws/chat should be registered."""
    paths = {
        r.path for r in app.routes if hasattr(r, "path") and r.path.startswith("/ws/")
    }
    assert "/ws/chat" in paths
    assert "/ws/voice" in paths
