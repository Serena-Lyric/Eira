"""add audit_log table

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-08

Audit trail for all admin mutating operations (POST/PUT/PATCH/DELETE).
Retention policy: 180 days (handled at query time or via periodic cleanup).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("path", sa.String(256), nullable=False),
        sa.Column("method", sa.String(8), nullable=False),
        sa.Column("body_summary", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_log_created", "audit_log", ["created_at"], postgresql_using="brin")
    op.create_index("idx_audit_log_user", "audit_log", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_audit_log_user", table_name="audit_log")
    op.drop_index("idx_audit_log_created", table_name="audit_log")
    op.drop_table("audit_log")
