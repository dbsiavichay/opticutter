"""add half_board_markup_pct to settings

Revision ID: 062613728d5e
Revises: 2066bce4a9e8
Create Date: 2026-07-03 19:14:03.459936

Configurable markup applied over price/2 when billing a half catalog board
(admin-editable via PATCH /settings/cutting, same pattern as
edge_banding_waste_factor). Existing rows default to 0.10 (+10%).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '062613728d5e'
down_revision: Union[str, None] = '2066bce4a9e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "half_board_markup_pct",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.10"),
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "half_board_markup_pct")
