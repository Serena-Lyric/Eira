"""Safety output node — redacts secrets from LLM output.

Phase 1: regex-based secret redaction.
"""

from app.core.safety_words import redact_output
from app.orchestrator.state import ChatState


async def safety_out(state: ChatState) -> dict:
    """Redact any secrets that might have leaked into the LLM response."""
    redacted = redact_output(state.llm_text)

    return {
        "safety_out_ok": True,
        "safety_out_reason": "",
        "llm_text": redacted,
    }
