from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.modules.users.enums import UserRole
from src.shared.database import Base
from src.shared.mixins import AuditMixin, TimestampMixin


class UserModel(TimestampMixin, AuditMixin, Base):
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
    # Sucursal asignada al staff (vendedor/operador). NULL = administrador global,
    # que ve y opera todas las sucursales. Editable por el admin (mueve de sucursal);
    # el cambio surte efecto al instante (la sucursal no viaja en el JWT).
    branch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("branches.id"), index=True, nullable=True
    )
