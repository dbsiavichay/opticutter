"""add price tiers and order discount

Revision ID: d3397779e235
Revises: 13f548649af1
Create Date: 2026-06-22 18:07:29.776130

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3397779e235'
down_revision: Union[str, None] = '13f548649af1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tarifas por defecto sembradas en la fila singleton de settings ya existente. Se
# inlinean (no se importan de config) para que la migración sea inmutable.
_DEFAULT_PRICE_TIERS = [
    {"code": "consumidor", "name": "Precio Consumidor", "rate": 0.0,
     "is_active": True, "sort_order": 1},
    {"code": "carpintero", "name": "Precio Carpintero", "rate": 0.02,
     "is_active": True, "sort_order": 2},
    {"code": "efectivo", "name": "Precio Efectivo", "rate": 0.05,
     "is_active": True, "sort_order": 3},
]


def upgrade() -> None:
    # Niveles de precio configurables en la fila singleton de settings.
    op.add_column("settings", sa.Column("price_tiers", sa.JSON(), nullable=True))
    # Nivel seleccionado en la cotización (vivo) y congelado en la orden + montos.
    op.add_column(
        "preorders",
        sa.Column(
            "price_tier_code",
            sa.String(length=32),
            nullable=False,
            server_default="consumidor",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "price_tier_code",
            sa.String(length=32),
            nullable=False,
            server_default="consumidor",
        ),
    )
    op.add_column(
        "orders",
        sa.Column("discount_rate", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "orders",
        sa.Column("discount_amount", sa.Float(), nullable=False, server_default="0"),
    )
    # Backfill: la fila singleton de settings ya existente recibe las tarifas por
    # defecto (si aún no existe, get_or_init la siembra al primer acceso). El construct
    # con tipo JSON serializa según el dialecto (SQLite/Postgres).
    settings_table = sa.table("settings", sa.column("price_tiers", sa.JSON()))
    op.execute(
        settings_table.update()
        .where(settings_table.c.price_tiers.is_(None))
        .values(price_tiers=_DEFAULT_PRICE_TIERS)
    )


def downgrade() -> None:
    op.drop_column("orders", "discount_amount")
    op.drop_column("orders", "discount_rate")
    op.drop_column("orders", "price_tier_code")
    op.drop_column("preorders", "price_tier_code")
    op.drop_column("settings", "price_tiers")
