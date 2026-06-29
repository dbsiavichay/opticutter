"""add order payment method columns

Revision ID: c8f2d5b41a07
Revises: b7c4e1a90f23
Create Date: 2026-06-29 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8f2d5b41a07"
down_revision: Union[str, None] = "b7c4e1a90f23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Forma de pago (informativa): se congela al transicionar de 'confirmed' a
    # 'queued'. Una orden puede tener ambos métodos a la vez; el método usado se
    # infiere de qué monto es > 0. Las órdenes existentes quedan en NULL (los PDFs
    # omiten el bloque cuando no hay datos).
    op.add_column("orders", sa.Column("payment_cash_amount", sa.Float(), nullable=True))
    op.add_column(
        "orders", sa.Column("payment_credit_amount", sa.Float(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("orders", "payment_credit_amount")
    op.drop_column("orders", "payment_cash_amount")
