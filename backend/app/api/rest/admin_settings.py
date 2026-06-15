"""Admin system settings endpoints — read and update key-value configuration.

Sensitive values (api_key, token, secret, password) are redacted from responses.

FIXME: §4.5 — API keys are stored as plaintext in the system_settings JSONB column.
Before production launch this must be upgraded to pgcrypto field-level encryption
with application-layer KMS wrapping. See docs/tech-debt/api-key-encryption.md.
"""

from collections.abc import Iterable
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db_session, require_admin, check_write_rate_limit
from app.domain.identity.models import User
from app.domain.system.service import SystemSettingService

logger = structlog.get_logger(__name__)


def get_settings_service(db: AsyncSession = Depends(get_db_session)) -> SystemSettingService:
    return SystemSettingService(db)


router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])

# Keys whose values contain sensitive data and should be redacted
REDACT_KEYS = {"api_key", "token", "secret", "password", "access_key"}


def _redact_sensitive(value: Any) -> Any:
    """Recursively redact sensitive keys in a dict value."""
    if not isinstance(value, dict):
        return value
    redacted = {}
    for k, v in value.items():
        if k in REDACT_KEYS:
            redacted[k] = "***"
        elif isinstance(v, dict):
            redacted[k] = _redact_sensitive(v)
        else:
            redacted[k] = v
    return redacted


async def _invalidate_provider_caches_if_needed(keys: Iterable[str]) -> None:
    """Invalidate provider caches when relevant DB settings change.

    LLM keys: trigger full ProviderRegistry invalidation.
    TTS/ASR/Embedding/Search keys: providers are created per-connection from
    DB on each WS connect / REST call, so no persistent cache to invalidate.
    Logging for audit trail.
    """
    # LLM cache — active connection pool affected
    if any(k == "llm" or k.startswith("llm.") or k.startswith("llm_") for k in keys):
        from app.capabilities.llm.provider_registry import get_provider_registry

        logger.info("admin_settings.llm_changed", keys=list(keys))
        await get_provider_registry().invalidate()

    # Log changes for other providers (picked up on next connection)
    for prefix in ("tts_", "asr_", "embedding_", "search_"):
        if any(k.startswith(prefix) for k in keys):
            logger.info("admin_settings.provider_changed", prefix=prefix, keys=list(keys))


# ── Schemas ──────────────────────────────────────────────────────────────

class SettingsOut(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)


class SettingsPatchIn(BaseModel):
    settings: dict[str, Any] = Field(description="Key-value pairs to upsert")


# ── Endpoints ────────────────────────────────────────────────────────────


# Valid provider values — used to reject unsupported settings (§5 fix)
_VALID_PROVIDER_VALUES: dict[str, set] = {
    "llm_provider": {"deepseek", "openai", "tongyi", "volc", "mock"},
    "tts_provider": {"xunfei", "mock"},
    "asr_provider": {"xunfei", "aliyun_nls", "mock"},
    "search_provider": {"tavily", "mock"},
    "embedding_provider": {"openai", "mock"},
}

# Provider keys to check for api_key_status (§6 fix)
_PROVIDER_API_KEY_KEYS = [
    "llm_api_key",
    "tts_api_key",
    "asr_api_key",
    "embedding_api_key",
    "search_api_key",
]


@router.get("", response_model=SettingsOut, summary="获取所有系统设置")
async def get_settings(
    _admin: User = Depends(require_admin),
    svc: SystemSettingService = Depends(get_settings_service),
) -> SettingsOut:
    """返回所有系统设置。API key 等敏感值已脱敏。"""
    all_settings = await svc.get_all()
    redacted = {k: _redact_sensitive(v) for k, v in all_settings.items()}

    # Generate api_key_status from stored keys (§6 fix)
    api_key_status: dict[str, str] = {}
    for provider_key in _PROVIDER_API_KEY_KEYS:
        name = provider_key.replace("_api_key", "")  # "llm_api_key" → "llm"
        val = all_settings.get(provider_key)
        if val and isinstance(val, str) and val.strip():
            api_key_status[name] = "configured"
        else:
            api_key_status[name] = "missing"
    redacted["api_key_status"] = api_key_status

    return SettingsOut(settings=redacted)


@router.patch("", response_model=SettingsOut, summary="批量更新系统设置")
async def patch_settings(
    body: SettingsPatchIn,
    _admin: User = Depends(require_admin),
    svc: SystemSettingService = Depends(get_settings_service),
    _rate: None = Depends(check_write_rate_limit),
) -> SettingsOut:
    """批量更新系统设置。未传的 key 不受影响。"""
    # Validate provider values (§5 fix)
    for key, value in body.settings.items():
        if key in _VALID_PROVIDER_VALUES and value not in _VALID_PROVIDER_VALUES[key]:
            raise HTTPException(
                400,
                detail=f"不支持的 {key} 值: '{value}'。"
                       f"支持: {', '.join(sorted(_VALID_PROVIDER_VALUES[key]))}",
            )
    await svc.set_many(body.settings)
    await _invalidate_provider_caches_if_needed(body.settings.keys())
    all_settings = await svc.get_all()
    redacted = {k: _redact_sensitive(v) for k, v in all_settings.items()}
    return SettingsOut(settings=redacted)


@router.get("/{key:path}", response_model=dict, summary="获取单个设置")
async def get_setting(
    key: str,
    _admin: User = Depends(require_admin),
    svc: SystemSettingService = Depends(get_settings_service),
) -> dict:
    """获取单个设置项的值（含脱敏）。"""
    val = await svc.get(key)
    if val is None:
        return {}
    return _redact_sensitive(val)


@router.patch("/{key:path}", response_model=dict, summary="更新单个设置")
async def patch_setting(
    key: str,
    body: dict,
    _admin: User = Depends(require_admin),
    svc: SystemSettingService = Depends(get_settings_service),
    _rate: None = Depends(check_write_rate_limit),
) -> dict:
    """更新单个设置项的值。"""
    row = await svc.set(key, body)
    await _invalidate_provider_caches_if_needed([key])
    return _redact_sensitive(row.value)
