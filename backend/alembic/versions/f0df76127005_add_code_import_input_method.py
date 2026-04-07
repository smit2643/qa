"""add_code_import_input_method

Revision ID: f0df76127005
Revises: c0eddf2d26cd
Create Date: 2026-04-07 11:04:06.314250

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0df76127005'
down_revision: Union[str, Sequence[str], None] = 'c0eddf2d26cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL requires ALTER TYPE to add enum values
    op.execute("ALTER TYPE inputmethod ADD VALUE IF NOT EXISTS 'code_import'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values — downgrade is a no-op
    pass
