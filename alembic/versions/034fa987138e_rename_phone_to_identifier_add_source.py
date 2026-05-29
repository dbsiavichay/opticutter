"""rename phone to identifier and add source

Revision ID: 034fa987138e
Revises: 6d5e6e6b2bff
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "034fa987138e"
down_revision: Union[str, None] = "6d5e6e6b2bff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("clients", "phone", new_column_name="identifier")
    op.add_column("clients", sa.Column("source", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "source")
    op.alter_column("clients", "identifier", new_column_name="phone")
