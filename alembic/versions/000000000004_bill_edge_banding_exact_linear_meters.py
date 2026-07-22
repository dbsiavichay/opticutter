"""bill edge banding by exact linear meters, no rounding

Revision ID: 000000000004
Revises: 000000000003
Create Date: 2026-07-21 13:38:50.196833

Edge banding used to be billed rounded up to the whole meter
(``math.ceil(net + waste)``); it's now billed exactly (``net + waste``, no
rounding), so ``order_lines.quantity`` must hold fractional linear meters for
edge-banding lines (still whole units for board lines).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "000000000004"
down_revision: Union[str, None] = "000000000003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "order_lines",
        "quantity",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "order_lines",
        "quantity",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
