"""Persona / Live2D configuration endpoints for the admin panel.

Models the left-sidebar settings: model selection, idle motions, speech rate.
These are persona-level (or global app-level) configs that drive how the
Live2D character behaves. Persisted in system_settings table under key
``persona_config`` as a JSONB blob.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db_session, require_admin, check_write_rate_limit
from app.domain.identity.models import User
from app.domain.system.service import SystemSettingService

router = APIRouter(prefix="/admin/persona-config", tags=["persona-config"])

PERSONA_CONFIG_KEY = "persona_config"


# ── Schemas ──────────────────────────────────────────────────────────

class MotionOption(BaseModel):
    """A motion parsed from the Live2D model."""
    group: str = ""       # 动作组名 (e.g. "Idle", "TapBody")
    index: int = 0        # 组内索引
    label: str = ""       # 展示标签 (e.g. "Idle_0", "挥手示意")


class PersonaConfig(BaseModel):
    """Persona-level Live2D & speech configuration."""
    # Live2D 模型选择
    active_model_id: str | None = None
    # 可用模型列表（前端同步用，后端不持久化此字段的全部内容，仅做透传参考）
    available_models: list[str] = Field(default_factory=list)

    # 待机动作选择 — 从模型内解析出的动作组/索引
    idle_motion_group: str | None = None
    idle_motion_index: int | None = None
    # 可用待机动作列表
    available_idle_motions: list[MotionOption] = Field(default_factory=list)

    # 待机动作（失去网络时）
    offline_idle_motion_group: str | None = None
    offline_idle_motion_index: int | None = None
    # 可用离线待机动作列表
    available_offline_motions: list[MotionOption] = Field(default_factory=list)

    # 默认语速
    default_speech_rate: float = 1.0  # 0.5 ~ 2.0

    # 全局默认背景 OSS key（admin 设置，web-user 无自定义背景时使用）
    default_background_oss_key: str | None = None
    # 动态生成的背景 URL（前端可直接使用，不持久化）
    default_background_url: str | None = None


class PersonaConfigUpdateIn(BaseModel):
    """部分更新 persona 配置。"""
    active_model_id: str | None = None
    idle_motion_group: str | None = None
    idle_motion_index: int | None = None
    offline_idle_motion_group: str | None = None
    offline_idle_motion_index: int | None = None
    default_speech_rate: float | None = None
    default_background_oss_key: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/", response_model=PersonaConfig, summary="获取 Persona 配置")
async def get_persona_config(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> PersonaConfig:
    """返回当前 persona 的 Live2D 和语音配置。

    从 system_settings 表读取 key ``persona_config``，无记录时返回默认值。
    动态生成 default_background_url（从 OSS key 生成 presigned URL）。
    """
    svc = SystemSettingService(db)
    stored = await svc.get(PERSONA_CONFIG_KEY)
    cfg = PersonaConfig(**(stored if isinstance(stored, dict) else {}))

    # 动态生成默认背景 presigned URL
    oss_key = cfg.default_background_oss_key
    if oss_key:
        try:
            from app.infra.oss import presign_get
            cfg.default_background_url = presign_get("eira-backgrounds", oss_key, expires=86400)
        except Exception:
            pass

    return cfg


@router.patch("/", summary="部分更新 Persona 配置")
async def update_persona_config(
    updates: PersonaConfigUpdateIn,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
    _rate: None = Depends(check_write_rate_limit),
) -> dict:
    """部分更新 persona 配置，仅传需要修改的字段。

    合并现有配置 → 应用更新 → 写回 system_settings 表。
    """
    svc = SystemSettingService(db)
    stored = await svc.get(PERSONA_CONFIG_KEY)
    current = stored if isinstance(stored, dict) else {}
    # Merge: only override fields that are explicitly provided (not None)
    update_dict = updates.model_dump(exclude_unset=True)
    current.update(update_dict)
    await svc.set(PERSONA_CONFIG_KEY, current, description="Persona Live2D & speech config")
    return {"success": True, "message": "Persona 配置已更新"}
