from functools import lru_cache
import os
from redis.asyncio import Redis


@lru_cache
def get_redis() -> Redis:
    url = os.environ.get("EIRA_REDIS_URL", "redis://localhost:6379/0")
    return Redis.from_url(url, decode_responses=True)
