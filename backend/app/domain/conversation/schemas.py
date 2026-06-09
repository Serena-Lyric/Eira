"""Pydantic schemas for conversation API."""

from datetime import datetime
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    persona_id: str | None = None
    title: str | None = None


class SessionOut(BaseModel):
    id: int
    user_id: int
    persona_id: str | None = None
    title: str | None = None
    created_at: datetime
    ended_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    audio_oss_key: str | None = None
    metadata_json: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationList(BaseModel):
    sessions: list[SessionOut]
    total: int
