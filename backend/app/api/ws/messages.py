"""Pydantic message schemas for the WebSocket chat protocol.

Protocol contract (locked per spec):

client → server:
  {"type":"user_text","session_id":"...","text":"...","ts":...}
  {"type":"interrupt"}                      # reserved phase 3

server → client:
  {"type":"state","phase":"thinking"}
  {"type":"token","text":"..."}             # streaming delta
  {"type":"action","tag":"wave"}            # Live2D motion trigger
  {"type":"done","message_id":123,"latency_ms":...,"tokens":{...}}
  {"type":"error","code":"...","detail":"..."}
"""

import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator

# ── Inbound (client → server) ────────────────────────────────────


class UserTextIn(BaseModel):
    type: Literal["user_text"]
    session_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=4096)
    ts: float | None = None


class InterruptIn(BaseModel):
    type: Literal["interrupt"]


# ── Outbound (server → client) ───────────────────────────────────


class StateOut(BaseModel):
    type: Literal["state"] = "state"
    phase: Literal["thinking", "streaming", "done", "error"]


class TokenOut(BaseModel):
    type: Literal["token"] = "token"
    text: str


class ActionOut(BaseModel):
    type: Literal["action"] = "action"
    tag: str  # wave / nod / happy


class DoneOut(BaseModel):
    type: Literal["done"] = "done"
    message_id: int | None = None
    latency_ms: float | None = None
    tokens: dict | None = None  # {"prompt": N, "completion": M}


class ErrorOut(BaseModel):
    type: Literal["error"] = "error"
    code: str
    detail: str


# ── Action tag parsing ───────────────────────────────────────────

_ACTION_TAG_RE = re.compile(r"\[(wave|nod|happy)\]")

# Tags mapped to motion groups (matches useActionParser.ts + available model motions)
# hiyori_pro_zh groups: Idle, Flick, FlickDown, FlickUp, Tap, Tap@Body, Flick@Body
# mao_pro_zh groups: Idle, "" (default)
ACTION_TAG_MAP: dict[str, str] = {
    "wave": "Flick",
    "nod": "FlickDown",
    "happy": "Tap",
    "greet": "FlickUp",
    "tap": "Tap@Body",
    "idle": "Idle",
}


def extract_action_tags(text: str) -> list[str]:
    """Return list of action tags found in text (e.g. ['wave', 'nod'])."""
    return _ACTION_TAG_RE.findall(text)


def strip_action_tags(text: str) -> str:
    """Remove action tags from display text."""
    return _ACTION_TAG_RE.sub("", text).strip()
