"""Base LLM provider interface — all provider adapters must implement this."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LlmDelta:
    """A single streaming token delta."""

    index: int
    text: str
    finish_reason: str | None = None


@dataclass(slots=True)
class LlmUsage:
    """Token usage counters."""

    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(slots=True)
class LlmResult:
    """Complete (non-streaming) LLM response."""

    text: str
    usage: LlmUsage | None = None
    model: str = ""
    latency_ms: float = 0.0
    finish_reason: str | None = None


@dataclass(slots=True)
class LlmCallContext:
    """Metadata shared across a single LLM call for logging."""

    request_id: str = ""
    session_id: str = ""
    user_id: str = ""
    provider: str = ""
    model: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class BaseLLMProvider(ABC):
    """Abstract LLM provider.

    All business code must call through this interface; never import
    provider-specific SDKs (openai / anthropic / etc.) directly.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def default_model(self) -> str: ...

    @abstractmethod
    async def stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[LlmDelta]:
        """Stream tokens from the LLM.  Yields one LlmDelta per chunk."""
        ...

    @abstractmethod
    async def complete(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> LlmResult:
        """Non-streaming completion — collects stream internally."""
        ...
