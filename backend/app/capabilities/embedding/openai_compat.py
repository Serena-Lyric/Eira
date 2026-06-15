"""OpenAI-compatible embedding provider."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog
import tiktoken
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from . import BaseEmbeddingProvider

logger = structlog.get_logger(__name__)

RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}
MAX_TOKENS = 8192  # text-embedding-3-small max input tokens
ENCODING = "cl100k_base"


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if 400 <= status < 500 and status not in RETRYABLE_HTTP_STATUSES:
            return False
        if status in RETRYABLE_HTTP_STATUSES:
            return True
    if isinstance(exc, (ConnectionError, TimeoutError, OSError, httpx.TransportError)):
        return True
    return False


def _truncate_text(text: str, max_tokens: int = MAX_TOKENS) -> str:
    """Truncate text to fit within token limit."""
    enc = tiktoken.get_encoding(ENCODING)
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return enc.decode(tokens[:max_tokens])


class OpenAICompatEmbeddingProvider(BaseEmbeddingProvider):
    """Embedding provider for OpenAI-compatible APIs (text-embedding-3-small, etc.).

    Uses raw httpx instead of the openai SDK client to avoid version
    compatibility issues with third-party API proxies (e.g. 4sapi.com).
    """

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.openai.com",
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        batch_size: int = 64,
        max_retries: int = 3,
        request_timeout: int = 30,
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._model = model
        self._dimensions = dimensions
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._request_timeout = request_timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def provider_name(self) -> str:
        return "openai_compat"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._api_base,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self._request_timeout),
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts, batching automatically."""
        if not texts:
            return []

        # Truncate texts
        truncated = [_truncate_text(t) for t in texts]

        all_embeddings: list[list[float]] = []

        for i in range(0, len(truncated), self._batch_size):
            batch = truncated[i : i + self._batch_size]
            batch_result = await self._embed_batch(batch)
            all_embeddings.extend(batch_result)

        return all_embeddings

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
        reraise=True,
    )
    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Call the embedding API for a single batch using raw httpx."""
        client = self._get_client()
        t0 = time.perf_counter()

        payload: dict[str, Any] = {
            "model": self._model,
            "input": texts,
        }
        # Only send dimensions if the API supports it (OpenAI-specific)
        if self._dimensions:
            payload["dimensions"] = self._dimensions

        response = await client.post("/v1/embeddings", json=payload)

        if response.status_code != 200:
            # Let tenacity handle retryable statuses
            response.raise_for_status()

        data = response.json()
        latency_ms = (time.perf_counter() - t0) * 1000

        embeddings = [d["embedding"] for d in data["data"]]

        logger.info(
            "embedding.provider.batch",
            provider=self.provider_name,
            model=self._model,
            batch_size=len(texts),
            latency_ms=round(latency_ms, 2),
        )

        return embeddings


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Mock embedding provider returning zero vectors for dev/testing."""

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def dimensions(self) -> int:
        return 1536

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dimensions for _ in texts]
