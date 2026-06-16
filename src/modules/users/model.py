from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.modules.users.enums import UserRole
from src.shared.database import Base


class UserModel(Base):
    """Usuario interno del sistema (staff): credenciales + rol.

    El login es por ``email`` (único). La contraseña nunca se guarda en claro:
    solo su hash bcrypt en ``hashed_password``. La baja es lógica (``is_active``)
    para no romper referencias ni perder trazabilidad.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(128))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default=UserRole.OPERATOR.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
