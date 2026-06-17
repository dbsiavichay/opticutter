from typing import Optional

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base
from src.shared.mixins import AuditMixin, TimestampMixin


class OptimizationModel(TimestampMixin, AuditMixin, Base):
    """Modelo ORM de la tabla ``optimizations`` (conservada, pero ya sin escrituras:
    las optimizaciones son cache-only desde S2). Sin relación ORM hacia ``clients``:
    el cómputo es efímero y la orden es la raíz durable."""

    __tablename__ = "optimizations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    total_boards_used: Mapped[int] = mapped_column(Integer)
    total_boards_cost: Mapped[float] = mapped_column(Float)
    requirements: Mapped[dict] = mapped_column(JSON)
    layouts: Mapped[dict] = mapped_column(JSON)
    materials_summary: Mapped[dict] = mapped_column(JSON, nullable=True)
    layout_groups: Mapped[dict] = mapped_column(JSON, nullable=True)
    optimization_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
