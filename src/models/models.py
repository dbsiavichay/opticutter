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


class OptimizationModel(Base):
    __tablename__ = "optimizations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    total_boards_used: Mapped[int] = mapped_column(Integer)
    total_boards_cost: Mapped[float] = mapped_column(Float)
    total_waste_percentage: Mapped[float] = mapped_column(Float)
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))

    client: Mapped["ClientModel"] = relationship(
        "ClientModel", back_populates="optimizations"
    )
    cuts: Mapped[list["OptimizationCutModel"]] = relationship(
        "OptimizationCutModel", back_populates="optimization"
    )
    layouts: Mapped[list["OptimizationLayoutModel"]] = relationship(
        "OptimizationLayoutModel", back_populates="optimization"
    )
    boards_used: Mapped[list["OptimizationBoardModel"]] = relationship(
        "OptimizationBoardModel", back_populates="optimization"
    )


class OptimizationCutModel(Base):
    __tablename__ = "optimization_cuts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    index: Mapped[int] = mapped_column(Integer)
    length: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    label: Mapped[Optional[str]] = mapped_column(String(64))
    allow_rotation: Mapped[bool] = mapped_column(default=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id"))
    optimization_id: Mapped[int] = mapped_column(ForeignKey("optimizations.id"))

    board: Mapped["BoardModel"] = relationship("BoardModel")
    optimization: Mapped["OptimizationModel"] = relationship(
        "OptimizationModel", back_populates="cuts"
    )


class OptimizationLayoutModel(Base):
    __tablename__ = "optimizations_layouts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    index: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    utilization_percentage: Mapped[float] = mapped_column(Float)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id"))
    optimization_id: Mapped[int] = mapped_column(ForeignKey("optimizations.id"))

    optimization: Mapped["OptimizationModel"] = relationship(
        "OptimizationModel", back_populates="board_layouts"
    )
    board: Mapped["BoardModel"] = relationship("BoardModel")
    layout_cuts: Mapped[list["OptmizationLayoutCutModel"]] = relationship(
        "OptmizationLayoutCutModel", back_populates="board_layout"
    )


class OptmizationLayoutCutModel(Base):
    __tablename__ = "optimization_layouts_cuts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    x: Mapped[int] = mapped_column(Integer)
    y: Mapped[int] = mapped_column(Integer)
    length: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    label: Mapped[Optional[str]] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(16))  # 'cut' or 'waste'
    optimization_layout_id: Mapped[int] = mapped_column(
        ForeignKey("optimizations_layouts.id")
    )
    optimization_layout: Mapped["OptimizationLayoutModel"] = relationship(
        "OptimizationLayoutModel", back_populates="layout_cuts"
    )


class OptimizationBoardModel(Base):
    __tablename__ = "optimization_boards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    used: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[float] = mapped_column(Float)
    total_cost: Mapped[float] = mapped_column(Float)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id"))
    optimization_id: Mapped[int] = mapped_column(ForeignKey("optimizations.id"))

    board: Mapped["BoardModel"] = relationship("BoardModel")
    optimization: Mapped["OptimizationModel"] = relationship(
        "OptimizationModel", back_populates="boards_used"
    )
