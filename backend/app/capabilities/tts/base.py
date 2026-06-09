"""Base TTS provider interface — all TTS adapters must implement this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class BaseTTSProvider(ABC):
    """Abstract TTS (Text-to-Speech) provider.

    All business code must call through this interface; never import
    provider-specific SDKs directly.
    """

    @abstractmethod
    async def stream(
        self,
        text: str,
        voice: str = "default",
        format: str = "opus",
    ) -> AsyncIterator[bytes]:
        """Stream synthesized speech as audio chunks.

        Yields audio bytes as they become available from the TTS engine.
        Chunks can be directly sent over WebSocket to the client.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release any resources held by the provider."""
        ...
