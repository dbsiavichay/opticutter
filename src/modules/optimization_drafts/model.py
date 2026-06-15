from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base


class OptimizationDraftModel(Base):
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
    client_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clients.id"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
