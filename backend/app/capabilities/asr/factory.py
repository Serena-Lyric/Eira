"""Factory for creating ASR provider instances from settings."""

from __future__ import annotations

from app.core.config import AsrSettings

from .base import BaseASRProvider
from .mock import MockASRProvider


def create_asr_provider(settings: AsrSettings) -> BaseASRProvider:
    """Instantiate the correct ASR provider based on settings.

    Returns MockASRProvider when provider == "mock" or when no API key is
    configured for a real provider (graceful fallback for dev).
    """
    if settings.provider == "mock":
        return MockASRProvider()

    if not settings.api_key:
        from structlog import get_logger

        get_logger(__name__).warning(
            "asr.provider.fallback_to_mock",
            provider=settings.provider,
            reason="no_api_key",
        )
        return MockASRProvider()

    # Real provider implementations (aliyun_nls, xunfei) to be added
    # when API keys are available. For now, fall back to mock.
    from structlog import get_logger

    get_logger(__name__).warning(
        "asr.provider.not_implemented",
        provider=settings.provider,
        reason="real_provider_not_yet_implemented",
    )
    return MockASRProvider()
