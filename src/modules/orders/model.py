from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base


class OrderStatus(str, Enum):
    """Estados del proceso productivo de una orden.

    La revisión previa del cliente (cotización mutable) vive en la pre-orden; una
    orden nace ya ``confirmed`` y desde ahí sólo avanza por producción.
    """

    confirmed = "confirmed"
    approved = "approved"
    in_production = "in_production"
    cut = "cut"
    completed = "completed"
    cancelled = "cancelled"


# Estados sin salida: la orden ya no se transforma.
TERMINAL_STATUSES = {OrderStatus.completed, OrderStatus.cancelled}

# Mapa de transiciones válidas de la máquina de estados (ver diseño §7.2).
TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.confirmed: {OrderStatus.approved, OrderStatus.cancelled},
    OrderStatus.approved: {OrderStatus.in_production, OrderStatus.cancelled},
    OrderStatus.in_production: {OrderStatus.cut},
    OrderStatus.cut: {OrderStatus.completed},
    OrderStatus.completed: set(),
    OrderStatus.cancelled: set(),
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
    # Quién creó la orden: staff (flujo directo) o NULL si nació de una
    # confirmación de cliente / del sistema (la pre-orden audita ese origen).
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

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
    boards: Mapped[list["OrderBoardModel"]] = relationship(
        "OrderBoardModel",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderBoardModel.id",
    )


class OrderLineModel(Base):
    """Línea de COBRO: un producto facturado (cantidad × precio congelado).

    Hoy el cobro es por tableros usados; el modelo admite cualquier producto
    (tablero, tapacanto, herraje) para órdenes mixtas futuras.

    ``product_id`` es nulo para materiales fuera del catálogo (retazos o medidas
    manuales): esos se identifican por ``product_code``/``product_name``.
    """

    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id"), nullable=True
    )
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

    ``product_id`` referencia el tablero (producto tipo ``board``) del que se corta;
    es nulo cuando el material está fuera del catálogo (retazo o medida manual).
    """

    __tablename__ = "order_pieces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id"), nullable=True
    )
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


class OrderBoardModel(Base):
    """Tablero FÍSICO del plan de corte, materializado desde el snapshot.

    Cada fila es una hoja real a cortar (los ``layout_groups`` del snapshot solo
    deduplican la vista). ``sheet_number`` es la secuencia global 1..N dentro de
    la orden (el ``sheet_number`` del snapshot se reinicia por material).
    ``product_id`` es nulo para materiales fuera del catálogo (retazo/manual).
    """

    __tablename__ = "order_boards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    sheet_number: Mapped[int] = mapped_column(Integer)
    material_key: Mapped[str] = mapped_column(String(64))
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id"), nullable=True
    )
    product_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    width: Mapped[float] = mapped_column(Float)
    height: Mapped[float] = mapped_column(Float)
    thickness: Mapped[float] = mapped_column(Float)
    # Rectángulos sobrantes del snapshot (display + futuro inventario de retazos).
    remainders: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # Cortes de guillotina (recorridos de sierra) para dibujar las líneas de corte.
    # Nulo en órdenes cuyo snapshot es previo a la serialización de ``cuts``.
    cuts: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="boards")
    pieces: Mapped[list["OrderPlacedPieceModel"]] = relationship(
        "OrderPlacedPieceModel",
        back_populates="board",
        cascade="all, delete-orphan",
        order_by="OrderPlacedPieceModel.id",
    )


class OrderPlacedPieceModel(Base):
    """Pieza COLOCADA en un tablero físico: la unidad que el operario marca.

    Geometría ya rotada (x, y, width, height) lista para dibujar; las dims
    nominales (``original_*``) sirven para agrupar piezas iguales en el front.
    ``piece_id`` conserva la identidad de instancia del snapshot (``label#N``).
    ``cut_at`` nulo = pendiente de corte; con fecha = cortada.
    """

    __tablename__ = "order_placed_pieces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("order_boards.id"), index=True)
    piece_id: Mapped[str] = mapped_column(String(160))
    label: Mapped[str] = mapped_column(String(128))
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    width: Mapped[float] = mapped_column(Float)
    height: Mapped[float] = mapped_column(Float)
    original_width: Mapped[float] = mapped_column(Float)
    original_height: Mapped[float] = mapped_column(Float)
    rotated: Mapped[bool] = mapped_column(Boolean, default=False)
    # Lados canteados geométricos, tal cual el snapshot (nulo si no lleva canto).
    edges: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    cut_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Quién marcó la pieza como cortada: FK al operario + etiqueta congelada.
    # NULL mientras esté pendiente (en sincronía con ``cut_at``).
    cut_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    cut_by_label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    order: Mapped["OrderModel"] = relationship("OrderModel")
    board: Mapped["OrderBoardModel"] = relationship(
        "OrderBoardModel", back_populates="pieces"
    )


class OrderStatusHistoryModel(Base):
    """Auditoría de transiciones de estado de una orden.

    ``actor`` es el TIPO de actor (``staff``/``client``/``system``); ``actor_user_id``
    es la FK al usuario de staff (NULL para cliente/sistema) y ``actor_label`` el
    snapshot legible del nombre al momento del hecho.
    """

    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    from_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    actor: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    actor_label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="history")
