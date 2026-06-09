"""Factory for creating LLM provider instances from settings."""

from __future__ import annotations

from typing import Literal

from app.core.config import LlmSettings

from .base import BaseLLMProvider
from .mock import MockProvider
from .openai_compat import OpenAICompatProvider

ProviderType = Literal["deepseek", "openai", "tongyi", "volc", "mock"]


def create_llm_provider(settings: LlmSettings) -> BaseLLMProvider:
    """Instantiate the correct provider based on settings.provider.

    Returns MockProvider when provider == "mock" or when no API key is
    configured for a real provider (graceful fallback for dev).
    """
    provider: ProviderType = settings.provider  # type: ignore[assignment]

    if provider == "mock":
        return MockProvider()

    if not settings.api_key:
        # Fallback to mock in dev when no key is set
        from structlog import get_logger

        get_logger(__name__).warning(
            "llm.provider.fallback_to_mock",
            provider=provider,
            reason="no_api_key",
        )
        return MockProvider()

    # All current providers are OpenAI-compatible
    return OpenAICompatProvider(
        api_key=settings.api_key,
        api_base=settings.api_base,
        model=settings.model,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
        max_retries=settings.max_retries,
        request_timeout=settings.request_timeout,
    )
