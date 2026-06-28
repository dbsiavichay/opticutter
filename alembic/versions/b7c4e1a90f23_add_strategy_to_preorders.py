"""add strategy column to preorders

Revision ID: b7c4e1a90f23
Revises: f3a9c1d8e240
Create Date: 2026-06-27 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c4e1a90f23"
down_revision: Union[str, None] = "f3a9c1d8e240"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Heurística de acomodo elegida (default | longOffcuts). Las pre-órdenes
    # existentes quedan en 'default' (el comportamiento histórico) vía server_default.
    # No necesita migración de enum: la columna es String(32).
    op.add_column(
        "preorders",
        sa.Column(
            "strategy",
            sa.String(length=32),
            nullable=False,
            server_default="default",
        ),
    )


def downgrade() -> None:
    op.drop_column("preorders", "strategy")
