"""Factory for creating ASR provider instances from settings."""

from __future__ import annotations

from app.core.config import AsrSettings

from .base import BaseASRProvider
from .mock import MockASRProvider


def create_asr_provider(settings: AsrSettings) -> BaseASRProvider:
    """Instantiate the correct ASR provider based on settings.

    Raises ValueError when real provider is configured but credentials are
    missing (no silent fallback). Mock is only enabled when explicitly set
    (tests).
    """
    if settings.provider == "mock":
        return MockASRProvider()

    if settings.provider == "xunfei":
        if not settings.api_key or not settings.api_secret or not settings.app_id:
            raise ValueError(
                "Xunfei ASR credentials incomplete: "
                "app_id, api_key, and api_secret are all required. "
                "Set EIRA_ASR__PROVIDER=mock for local development."
            )

        from .xunfei import XunfeiASRProvider
        return XunfeiASRProvider(
            app_id=settings.app_id,
            api_key=settings.api_key,
            api_secret=settings.api_secret,
            api_base=settings.api_base or None,
            request_timeout=settings.request_timeout,
        )

    # Unknown / unimplemented real provider
    raise ValueError(
        f"ASR provider '{settings.provider}' is not implemented. "
        "Available: xunfei, mock."
    )
