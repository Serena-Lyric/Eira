"""Conversation service — business logic for sessions and messages."""

from fastapi import HTTPException
from .models import ChatSession, ChatMessage
from .repository import ConversationRepository
from .schemas import SessionCreate, SessionOut, ChatMessageOut, ConversationList


class ConversationService:
    def __init__(self, repo: ConversationRepository):
        self.repo = repo

    async def create_session(self, user_id: int, payload: SessionCreate) -> SessionOut:
        s = ChatSession(
            user_id=user_id,
            persona_id=payload.persona_id,
            title=payload.title,
        )
        s = await self.repo.create_session(s)
        return SessionOut.model_validate(s)

    async def list_sessions(
        self, user_id: int, limit: int = 20, offset: int = 0
    ) -> ConversationList:
        sessions, total = await self.repo.list_sessions(user_id, limit, offset)
        return ConversationList(
            sessions=[SessionOut.model_validate(s) for s in sessions],
            total=total,
        )

    async def get_messages(
        self, session_id: int, user_id: int, limit: int = 200, offset: int = 0
    ) -> list[ChatMessageOut]:
        s = await self.repo.get_session(session_id)
        if not s or s.user_id != user_id:
            raise HTTPException(404, "session_not_found")
        msgs = await self.repo.list_messages(session_id, limit, offset)
        return [ChatMessageOut.model_validate(m) for m in msgs]

    async def add_user_message(
        self, session_id: int, content: str, user_id: int
    ) -> ChatMessage:
        s = await self.repo.get_session(session_id)
        if not s or s.user_id != user_id:
            raise HTTPException(404, "session_not_found")
        msg = ChatMessage(session_id=session_id, role="user", content=content)
        return await self.repo.add_message(msg)

    async def add_assistant_message(
        self, session_id: int, content: str, metadata_json: str | None = None
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=content,
            metadata_json=metadata_json,
        )
        return await self.repo.add_message(msg)
