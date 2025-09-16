"""
Importa todos los modelos aquí para que Alembic pueda detectarlos automáticamente.
Cuando crees modelos nuevos, impórtalos aquí para que las migraciones funcionen.

Ejemplo:
from .user import User
from .project import Project
"""


from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
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

    cut_items: Mapped[list["CutItemModel"]] = relationship(
        "CutItemModel", back_populates="board"
    )
    board_layouts: Mapped[list["BoardLayoutModel"]] = relationship(
        "BoardLayoutModel", back_populates="board" 
    )


class OptimizationModel(Base):
    __tablename__ = "optimizations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))

    client: Mapped["ClientModel"] = relationship(
        "ClientModel", back_populates="optimizations"
    )
    cut_items: Mapped[list["CutItemModel"]] = relationship(
        "CutItemModel", back_populates="optimization"
    )
    board_layouts: Mapped[list["BoardLayoutModel"]] = relationship(
        "BoardLayoutModel", back_populates="optimization"
    )


class CutItemModel(Base):
    __tablename__ = "cut_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    length: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    label: Mapped[Optional[str]] = mapped_column(String(64))
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id"))
    optimization_id: Mapped[int] = mapped_column(ForeignKey("optimizations.id"))

    board: Mapped["BoardModel"] = relationship("BoardModel", back_populates="cut_items")
    optimization: Mapped["OptimizationModel"] = relationship(
        "OptimizationModel", back_populates="cut_items"
    )


class BoardLayoutModel(Base):
    __tablename__ = "board_layouts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    index: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    utilization_percentage: Mapped[float] = mapped_column(Float)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id"))
    optimization_id: Mapped[int] = mapped_column(ForeignKey("optimizations.id"))

    optimization: Mapped["OptimizationModel"] = relationship(
        "OptimizationModel", back_populates="board_layouts"
    )
    board: Mapped["BoardModel"] = relationship(
        "BoardModel", back_populates="board_layouts"
    )
    cuts_placed: Mapped[list["CutPlacedModel"]] = relationship(
        "CutPlacedModel", back_populates="board_layout"
    )


class CutPlacedModel(Base):
    __tablename__ = "cuts_placed"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    x: Mapped[int] = mapped_column(Integer)
    y: Mapped[int] = mapped_column(Integer)
    length: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    label: Mapped[Optional[str]] = mapped_column(String(64))
    board_layout_id: Mapped[int] = mapped_column(ForeignKey("board_layouts.id"))

    board_layout: Mapped["BoardLayoutModel"] = relationship(
        "BoardLayoutModel", back_populates="cuts_placed"
    )
