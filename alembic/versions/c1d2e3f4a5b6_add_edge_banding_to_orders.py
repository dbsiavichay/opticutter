"""add edge banding to order lines and pieces

Revision ID: c1d2e3f4a5b6
Revises: a7b8c9d0e1f2
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tapacanto: metros exactos (con merma) en la línea de cobro y spec por pieza.
    op.add_column("order_lines", sa.Column("linear_m", sa.Float(), nullable=True))
    op.add_column("order_pieces", sa.Column("edges", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("order_pieces", "edges")
    op.drop_column("order_lines", "linear_m")
