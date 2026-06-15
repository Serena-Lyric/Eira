"""WebSocket endpoint /ws/chat — drives the orchestrator and streams tokens."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from pydantic import ValidationError

from app.core.config import get_settings
from app.capabilities.llm.base import BaseLLMProvider
from app.capabilities.llm.provider_registry import (
    get_provider_registry,
    get_effective_llm_settings,
)
from app.domain.identity.models import User
from app.orchestrator.state import ChatState
from app.orchestrator.graph import build_graph
from app.orchestrator.nodes import safety_in, safety_out
from app.domain.conversation.repository import ConversationRepository
from app.domain.conversation.models import ChatSession, ChatMessage
from app.domain.identity.models import User as UserModel
from app.domain.persona.resolver import get_default_persona_prompt, DEFAULT_PERSONA_FALLBACK
from app.infra.db import get_session_factory

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

    # Load conversation history from DB
    history: list[dict[str, Any]] = []
    try:
        session_id_int = int(session_id)
        factory = get_session_factory()
        async with factory() as db_session:
            repo = ConversationRepository(db_session)
            msgs = await repo.list_messages(session_id_int, limit=20)
            history = [{"role": m.role, "content": m.content} for m in msgs[-20:]]
    except (ValueError, TypeError):
        logger.warning(
            "ws.chat.non_integer_session_id",
            session_id=session_id,
            user_id=user.id,
            detail="前端 fallback session_id 无法转为整数 — 历史记录不会加载。检查 createSession() 是否成功调用 REST API。",
        )

    # Resolve persona prompt: DB default persona > hardcoded fallback
    persona_prompt = await get_default_persona_prompt()
    if not persona_prompt:
        persona_prompt = DEFAULT_PERSONA_FALLBACK

    state = ChatState(
        session_id=session_id,
        user_id=str(user.id),
        user_text=clean_text,
        history=history,
        persona_prompt=persona_prompt,
    )

    await ws.send_json(StateOut(phase="thinking").model_dump())

    try:
        graph = build_graph(provider, safety_in.safety_in, safety_out.safety_out)

        # We need to stream tokens. Since the current graph collects the full
        # response, we split the llm_text into pseudo-tokens for streaming.
        # In a production system we'd integrate streaming at the node level.
        t_stream_start = time.perf_counter()

        # Run the graph
        result_dict = await graph.ainvoke(state)

        if result_dict.get("error"):
            await ws.send_json(
                ErrorOut(code="llm_error", detail=result_dict["error"]).model_dump()
            )
            await ws.send_json(StateOut(phase="error").model_dump())
            return

        full_text: str = result_dict.get("llm_text", "")
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
        # Use the persisted message ID from the graph's persist node
        persisted_msg_id = result_dict.get("assistant_message_id")
        await ws.send_json(
            DoneOut(
                message_id=int(persisted_msg_id) if persisted_msg_id else None,
                latency_ms=round(latency_ms, 2),
                tokens={"completion": len(full_text)},
                sources=result_dict.get("knowledge_sources") or None,
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

    # Load real user from DB (not a stub with empty email)
    user: UserModel
    try:
        factory = get_session_factory()
        async with factory() as db_session:
            from app.domain.identity.repository import UserRepository
            repo = UserRepository(db_session)
            u = await repo.get_by_id(user_id)
            if u:
                user = u
            else:
                user = UserModel(id=user_id, email=f"user-{user_id}@unknown", password_hash="", role="visitor")
    except Exception:
        user = UserModel(id=user_id, email=f"user-{user_id}@unknown", password_hash="", role="visitor")

    settings = await get_effective_llm_settings()
    provider = await get_provider_registry().get(settings)

    try:
        while True:
            raw = await ws.receive_text()

            # Per-connection message rate limit (§7.4)
            from app.core.rate_limit import get_ws_limiter
            if not await get_ws_limiter().check(str(user_id), "ws_chat"):
                await ws.send_json(
                    ErrorOut(code="rate_limited", detail="消息过于频繁，请稍后再试").model_dump()
                )
                continue

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
                await _process_user_text(ws, msg, provider, user)

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
        print(f"[chat.ws] WebSocketDisconnect user_id={user_id}", flush=True)
        logger.info("ws.chat.disconnect", user_id=user_id)
    except Exception as exc:
        print(f"[chat.ws] Fatal error user_id={user_id}: {exc}", flush=True)
        logger.error("ws.chat.fatal", user_id=user_id, error=str(exc))
        try:
            await ws.close(code=4000)
        except Exception as exc2:
            logger.debug("ws.close_failed", user_id=user_id, error=str(exc2))
