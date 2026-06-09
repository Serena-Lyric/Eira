"""Safety input node — validates user input before LLM processing.

Phase 1: length truncation + keyword blacklist.
"""

from app.core.safety_words import is_input_safe
from app.orchestrator.state import ChatState


async def safety_in(state: ChatState) -> dict:
    """Validate user input.

    If the input fails safety checks, sets safety_in_ok=False so the graph
    short-circuits to emit with a fallback response.
    """
    ok, reason = is_input_safe(state.user_text)

    if not ok:
        return {
            "safety_in_ok": False,
            "safety_in_reason": reason,
            "llm_text": "抱歉，您的消息包含不支持的内容，无法处理。",
        }

    return {
        "safety_in_ok": True,
        "safety_in_reason": "",
    }
