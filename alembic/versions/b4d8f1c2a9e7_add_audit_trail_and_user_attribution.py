"""add audit trail and user attribution

Revision ID: b4d8f1c2a9e7
Revises: 862298678742
Create Date: 2026-06-17 12:00:00.000000

Atribución de usuario y auditoría transversal:

- ``created_by``/``updated_by`` (FK nullable a ``users``) en catálogo y agregados,
  más ``created_at``/``updated_at`` donde faltaban (clients, products, settings).
- Atribución real del actor en el historial de órdenes (``actor_user_id`` +
  ``actor_label``) y quién cortó cada pieza (``cut_by`` + ``cut_by_label``).
- Nueva tabla ``preorder_status_history`` (espejo de ``order_status_history``).

Las FK son nullable: las acciones de cliente/sistema y las filas previas a esta
funcionalidad quedan en NULL. Se usa ``batch_alter_table`` para que SQLite pueda
añadir columnas con FK (copia-y-mueve); en Postgres es un ALTER directo.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4d8f1c2a9e7"
down_revision: Union[str, None] = "862298678742"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Convención para nombrar las constraints reflejadas al recrear la tabla en SQLite.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _batch(table: str):
    """``batch_alter_table`` con la convención de nombres aplicada."""
    return op.batch_alter_table(table, naming_convention=NAMING_CONVENTION)


def _user_fk(table: str, name: str) -> sa.Column:
    """Columna FK nullable a ``users.id`` con nombre explícito (lo exige el batch)."""
    return sa.Column(
        name,
        sa.Integer(),
        sa.ForeignKey("users.id", name=f"fk_{table}_{name}_users"),
        nullable=True,
    )


def upgrade() -> None:
    # Catálogo y agregados: timestamps faltantes + atribución created_by/updated_by.
    with _batch("clients") as batch:
        batch.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        batch.add_column(_user_fk("clients", "created_by"))
        batch.add_column(_user_fk("clients", "updated_by"))

    with _batch("products") as batch:
        batch.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        batch.add_column(_user_fk("products", "created_by"))
        batch.add_column(_user_fk("products", "updated_by"))

    with _batch("settings") as batch:
        batch.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
        batch.add_column(_user_fk("settings", "created_by"))
        batch.add_column(_user_fk("settings", "updated_by"))

    with _batch("orders") as batch:
        batch.add_column(_user_fk("orders", "created_by"))

    with _batch("preorders") as batch:
        batch.add_column(_user_fk("preorders", "created_by"))
        batch.add_column(_user_fk("preorders", "updated_by"))

    # Historial de órdenes: actor real (FK + snapshot legible).
    with _batch("order_status_history") as batch:
        batch.add_column(_user_fk("order_status_history", "actor_user_id"))
        batch.add_column(sa.Column("actor_label", sa.String(length=128), nullable=True))

    # Plan de corte: quién cortó cada pieza.
    with _batch("order_placed_pieces") as batch:
        batch.add_column(_user_fk("order_placed_pieces", "cut_by"))
        batch.add_column(sa.Column("cut_by_label", sa.String(length=128), nullable=True))

    # Historial de pre-órdenes (no existía): espejo de order_status_history.
    op.create_table(
        "preorder_status_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "preorder_id", sa.Integer(), sa.ForeignKey("preorders.id"), nullable=False
        ),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=32), nullable=True),
        sa.Column(
            "actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("actor_label", sa.String(length=128), nullable=True),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_preorder_status_history_preorder_id",
        "preorder_status_history",
        ["preorder_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_preorder_status_history_preorder_id",
        table_name="preorder_status_history",
    )
    op.drop_table("preorder_status_history")

    with _batch("order_placed_pieces") as batch:
        batch.drop_column("cut_by_label")
        batch.drop_column("cut_by")

    with _batch("order_status_history") as batch:
        batch.drop_column("actor_label")
        batch.drop_column("actor_user_id")

    with _batch("preorders") as batch:
        batch.drop_column("updated_by")
        batch.drop_column("created_by")

    with _batch("orders") as batch:
        batch.drop_column("created_by")

    with _batch("settings") as batch:
        batch.drop_column("updated_by")
        batch.drop_column("created_by")
        batch.drop_column("created_at")

    with _batch("products") as batch:
        batch.drop_column("updated_by")
        batch.drop_column("created_by")
        batch.drop_column("updated_at")
        batch.drop_column("created_at")

    with _batch("clients") as batch:
        batch.drop_column("updated_by")
        batch.drop_column("created_by")
        batch.drop_column("updated_at")
        batch.drop_column("created_at")
