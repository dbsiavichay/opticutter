"""add phone and email to clients

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: el cliente se crea perezosamente (resolve) antes de conocerse el
    # celular; la obligatoriedad es regla de negocio al generar proforma/orden.
    op.add_column("clients", sa.Column("phone", sa.String(length=32), nullable=True))
    op.add_column("clients", sa.Column("email", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "email")
    op.drop_column("clients", "phone")
