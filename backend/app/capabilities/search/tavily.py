"""Tavily search provider with Redis daily budget limiting."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx
import structlog

from app.infra.redis import get_redis
from . import BaseSearchProvider, SearchResult

logger = structlog.get_logger(__name__)


class TavilySearchProvider(BaseSearchProvider):
    """Tavily Search API provider with daily budget enforcement."""

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.tavily.com/search",
        daily_limit: int = 100,
        request_timeout: int = 15,
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base
        self._daily_limit = daily_limit
        self._request_timeout = request_timeout

    @property
    def provider_name(self) -> str:
        return "tavily"

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search Tavily API, respecting daily budget.

        Returns empty list if daily budget is exhausted.
        """
        # Check daily budget
        if not await self._check_budget():
            logger.warning(
                "search.budget.exceeded",
                provider="tavily",
                daily_limit=self._daily_limit,
            )
            return []

        t0 = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=self._request_timeout) as client:
                response = await client.post(
                    self._api_base,
                    json={
                        "api_key": self._api_key,
                        "query": query,
                        "search_depth": "basic",
                        "max_results": top_k,
                    },
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("results", [])[:top_k]:
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("content", ""),
                        score=item.get("score", 1.0),
                    )
                )

            latency_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                "search.provider.call",
                provider="tavily",
                query=query[:100],
                result_count=len(results),
                latency_ms=round(latency_ms, 2),
            )

            # Increment budget counter
            await self._increment_budget()

            return results

        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.error(
                "search.provider.error",
                provider="tavily",
                query=query[:100],
                latency_ms=round(latency_ms, 2),
                error=str(exc),
            )
            return []

    async def _check_budget(self) -> bool:
        """Check if daily search budget remains."""
        try:
            redis = get_redis()
            today = datetime.now(timezone.utc).strftime("%Y%m%d")
            key = f"search:budget:{today}"
            count = await redis.get(key)
            current = int(count) if count else 0
            return current < self._daily_limit
        except Exception:
            # If Redis is unavailable, allow the request (fail open)
            return True

    async def _increment_budget(self) -> None:
        """Increment the daily search counter."""
        try:
            redis = get_redis()
            today = datetime.now(timezone.utc).strftime("%Y%m%d")
            key = f"search:budget:{today}"
            await redis.incr(key)
            # Set TTL to 48 hours (covers today + buffer)
            await redis.expire(key, 172800)
        except Exception as exc:
            logger.debug("search.budget_counter_failed", error=str(exc))


class MockSearchProvider(BaseSearchProvider):
    """Mock search provider returning empty results for dev/testing."""

    @property
    def provider_name(self) -> str:
        return "mock"

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        return []
