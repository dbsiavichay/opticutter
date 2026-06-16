"""add preorders and relocate review links from orders

Revision ID: b1c2d3e4f5a6
Revises: 16073b8b2b20
Create Date: 2026-06-15 17:00:00.000000

El enlace y la confirmación del cliente se mueven de la orden (inmutable) a la
pre-orden (mutable): se crean ``preorders`` + ``preorder_review_links`` y se
retira ``order_review_links`` (la orden ahora nace 'confirmed').
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "16073b8b2b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "preorders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("materials", sa.JSON(), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "preorder_review_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("preorder_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("used_meta", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["preorder_id"], ["preorders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_preorder_review_links_preorder_id",
        "preorder_review_links",
        ["preorder_id"],
    )
    # La revisión del cliente ya no vive en la orden.
    op.drop_index("ix_order_review_links_order_id", table_name="order_review_links")
    op.drop_table("order_review_links")


def downgrade() -> None:
    op.create_table(
        "order_review_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("used_meta", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_order_review_links_order_id", "order_review_links", ["order_id"]
    )
    op.drop_index(
        "ix_preorder_review_links_preorder_id", table_name="preorder_review_links"
    )
    op.drop_table("preorder_review_links")
    op.drop_table("preorders")
