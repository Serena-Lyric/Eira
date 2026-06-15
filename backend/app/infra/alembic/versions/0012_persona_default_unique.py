"""persona default uniqueness — ensure only one default persona exists system-wide.

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-14
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = '0012'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Clean up duplicate defaults: keep the latest non-disabled default, unset others.
    # Only one persona should be is_default=True at any time.
    op.execute(sa.text("""
        UPDATE personas SET is_default = false
        WHERE is_default = true
          AND id NOT IN (
            SELECT id FROM personas
            WHERE is_default = true AND disabled = false
            ORDER BY updated_at DESC LIMIT 1
          )
    """))

    # Also unset defaults on disabled personas
    op.execute(sa.text("""
        UPDATE personas SET is_default = false
        WHERE is_default = true AND disabled = true
    """))

    # Partial unique index: at most one enabled persona can be default
    op.create_index(
        'uq_persona_default_active',
        'personas',
        ['is_default'],
        unique=True,
        postgresql_where=sa.text('is_default = true AND disabled = false'),
    )


def downgrade() -> None:
    op.drop_index('uq_persona_default_active', table_name='personas')
