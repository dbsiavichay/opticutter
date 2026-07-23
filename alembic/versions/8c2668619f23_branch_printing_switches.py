"""branch printing switches

Revision ID: 8c2668619f23
Revises: 000000000001
Create Date: 2026-07-23 03:28:03.272339

Per-branch switches for the print agent: whether the branch's shop has a thermal
label printer and/or a sheet printer. ``server_default = true`` so every existing
branch keeps printing exactly as before the deploy; the admin unticks the ones
with no hardware, and the enqueue then skips without rendering or spooling.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c2668619f23'
down_revision: Union[str, None] = '000000000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('branches', sa.Column('print_labels_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('branches', sa.Column('print_consolidated_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False))


def downgrade() -> None:
    op.drop_column('branches', 'print_consolidated_enabled')
    op.drop_column('branches', 'print_labels_enabled')
