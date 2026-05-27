"""users and roles

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=True),
        sa.Column(
            "role", sa.String(16), nullable=False, server_default="visitor"
        ),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="active"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_check_constraint(
        "ck_users_role", "users", "role IN ('visitor','admin')"
    )
    op.create_check_constraint(
        "ck_users_status", "users", "status IN ('active','disabled')"
    )


def downgrade() -> None:
    op.drop_table("users")
