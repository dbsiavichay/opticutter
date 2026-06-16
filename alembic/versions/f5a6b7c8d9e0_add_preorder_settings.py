"""add preorder config columns to settings

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-06-16 10:05:00.000000

Mueve la config de la pre-orden (vigencia + tope de abiertas por cliente) de las
variables de entorno a la fila singleton de ``settings``, igual que los parámetros de
corte y el membrete. El ``server_default`` backfillea la fila existente a los defaults
(15 días / 5 abiertas); en runtime ``SettingsService.get_or_init`` siembra valores
explícitos desde ``config``.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "preorder_validity_days",
            sa.Integer(),
            nullable=False,
            server_default="15",
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "max_open_preorders_per_client",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "max_open_preorders_per_client")
    op.drop_column("settings", "preorder_validity_days")
