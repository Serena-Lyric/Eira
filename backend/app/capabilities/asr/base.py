"""Base ASR provider interface — all ASR adapters must implement this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True)
class AsrEvent:
    """A single ASR result event (partial or final)."""

    kind: Literal["partial", "final"]
    text: str
    is_final: bool


class BaseASRProvider(ABC):
    """Abstract ASR provider.

    All business code must call through this interface; never import
    provider-specific SDKs directly.
    """

    @abstractmethod
    async def stream(
        self, audio: AsyncIterator[bytes], lang: str = "zh"
    ) -> AsyncIterator[AsrEvent]:
        """Stream ASR results from audio chunks.

        Yields AsrEvent objects as recognition progresses.
        Partial events have is_final=False; the last event has is_final=True.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release any resources held by the provider."""
        ...
