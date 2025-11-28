from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


class ClientModel(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(64))
    last_name: Mapped[Optional[str]] = mapped_column(String(64))

    optimizations: Mapped[list["OptimizationModel"]] = relationship(
        "OptimizationModel", back_populates="client"
    )


class BoardModel(Base):
    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(256))
    length: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    thickness: Mapped[int] = mapped_column(Integer)
    grain_direction: Mapped[Optional[str]] = mapped_column(String(4))
    price: Mapped[float] = mapped_column(Float)


class OptimizationModel(Base):
    __tablename__ = "optimizations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    total_boards_used: Mapped[int] = mapped_column(Integer)
    total_boards_cost: Mapped[float] = mapped_column(Float)
    requirements: Mapped[dict] = mapped_column(JSON)
    solution: Mapped[dict] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))

    client: Mapped["ClientModel"] = relationship(
        "ClientModel", back_populates="optimizations"
    )
