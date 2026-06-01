"""rename solution to layouts in optimizations

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("optimizations", "solution", new_column_name="layouts")


def downgrade() -> None:
    op.alter_column("optimizations", "layouts", new_column_name="solution")
