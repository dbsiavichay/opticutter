"""add remainders and cuts to order boards

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sobrantes (display + futuro inventario de retazos) y cortes de guillotina
    # (líneas de sierra para la vista de taller), copiados del snapshot al
    # materializar el plan de corte. Nulos en tableros previos a esta feature.
    op.add_column(
        "order_boards", sa.Column("remainders", sa.JSON(), nullable=True)
    )
    op.add_column("order_boards", sa.Column("cuts", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("order_boards", "cuts")
    op.drop_column("order_boards", "remainders")
