from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base


class OrderStatus(str, Enum):
    """Estados del proceso comercial de una orden."""

    draft = "draft"
    quoted = "quoted"
    confirmed = "confirmed"
    approved = "approved"
    in_production = "in_production"
    cut = "cut"
    completed = "completed"
    cancelled = "cancelled"
    expired = "expired"


# Estados sin salida: la orden ya no se transforma.
TERMINAL_STATUSES = {OrderStatus.completed, OrderStatus.cancelled, OrderStatus.expired}

# Pendientes (abiertas, pre-producción): cuentan para el tope antiabuso por cliente.
PENDING_STATUSES = {OrderStatus.confirmed, OrderStatus.approved}

# Mapa de transiciones válidas de la máquina de estados (ver diseño §7.2).
TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.draft: {OrderStatus.quoted, OrderStatus.cancelled},
    OrderStatus.quoted: {
        OrderStatus.confirmed,
        OrderStatus.expired,
        OrderStatus.cancelled,
    },
    OrderStatus.confirmed: {OrderStatus.approved, OrderStatus.cancelled},
    OrderStatus.approved: {OrderStatus.in_production, OrderStatus.cancelled},
    OrderStatus.in_production: {OrderStatus.cut},
    OrderStatus.cut: {OrderStatus.completed},
    OrderStatus.completed: set(),
    OrderStatus.cancelled: set(),
    OrderStatus.expired: set(),
}


class OrderModel(Base):
    """Raíz de agregado: pedido con snapshot inmutable y máquina de estados."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[Optional[str]] = mapped_column(String(32), unique=True, nullable=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    status: Mapped[str] = mapped_column(String(32), default=OrderStatus.confirmed.value)

    optimization_snapshot: Mapped[dict] = mapped_column(JSON)
    optimization_hash: Mapped[str] = mapped_column(String(64))

    currency: Mapped[str] = mapped_column(String(8), default="USD")
    subtotal: Mapped[float] = mapped_column(Float)
    total: Mapped[float] = mapped_column(Float)
    total_boards_used: Mapped[int] = mapped_column(Integer)

    external_invoice_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    client: Mapped["ClientModel"] = relationship("ClientModel")  # noqa: F821
    lines: Mapped[list["OrderLineModel"]] = relationship(
        "OrderLineModel", back_populates="order", cascade="all, delete-orphan"
    )
    pieces: Mapped[list["OrderPieceModel"]] = relationship(
        "OrderPieceModel", back_populates="order", cascade="all, delete-orphan"
    )
    history: Mapped[list["OrderStatusHistoryModel"]] = relationship(
        "OrderStatusHistoryModel",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusHistoryModel.id",
    )


class OrderLineModel(Base):
    """Línea de COBRO: un producto facturado (cantidad × precio congelado).

    Hoy el cobro es por tableros usados; el modelo admite cualquier producto
    (tablero, tapacanto, herraje) para órdenes mixtas futuras.
    """

    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_snapshot: Mapped[float] = mapped_column(Float)
    line_total: Mapped[float] = mapped_column(Float)
    avg_efficiency: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_area_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Tapacanto: metros lineales exactos (con merma) para mostrar; ``quantity``
    # guarda los metros enteros cobrados. Nulo para tableros.
    linear_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="lines")


class OrderPieceModel(Base):
    """Pieza de la LISTA DE CORTE (insumo de producción; no se cobra).

    ``product_id`` referencia el tablero (producto tipo ``board``) del que se corta.
    """

    __tablename__ = "order_pieces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    height: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    can_rotate: Mapped[bool] = mapped_column(Boolean, default=True)
    # Tapacanto de la pieza (lados nominales + producto), p. ej.
    # ``{"product_id": 42, "sides": ["top", "left"]}``. Nulo si no lleva canto.
    edges: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="pieces")


class OrderStatusHistoryModel(Base):
    """Auditoría de transiciones de estado de una orden."""

    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    from_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    actor: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="history")
