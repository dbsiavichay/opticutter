"""drop orders.expires_at

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-06-16 10:00:00.000000

La vigencia (y el barrido perezoso de expiración) de la ORDEN se retiró: la
cotización mutable vive en la pre-orden y la orden nace ya ``confirmed``. La columna
``expires_at`` queda sin uso.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ``batch_alter_table`` es obligatorio para SQLite (dev), que no soporta DROP
    # COLUMN directo en versiones antiguas; en Postgres (prod) se traduce a un ALTER
    # nativo.
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_column("expires_at")


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))
