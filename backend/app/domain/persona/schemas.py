"""Pydantic schemas for persona / character card CRUD."""

from pydantic import BaseModel, Field


# ── Input schemas ────────────────────────────────────────────────────────

class PersonaCreateIn(BaseModel):
    """Fields accepted when creating a new persona."""
    name: str = Field(min_length=1, max_length=128)
    scope: str = Field(default="public", pattern="^(public|user)$")
    description: str = ""
    personality: str = ""
    scenario: str = ""
    first_mes: str = ""
    mes_example: str = ""
    system_prompt: str = Field(min_length=10, description="角色系统提示词（至少 10 个字符）")
    avatar_asset_id: int | None = None
    live2d_asset_id: int | None = None
    voice_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_default: bool = False


class PersonaPatchIn(BaseModel):
    """Fields accepted when partially updating a persona. Only provided fields are changed."""
    name: str | None = Field(None, min_length=1, max_length=128)
    scope: str | None = Field(None, pattern="^(public|user)$")
    description: str | None = None
    personality: str | None = None
    scenario: str | None = None
    first_mes: str | None = None
    mes_example: str | None = None
    system_prompt: str | None = None
    avatar_asset_id: int | None = None
    live2d_asset_id: int | None = None
    voice_id: str | None = None
    tags: list[str] | None = None
    is_default: bool | None = None
    disabled: bool | None = None


# ── Output schemas ───────────────────────────────────────────────────────

class PersonaOut(BaseModel):
    id: int
    scope: str
    user_id: int | None = None
    name: str
    description: str | None = None
    personality: str | None = None
    scenario: str | None = None
    first_mes: str | None = None
    mes_example: str | None = None
    system_prompt: str | None = None
    avatar_asset_id: int | None = None
    live2d_asset_id: int | None = None
    voice_id: str | None = None
    tags: list[str] | None = None
    is_default: bool = False
    disabled: bool = False
    created_at: str | None = None
    updated_at: str | None = None

    model_config = {"from_attributes": True}


class PersonaListOut(BaseModel):
    items: list[PersonaOut]
    total: int
    page: int = 1
    page_size: int = 20
