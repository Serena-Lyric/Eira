from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User


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
