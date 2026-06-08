"""Mock TTS provider for development and testing.

Generates simple audio-like binary data (not real audio — silent opus-like frames).
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator

from .base import BaseTTSProvider


class MockTTSProvider(BaseTTSProvider):
    """Mock TTS provider that generates fake audio chunks.

    Useful for development and testing without requiring a real TTS service.
    Generates deterministic bytes based on text content.
    """

    CHUNK_SIZE = 320  # ~20ms of opus at 16kHz mono

    def __init__(self, latency_ms: int = 10):
        self._latency_ms = latency_ms

    async def stream(
        self,
        text: str,
        voice: str = "default",
        format: str = "opus",
    ) -> AsyncIterator[bytes]:
        """Generate fake audio chunks based on text length."""
        if not text:
            # Return minimal audio
            yield b"\x00" * self.CHUNK_SIZE
            return

        # Calculate chunk count proportional to text length
        # ~3 chars per 20ms of speech (rough estimate for Chinese)
        chars_per_chunk = 3
        num_chunks = max(1, len(text) // chars_per_chunk)

        for i in range(num_chunks):
            if self._latency_ms > 0:
                await asyncio.sleep(self._latency_ms / 1000)
            # Generate deterministic bytes based on text and chunk index
            seed = hashlib.md5(f"{text}:{voice}:{i}".encode()).digest()
            chunk = seed * (self.CHUNK_SIZE // len(seed) + 1)
            yield chunk[: self.CHUNK_SIZE]

    async def close(self) -> None:
        """Release mock resources (no-op)."""
        pass
