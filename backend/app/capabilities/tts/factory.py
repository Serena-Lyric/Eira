"""Factory for creating TTS provider instances from settings."""

from __future__ import annotations

from app.core.config import TtsSettings

from .base import BaseTTSProvider
from .mock import MockTTSProvider


def create_tts_provider(settings: TtsSettings) -> BaseTTSProvider:
    """Instantiate the correct TTS provider based on settings.

    Returns MockTTSProvider when provider == "mock" or when no API key is
    configured for a real provider (graceful fallback for dev).
    """
    if settings.provider == "mock":
        return MockTTSProvider()

    if not settings.api_key:
        from structlog import get_logger

        get_logger(__name__).warning(
            "tts.provider.fallback_to_mock",
            provider=settings.provider,
            reason="no_api_key",
        )
        return MockTTSProvider()

    # Real provider implementations (aliyun_nls, azure) to be added
    # when API keys are available. For now, fall back to mock.
    from structlog import get_logger

    get_logger(__name__).warning(
        "tts.provider.not_implemented",
        provider=settings.provider,
        reason="real_provider_not_yet_implemented",
    )
    return MockTTSProvider()
