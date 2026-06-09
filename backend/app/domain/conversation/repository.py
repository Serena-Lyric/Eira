"""Repository for chat sessions, messages, and user feedback."""

from datetime import datetime, timezone

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from .models import ChatSession, ChatMessage, Feedback


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


class FeedbackRepository:
    """用户服务建议 / 反馈的持久化操作。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, fb: Feedback) -> Feedback:
        self.session.add(fb)
        await self.session.flush()
        return fb

    async def get_by_id(self, feedback_id: int) -> Feedback | None:
        return await self.session.get(Feedback, feedback_id)

    async def list_all(
        self, limit: int = 50, offset: int = 0
    ) -> list[Feedback]:
        """按创建时间倒序返回所有反馈。"""
        q = (
            select(Feedback)
            .order_by(Feedback.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list((await self.session.execute(q)).scalars().all())

    async def update_reply(
        self, feedback_id: int, reply_text: str
    ) -> Feedback | None:
        """为指定反馈保存管理员回复，标记为已回复。"""
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(Feedback)
            .where(Feedback.id == feedback_id)
            .values(reply_text=reply_text, replied=True, replied_at=now)
        )
        await self.session.flush()
        return await self.get_by_id(feedback_id)
