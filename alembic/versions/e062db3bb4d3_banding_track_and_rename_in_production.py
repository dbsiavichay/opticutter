"""banding track and rename in_production to queued

Revision ID: e062db3bb4d3
Revises: d3397779e235
Create Date: 2026-06-23 20:24:39.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e062db3bb4d3"
down_revision: Union[str, None] = "d3397779e235"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Pista paralela de canteado en la orden. Las órdenes existentes quedan en
    # 'not_applicable' (no se gatea el canteado retroactivamente; arranca limpio).
    op.add_column(
        "orders",
        sa.Column(
            "banding_status",
            sa.String(length=16),
            nullable=False,
            server_default="not_applicable",
        ),
    )
    op.add_column(
        "orders", sa.Column("banding_started_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("banding_started_by", sa.Integer(), nullable=True)
    )
    op.add_column(
        "orders",
        sa.Column("banding_started_by_label", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "orders", sa.Column("banding_finished_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("banding_finished_by", sa.Integer(), nullable=True)
    )
    op.add_column(
        "orders",
        sa.Column("banding_finished_by_label", sa.String(length=128), nullable=True),
    )
    # FKs al usuario que registró inicio/fin del canteado (mismo patrón que assigned_to_id).
    op.create_foreign_key(
        "fk_orders_banding_started_by_users",
        "orders",
        "users",
        ["banding_started_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_orders_banding_finished_by_users",
        "orders",
        "users",
        ["banding_finished_by"],
        ["id"],
    )

    # Renombre de estado 'in_production' → 'queued' (etiqueta "En cola"). Sin enum/
    # check constraints (la columna es String): basta un UPDATE de las filas vivas
    # y del historial de transiciones.
    op.execute("UPDATE orders SET status = 'queued' WHERE status = 'in_production'")
    op.execute(
        "UPDATE order_status_history SET from_status = 'queued' "
        "WHERE from_status = 'in_production'"
    )
    op.execute(
        "UPDATE order_status_history SET to_status = 'queued' "
        "WHERE to_status = 'in_production'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE order_status_history SET to_status = 'in_production' "
        "WHERE to_status = 'queued'"
    )
    op.execute(
        "UPDATE order_status_history SET from_status = 'in_production' "
        "WHERE from_status = 'queued'"
    )
    op.execute("UPDATE orders SET status = 'in_production' WHERE status = 'queued'")
    op.drop_constraint(
        "fk_orders_banding_finished_by_users", "orders", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_orders_banding_started_by_users", "orders", type_="foreignkey"
    )
    op.drop_column("orders", "banding_finished_by_label")
    op.drop_column("orders", "banding_finished_by")
    op.drop_column("orders", "banding_finished_at")
    op.drop_column("orders", "banding_started_by_label")
    op.drop_column("orders", "banding_started_by")
    op.drop_column("orders", "banding_started_at")
    op.drop_column("orders", "banding_status")
