"""add cutting plan tables

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Plan de corte materializado: un tablero físico por layout del snapshot.
    op.create_table(
        "order_boards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("sheet_number", sa.Integer(), nullable=False),
        sa.Column("material_key", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("product_code", sa.String(length=64), nullable=True),
        sa.Column("product_name", sa.String(length=128), nullable=True),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("thickness", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_boards_order_id", "order_boards", ["order_id"])

    # Piezas colocadas: la unidad que el operario marca como cortada (cut_at).
    op.create_table(
        "order_placed_pieces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("board_id", sa.Integer(), nullable=False),
        sa.Column("piece_id", sa.String(length=160), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("original_width", sa.Float(), nullable=False),
        sa.Column("original_height", sa.Float(), nullable=False),
        sa.Column("rotated", sa.Boolean(), nullable=False),
        sa.Column("edges", sa.JSON(), nullable=True),
        sa.Column("cut_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["board_id"], ["order_boards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_order_placed_pieces_order_id", "order_placed_pieces", ["order_id"]
    )
    op.create_index(
        "ix_order_placed_pieces_board_id", "order_placed_pieces", ["board_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_order_placed_pieces_board_id", table_name="order_placed_pieces"
    )
    op.drop_index(
        "ix_order_placed_pieces_order_id", table_name="order_placed_pieces"
    )
    op.drop_table("order_placed_pieces")
    op.drop_index("ix_order_boards_order_id", table_name="order_boards")
    op.drop_table("order_boards")
