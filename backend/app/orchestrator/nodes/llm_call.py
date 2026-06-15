"""LLM call node — invokes the provider and collects the full response.

System prompt instructs the model to optionally insert action tags like
[wave], [nod], [happy] to trigger Live2D motions on the frontend.
"""

from __future__ import annotations

import time
import uuid

import structlog
from app.capabilities.llm.base import BaseLLMProvider
from app.orchestrator.state import ChatState
from app.domain.persona.resolver import DEFAULT_PERSONA_FALLBACK

logger = structlog.get_logger(__name__)

# 最终 fallback system prompt — 仅当 DB 无默认 persona 且 state.persona_prompt 为空时使用
_SYSTEM_PROMPT = DEFAULT_PERSONA_FALLBACK


async def llm_call(state: ChatState, provider: BaseLLMProvider) -> dict:
    """Call the LLM with conversation history and collect the response."""
    request_id = state.request_id or uuid.uuid4().hex[:12]
    t0 = time.perf_counter()

    # Build system prompt with RAG context if available
    system_content = state.persona_prompt or _SYSTEM_PROMPT

    if state.retrieved_chunks:
        context_text = "\n".join(state.retrieved_chunks)
        system_content += (
            "\n\n根据以下参考资料回答用户问题：\n"
            f"<context>\n{context_text}\n</context>\n\n"
            "如果参考资料不足以回答问题，请基于你的知识诚实回答，"
            "并说明信息来源的局限性。"
        )

    messages: list[dict] = [
        {"role": "system", "content": system_content},
    ]
    # Append history (oldest first)
    for h in state.history:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    # Append current user message
    messages.append({"role": "user", "content": state.user_text})

    logger.info(
        "orchestrator.node.start",
        node="llm_call",
        request_id=request_id,
        session_id=state.session_id,
        user_id=state.user_id,
    )

    try:
        parts: list[str] = []
        async for delta in provider.stream(messages):
            parts.append(delta.text)

        llm_text = "".join(parts)
        latency_ms = (time.perf_counter() - t0) * 1000

        logger.info(
            "orchestrator.node.end",
            node="llm_call",
            request_id=request_id,
            session_id=state.session_id,
            latency_ms=round(latency_ms, 2),
            text_len=len(llm_text),
        )

        return {
            "llm_text": llm_text,
            "llm_meta": {
                "model": provider.default_model,
                "latency_ms": latency_ms,
                "request_id": request_id,
            },
        }
    except Exception as exc:
        logger.error(
            "orchestrator.node.error",
            node="llm_call",
            request_id=request_id,
            error=str(exc),
        )
        return {
            "error": f"LLM call failed: {exc}",
            "llm_text": "抱歉，我暂时无法处理您的请求，请稍后再试。",
            "llm_meta": {
                "model": provider.default_model,
                "latency_ms": (time.perf_counter() - t0) * 1000,
                "request_id": request_id,
                "error": str(exc),
            },
        }
