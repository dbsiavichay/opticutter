"""add materials_summary to optimizations

Revision ID: a1b2c3d4e5f6
Revises: 034fa987138e
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "034fa987138e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "optimizations",
        sa.Column("materials_summary", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("optimizations", "materials_summary")
