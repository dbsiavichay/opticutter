"""add layout_groups to optimizations

Revision ID: b2c3d4e5f6a7
Revises: d4e5f6a7b8c9
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "optimizations",
        sa.Column("layout_groups", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("optimizations", "layout_groups")
