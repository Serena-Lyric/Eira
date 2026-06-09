"""OpenAI-compatible provider (DeepSeek / OpenAI / Tongyi / Volc)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import structlog
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .base import BaseLLMProvider, LlmDelta, LlmResult, LlmUsage, LlmCallContext

logger = structlog.get_logger(__name__)

RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}


def _is_retryable(exc: Exception) -> bool:
    """Decide whether an exception should trigger a retry."""
    # openai errors carry status_code on the response
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is not None:
        if 400 <= status < 500 and status not in RETRYABLE_HTTP_STATUSES:
            return False  # 4xx (except 429) are not retryable
        if status in RETRYABLE_HTTP_STATUSES:
            return True
    # Network-level errors (ConnectionError, etc.) → retry
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    return False


class OpenAICompatProvider(BaseLLMProvider):
    """Provider for any OpenAI-compatible API (DeepSeek, OpenAI, etc.)."""

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        max_tokens: int = 2048,
        temperature: float = 0.7,
        max_retries: int = 3,
        request_timeout: int = 60,
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._max_retries = max_retries
        self._request_timeout = request_timeout
        self._client: AsyncOpenAI | None = None

    @property
    def provider_name(self) -> str:
        return "openai_compat"

    @property
    def default_model(self) -> str:
        return self._model

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._api_base,
                timeout=self._request_timeout,
                max_retries=0,  # we handle retries ourselves via tenacity
            )
        return self._client

    async def stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[LlmDelta]:
        client = self._get_client()
        model = kwargs.get("model", self._model)
        max_tokens = kwargs.get("max_tokens", self._max_tokens)
        temperature = kwargs.get("temperature", self._temperature)

        @retry(
            retry=retry_if_exception(_is_retryable),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
            reraise=True,
        )
        async def _stream_with_retry():
            idx = 0
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        idx += 1
                        yield LlmDelta(
                            index=idx,
                            text=delta.content,
                            finish_reason=chunk.choices[0].finish_reason,
                        )
                # Usage chunk (some providers emit a final chunk with usage only)
                elif hasattr(chunk, "usage") and chunk.usage:
                    pass  # usage-only chunk, no text

        async for delta in _stream_with_retry():
            yield delta

    async def close(self) -> None:
        """Release the underlying AsyncOpenAI client and its connection pool."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def complete(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> LlmResult:
        t0 = time.perf_counter()
        parts: list[str] = []
        finish_reason: str | None = None
        usage = LlmUsage()

        async for delta in self.stream(messages, **kwargs):
            parts.append(delta.text)
            if delta.finish_reason:
                finish_reason = delta.finish_reason

        latency_ms = (time.perf_counter() - t0) * 1000
        return LlmResult(
            text="".join(parts),
            usage=usage,
            model=kwargs.get("model", self._model),
            latency_ms=latency_ms,
            finish_reason=finish_reason,
        )
