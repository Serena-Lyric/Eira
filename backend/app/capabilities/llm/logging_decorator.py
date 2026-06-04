"""LLM call logging decorator — records structured logs for every LLM invocation."""

from __future__ import annotations

import time
from collections.abc import Callable, Awaitable
from functools import wraps
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def log_llm_call(
    provider: str = "unknown",
    model: str = "unknown",
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Decorator that logs start/end/error for LLM calls.

    Usage:
        @log_llm_call(provider="deepseek", model="deepseek-chat")
        async def stream(self, messages): ...
    """

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            logger.info(
                "llm.call.start",
                provider=provider,
                model=model,
                fn=func.__name__,
            )
            try:
                result = await func(*args, **kwargs)
                latency_ms = (time.perf_counter() - t0) * 1000
                logger.info(
                    "llm.call.end",
                    provider=provider,
                    model=model,
                    fn=func.__name__,
                    latency_ms=round(latency_ms, 2),
                )
                return result
            except Exception as exc:
                latency_ms = (time.perf_counter() - t0) * 1000
                logger.error(
                    "llm.call.error",
                    provider=provider,
                    model=model,
                    fn=func.__name__,
                    latency_ms=round(latency_ms, 2),
                    error=str(exc),
                )
                raise

        return wrapper

    return decorator
