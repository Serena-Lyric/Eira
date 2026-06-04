from collections.abc import AsyncGenerator
from fastapi import Depends, HTTPException, Header
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
