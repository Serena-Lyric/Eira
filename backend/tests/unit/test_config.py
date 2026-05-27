import os
from app.core.config import get_settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("EIRA_DB_DSN", "postgresql+asyncpg://x:y@h/d")
    monkeypatch.setenv("EIRA_REDIS_URL", "redis://h:6379/1")
    get_settings.cache_clear()
    s = get_settings()
    assert s.db.dsn == "postgresql+asyncpg://x:y@h/d"
    assert s.redis.url == "redis://h:6379/1"
    assert s.app.env in ("dev", "staging", "prod")
