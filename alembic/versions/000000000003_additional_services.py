"""additional services catalog + quote/order service lines

Revision ID: 000000000003
Revises: 000000000002
Create Date: 2026-07-16 00:00:00.000000

Adds the ``additional_services`` catalog (name + default price + active flag) and
the plumbing to bill services on top of a quote/order:
- ``preorders.additional_services`` (JSON list of service lines, editable).
- ``orders.additional_services_total`` (frozen sum, billed after the discount;
  the per-line breakdown lives inside ``orders.optimization_snapshot``).
Follows the metadata naming convention (SET NULL for audit FKs).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "000000000003"
down_revision: Union[str, None] = "000000000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "additional_services",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "price >= 0", name=op.f("ck_additional_services_price_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_additional_services_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_additional_services_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_additional_services")),
        sa.UniqueConstraint("name", name=op.f("uq_additional_services_name")),
    )

    op.add_column(
        "preorders",
        sa.Column(
            "additional_services",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )

    op.add_column(
        "orders",
        sa.Column(
            "additional_services_total",
            sa.Float(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "additional_services_total_non_negative",
        "orders",
        "additional_services_total >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_orders_additional_services_total_non_negative"),
        "orders",
        type_="check",
    )
    op.drop_column("orders", "additional_services_total")
    op.drop_column("preorders", "additional_services")
    op.drop_table("additional_services")
