"""add disabled and deleted_at columns to users table

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-08

Extends the users table with:
  - disabled (bool): soft-disable a user account without deleting
  - deleted_at (timestamptz): soft-delete marker
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("disabled", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_users_active", "users", ["disabled", "deleted_at"])


def downgrade() -> None:
    op.drop_index("idx_users_active", table_name="users")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "disabled")
