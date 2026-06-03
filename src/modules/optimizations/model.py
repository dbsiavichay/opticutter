from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base


class OptimizationModel(Base):
    """Modelo ORM para optimizaciones"""

    __tablename__ = "optimizations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    total_boards_used: Mapped[int] = mapped_column(Integer)
    total_boards_cost: Mapped[float] = mapped_column(Float)
    requirements: Mapped[dict] = mapped_column(JSON)
    layouts: Mapped[dict] = mapped_column(JSON)
    materials_summary: Mapped[dict] = mapped_column(JSON, nullable=True)
    layout_groups: Mapped[dict] = mapped_column(JSON, nullable=True)
    optimization_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))

    client: Mapped["ClientModel"] = relationship(  # noqa: F821
        "ClientModel", back_populates="optimizations"
    )
