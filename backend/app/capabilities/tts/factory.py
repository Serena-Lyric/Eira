"""Factory for creating TTS provider instances from settings."""

from __future__ import annotations

from app.core.config import TtsSettings

from .base import BaseTTSProvider
from .mock import MockTTSProvider


def create_tts_provider(settings: TtsSettings) -> BaseTTSProvider:
    """Instantiate the correct TTS provider based on settings.

    Raises ValueError when real provider is configured but credentials are
    missing (no silent fallback). Mock is only enabled when explicitly set
    (tests).
    """
    if settings.provider == "mock":
        return MockTTSProvider()

    if settings.provider == "xunfei":
        if not settings.api_key or not settings.api_secret or not settings.app_id:
            raise ValueError(
                "Xunfei TTS credentials incomplete: "
                "app_id, api_key, and api_secret are all required. "
                "Set EIRA_TTS__PROVIDER=mock for local development."
            )

        from .xunfei import XunfeiTTSProvider
        return XunfeiTTSProvider(
            app_id=settings.app_id,
            api_key=settings.api_key,
            api_secret=settings.api_secret,
            api_base=settings.api_base or None,
            voice=settings.voice,
            sample_rate=settings.sample_rate,
            request_timeout=settings.request_timeout,
        )

    # Unknown / unimplemented real provider
    raise ValueError(
        f"TTS provider '{settings.provider}' is not implemented. "
        "Available: xunfei, mock."
    )
