"""make order_lines/order_pieces product_id nullable

Permite órdenes con materiales fuera del catálogo (retazos/manual), que se
resuelven a ``product_id = NULL`` y se identifican por ``product_code``/``product_name``.

Revision ID: e1f2a3b4c5d6
Revises: d2e3f4a5b6c7
Create Date: 2026-06-11 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ``batch_alter_table`` es obligatorio para SQLite (dev), que no soporta
    # ALTER COLUMN directo; en Postgres (prod) se traduce a un ALTER nativo.
    with op.batch_alter_table("order_lines") as batch_op:
        batch_op.alter_column("product_id", existing_type=sa.Integer(), nullable=True)
    with op.batch_alter_table("order_pieces") as batch_op:
        batch_op.alter_column("product_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("order_pieces") as batch_op:
        batch_op.alter_column("product_id", existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table("order_lines") as batch_op:
        batch_op.alter_column("product_id", existing_type=sa.Integer(), nullable=False)
