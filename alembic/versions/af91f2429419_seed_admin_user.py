"""seed admin user

Revision ID: af91f2429419
Revises: 4e158361b42c
Create Date: 2026-06-16 12:12:21.472215

Siembra el primer administrador de forma idempotente desde las variables de
entorno ADMIN_EMAIL / ADMIN_PASSWORD. No-op si alguna está vacía o si ya existe
un usuario con ese email, por lo que es seguro re-aplicar en cualquier entorno.
"""

from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from src.shared.config import config
from src.shared.security import hash_password

# revision identifiers, used by Alembic.
revision: str = "af91f2429419"
down_revision: Union[str, None] = "4e158361b42c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    email = (config.ADMIN_EMAIL or "").strip()
    password = config.ADMIN_PASSWORD or ""
    if not email or not password:
        return  # sin credenciales configuradas no se siembra nada

    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT id FROM users WHERE email = :email"), {"email": email}
    ).first()
    if existing is not None:
        return  # ya existe: idempotente

    now = datetime.utcnow()
    bind.execute(
        sa.text(
            "INSERT INTO users "
            "(email, full_name, hashed_password, role, is_active, created_at, updated_at) "
            "VALUES "
            "(:email, :full_name, :hashed_password, :role, :is_active, :created_at, :updated_at)"
        ),
        {
            "email": email,
            "full_name": "Administrador",
            "hashed_password": hash_password(password),
            "role": "administrador",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
    )


def downgrade() -> None:
    email = (config.ADMIN_EMAIL or "").strip()
    if not email:
        return
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM users WHERE email = :email"), {"email": email})
