"""Load conversation context (history, persona) from persistence layer.

Phase 2: loads conversation history from DB if session_id is provided.
"""

import structlog

from app.orchestrator.state import ChatState

logger = structlog.get_logger(__name__)

_DEFAULT_PERSONA = (
    "你是一个友好的AI导游助手，名字叫'Eira'。请用中文回复，语气亲切自然、热情开朗。"
)


async def load_context(state: ChatState) -> dict:
    """Load recent conversation history and persona prompt.

    Loads history from DB when session_id is numeric and the services are available.
    Falls back to default persona prompt if none is set.
    """
    persona_prompt = state.persona_prompt or _DEFAULT_PERSONA

    # Try loading history from DB if session_id looks like an integer
    history = list(state.history)
    if state.session_id and not history:
        try:
            session_id_int = int(state.session_id)
        except (ValueError, TypeError):
            session_id_int = None

        if session_id_int is not None:
            try:
                from app.core.deps import get_db_session
                from app.domain.conversation.repository import ConversationRepository

                # We need a new async session — create one directly
                from app.infra.db import get_session_factory

                factory = get_session_factory()
                async with factory() as session:
                    repo = ConversationRepository(session)
                    msgs = await repo.list_messages(session_id_int, limit=20)
                    history = [
                        {"role": m.role, "content": m.content}
                        for m in msgs[-20:]  # Last 20 messages
                    ]
            except Exception as exc:
                # Graceful fallback — history stays empty
                logger.debug("context.history_load_failed", session_id=state.session_id, error=str(exc))

    return {
        "history": history,
        "persona_prompt": persona_prompt,
        "retrieved_chunks": state.retrieved_chunks,
    }
