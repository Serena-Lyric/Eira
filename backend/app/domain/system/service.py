"""System settings service — key-value store with optional Redis pub/sub invalidation."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from .models import SystemSetting


class SystemSettingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str) -> Any | None:
        row = await self.session.get(SystemSetting, key)
        return row.value if row else None

    async def set(self, key: str, value: Any, description: str = "") -> SystemSetting:
        """Upsert a system setting value (INSERT … ON CONFLICT DO UPDATE).

        Uses PostgreSQL native upsert to avoid read-then-write race conditions
        under concurrent access (§10 fix).
        """
        now = datetime.now(timezone.utc)
        stmt = (
            pg_insert(SystemSetting)
            .values(key=key, value=value, description=description,
                    updated_at=now)
            .on_conflict_do_update(
                index_elements=[SystemSetting.key],
                set_={
                    "value": value,
                    "description": description,
                    "updated_at": now,
                },
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()
        # Fetch the upserted row to return
        row = await self.session.get(SystemSetting, key)
        return row

    async def get_all(self) -> dict[str, Any]:
        """Return all settings as a dict keyed by setting key."""
        result = await self.session.execute(select(SystemSetting))
        return {row.key: row.value for row in result.scalars().all()}

    async def get_group(self, prefix: str) -> dict[str, Any]:
        """Return settings whose key starts with the given prefix."""
        result = await self.session.execute(
            select(SystemSetting).where(SystemSetting.key.startswith(prefix))
        )
        return {row.key: row.value for row in result.scalars().all()}

    async def set_many(self, settings: dict[str, Any]) -> list[SystemSetting]:
        """Batch set multiple settings (each is individually upserted)."""
        rows = []
        for key, value in settings.items():
            row = await self.set(key, value)
            rows.append(row)
        return rows
