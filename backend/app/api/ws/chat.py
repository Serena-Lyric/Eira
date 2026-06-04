"""WebSocket endpoint /ws/chat — drives the orchestrator and streams tokens."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from pydantic import ValidationError

from app.core.config import get_settings, LlmSettings
from app.capabilities.llm.factory import create_llm_provider
from app.capabilities.llm.base import BaseLLMProvider
from app.domain.identity.models import User
from app.orchestrator.state import ChatState
from app.orchestrator.graph import build_graph
from app.orchestrator.nodes import safety_in, safety_out
from app.domain.conversation.repository import ConversationRepository
from app.domain.conversation.models import ChatSession, ChatMessage
from app.domain.identity.models import User as UserModel

from .messages import (
    UserTextIn,
    StateOut,
    TokenOut,
    ActionOut,
    DoneOut,
    ErrorOut,
    extract_action_tags,
    strip_action_tags,
    ACTION_TAG_MAP,
)

logger = structlog.get_logger(__name__)

router = APIRouter()

# In-memory provider cache (cleared on config change)
_provider_cache: dict[str, BaseLLMProvider] = {}


def _get_provider(settings: LlmSettings) -> BaseLLMProvider:
    """Return a cached or new provider instance."""
    key = f"{settings.provider}:{settings.model}"
    if key not in _provider_cache:
        _provider_cache[key] = create_llm_provider(settings)
    return _provider_cache[key]


async def _process_user_text(
    ws: WebSocket,
    msg: UserTextIn,
    provider: BaseLLMProvider,
    user: User,
) -> None:
    """Run the orchestrator graph and stream results back over WS."""
    t0 = time.perf_counter()
    session_id = msg.session_id

    # Parse user text → extract action tags → strip for LLM
    clean_text = strip_action_tags(msg.text)

    state = ChatState(
        session_id=session_id,
        user_id=str(user.id),
        user_text=clean_text,
        persona_prompt="你是一个友好的AI导游助手，名字叫'Eira'。请用中文回复，语气亲切自然、热情开朗。\n\n你可以在回复中插入以下动作标记来触发Live2D角色动画：\n- [wave] — 挥手（用于打招呼）\n- [nod] — 点头（用于表示同意或确认）\n- [happy] — 开心（用于表达愉快或称赞）\n\n动作标记应该自然地出现在对话中，不要滥用。每轮对话最多使用1-2个标记。",
    )

    await ws.send_json(StateOut(phase="thinking").model_dump())

    try:
        graph = build_graph(provider, safety_in.safety_in, safety_out.safety_out)

        # We need to stream tokens. Since the current graph collects the full
        # response, we split the llm_text into pseudo-tokens for streaming.
        # In a production system we'd integrate streaming at the node level.
        t_stream_start = time.perf_counter()

        # Run the graph
        result: ChatState = await graph.ainvoke(state)

        if result.error:
            await ws.send_json(
                ErrorOut(code="llm_error", detail=result.error).model_dump()
            )
            await ws.send_json(StateOut(phase="error").model_dump())
            return

        full_text: str = result.llm_text
        await ws.send_json(StateOut(phase="streaming").model_dump())

        # Stream token-by-token (character chunks for Chinese)
        # Extract action tags first so we know when to emit action frames
        tags_found: list[str] = extract_action_tags(full_text)
        tags_emitted: set[int] = set()  # track tag indices already emitted
        display_text = strip_action_tags(full_text)

        # Emit action frames for each tag found
        for tag in tags_found:
            motion = ACTION_TAG_MAP.get(tag, "TapBody")
            await ws.send_json(ActionOut(tag=motion).model_dump())
            # Small delay so frontend can process action before tokens resume
            await asyncio.sleep(0.05)

        # Stream display text in small chunks
        chunk_size = 2  # characters per token frame
        for i in range(0, len(display_text), chunk_size):
            chunk = display_text[i : i + chunk_size]
            if chunk:
                await ws.send_json(TokenOut(text=chunk).model_dump())
                # Brief yield to avoid overwhelming the WS buffer
                await asyncio.sleep(0.01)

        latency_ms = (time.perf_counter() - t0) * 1000
        await ws.send_json(
            DoneOut(
                message_id=None,  # would be set if we persisted via T1.3
                latency_ms=round(latency_ms, 2),
                tokens={"completion": len(full_text)},
            ).model_dump()
        )
        await ws.send_json(StateOut(phase="done").model_dump())

    except Exception as exc:
        logger.error("ws.chat.error", session_id=session_id, error=str(exc))
        await ws.send_json(
            ErrorOut(code="internal_error", detail=str(exc)).model_dump()
        )
        await ws.send_json(StateOut(phase="error").model_dump())


@router.websocket("/ws/chat")
async def websocket_chat(
    ws: WebSocket,
    token: str = Query(...),
):
    """WebSocket endpoint for chat.

    Authentication: Bearer token passed as ?token= query parameter.
    Protocol: see api/ws/messages.py for the full contract.
    """
    # Authenticate via WS query param
    try:
        from app.core.security import decode_token
        payload = decode_token(token)
        assert payload.get("kind") == "access"
        user_id = int(payload["sub"])
    except Exception:
        await ws.accept()
        await ws.send_json(
            ErrorOut(code="auth_failed", detail="invalid_token").model_dump()
        )
        await ws.close(code=4001)
        return

    await ws.accept()
    settings = get_settings().llm
    provider = _get_provider(settings)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json(
                    ErrorOut(code="bad_json", detail="invalid JSON").model_dump()
                )
                continue

            msg_type = data.get("type")

            if msg_type == "user_text":
                try:
                    msg = UserTextIn(**data)
                except ValidationError as e:
                    await ws.send_json(
                        ErrorOut(code="bad_message", detail=str(e)).model_dump()
                    )
                    continue
                await _process_user_text(ws, msg, provider, UserModel(id=user_id, email="", password_hash="", role="visitor"))

            elif msg_type == "interrupt":
                # Reserved for Phase 3 (ASR/TTS)
                logger.info("ws.chat.interrupt", user_id=user_id)
                # No-op for now

            else:
                await ws.send_json(
                    ErrorOut(
                        code="unknown_type",
                        detail=f"unknown message type: {msg_type}",
                    ).model_dump()
                )

    except WebSocketDisconnect:
        logger.info("ws.chat.disconnect", user_id=user_id)
    except Exception as exc:
        logger.error("ws.chat.fatal", user_id=user_id, error=str(exc))
        try:
            await ws.close(code=4000)
        except Exception:
            pass
