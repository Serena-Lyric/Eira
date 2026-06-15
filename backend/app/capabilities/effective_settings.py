"""DB-aware effective settings for TTS, ASR, Embedding, Search providers.

Follows the same priority pattern as get_effective_llm_settings():
    DB system_settings override > env var > code defaults

Admin stores provider configuration as flat keys under prefixes:
    tts_provider, tts_api_key, tts_api_secret, tts_app_id, tts_voice, ...
    asr_provider, asr_api_key, ...
    embedding_provider, embedding_model, ...
    search_provider, search_api_key, ...
"""

from __future__ import annotations

import structlog
from app.core.config import (
    get_settings,
    TtsSettings,
    AsrSettings,
    EmbeddingSettings,
    SearchSettings,
)

logger = structlog.get_logger(__name__)

# Mapping: frontend/DB flat key prefix → Settings model field names
# Used to validate that DB values map to actual pydantic fields.
_PREFIX_MODEL_FIELDS: dict[str, frozenset] = {
    "tts_": frozenset(TtsSettings.model_fields.keys()),
    "asr_": frozenset(AsrSettings.model_fields.keys()),
    "embedding_": frozenset(EmbeddingSettings.model_fields.keys()),
    "search_": frozenset(SearchSettings.model_fields.keys()),
}


async def _get_db_overrides(prefix: str) -> dict:
    """Fetch all system_settings keys starting with *prefix*.

    Returns a dict with the prefix stripped from keys, suitable for
    pydantic model_copy(update=...).
    """
    try:
        from sqlalchemy import select
        from app.infra.db import get_session_factory
        from app.domain.system.models import SystemSetting

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(SystemSetting).where(SystemSetting.key.startswith(prefix))
            )
            rows = result.scalars().all()
            overrides: dict = {}
            valid_fields = _PREFIX_MODEL_FIELDS.get(prefix, frozenset())
            for r in rows:
                field = r.key.removeprefix(prefix)  # "tts_provider" → "provider"
                if field in valid_fields and r.value is not None:
                    overrides[field] = r.value
            if overrides:
                logger.debug(
                    "effective_settings.db_overrides",
                    prefix=prefix,
                    keys=list(overrides.keys()),
                )
            return overrides
    except Exception as exc:
        logger.debug("effective_settings.db_unavailable", prefix=prefix, error=str(exc))
        return {}


async def get_effective_tts_settings() -> TtsSettings:
    """Return TtsSettings with DB overrides merged over env-var defaults."""
    base = get_settings().tts
    overrides = await _get_db_overrides("tts_")
    if overrides:
        return base.model_copy(update=overrides)
    return base


async def get_effective_asr_settings() -> AsrSettings:
    """Return AsrSettings with DB overrides merged over env-var defaults."""
    base = get_settings().asr
    overrides = await _get_db_overrides("asr_")
    if overrides:
        return base.model_copy(update=overrides)
    return base


async def get_effective_embedding_settings() -> EmbeddingSettings:
    """Return EmbeddingSettings with DB overrides merged over env-var defaults."""
    base = get_settings().embedding
    overrides = await _get_db_overrides("embedding_")
    if overrides:
        return base.model_copy(update=overrides)
    return base


async def get_effective_search_settings() -> SearchSettings:
    """Return SearchSettings with DB overrides merged over env-var defaults."""
    base = get_settings().search
    overrides = await _get_db_overrides("search_")
    if overrides:
        return base.model_copy(update=overrides)
    return base
