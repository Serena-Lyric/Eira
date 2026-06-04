"""Load conversation context (history, persona) from persistence layer.

Phase 1 stub — returns the state unchanged. Phase 2+ will load from PG.
"""

from app.orchestrator.state import ChatState


async def load_context(state: ChatState) -> dict:
    """Load recent conversation history and persona prompt.

    Phase 1: returns empty context (no RAG, no persona selection).
    Future phases will query the conversation repository and persona store.
    """
    # Stub — history already empty; persona_prompt uses default
    return {
        "history": state.history,
        "persona_prompt": state.persona_prompt or "你是一个友好的AI导游助手。请用中文回复，语气亲切自然。",
        "retrieved_chunks": state.retrieved_chunks,
    }
