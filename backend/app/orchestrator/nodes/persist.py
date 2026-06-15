"""Persist node — saves user message and assistant response to the DB."""

from __future__ import annotations

import re
import structlog
from app.orchestrator.state import ChatState

logger = structlog.get_logger(__name__)

# §5.3 fix: Strip geolocation prefix injected by frontend before persisting
_GEOLOCATION_RE = re.compile(r'\[用户位置[^\]]*\]\s*\n?')


async def persist(state: ChatState) -> dict:
    """Persist the conversation turn (user + assistant messages) to the DB.

    Writes both the user message and the assistant response to the
    chat_messages table via ConversationRepository. Returns the persisted
    message IDs so the WS layer can include them in DoneOut.
    """
    try:
        from app.infra.db import get_session_factory
        from app.domain.conversation.repository import ConversationRepository
        from app.domain.conversation.models import ChatMessage
        from datetime import datetime, timezone

        session_id = int(state.session_id)
        now = datetime.now(timezone.utc)

        factory = get_session_factory()
        async with factory() as db:
            repo = ConversationRepository(db)

            # Persist user message — strip geolocation prefix
            clean_content = _GEOLOCATION_RE.sub('', state.user_text).strip()
            user_msg = ChatMessage(
                session_id=session_id,
                role="user",
                content=clean_content,
                created_at=now,
            )
            user_msg = await repo.add_message(user_msg)

            # Persist assistant response
            assistant_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=state.llm_text,
                created_at=now,
            )
            assistant_msg = await repo.add_message(assistant_msg)

            await db.commit()

            logger.info(
                "orchestrator.node.persist.ok",
                session_id=session_id,
                user_msg_id=user_msg.id,
                assistant_msg_id=assistant_msg.id,
            )
            return {
                "user_message_id": user_msg.id,
                "assistant_message_id": assistant_msg.id,
            }

    except (ValueError, TypeError):
        logger.warning(
            "orchestrator.node.persist.skip",
            session_id=state.session_id,
            detail="non-integer session_id — cannot persist to DB",
        )
        return {}
    except Exception as exc:
        logger.error(
            "orchestrator.node.persist.error",
            session_id=state.session_id,
            error=str(exc),
        )
        return {}
