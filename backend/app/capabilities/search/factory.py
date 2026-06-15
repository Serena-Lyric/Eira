"""Factory for creating search provider instances from settings."""

from __future__ import annotations

from app.core.config import SearchSettings
from . import BaseSearchProvider
from .tavily import TavilySearchProvider, MockSearchProvider


def create_search_provider(settings: SearchSettings) -> BaseSearchProvider:
    """Instantiate the correct search provider based on settings."""
    if settings.provider == "mock":
        return MockSearchProvider()

    if not settings.api_key:
        from structlog import get_logger
        get_logger(__name__).warning(
            "search.provider.fallback_to_mock",
            provider=settings.provider,
            reason="no_api_key",
        )
        return MockSearchProvider()

    return TavilySearchProvider(
        api_key=settings.api_key,
        api_base=settings.api_base,
        daily_limit=settings.daily_limit,
        request_timeout=settings.request_timeout,
    )
