"""WebSocket endpoint /ws/voice — voice-driven chat with ASR + LLM streaming."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import ValidationError

from app.core.config import get_settings
from app.capabilities.asr.base import BaseASRProvider
from app.capabilities.asr.factory import create_asr_provider
from app.capabilities.llm.base import BaseLLMProvider
from app.capabilities.llm.factory import create_llm_provider
from app.orchestrator.state import ChatState
from app.orchestrator.graph import build_graph
from app.orchestrator.nodes import safety_in, safety_out
from app.orchestrator.nodes.llm_call import llm_call as _llm_call_node

from .messages import (
    TokenOut,
    ActionOut,
    extract_action_tags,
    strip_action_tags,
    ACTION_TAG_MAP,
)
from .voice_messages import (
    VoiceStartIn,
    VoiceEndIn,
    VoiceBargeInIn,
    AsrPartialOut,
    AsrFinalOut,
    VoiceDoneOut,
    VoiceErrorOut,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/voice")
async def websocket_voice(
    ws: WebSocket,
    token: str = Query(...),
):
    """WebSocket endpoint for voice-driven chat.

    Authentication: Bearer token passed as ?token= query parameter.
    Protocol: see api/ws/voice_messages.py for the full contract.

    Flow:
        1. Client sends voice.start → server initializes ASR stream
        2. Client sends binary audio frames → ASR produces partial results
        3. Client sends voice.end → ASR finalizes → orchestrator runs → tokens streamed
        4. Client sends voice.barge_in → cancel current processing
    """
    # Authenticate
    try:
        from app.core.security import decode_token
        payload = decode_token(token)
        assert payload.get("kind") == "access"
        user_id = int(payload["sub"])
    except Exception:
        await ws.accept()
        await ws.send_json(
            VoiceErrorOut(code="auth_failed", detail="invalid_token").model_dump()
        )
        await ws.close(code=4001)
        return

    await ws.accept()

    settings = get_settings()
    asr_provider = create_asr_provider(settings.asr)
    llm_provider = create_llm_provider(settings.llm)

    # State for the current voice session
    audio_buffer: list[bytes] = []
    asr_active = False
    current_lang = "zh"
    cancel_event = asyncio.Event()

    async def flush_audio_and_recognize() -> str:
        """Feed buffered audio to ASR and return final recognized text."""
        nonlocal audio_buffer, asr_active, cancel_event

        async def audio_iter():
            for chunk in audio_buffer:
                yield chunk

        last_partial = ""
        full_text = ""
        async for evt in asr_provider.stream(audio_iter(), lang=current_lang):
            if cancel_event.is_set():
                break
            if not evt.is_final:
                last_partial = evt.text
                await ws.send_json(AsrPartialOut(text=evt.text).model_dump())
            else:
                full_text = evt.text
                await ws.send_json(AsrFinalOut(text=evt.text).model_dump())

        audio_buffer.clear()
        asr_active = False
        return full_text or last_partial

    async def run_orchestrator(text: str) -> None:
        """Run the orchestrator graph and stream results."""
        t0 = time.perf_counter()

        clean_text = strip_action_tags(text)
        state = ChatState(
            session_id=f"voice-{user_id}-{int(t0)}",
            user_id=str(user_id),
            user_text=clean_text,
        )

        try:
            graph = build_graph(llm_provider, safety_in.safety_in, safety_out.safety_out)
            result: ChatState = await graph.ainvoke(state)

            if result.error:
                await ws.send_json(
                    VoiceErrorOut(code="llm_error", detail=result.error).model_dump()
                )
                return

            full_text: str = result.llm_text

            # Emit action tags
            tags_found = extract_action_tags(full_text)
            for tag in tags_found:
                if cancel_event.is_set():
                    return
                motion = ACTION_TAG_MAP.get(tag, "TapBody")
                await ws.send_json(ActionOut(tag=motion).model_dump())
                await asyncio.sleep(0.05)

            # Stream text tokens
            display_text = strip_action_tags(full_text)
            chunk_size = 2
            for i in range(0, len(display_text), chunk_size):
                if cancel_event.is_set():
                    return
                chunk = display_text[i : i + chunk_size]
                if chunk:
                    await ws.send_json(TokenOut(text=chunk).model_dump())
                    await asyncio.sleep(0.01)

            latency_ms = (time.perf_counter() - t0) * 1000
            await ws.send_json(
                VoiceDoneOut(
                    latency_ms=round(latency_ms, 2),
                    tokens={"completion": len(full_text)},
                    sources=result.knowledge_sources if result.knowledge_sources else None,
                ).model_dump()
            )

        except Exception as exc:
            logger.error("ws.voice.orchestrator.error", user_id=user_id, error=str(exc))
            await ws.send_json(
                VoiceErrorOut(code="internal_error", detail=str(exc)).model_dump()
            )

    try:
        while True:
            raw = await ws.receive()

            # Handle binary (audio) frames
            if "bytes" in raw:
                audio_chunk = raw["bytes"]
                if asr_active:
                    audio_buffer.append(audio_chunk)
                continue

            # Handle text (JSON control) messages
            if "text" not in raw:
                continue

            try:
                data = json.loads(raw["text"])
            except json.JSONDecodeError:
                await ws.send_json(
                    VoiceErrorOut(code="bad_json", detail="invalid JSON").model_dump()
                )
                continue

            msg_type = data.get("type")

            if msg_type == "voice.start":
                try:
                    msg = VoiceStartIn(**data)
                except ValidationError as e:
                    await ws.send_json(
                        VoiceErrorOut(code="bad_message", detail=str(e)).model_dump()
                    )
                    continue
                asr_active = True
                current_lang = msg.lang
                audio_buffer.clear()
                cancel_event.clear()
                logger.info("ws.voice.start", user_id=user_id, lang=current_lang)

            elif msg_type == "voice.end":
                if not asr_active:
                    continue
                text = await flush_audio_and_recognize()
                if text and not cancel_event.is_set():
                    await run_orchestrator(text)

            elif msg_type == "voice.barge_in":
                cancel_event.set()
                asr_active = False
                audio_buffer.clear()
                logger.info("ws.voice.barge_in", user_id=user_id)

            else:
                await ws.send_json(
                    VoiceErrorOut(
                        code="unknown_type",
                        detail=f"unknown message type: {msg_type}",
                    ).model_dump()
                )

    except WebSocketDisconnect:
        logger.info("ws.voice.disconnect", user_id=user_id)
    except Exception as exc:
        logger.error("ws.voice.fatal", user_id=user_id, error=str(exc))
        try:
            await ws.close(code=4000)
        except Exception:
            pass
    finally:
        await asr_provider.close()
