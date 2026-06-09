"""SQLAlchemy models for chat sessions and messages."""

from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, String, DateTime, ForeignKey, Text, func
from app.domain.identity.models import Base


class ChatSession(Base):
    __tablename__ = "chat_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    persona_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="session", order_by="ChatMessage.id"
    )


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chat_session.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    audio_oss_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")


class Feedback(Base):
    """用户提交的服务建议 / 反馈，Admin 面板可查看和回复。"""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    replied: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    replied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
