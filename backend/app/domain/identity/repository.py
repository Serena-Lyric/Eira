import json
from datetime import datetime, timezone
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User, UserPreferences


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        return (
            await self.session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

    async def get_by_id(self, uid: int) -> User | None:
        return await self.session.get(User, uid)

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def list_users(
        self,
        keyword: str | None = None,
        role: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        """Paginated user list with optional keyword and role filters.
        Excludes soft-deleted users (deleted_at IS NOT NULL).
        """
        conditions = [User.deleted_at.is_(None)]

        if role:
            conditions.append(User.role == role)
        if keyword:
            kw = f"%{keyword}%"
            conditions.append(
                or_(User.email.ilike(kw), User.display_name.ilike(kw))
            )

        base = select(User).where(*conditions)
        count_q = select(func.count()).select_from(base.subquery())
        total = (await self.session.execute(count_q)).scalar_one()

        offset = (page - 1) * page_size
        rows = (
            await self.session.execute(
                base.order_by(User.created_at.desc()).offset(offset).limit(page_size)
            )
        ).scalars().all()

        return list(rows), total

    async def update_user(self, user: User) -> User:
        user.updated_at = datetime.now(timezone.utc)
        self.session.add(user)
        await self.session.flush()
        return user

    async def soft_delete(self, uid: int) -> None:
        user = await self.get_by_id(uid)
        if user:
            user.deleted_at = datetime.now(timezone.utc)
            user.updated_at = datetime.now(timezone.utc)
            self.session.add(user)
            await self.session.flush()

    async def count_active_admins(self) -> int:
        """Count non-disabled, non-deleted admin users."""
        result = await self.session.execute(
            select(func.count(User.id)).where(
                User.role == "admin",
                User.disabled == False,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one()

    # ── User Preferences ──────────────────────────────────────────────

    async def get_preferences(self, user_id: int) -> dict | None:
        """读取用户偏好 JSON，无记录返回 None。"""
        result = await self.session.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        try:
            return json.loads(row.preferences_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    async def save_preferences(self, user_id: int, data: dict) -> None:
        """创建或更新用户偏好。"""
        result = await self.session.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if row is not None:
            row.preferences_json = json.dumps(data, ensure_ascii=False)
            row.updated_at = now
        else:
            row = UserPreferences(
                user_id=user_id,
                preferences_json=json.dumps(data, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
            self.session.add(row)
        await self.session.flush()
