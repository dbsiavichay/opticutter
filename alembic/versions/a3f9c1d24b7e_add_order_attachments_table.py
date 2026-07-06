"""add order attachments table

Revision ID: a3f9c1d24b7e
Revises: 062613728d5e
Create Date: 2026-07-04 10:00:00.000000

Order attachments (anexos): PDFs/screenshots attached to an order while it is
still open (not completed/dispatched/cancelled). Only metadata lives here; the
bytes stay on local disk under ``config.ATTACHMENTS_DIR`` at ``stored_key``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f9c1d24b7e'
down_revision: Union[str, None] = '062613728d5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'order_attachments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('stored_key', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=128), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stored_key'),
    )
    op.create_index(
        op.f('ix_order_attachments_order_id'),
        'order_attachments',
        ['order_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_order_attachments_order_id'), table_name='order_attachments'
    )
    op.drop_table('order_attachments')
