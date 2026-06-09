from fastapi import HTTPException, status
from app.core.security import hash_password, verify_password, issue_token, decode_token
from app.infra.redis import get_redis
from app.core.config import get_settings
from .models import User
from .repository import UserRepository
from .schemas import RegisterIn, LoginIn, TokenPair, UserOut, PaginatedUsers, UserDetailOut

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

    # ── Admin user management ─────────────────────────────────────────

    async def list_users(
        self, keyword: str | None = None, role: str | None = None,
        page: int = 1, page_size: int = 20,
    ) -> PaginatedUsers:
        items, total = await self.repo.list_users(keyword=keyword, role=role, page=page, page_size=page_size)
        return PaginatedUsers(
            items=[UserOut(id=u.id, email=u.email, display_name=u.display_name, role=u.role) for u in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_user_detail(self, uid: int) -> UserDetailOut:
        u = await self.repo.get_by_id(uid)
        if not u or u.deleted_at is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
        return UserDetailOut(
            id=u.id, email=u.email, display_name=u.display_name,
            role=u.role, status=u.status, disabled=u.disabled,
            created_at=u.created_at.isoformat() if u.created_at else None,
            updated_at=u.updated_at.isoformat() if u.updated_at else None,
        )

    async def set_user_role(self, uid: int, role: str, admin_id: int) -> User:
        if uid == admin_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_change_own_role")
        if role not in ("visitor", "admin"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_role")
        u = await self.repo.get_by_id(uid)
        if not u or u.deleted_at is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
        u.role = role
        return await self.repo.update_user(u)

    async def set_user_disabled(self, uid: int, disabled: bool, admin_id: int) -> User:
        if uid == admin_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_disable_self")
        if disabled:
            # Prevent disabling the last active admin
            active_admins = await self.repo.count_active_admins()
            target = await self.repo.get_by_id(uid)
            if target and target.role == "admin" and active_admins <= 1:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_disable_last_admin")
        u = await self.repo.get_by_id(uid)
        if not u or u.deleted_at is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
        u.disabled = disabled
        return await self.repo.update_user(u)

    async def soft_delete_user(self, uid: int, admin_id: int) -> None:
        if uid == admin_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_delete_self")
        u = await self.repo.get_by_id(uid)
        if not u or u.deleted_at is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found")
        # Prevent soft-deleting the last active admin
        active_admins = await self.repo.count_active_admins()
        if u.role == "admin" and active_admins <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_delete_last_admin")
        await self.repo.soft_delete(uid)
