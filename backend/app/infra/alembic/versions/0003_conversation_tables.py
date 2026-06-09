"""conversation tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_session",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("persona_id", sa.String(64), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_chat_session_user_id", "chat_session", ["user_id"])

    op.create_table(
        "chat_message",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.BigInteger,
            sa.ForeignKey("chat_session.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("audio_oss_key", sa.String(512), nullable=True),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_chat_message_session_id", "chat_message", ["session_id"])
    op.create_check_constraint(
        "ck_chat_message_role",
        "chat_message",
        "role IN ('user','assistant')",
    )


def downgrade() -> None:
    op.drop_table("chat_message")
    op.drop_table("chat_session")
