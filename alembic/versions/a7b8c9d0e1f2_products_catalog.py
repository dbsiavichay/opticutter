"""products catalog: replace boards with a unified products table

Generaliza el catálogo: ``boards`` -> ``products`` (tabla única con columnas
comunes + ``attributes`` JSON por tipo). Copia los tableros existentes a
``products`` conservando su ``id`` para no romper las FKs de las órdenes, y
renombra ``order_lines``/``order_pieces`` de ``board_*`` a ``product_*``
repuntando la FK a ``products.id``.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PRODUCTS_TABLE = sa.table(
    "products",
    sa.column("id", sa.Integer),
    sa.column("type", sa.String),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("description", sa.String),
    sa.column("price", sa.Float),
    sa.column("is_active", sa.Boolean),
    sa.column("attributes", sa.JSON),
)

_BOARDS_TABLE = sa.table(
    "boards",
    sa.column("id", sa.Integer),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("description", sa.String),
    sa.column("height", sa.Integer),
    sa.column("width", sa.Integer),
    sa.column("thickness", sa.Integer),
    sa.column("grain_direction", sa.String),
    sa.column("price", sa.Float),
)


def _reset_pk_sequence(bind, table: str) -> None:
    """Realinea la secuencia del PK en Postgres tras insertar ids explícitos."""
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
            )
        )


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=256), nullable=True),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_products_type", "products", ["type"])

    # Migra los tableros existentes -> products (mismo id; atributos en camelCase,
    # forma canónica del API).
    boards = bind.execute(sa.select(_BOARDS_TABLE)).mappings().all()
    rows = []
    for b in boards:
        attributes = {
            "height": b["height"],
            "width": b["width"],
            "thickness": b["thickness"],
        }
        if b["grain_direction"] is not None:
            attributes["grainDirection"] = b["grain_direction"]
        rows.append(
            {
                "id": b["id"],
                "type": "board",
                "code": b["code"],
                "name": b["name"],
                "description": b["description"],
                "price": b["price"],
                "is_active": True,
                "attributes": attributes,
            }
        )
    if rows:
        op.bulk_insert(_PRODUCTS_TABLE, rows)
        _reset_pk_sequence(bind, "products")

    # Renombra columnas y repunta FKs (board_* -> product_*, FK -> products.id).
    # Reconstrucción explícita (portable SQLite/Postgres) de las tablas hijas.
    op.create_table(
        "order_lines_new",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(length=32), nullable=True),
        sa.Column("product_name", sa.String(length=128), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_snapshot", sa.Float(), nullable=False),
        sa.Column("line_total", sa.Float(), nullable=False),
        sa.Column("avg_efficiency", sa.Float(), nullable=True),
        sa.Column("total_area_m2", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    bind.execute(
        sa.text(
            "INSERT INTO order_lines_new (id, order_id, product_id, product_code, "
            "product_name, quantity, unit_price_snapshot, line_total, avg_efficiency, "
            "total_area_m2) SELECT id, order_id, board_id, board_code, board_name, "
            "quantity, unit_price_snapshot, line_total, avg_efficiency, total_area_m2 "
            "FROM order_lines"
        )
    )
    op.drop_table("order_lines")
    op.rename_table("order_lines_new", "order_lines")

    op.create_table(
        "order_pieces_new",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=True),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("can_rotate", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    bind.execute(
        sa.text(
            "INSERT INTO order_pieces_new (id, order_id, product_id, label, height, "
            "width, quantity, priority, can_rotate) SELECT id, order_id, board_id, "
            "label, height, width, quantity, priority, can_rotate FROM order_pieces"
        )
    )
    op.drop_table("order_pieces")
    op.rename_table("order_pieces_new", "order_pieces")

    op.drop_table("boards")


def downgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "boards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=256), nullable=True),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("thickness", sa.Integer(), nullable=False),
        sa.Column("grain_direction", sa.String(length=4), nullable=True),
        sa.Column("price", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )

    products = (
        bind.execute(
            sa.select(_PRODUCTS_TABLE).where(_PRODUCTS_TABLE.c.type == "board")
        )
        .mappings()
        .all()
    )
    rows = []
    for p in products:
        attributes = p["attributes"] or {}
        rows.append(
            {
                "id": p["id"],
                "code": p["code"],
                "name": p["name"],
                "description": p["description"],
                "height": attributes.get("height"),
                "width": attributes.get("width"),
                "thickness": attributes.get("thickness"),
                "grain_direction": attributes.get("grainDirection"),
                "price": p["price"],
            }
        )
    if rows:
        op.bulk_insert(_BOARDS_TABLE, rows)
        _reset_pk_sequence(bind, "boards")

    op.create_table(
        "order_lines_old",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("board_id", sa.Integer(), nullable=False),
        sa.Column("board_code", sa.String(length=32), nullable=True),
        sa.Column("board_name", sa.String(length=128), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_snapshot", sa.Float(), nullable=False),
        sa.Column("line_total", sa.Float(), nullable=False),
        sa.Column("avg_efficiency", sa.Float(), nullable=True),
        sa.Column("total_area_m2", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    bind.execute(
        sa.text(
            "INSERT INTO order_lines_old (id, order_id, board_id, board_code, "
            "board_name, quantity, unit_price_snapshot, line_total, avg_efficiency, "
            "total_area_m2) SELECT id, order_id, product_id, product_code, "
            "product_name, quantity, unit_price_snapshot, line_total, avg_efficiency, "
            "total_area_m2 FROM order_lines"
        )
    )
    op.drop_table("order_lines")
    op.rename_table("order_lines_old", "order_lines")

    op.create_table(
        "order_pieces_old",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("board_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=True),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("can_rotate", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    bind.execute(
        sa.text(
            "INSERT INTO order_pieces_old (id, order_id, board_id, label, height, "
            "width, quantity, priority, can_rotate) SELECT id, order_id, product_id, "
            "label, height, width, quantity, priority, can_rotate FROM order_pieces"
        )
    )
    op.drop_table("order_pieces")
    op.rename_table("order_pieces_old", "order_pieces")

    op.drop_index("ix_products_type", table_name="products")
    op.drop_table("products")
