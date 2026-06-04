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

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """你是一个友好的AI导游助手，名字叫"Eira"。请用中文回复，语气亲切自然、热情开朗。

你可以在回复中插入以下动作标记来触发Live2D角色动画：
- [wave] — 挥手（用于打招呼）
- [nod] — 点头（用于表示同意或确认）
- [happy] — 开心（用于表达愉快或称赞）

动作标记应该自然地出现在对话中，不要滥用。每轮对话最多使用1-2个标记。

请根据用户的问题提供有帮助的旅行建议、路线推荐或信息解答。"""


async def llm_call(state: ChatState, provider: BaseLLMProvider) -> dict:
    """Call the LLM with conversation history and collect the response."""
    request_id = state.request_id or uuid.uuid4().hex[:12]
    t0 = time.perf_counter()

    messages: list[dict] = [
        {"role": "system", "content": state.persona_prompt or _SYSTEM_PROMPT},
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
