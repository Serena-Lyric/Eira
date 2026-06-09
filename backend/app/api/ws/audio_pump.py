"""Audio pump — pushes TTS audio frames over WebSocket with backpressure."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import structlog
from fastapi import WebSocket

logger = structlog.get_logger(__name__)

# Estimated duration per opus chunk at 24kHz (in ms)
ESTIMATED_CHUNK_DURATION_MS = 20


class AudioPump:
    """Pushes TTS audio frames through a WebSocket with backpressure control.

    Usage:
        pump = AudioPump(ws)
        async for chunk in tts_provider.stream(text):
            await pump.push(chunk)
        await pump.flush()
    """

    def __init__(
        self,
        ws: WebSocket,
        *,
        backpressure_threshold_ms: int = 3000,
        estimated_chunk_ms: int = ESTIMATED_CHUNK_DURATION_MS,
    ):
        self._ws = ws
        self._backpressure_threshold_ms = backpressure_threshold_ms
        self._estimated_chunk_ms = estimated_chunk_ms
        self._buffered_ms = 0
        self._cancelled = False

    async def push(self, chunk: bytes) -> None:
        """Push one audio chunk as a binary WebSocket frame.

        Implements backpressure: if estimated buffered audio exceeds the
        threshold, sleeps 50ms to let the frontend consume audio.
        """
        if self._cancelled:
            return

        await self._ws.send_bytes(chunk)

        # Track estimated buffer size
        self._buffered_ms += self._estimated_chunk_ms

        # Backpressure check: if frontend buffer > threshold, slow down
        if self._buffered_ms >= self._backpressure_threshold_ms:
            await asyncio.sleep(0.05)
            # Assume frontend consumed ~100ms during the sleep
            self._buffered_ms = max(0, self._buffered_ms - 100)

    async def stream_and_push(self, audio_iter: AsyncIterator[bytes]) -> None:
        """Stream audio chunks from a TTS provider and push them over WS.

        Args:
            audio_iter: Async iterator yielding audio bytes from a TTS provider.
        """
        async for chunk in audio_iter:
            if self._cancelled:
                break
            await self.push(chunk)

    async def flush(self) -> None:
        """Reset the buffered audio counter (called when audio stream ends)."""
        self._buffered_ms = 0

    def cancel(self) -> None:
        """Cancel the current audio stream (e.g., on barge-in)."""
        self._cancelled = True

    def reset(self) -> None:
        """Reset cancellation flag for a new stream."""
        self._cancelled = False
        self._buffered_ms = 0
