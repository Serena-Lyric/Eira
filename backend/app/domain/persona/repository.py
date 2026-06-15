from datetime import datetime, timezone
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Persona


class PersonaRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, persona_id: int) -> Persona | None:
        return await self.session.get(Persona, persona_id)

    async def create(self, persona: Persona) -> Persona:
        self.session.add(persona)
        await self.session.flush()
        return persona

    async def update(self, persona: Persona) -> Persona:
        persona.updated_at = datetime.now(timezone.utc)
        self.session.add(persona)
        await self.session.flush()
        return persona

    async def hard_delete(self, persona_id: int) -> bool:
        """Permanently delete a persona. Returns True if deleted, False if not found."""
        from sqlalchemy import delete
        result = await self.session.execute(
            delete(Persona).where(Persona.id == persona_id)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def list_personas(
        self,
        scope: str | None = None,
        user_id: int | None = None,
        include_disabled: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Persona], int]:
        """Paginated persona list. Admin sees all (user_id=None), users see their own + public."""
        conditions = []

        if not include_disabled:
            conditions.append(Persona.disabled == False)

        if scope:
            conditions.append(Persona.scope == scope)

        if user_id is not None:
            # User sees: public personas OR their own user-scoped personas
            from sqlalchemy import or_
            conditions.append(
                or_(Persona.scope == "public", Persona.user_id == user_id)
            )

        base = select(Persona).where(*conditions)
        count_q = select(func.count()).select_from(base.subquery())
        total = (await self.session.execute(count_q)).scalar_one()

        offset = (page - 1) * page_size
        rows = (
            await self.session.execute(
                base.order_by(Persona.created_at.desc()).offset(offset).limit(page_size)
            )
        ).scalars().all()

        return list(rows), total

    async def clear_default_for_scope(self, scope: str, user_id: int | None = None) -> None:
        """Unset is_default for ALL personas — only one default allowed system-wide.

        Regardless of scope, always clears ALL existing defaults so that exactly
        one persona can be the default at any time.
        """
        await self.session.execute(
            update(Persona).where(Persona.is_default == True).values(is_default=False)
        )
        await self.session.flush()
