"""Persona domain service — CRUD, import/export, and permission checks."""

import json
from fastapi import HTTPException, status
from .models import Persona
from .repository import PersonaRepository
from .schemas import PersonaCreateIn, PersonaPatchIn, PersonaOut, PersonaListOut


def _to_out(p: Persona) -> PersonaOut:
    return PersonaOut(
        id=p.id,
        scope=p.scope,
        user_id=p.user_id,
        name=p.name,
        description=p.description,
        personality=p.personality,
        scenario=p.scenario,
        first_mes=p.first_mes,
        mes_example=p.mes_example,
        system_prompt=p.system_prompt,
        avatar_asset_id=p.avatar_asset_id,
        live2d_asset_id=p.live2d_asset_id,
        voice_id=p.voice_id,
        tags=p.tags or [],
        is_default=p.is_default if p.is_default is not None else False,
        disabled=p.disabled if p.disabled is not None else False,
        created_at=p.created_at.isoformat() if p.created_at else None,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
    )


class PersonaService:
    def __init__(self, repo: PersonaRepository):
        self.repo = repo

    # ── CRUD ─────────────────────────────────────────────────────────────

    async def list_personas_admin(
        self, scope: str | None = None, page: int = 1, page_size: int = 20,
    ) -> PersonaListOut:
        items, total = await self.repo.list_personas(
            scope=scope, include_disabled=True, page=page, page_size=page_size,
        )
        return PersonaListOut(
            items=[_to_out(p) for p in items], total=total, page=page, page_size=page_size,
        )

    async def list_personas_user(
        self, user_id: int, scope: str | None = None, page: int = 1, page_size: int = 20,
    ) -> PersonaListOut:
        items, total = await self.repo.list_personas(
            scope=scope, user_id=user_id, include_disabled=False, page=page, page_size=page_size,
        )
        return PersonaListOut(
            items=[_to_out(p) for p in items], total=total, page=page, page_size=page_size,
        )

    async def get_persona(self, persona_id: int) -> Persona:
        p = await self.repo.get_by_id(persona_id)
        if not p:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "persona_not_found")
        return p

    async def create_persona(self, data: PersonaCreateIn, user_id: int) -> PersonaOut:
        if data.is_default:
            await self.repo.clear_default_for_scope(data.scope, user_id)

        p = Persona(
            scope=data.scope,
            user_id=user_id,
            name=data.name,
            description=data.description,
            personality=data.personality,
            scenario=data.scenario,
            first_mes=data.first_mes,
            mes_example=data.mes_example,
            system_prompt=data.system_prompt,
            avatar_asset_id=data.avatar_asset_id,
            live2d_asset_id=data.live2d_asset_id,
            voice_id=data.voice_id,
            tags=data.tags,
            is_default=data.is_default,
        )
        p = await self.repo.create(p)
        return _to_out(p)

    async def create_persona_admin(self, data: PersonaCreateIn) -> PersonaOut:
        """Admin creating a persona — user_id from data may be set for user-scoped."""
        if data.is_default:
            await self.repo.clear_default_for_scope(data.scope, data.user_id if data.scope == "user" else None)

        p = Persona(
            scope=data.scope,
            user_id=data.user_id if data.scope == "user" else None,
            name=data.name,
            description=data.description,
            personality=data.personality,
            scenario=data.scenario,
            first_mes=data.first_mes,
            mes_example=data.mes_example,
            system_prompt=data.system_prompt,
            avatar_asset_id=data.avatar_asset_id,
            live2d_asset_id=data.live2d_asset_id,
            voice_id=data.voice_id,
            tags=data.tags,
            is_default=data.is_default,
        )
        p = await self.repo.create(p)
        return _to_out(p)

    async def patch_persona(self, persona_id: int, data: PersonaPatchIn, user_id: int | None = None) -> PersonaOut:
        p = await self.get_persona(persona_id)

        # Permission: user can only edit their own user-scoped personas
        if user_id is not None and p.scope == "user" and p.user_id != user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "not_your_persona")

        # Handle is_default
        if data.is_default is True and not p.is_default:
            await self.repo.clear_default_for_scope(p.scope, p.user_id)

        # Apply partial updates
        for field_name in ("name", "scope", "description", "personality", "scenario",
                           "first_mes", "mes_example", "system_prompt", "voice_id"):
            val = getattr(data, field_name, None)
            if val is not None:
                setattr(p, field_name, val)

        for field_name in ("avatar_asset_id", "live2d_asset_id", "is_default", "disabled"):
            val = getattr(data, field_name, None)
            if val is not None:
                setattr(p, field_name, val)

        if data.tags is not None:
            p.tags = data.tags

        p = await self.repo.update(p)
        return _to_out(p)

    async def set_default(self, persona_id: int) -> PersonaOut:
        p = await self.get_persona(persona_id)
        await self.repo.clear_default_for_scope(p.scope, p.user_id)
        p.is_default = True
        p = await self.repo.update(p)
        return _to_out(p)

    async def delete_persona(self, persona_id: int) -> None:
        """Permanently delete a persona and clean up chat_session references."""
        from sqlalchemy import text
        # Clear dangling persona_id references in chat_session (stored as free-text, no FK)
        await self.repo.session.execute(
            text("UPDATE chat_session SET persona_id = NULL WHERE persona_id = :pid"),
            {"pid": str(persona_id)},
        )
        deleted = await self.repo.hard_delete(persona_id)
        if not deleted:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "persona_not_found")

    # ── SillyTavern V2 Import / Export ───────────────────────────────────

    ST_V2_FIELDS = (
        "name", "description", "personality", "scenario",
        "first_mes", "mes_example", "system_prompt",
    )

    async def import_v2(self, data: dict, user_id: int, scope: str = "user") -> PersonaOut:
        """Import a SillyTavern V2 character JSON.

        SillyTavern fields are mapped 1:1 (names match).
        Only the subset of fields defined in ST_V2_FIELDS is imported.
        """
        st_data = data.get("data", data)  # SillyTavern wraps in "data" or not

        persona_data: dict = {"scope": scope}
        for field in self.ST_V2_FIELDS:
            if field in st_data:
                persona_data[field] = st_data[field]

        # Tags: SillyTavern uses "tags" as list of strings
        if "tags" in st_data and isinstance(st_data["tags"], list):
            persona_data["tags"] = st_data["tags"]

        # Name is required
        if not persona_data.get("name"):
            persona_data["name"] = st_data.get("name", "Imported Character")

        # system_prompt is required (min 10 chars) — generate default if missing
        if not persona_data.get("system_prompt") or len(persona_data.get("system_prompt", "").strip()) < 10:
            persona_data["system_prompt"] = (
                f"你是{persona_data.get('name', '一个角色')}。请用中文回复。"
            )

        create_in = PersonaCreateIn(**persona_data)
        return await self.create_persona(create_in, user_id)

    def export_v2(self, persona: Persona) -> dict:
        """Export a persona as SillyTavern V2 JSON format."""
        st_data = {}
        for field in self.ST_V2_FIELDS:
            val = getattr(persona, field, None)
            if val:
                st_data[field] = val

        if persona.tags:
            st_data["tags"] = persona.tags

        return {"data": st_data}
