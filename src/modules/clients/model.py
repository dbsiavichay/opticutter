from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base


class ClientModel(Base):
    """Modelo ORM para clientes."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(32), unique=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(64))
    last_name: Mapped[Optional[str]] = mapped_column(String(64))
    source: Mapped[Optional[str]] = mapped_column(String(64))

    optimizations: Mapped[list["OptimizationModel"]] = relationship(  # noqa: F821
        "OptimizationModel", back_populates="client"
    )
