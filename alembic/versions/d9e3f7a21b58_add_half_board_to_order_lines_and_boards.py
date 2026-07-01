"""add half_board to order lines and boards

Revision ID: d9e3f7a21b58
Revises: 000000000001
Create Date: 2026-06-30

Half boards: catalog sheets whose content fits in a half board are billed at
half price and materialized as a half in the cutting plan. Flags each billing
line and each physical board as a half (``half_board``).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9e3f7a21b58"
down_revision: Union[str, None] = "000000000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "order_lines",
        sa.Column(
            "half_board",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "order_boards",
        sa.Column(
            "half_board",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("order_boards", "half_board")
    op.drop_column("order_lines", "half_board")
