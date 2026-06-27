"""add order dispatched state columns

Revision ID: f3a9c1d8e240
Revises: 7bf6a28b53ac
Create Date: 2026-06-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3a9c1d8e240"
down_revision: Union[str, None] = "7bf6a28b53ac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Despacho (entrega física al cliente): se congela al transicionar a
    # 'despachado'. Las órdenes existentes quedan en NULL (no se despacharon aún).
    # El estado 'despachado' no necesita migración de enum: status es String(32).
    op.add_column("orders", sa.Column("dispatched_at", sa.DateTime(), nullable=True))
    op.add_column("orders", sa.Column("dispatched_by", sa.Integer(), nullable=True))
    op.add_column(
        "orders",
        sa.Column("dispatched_by_label", sa.String(length=128), nullable=True),
    )
    # FK al usuario que registró el despacho (mismo patrón que assigned_to_id).
    op.create_foreign_key(
        "fk_orders_dispatched_by_users",
        "orders",
        "users",
        ["dispatched_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_orders_dispatched_by_users", "orders", type_="foreignkey")
    op.drop_column("orders", "dispatched_by_label")
    op.drop_column("orders", "dispatched_by")
    op.drop_column("orders", "dispatched_at")
