"""TTL-aware provider cache with cleanup and invalidation.

Replaces the module-level _provider_cache dict in ws/chat.py (§6.1 fix).
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass

import structlog

from app.core.config import LlmSettings
from .base import BaseLLMProvider
from .factory import create_llm_provider

logger = structlog.get_logger(__name__)

# ── Cache entry ────────────────────────────────────────────────────────────


@dataclass(slots=True)
class _CacheEntry:
    provider: BaseLLMProvider
    created_at: float  # monotonic seconds
    settings_hash: str


# ── Registry ───────────────────────────────────────────────────────────────


class ProviderRegistry:
    """TTL-aware cache for BaseLLMProvider instances.

    - Cache key：SHA-256 of all LlmSettings fields (api_key changes trigger rebuild)
    - TTL: configurable in seconds (default 300)
    - Expired entries are closed and replaced on next access
    - invalidate() closes all cached providers immediately

    Thread/async safety: all public methods are guarded by an asyncio.Lock.
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = ttl_seconds
        self._cache: dict[str, _CacheEntry] = {}
        self._lock = asyncio.Lock()

    # ── Public API ──────────────────────────────────────────────────────

    async def get(self, settings: LlmSettings) -> BaseLLMProvider:
        """Return a cached or newly created provider for *settings*.

        If the cached entry has expired or the settings hash differs, the old
        provider is closed and a fresh one is created.
        """
        key = _build_cache_key(settings)
        now = time.monotonic()

        async with self._lock:
            entry = self._cache.get(key)

            # Fast path: valid cache hit
            if entry is not None and (now - entry.created_at) < self._ttl:
                return entry.provider

            # Slow path: miss, expired, or settings changed → rebuild
            if entry is not None:
                logger.info(
                    "provider_cache.evict",
                    key=key[:16],
                    age_seconds=round(now - entry.created_at, 1),
                    reason="expired" if (now - entry.created_at) >= self._ttl else "settings_changed",
                )
                await _safe_close(entry.provider, key)

            provider = create_llm_provider(settings)
            self._cache[key] = _CacheEntry(
                provider=provider,
                created_at=now,
                settings_hash=key,
            )
            logger.info("provider_cache.create", key=key[:16])
            return provider

    async def invalidate(self) -> None:
        """Close all cached providers and clear the cache.

        Called when admin changes LLM settings via PATCH /admin/settings.
        """
        async with self._lock:
            if not self._cache:
                return
            logger.info("provider_cache.invalidate", count=len(self._cache))
            for key, entry in list(self._cache.items()):
                await _safe_close(entry.provider, key)
            self._cache.clear()

    @property
    def size(self) -> int:
        """Number of entries currently in cache (non-blocking, best-effort)."""
        return len(self._cache)


# ── Helpers ────────────────────────────────────────────────────────────────


def _build_cache_key(settings: LlmSettings) -> str:
    """Build a stable cache key from all relevant LlmSettings fields.

    Includes api_key so that key rotation triggers a new provider instance.
    """
    raw = (
        f"{settings.provider}|"
        f"{settings.api_key}|"
        f"{settings.api_base}|"
        f"{settings.model}|"
        f"{settings.max_tokens}|"
        f"{settings.temperature}|"
        f"{settings.max_retries}|"
        f"{settings.request_timeout}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


async def _safe_close(provider: BaseLLMProvider, key: str) -> None:
    """Close a provider, logging but not raising on errors."""
    try:
        await provider.close()
    except Exception as exc:
        logger.warning("provider_cache.close_error", key=key[:16], error=str(exc))


# ── Module-level singleton ─────────────────────────────────────────────────

_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    """Return the module-level ProviderRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


# ── Effective settings (env vars + DB override) ────────────────────────────


async def get_effective_llm_settings() -> LlmSettings:
    """Return LlmSettings with DB overrides merged over env-var defaults.

    Priority: DB system_settings (nested key "llm" or flat keys) > env vars > code defaults.

    Supports both storage formats:
    - Nested: key="llm" → {"provider":"deepseek","model":"deepseek-chat",...}
    - Flat (admin panel): key="llm_provider", "llm_model", etc.
    """
    from app.core.config import get_settings

    base = get_settings().llm

    try:
        from sqlalchemy import select
        from app.infra.db import get_session_factory
        from app.domain.system.models import SystemSetting

        factory = get_session_factory()
        async with factory() as session:
            # Try nested "llm" key first
            result = await session.execute(
                select(SystemSetting).where(SystemSetting.key == "llm")
            )
            row = result.scalar_one_or_none()
            if row is not None and isinstance(row.value, dict):
                db_values: dict = row.value
                merged = base.model_copy(update={
                    k: v for k, v in db_values.items()
                    if k in type(base).model_fields and v is not None
                })
                logger.debug("llm_settings.merged_from_nested_key", keys=list(db_values.keys()))
                return merged

            # Fallback: collect flat keys from admin panel
            flat_keys = ["llm_provider", "llm_model", "llm_api_key", "llm_api_base",
                         "llm_max_tokens", "llm_temperature"]
            result = await session.execute(
                select(SystemSetting).where(SystemSetting.key.in_(flat_keys))
            )
            flat_rows = result.scalars().all()
            flat_values: dict[str, object] = {}
            for r in flat_rows:
                # Map flat key → LlmSettings field name
                field = r.key.removeprefix("llm_")  # e.g. "llm_provider" → "provider"
                flat_values[field] = r.value

            if flat_values:
                merged = base.model_copy(update={
                    k: v for k, v in flat_values.items()
                    if k in type(base).model_fields and v is not None
                })
                logger.debug("llm_settings.merged_from_flat_keys", keys=list(flat_values.keys()))
                return merged

            return base
    except Exception as exc:
        logger.debug("llm_settings.db_unavailable", error=str(exc))
        return base
