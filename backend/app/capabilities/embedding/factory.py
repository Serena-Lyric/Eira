"""Factory for creating embedding provider instances from settings."""

from __future__ import annotations

from app.core.config import EmbeddingSettings
from . import BaseEmbeddingProvider
from .openai_compat import OpenAICompatEmbeddingProvider, MockEmbeddingProvider


def create_embedding_provider(
    settings: EmbeddingSettings,
) -> BaseEmbeddingProvider:
    """Instantiate the correct embedding provider based on settings."""
    if settings.provider == "mock":
        return MockEmbeddingProvider()

    if not settings.api_key:
        from structlog import get_logger
        get_logger(__name__).warning(
            "embedding.provider.fallback_to_mock",
            provider=settings.provider,
            reason="no_api_key",
        )
        return MockEmbeddingProvider()

    return OpenAICompatEmbeddingProvider(
        api_key=settings.api_key,
        api_base=settings.api_base,
        model=settings.model,
        dimensions=settings.dimensions,
        batch_size=settings.batch_size,
        max_retries=settings.max_retries,
        request_timeout=settings.request_timeout,
    )
