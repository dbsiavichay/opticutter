"""add client_note to preorders

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-15 18:30:00.000000

Acción "solicitar cambios" del cliente: la pre-orden pasa a ``changes_requested``
y guarda la solicitud (texto libre) en ``client_note``.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "preorders", sa.Column("client_note", sa.String(length=512), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("preorders", "client_note")
