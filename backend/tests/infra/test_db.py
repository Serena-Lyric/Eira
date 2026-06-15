import pytest
from sqlalchemy import text
from app.infra.db import get_engine


@pytest.mark.asyncio
async def test_pgvector_extension_available():
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname='vector'")
        )
        assert result.scalar() == "vector"


@pytest.mark.asyncio
async def test_schema_version_table_exists():
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT to_regclass('public.schema_version')")
        )
        assert result.scalar() == "schema_version"
