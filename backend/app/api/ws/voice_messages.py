"""Pydantic message schemas for the WebSocket voice protocol.

Protocol contract:

client → server:
  Binary frames: audio data (WebM/Opus chunks)
  {"type": "voice.start", "lang": "zh"}
  {"type": "voice.end"}
  {"type": "voice.barge_in"}

server → client:
  {"type": "asr.partial", "text": "..."}
  {"type": "asr.final", "text": "最终文本"}
  {"type": "chat.token", "text": "..."}
  {"type": "chat.action", "tag": "wave"}
  {"type": "chat.done", "message_id": ..., "latency_ms": ...}
  {"type": "error", "code": "...", "detail": "..."}
  Binary frames: TTS audio chunks (from T3.5)
"""

from typing import Literal

from pydantic import BaseModel, Field


# ── Inbound (client → server) ─────────────────────────────────────────


class VoiceStartIn(BaseModel):
    type: Literal["voice.start"] = "voice.start"
    lang: str = Field(default="zh", max_length=8)


class VoiceEndIn(BaseModel):
    type: Literal["voice.end"] = "voice.end"


class VoiceBargeInIn(BaseModel):
    type: Literal["voice.barge_in"] = "voice.barge_in"


# ── Outbound (server → client) ────────────────────────────────────────


class AsrPartialOut(BaseModel):
    type: Literal["asr.partial"] = "asr.partial"
    text: str


class AsrFinalOut(BaseModel):
    type: Literal["asr.final"] = "asr.final"
    text: str


class VoiceDoneOut(BaseModel):
    type: Literal["chat.done"] = "chat.done"
    message_id: int | None = None
    latency_ms: float | None = None
    tokens: dict | None = None
    sources: list[dict] | None = None


class VoiceErrorOut(BaseModel):
    type: Literal["error"] = "error"
    code: str
    detail: str
