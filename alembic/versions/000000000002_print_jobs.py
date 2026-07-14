"""print agents and print jobs

Revision ID: 000000000002
Revises: 000000000001
Create Date: 2026-07-13 00:00:00.000000

Adds the silent-printing queue: ``print_agents`` (one per branch shop PC, holding
only the sha256 token hash) and ``print_jobs`` (server-rendered payloads spooled
to disk and delivered to the branch's agent via long-poll). Follows the metadata
naming convention (SET NULL for audit/agent FKs, CASCADE for branch/order).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "000000000002"
down_revision: Union[str, None] = "000000000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "print_agents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=op.f("fk_print_agents_branch_id_branches"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_print_agents_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_print_agents_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_print_agents")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_print_agents_token_hash")),
    )
    op.create_index(
        op.f("ix_print_agents_branch_id"), "print_agents", ["branch_id"], unique=False
    )
    op.create_table(
        "print_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("placed_piece_id", sa.Integer(), nullable=True),
        sa.Column("job_type", sa.String(length=16), nullable=False),
        sa.Column("payload_format", sa.String(length=8), nullable=False),
        sa.Column("payload_path", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("done_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["print_agents.id"],
            name=op.f("fk_print_jobs_agent_id_print_agents"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=op.f("fk_print_jobs_branch_id_branches"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_print_jobs_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["placed_piece_id"],
            ["order_placed_pieces.id"],
            name=op.f("fk_print_jobs_placed_piece_id_order_placed_pieces"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_print_jobs_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_print_jobs_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_print_jobs")),
    )
    op.create_index(
        op.f("ix_print_jobs_order_id"), "print_jobs", ["order_id"], unique=False
    )
    op.create_index(
        "ix_print_jobs_branch_status",
        "print_jobs",
        ["branch_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_print_jobs_branch_status", table_name="print_jobs")
    op.drop_index(op.f("ix_print_jobs_order_id"), table_name="print_jobs")
    op.drop_table("print_jobs")
    op.drop_index(op.f("ix_print_agents_branch_id"), table_name="print_agents")
    op.drop_table("print_agents")
