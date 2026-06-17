"""multi sucursal: tabla branches + branch_id en orders/preorders/drafts/users

Revision ID: b1f2c3d4e5a6
Revises: 4685fa13b87b
Create Date: 2026-06-17 16:00:00.000000

Aísla las órdenes por sucursal. Crea la entidad ``branches`` (antes solo un JSON de
membrete en ``settings.company_branches``), añade ``branch_id`` a las tablas que
deben aislarse y rellena las filas existentes con una sucursal por defecto. El
``branch_id`` de ``users`` queda nullable a propósito: NULL = administrador global.
"""
import json
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1f2c3d4e5a6"
down_revision: Union[str, None] = "4685fa13b87b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tablas que se aíslan por sucursal con branch_id NOT NULL (se rellenan al migrar).
_SCOPED_NOT_NULL = ("orders", "preorders", "optimization_drafts")


def _seed_branches(conn) -> int:
    """Crea las sucursales desde ``settings.company_branches`` (o una por defecto).

    Devuelve el id de la primera sucursal, usada como destino del backfill.
    """
    branches: list = []
    row = conn.execute(
        sa.text("SELECT company_branches FROM settings WHERE id = 1")
    ).fetchone()
    if row and row[0]:
        raw = row[0]
        if isinstance(raw, str):  # SQLite guarda el JSON como texto
            raw = json.loads(raw)
        branches = raw or []
    if not branches:
        branches = [{"name": "Principal", "address": None}]

    now = datetime.utcnow()
    first_id = None
    for i, b in enumerate(branches, start=1):
        code = f"SUC-{i}"
        conn.execute(
            sa.text(
                "INSERT INTO branches (code, name, address, is_active, "
                "created_at, updated_at) VALUES "
                "(:code, :name, :address, :active, :now, :now)"
            ),
            {
                "code": code,
                "name": b.get("name") or code,
                "address": b.get("address"),
                "active": True,
                "now": now,
            },
        )
        bid = conn.execute(
            sa.text("SELECT id FROM branches WHERE code = :code"), {"code": code}
        ).scalar()
        if first_id is None:
            first_id = bid
    return first_id


def upgrade() -> None:
    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("address", sa.String(length=256), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_branches_code"), "branches", ["code"], unique=True)

    conn = op.get_bind()
    default_branch_id = _seed_branches(conn)

    # branch_id nullable + índice + FK en cada tabla aislada (+ users).
    for table in (*_SCOPED_NOT_NULL, "users"):
        op.add_column(table, sa.Column("branch_id", sa.Integer(), nullable=True))
        op.create_index(
            op.f(f"ix_{table}_branch_id"), table, ["branch_id"], unique=False
        )
        op.create_foreign_key(
            f"fk_{table}_branch_id_branches", table, "branches", ["branch_id"], ["id"]
        )

    # Backfill: todo lo existente a la sucursal por defecto.
    for table in _SCOPED_NOT_NULL:
        conn.execute(
            sa.text(f"UPDATE {table} SET branch_id = :bid WHERE branch_id IS NULL"),
            {"bid": default_branch_id},
        )
    # Usuarios: el staff (no admin) a la sucursal por defecto; los admin quedan NULL
    # (globales: ven y operan todas las sucursales).
    conn.execute(
        sa.text(
            "UPDATE users SET branch_id = :bid "
            "WHERE role != 'administrador' AND branch_id IS NULL"
        ),
        {"bid": default_branch_id},
    )

    # Cierra el NOT NULL en las tablas aisladas (users queda nullable).
    for table in _SCOPED_NOT_NULL:
        op.alter_column(table, "branch_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    for table in (*_SCOPED_NOT_NULL, "users"):
        op.drop_constraint(
            f"fk_{table}_branch_id_branches", table, type_="foreignkey"
        )
        op.drop_index(op.f(f"ix_{table}_branch_id"), table_name=table)
        op.drop_column(table, "branch_id")
    op.drop_index(op.f("ix_branches_code"), table_name="branches")
    op.drop_table("branches")
