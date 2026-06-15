import pytest
from app.infra.redis import get_redis


@pytest.mark.asyncio
async def test_redis_set_and_get():
    r = get_redis()
    await r.set("test:key", "hello", ex=10)
    assert await r.get("test:key") == "hello"
    await r.delete("test:key")
