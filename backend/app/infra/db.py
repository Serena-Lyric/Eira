from functools import lru_cache
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from app.core.config import get_settings


def _build_dsn() -> str:
    return get_settings().db.dsn


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(_build_dsn(), pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker:
    return async_sessionmaker(get_engine(), expire_on_commit=False)
