from typing import Optional

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base
from src.shared.mixins import AuditMixin, TimestampMixin


class OptimizationDraftModel(TimestampMixin, AuditMixin, Base):
    """Borrador del optimizador: trabajo en progreso, durable y mutable.

    A diferencia de la optimización (cómputo efímero, cache-only) y de la orden
    (salida inmutable congelada), un borrador es la **entrada cruda editable** del
    optimizador guardada para retomarla luego. ``payload`` es un bag JSON opaco con
    el estado del formulario tal cual lo envía el frontend (incluidas filas a medio
    llenar): el backend lo persiste sin validar su esquema interno.

    Es global del taller (no hay usuarios); ``client_id`` es opcional, solo metadato.
    """

    __tablename__ = "optimization_drafts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    # Sucursal dueña del borrador: aísla el trabajo en progreso entre sucursales.
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), index=True)
    client_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clients.id"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON)

    branch: Mapped["BranchModel"] = relationship("BranchModel")  # noqa: F821
