from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base
from src.shared.mixins import AuditMixin, TimestampMixin


class BranchModel(TimestampMixin, AuditMixin, Base):
    """Sucursal (almacén) del negocio: entidad raíz del aislamiento multi-sucursal.

    Antes las sucursales solo existían como un JSON de membrete en ``settings``;
    ahora son una entidad real a la que apuntan órdenes, pre-órdenes, borradores y
    usuarios (``branch_id``). El staff (vendedor/operador) queda atado a una
    sucursal; el administrador no (ve y opera todas). La baja es lógica
    (``is_active``) para no romper las FKs históricas.
    """

    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    address: Mapped[Optional[str]] = mapped_column(String(256))
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
