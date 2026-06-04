"""Emit node — the terminal node that signals completion.

In the WS flow this is a no-op because token frames are already pushed
during streaming. In a future batch/HTTP flow this could trigger
notifications.
"""

from app.orchestrator.state import ChatState


async def emit(state: ChatState) -> dict:
    """Final node — pass-through; the WS handler reads state.llm_text directly."""
    return {}
