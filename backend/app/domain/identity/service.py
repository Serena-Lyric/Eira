from fastapi import HTTPException, status
from app.core.security import hash_password, verify_password, issue_token, decode_token
from app.infra.redis import get_redis
from app.core.config import get_settings
from .models import User
from .repository import UserRepository
from .schemas import RegisterIn, LoginIn, TokenPair

REFRESH_KEY = "auth:refresh:{token}"


class IdentityService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def register(self, payload: RegisterIn) -> User:
        if await self.repo.get_by_email(payload.email):
            raise HTTPException(status.HTTP_409_CONFLICT, "email_taken")
        u = User(
            email=payload.email,
            password_hash=hash_password(payload.password),
            display_name=payload.display_name,
        )
        return await self.repo.create(u)

    async def login(self, payload: LoginIn) -> TokenPair:
        u = await self.repo.get_by_email(payload.email)
        if not u or not verify_password(payload.password, u.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
        if u.status != "active":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
        return await self._issue_pair(u)

    async def refresh(self, refresh_token: str) -> TokenPair:
        try:
            payload = decode_token(refresh_token)
            assert payload.get("kind") == "refresh"
        except Exception:
            raise HTTPException(401, "invalid_token")
        r = get_redis()
        if not await r.get(REFRESH_KEY.format(token=refresh_token)):
            raise HTTPException(401, "revoked_token")
        u = await self.repo.get_by_id(int(payload["sub"]))
        if not u or u.status != "active":
            raise HTTPException(401, "invalid_token")
        await r.delete(REFRESH_KEY.format(token=refresh_token))
        return await self._issue_pair(u)

    async def _issue_pair(self, u: User) -> TokenPair:
        access = issue_token(str(u.id), u.role, "access")
        refresh = issue_token(str(u.id), u.role, "refresh")
        await get_redis().set(
            REFRESH_KEY.format(token=refresh),
            str(u.id),
            ex=get_settings().jwt.refresh_ttl_seconds,
        )
        return TokenPair(access_token=access, refresh_token=refresh)
