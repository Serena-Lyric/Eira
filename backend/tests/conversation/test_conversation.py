"""Unit tests for conversation domain (T1.3) — covers service + repository edge paths."""

from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.domain.conversation.repository import ConversationRepository
from app.domain.conversation.service import ConversationService
from app.domain.conversation.schemas import SessionCreate


@pytest.mark.asyncio
async def test_service_add_user_message():
    """Service.add_user_message delegates to repository correctly."""
    mock_repo = MagicMock(spec=ConversationRepository)
    mock_repo.get_session = AsyncMock(return_value=MagicMock(user_id=1, id=10))
    mock_repo.add_message = AsyncMock(return_value=MagicMock(id=1, role="user", content="hello"))

    svc = ConversationService(mock_repo)
    msg = await svc.add_user_message(session_id=10, content="hello", user_id=1)
    assert msg.role == "user"
    assert msg.content == "hello"


@pytest.mark.asyncio
async def test_service_add_user_message_wrong_user_raises():
    """Service.add_user_message rejects wrong user."""
    mock_repo = MagicMock(spec=ConversationRepository)
    mock_repo.get_session = AsyncMock(return_value=MagicMock(user_id=2, id=10))

    svc = ConversationService(mock_repo)
    with pytest.raises(Exception) as exc_info:
        await svc.add_user_message(session_id=10, content="hack", user_id=1)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_service_add_assistant_message():
    """Service.add_assistant_message creates an assistant message."""
    mock_repo = MagicMock(spec=ConversationRepository)
    mock_repo.add_message = AsyncMock(return_value=MagicMock(id=2, role="assistant", content="reply"))

    svc = ConversationService(mock_repo)
    msg = await svc.add_assistant_message(session_id=10, content="reply")
    assert msg.role == "assistant"
    assert msg.content == "reply"


@pytest.mark.asyncio
async def test_service_get_messages_session_not_found():
    """Service.get_messages raises 404 for missing session."""
    mock_repo = MagicMock(spec=ConversationRepository)
    mock_repo.get_session = AsyncMock(return_value=None)

    svc = ConversationService(mock_repo)
    with pytest.raises(Exception) as exc_info:
        await svc.get_messages(session_id=999, user_id=1)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_repository_end_session():
    """Repository.end_session sets ended_at."""
    mock_session_obj = MagicMock()
    mock_repo = ConversationRepository(session=AsyncMock())
    mock_repo.get_session = AsyncMock(return_value=mock_session_obj)

    await mock_repo.end_session(session_id=1)
    assert mock_session_obj.ended_at is not None


@pytest.mark.asyncio
async def test_service_create_session_with_persona():
    """SessionCreate with persona_id propagates correctly."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    mock_repo = MagicMock(spec=ConversationRepository)
    mock_repo.create_session = AsyncMock(return_value=MagicMock(
        id=1, user_id=42, persona_id="guide1", title="Test", created_at=now, ended_at=None
    ))

    svc = ConversationService(mock_repo)
    result = await svc.create_session(42, SessionCreate(persona_id="guide1", title="Test"))
    assert result.persona_id == "guide1"
    assert result.title == "Test"
