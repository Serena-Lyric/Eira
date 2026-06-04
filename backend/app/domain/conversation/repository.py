"""Repository for chat sessions and messages."""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from .models import ChatSession, ChatMessage


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Session ──────────────────────────────────────────────

    async def create_session(self, s: ChatSession) -> ChatSession:
        self.session.add(s)
        await self.session.flush()
        return s

    async def get_session(self, session_id: int) -> ChatSession | None:
        return await self.session.get(ChatSession, session_id)

    async def list_sessions(
        self, user_id: int, limit: int = 20, offset: int = 0
    ) -> tuple[list[ChatSession], int]:
        q = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_q = select(func.count()).where(ChatSession.user_id == user_id)
        rows = (await self.session.execute(q)).scalars().all()
        total = (await self.session.execute(count_q)).scalar_one()
        return list(rows), total

    async def end_session(self, session_id: int) -> None:
        s = await self.get_session(session_id)
        if s:
            s.ended_at = func.now()
            self.session.add(s)
            await self.session.flush()

    # ── Messages ─────────────────────────────────────────────

    async def add_message(self, msg: ChatMessage) -> ChatMessage:
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def list_messages(
        self, session_id: int, limit: int = 200, offset: int = 0
    ) -> list[ChatMessage]:
        q = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.asc())
            .offset(offset)
            .limit(limit)
        )
        return list((await self.session.execute(q)).scalars().all())
