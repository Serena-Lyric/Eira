"""init pgvector and schema_version

Revision ID: 0001
Revises:
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "schema_version",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("note", sa.String(255), nullable=True),
    )
    op.execute("INSERT INTO schema_version(note) VALUES ('phase 0 init')")


def downgrade() -> None:
    op.drop_table("schema_version")
