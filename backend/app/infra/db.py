from functools import lru_cache
import os
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


def _build_dsn() -> str:
    return os.environ.get(
        "EIRA_DB_DSN",
        "postgresql+asyncpg://eira:eira@localhost:5432/eira",
    )


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(_build_dsn(), pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker:
    return async_sessionmaker(get_engine(), expire_on_commit=False)
