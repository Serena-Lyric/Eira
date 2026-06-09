"""Persist node — saves user message and assistant response to the DB.

Phase 1 stub — logs to structlog; T1.3 wires the real repository.
"""

from __future__ import annotations

import structlog
from app.orchestrator.state import ChatState

logger = structlog.get_logger(__name__)


async def persist(state: ChatState) -> dict:
    """Persist the conversation turn (user + assistant messages).

    Phase 1 stub: logs the messages. T1.3 will replace with real DB writes
    via the ConversationService.
    """
    logger.info(
        "orchestrator.node.start",
        node="persist",
        session_id=state.session_id,
        user_id=state.user_id,
        user_text_len=len(state.user_text),
        llm_text_len=len(state.llm_text),
    )

    # T1.3 will inject: await conversation_service.add_message(...)

    logger.info(
        "orchestrator.node.end",
        node="persist",
        session_id=state.session_id,
    )
    return {}
