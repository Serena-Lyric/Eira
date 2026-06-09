"""Mock LLM provider — returns fixed Chinese text for testing without API keys."""

from collections.abc import AsyncIterator
from typing import Any

from .base import BaseLLMProvider, LlmDelta, LlmResult, LlmUsage

_MOCK_RESPONSE = (
    "你好！我已经收到了您的消息。根据您当前的位置和偏好，"
    "我建议您从中央广场出发，沿途可以欣赏到美丽的园林景观，"
    "大约15分钟后就能到达主展馆。需要我为您详细导航吗？"
)


class MockProvider(BaseLLMProvider):
    """Returns a fixed Chinese response, character-by-character in stream mode."""

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def default_model(self) -> str:
        return "mock-model"

    async def stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[LlmDelta]:
        chars_per_chunk = kwargs.get("chars_per_chunk", 3)
        text = kwargs.get("mock_text", _MOCK_RESPONSE)
        for i in range(0, len(text), chars_per_chunk):
            chunk = text[i : i + chars_per_chunk]
            yield LlmDelta(
                index=i // chars_per_chunk,
                text=chunk,
                finish_reason="stop" if i + chars_per_chunk >= len(text) else None,
            )

    async def close(self) -> None:
        """Mock provider has no resources to release."""
        pass

    async def complete(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> LlmResult:
        text = kwargs.get("mock_text", _MOCK_RESPONSE)
        return LlmResult(
            text=text,
            usage=LlmUsage(prompt_tokens=10, completion_tokens=len(text)),
            model="mock-model",
            latency_ms=5.0,
            finish_reason="stop",
        )
