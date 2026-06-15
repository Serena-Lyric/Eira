from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, String, Integer, Text, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB

from app.domain.identity.models import Base


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(10), default="public")
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text, default="")
    personality: Mapped[str | None] = mapped_column(Text, default="")
    scenario: Mapped[str | None] = mapped_column(Text, default="")
    first_mes: Mapped[str | None] = mapped_column(Text, default="")
    mes_example: Mapped[str | None] = mapped_column(Text, default="")
    system_prompt: Mapped[str | None] = mapped_column(Text, default="")
    avatar_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    live2d_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    voice_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
