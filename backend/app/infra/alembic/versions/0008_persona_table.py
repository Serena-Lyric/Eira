"""add personas table

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-08

Persona / character card table, aligned with SillyTavern V2 schema.
Supports public and user-scoped personas, default persona per user,
and optional links to avatar/live2d/voice assets.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "personas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(10), server_default=sa.text("'public'"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("personality", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("scenario", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("first_mes", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("mes_example", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("system_prompt", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("avatar_asset_id", sa.Integer(), nullable=True),
        sa.Column("live2d_asset_id", sa.Integer(), nullable=True),
        sa.Column("voice_id", sa.String(64), nullable=True),
        sa.Column("tags", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("disabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["avatar_asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["live2d_asset_id"], ["assets.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_personas_scope", "personas", ["scope", "disabled"])
    op.create_index("idx_personas_user", "personas", ["user_id"])
    # Partial unique index: only one default persona per user
    op.execute(
        """
        CREATE UNIQUE INDEX idx_personas_default
        ON personas (user_id, is_default)
        WHERE is_default = TRUE AND user_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("idx_personas_default", table_name="personas")
    op.drop_index("idx_personas_user", table_name="personas")
    op.drop_index("idx_personas_scope", table_name="personas")
    op.drop_table("personas")
