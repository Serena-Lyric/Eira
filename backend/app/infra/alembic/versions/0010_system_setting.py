"""add system_settings table

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-08

Key-value settings table for system-wide configuration.
Stores LLM defaults, quotas, security patterns, voice config, etc.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
