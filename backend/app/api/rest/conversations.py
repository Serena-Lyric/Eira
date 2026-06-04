"""REST endpoints for conversation sessions and messages."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db_session, get_current_user
from app.domain.identity.models import User
from app.domain.conversation.repository import ConversationRepository
from app.domain.conversation.service import ConversationService
from app.domain.conversation.schemas import (
    SessionCreate,
    SessionOut,
    ChatMessageOut,
    ConversationList,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_conversation_service(
    s: AsyncSession = Depends(get_db_session),
) -> ConversationService:
    return ConversationService(ConversationRepository(s))


@router.post("", status_code=201)
async def create_session(
    payload: SessionCreate,
    user: User = Depends(get_current_user),
    svc: ConversationService = Depends(get_conversation_service),
) -> SessionOut:
    """Create a new chat session."""
    return await svc.create_session(user.id, payload)


@router.get("")
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    svc: ConversationService = Depends(get_conversation_service),
) -> ConversationList:
    """List sessions for the current user, newest first."""
    return await svc.list_sessions(user.id, limit, offset)


@router.get("/{session_id}/messages")
async def list_messages(
    session_id: int,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    svc: ConversationService = Depends(get_conversation_service),
) -> list[ChatMessageOut]:
    """List messages for a session, oldest first."""
    return await svc.get_messages(session_id, user.id, limit, offset)
