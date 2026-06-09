from collections.abc import AsyncGenerator
from fastapi import Depends, HTTPException, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import decode_token
from app.infra.db import get_session_factory
from app.domain.identity.repository import UserRepository
from app.domain.identity.service import IdentityService
from app.domain.identity.models import User


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    s = factory()
    try:
        yield s
        await s.commit()
    except Exception:
        await s.rollback()
        raise
    finally:
        await s.close()


def get_identity_service(
    s: AsyncSession = Depends(get_db_session),
) -> IdentityService:
    return IdentityService(UserRepository(s))


async def get_current_user(
    authorization: str = Header(None),
    svc: IdentityService = Depends(get_identity_service),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing_token")
    try:
        payload = decode_token(authorization.removeprefix("Bearer "))
        assert payload.get("kind") == "access"
    except Exception:
        raise HTTPException(401, "invalid_token")
    u = await svc.repo.get_by_id(int(payload["sub"]))
    if not u or u.status != "active":
        raise HTTPException(401, "invalid_token")
    return u


def require_admin(u: User = Depends(get_current_user)) -> User:
    if u.role != "admin":
        raise HTTPException(403, "forbidden")
    return u


# ── Rate limiting ─────────────────────────────────────────────────────────


async def check_chat_rate_limit(
    user: User = Depends(get_current_user),
) -> None:
    """Rate-limit chat endpoints per user. Raises 429 if exceeded."""
    from app.core.rate_limit import get_chat_limiter

    limiter = get_chat_limiter()
    if not await limiter.check(str(user.id), "chat"):
        raise HTTPException(429, "请求过于频繁，请稍后再试")


async def check_upload_rate_limit(
    user: User = Depends(get_current_user),
) -> None:
    """Rate-limit upload endpoints per user. Raises 429 if exceeded."""
    from app.core.rate_limit import get_upload_limiter

    limiter = get_upload_limiter()
    if not await limiter.check(str(user.id), "upload"):
        raise HTTPException(429, "上传过于频繁，请稍后再试")


async def check_write_rate_limit(
    user: User = Depends(get_current_user),
) -> None:
    """Rate-limit write (POST/PATCH/DELETE) endpoints per user. Raises 429 if exceeded.

    §5.4 / spec §7.4 — write operations get a dedicated token bucket
    (capacity=20, rate=3 tokens/s) separate from uploads.
    """
    from app.core.rate_limit import get_write_limiter

    limiter = get_write_limiter()
    if not await limiter.check(str(user.id), "write"):
        raise HTTPException(429, "操作过于频繁，请稍后再试")


async def check_auth_rate_limit(
    request: Request,
) -> None:
    """Rate-limit auth endpoints (login/register/refresh) per client IP.

    §5.4 — strict limit (capacity=5, rate=0.5 tokens/s) to prevent brute-force.
    Uses client IP instead of user_id since the user is not authenticated yet.
    """
    from app.core.rate_limit import get_auth_limiter

    client_ip = request.client.host if request.client else "unknown"
    limiter = get_auth_limiter()
    if not await limiter.check(client_ip, "auth"):
        raise HTTPException(429, "请求过于频繁，请稍后再试")
