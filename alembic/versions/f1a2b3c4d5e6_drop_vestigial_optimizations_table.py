"""drop vestigial optimizations table

Revision ID: f1a2b3c4d5e6
Revises: 000000000001
Create Date: 2026-07-06 19:30:00.000000

The ``optimizations`` table has been cache-only (Redis, keyed by input hash)
since S2: nothing ever wrote to or read from it, and its ORM model was removed.
Drop the dead table. The downgrade recreates it exactly as the consolidated
initial schema did, so the migration is reversible.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "000000000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("optimizations")


def downgrade() -> None:
    op.create_table(
        "optimizations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("total_boards_used", sa.Integer(), nullable=False),
        sa.Column("total_boards_cost", sa.Float(), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("layouts", sa.JSON(), nullable=False),
        sa.Column("materials_summary", sa.JSON(), nullable=True),
        sa.Column("layout_groups", sa.JSON(), nullable=True),
        sa.Column("optimization_hash", sa.String(length=64), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
