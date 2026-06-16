"""add settings singleton table

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-06-15 19:00:00.000000

Persiste la configuración única de la aplicación (parámetros de corte + datos de
empresa) que antes vivía solo en variables de entorno. Es una tabla singleton: la
fila ``id=1`` se siembra perezosamente desde ``config`` en la primera lectura, así
que la migración crea únicamente la tabla.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kerf", sa.Float(), nullable=False),
        sa.Column("top_trim", sa.Float(), nullable=False),
        sa.Column("bottom_trim", sa.Float(), nullable=False),
        sa.Column("left_trim", sa.Float(), nullable=False),
        sa.Column("right_trim", sa.Float(), nullable=False),
        sa.Column("edge_banding_waste_factor", sa.Float(), nullable=False),
        sa.Column("company_name", sa.String(length=128), nullable=False),
        sa.Column("company_tagline", sa.String(length=256), nullable=False),
        sa.Column("company_email", sa.String(length=128), nullable=False),
        sa.Column("company_phone", sa.String(length=128), nullable=False),
        sa.Column("company_branches", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("settings")
