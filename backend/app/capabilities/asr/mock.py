"""Mock ASR provider for development and testing.

Returns simulated recognition text based on chunk count (not actual audio analysis).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from .base import BaseASRProvider, AsrEvent


_MOCK_TEXTS: dict[str, str] = {
    "zh": "你好，今天天气不错，适合外出游玩。请问有什么可以帮您的？",
    "en": "Hello! The weather is nice today, perfect for going out. How can I help you?",
    "ja": "こんにちは、今日はいい天気ですね。お手伝いできることはありますか？",
}


class MockASRProvider(BaseASRProvider):
    """Mock ASR provider that returns simulated recognition text.

    Useful for development and testing without requiring a real ASR service.
    """

    def __init__(self, latency_ms: int = 50):
        self._latency_ms = latency_ms
        self._closed = False

    async def stream(
        self, audio: AsyncIterator[bytes], lang: str = "zh"
    ) -> AsyncIterator[AsrEvent]:
        """Simulate streaming ASR: emit partial events then a final event."""
        text = _MOCK_TEXTS.get(lang, _MOCK_TEXTS["zh"])
        chars = list(text)

        # Emit partial events as characters accumulate
        partial = ""
        for i, char in enumerate(chars):
            partial += char
            if self._latency_ms > 0:
                await asyncio.sleep(self._latency_ms / 1000)
            # Emit partial every 4 chars or at end
            if len(partial) >= 4 or i == len(chars) - 1:
                yield AsrEvent(kind="partial", text=partial, is_final=False)

        # Count audio chunks to simulate varying recognition quality
        _chunk_count = 0
        async for _ in audio:
            _chunk_count += 1

        # Final event with full text
        yield AsrEvent(kind="final", text=text, is_final=True)

    async def close(self) -> None:
        """Release mock resources (no-op)."""
        self._closed = True
