"""Redis-backed token-bucket rate limiter.

Implements spec §7.4: per (user_id, endpoint) dimension with configurable
capacity and refill rate.  Uses a Lua script for atomic get-and-decrement,
avoiding race conditions without distributed locks.

If Redis is unreachable the limiter fails open (allows the request through)
and logs a warning — availability is preferred over security in that scenario.
"""

from __future__ import annotations

import time
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# ── Lua script (atomic token bucket) ──────────────────────────────────────

_RATE_LIMIT_LUA = """
local key        = KEYS[1]
local capacity   = tonumber(ARGV[1])
local rate       = tonumber(ARGV[2])   -- tokens / second
local now        = tonumber(ARGV[3])
local requested  = tonumber(ARGV[4])

local bucket = redis.call("HMGET", key, "tokens", "last_refill")
local tokens = tonumber(bucket[1])
local last   = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    last   = now
end

-- Refill
local elapsed = math.max(0, now - last)
tokens = math.min(capacity, tokens + elapsed * rate)
last   = now

if tokens >= requested then
    tokens = tokens - requested
    redis.call("HMSET", key, "tokens", tokens, "last_refill", last)
    redis.call("EXPIRE", key, 60)
    return 1
else
    redis.call("HMSET", key, "tokens", tokens, "last_refill", last)
    redis.call("EXPIRE", key, 60)
    return 0
end
"""


class RateLimiter:
    """Token-bucket rate limiter backed by Redis."""

    def __init__(self, capacity: int = 60, rate: float = 10.0) -> None:
        self.capacity = capacity
        self.rate = rate

    async def check(self, user_id: str, endpoint: str, cost: int = 1) -> bool:
        """Return True if the request is allowed, False if rate-limited.

        Respects the global RateLimitSettings.enabled flag — when disabled,
        always allows.  Fails open: if Redis is unreachable the call returns
        True and logs a warning so the service stays available.
        """
        if not get_settings().rate_limit.enabled:
            return True

        try:
            from app.infra.redis import get_redis

            redis = get_redis()
            key = f"rate_limit:{user_id}:{endpoint}"
            now = time.time()
            result = await redis.eval(
                _RATE_LIMIT_LUA,
                1,
                key,
                str(self.capacity),
                str(self.rate),
                str(now),
                str(cost),
            )
            return bool(result)
        except Exception as exc:
            logger.warning(
                "rate_limit.redis_error",
                user_id=user_id,
                endpoint=endpoint,
                error=str(exc),
            )
            return True  # fail open


# ── Pre-configured instances (tunable via RateLimitSettings) ──────────────

def _build_limiters():
    """Build rate limiter instances from current settings."""
    s = get_settings().rate_limit
    return (
        RateLimiter(capacity=s.chat_capacity, rate=s.chat_rate),
        RateLimiter(capacity=s.upload_capacity, rate=s.upload_rate),
        RateLimiter(capacity=s.ws_capacity, rate=s.ws_rate),
        RateLimiter(capacity=s.write_capacity, rate=s.write_rate),
        RateLimiter(capacity=s.auth_capacity, rate=s.auth_rate),
    )


# Module-level singletons — re-initialised when settings change is acceptable
# because get_settings() is lru_cache'd.
chat_rate_limiter: RateLimiter | None = None
upload_rate_limiter: RateLimiter | None = None
ws_message_limiter: RateLimiter | None = None
write_rate_limiter: RateLimiter | None = None
auth_rate_limiter: RateLimiter | None = None


def _ensure_limiters() -> None:
    global chat_rate_limiter, upload_rate_limiter, ws_message_limiter, write_rate_limiter, auth_rate_limiter
    if chat_rate_limiter is None:
        chat_rate_limiter, upload_rate_limiter, ws_message_limiter, write_rate_limiter, auth_rate_limiter = _build_limiters()


def get_chat_limiter() -> RateLimiter:
    _ensure_limiters()
    return chat_rate_limiter  # type: ignore[return-value]


def get_upload_limiter() -> RateLimiter:
    _ensure_limiters()
    return upload_rate_limiter  # type: ignore[return-value]


def get_ws_limiter() -> RateLimiter:
    _ensure_limiters()
    return ws_message_limiter  # type: ignore[return-value]


def get_write_limiter() -> RateLimiter:
    _ensure_limiters()
    return write_rate_limiter  # type: ignore[return-value]


def get_auth_limiter() -> RateLimiter:
    _ensure_limiters()
    return auth_rate_limiter  # type: ignore[return-value]
