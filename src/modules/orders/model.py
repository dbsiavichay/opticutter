from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.modules.users.enums import UserRole
from src.shared.database import Base
from src.shared.mixins import AuditMixin, TimestampMixin


class OrderStatus(str, Enum):
    """Estados del proceso de CORTE de una orden.

    La revisión previa del cliente (cotización mutable) vive en la pre-orden; una
    orden nace ya ``confirmed`` y desde ahí sólo avanza por producción. ``queued``
    es la cola de taller: la orden está lista pero el corte aún no empieza (entrar
    a ``cutting`` marca el inicio del corte; ``cut`` su fin).

    El CANTEADO corre en una pista paralela e independiente (``BandingStatus``): el
    canteador puede ir canteando piezas que el operador libera, sin esperar a que
    todo el corte termine.
    """

    confirmed = "confirmed"
    queued = "queued"
    cutting = "cutting"
    cut = "cut"
    completed = "completed"
    dispatched = "despachado"
    cancelled = "cancelled"


class BandingStatus(str, Enum):
    """Estado de la pista paralela de CANTEADO (tapacantos).

    Dimensión ortogonal a ``OrderStatus``: avanza por su cuenta mientras el corte
    sigue su curso. ``not_applicable`` = la orden no lleva tapacantos (nada que
    cantear). El canteador la mueve ``pending → in_progress → done``.
    """

    not_applicable = "not_applicable"
    pending = "pending"
    in_progress = "in_progress"
    done = "done"


# Estados de canteado que aún bloquean el cierre de la orden (queda canteado por hacer).
BANDING_PENDING_STATUSES = {BandingStatus.pending, BandingStatus.in_progress}

# Estados de corte en los que el canteado puede registrarse (ya hay piezas liberadas).
BANDING_MUTABLE_ORDER_STATUSES = {OrderStatus.cutting, OrderStatus.cut}

# Estados sin salida: la orden ya no se transforma. ``dispatched`` (mercadería
# entregada al cliente) es el cierre real del ciclo; ``completed`` deja de ser
# terminal en el grafo (avanza a ``dispatched``) pero sigue contando como "no
# activa" para el control de duplicados/cap de pendientes.
TERMINAL_STATUSES = {
    OrderStatus.completed,
    OrderStatus.dispatched,
    OrderStatus.cancelled,
}

# Mapa de transiciones válidas de la máquina de estados.
TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.confirmed: {OrderStatus.queued, OrderStatus.cancelled},
    OrderStatus.queued: {OrderStatus.cutting},
    OrderStatus.cutting: {OrderStatus.cut, OrderStatus.queued},
    OrderStatus.cut: {OrderStatus.completed},
    OrderStatus.completed: {OrderStatus.dispatched},
    OrderStatus.dispatched: set(),
    OrderStatus.cancelled: set(),
}

# Qué roles pueden ejecutar cada transición (from, to) → roles permitidos.
TRANSITION_ROLES: dict[tuple[OrderStatus, OrderStatus], tuple[UserRole, ...]] = {
    (OrderStatus.confirmed, OrderStatus.queued): (
        UserRole.ADMIN,
        UserRole.SELLER,
    ),
    (OrderStatus.confirmed, OrderStatus.cancelled): (UserRole.ADMIN, UserRole.SELLER),
    (OrderStatus.queued, OrderStatus.cutting): (
        UserRole.ADMIN,
        UserRole.OPERATOR,
    ),
    (OrderStatus.cutting, OrderStatus.queued): (UserRole.ADMIN,),
    (OrderStatus.cutting, OrderStatus.cut): (UserRole.ADMIN, UserRole.OPERATOR),
    (OrderStatus.cut, OrderStatus.completed): (UserRole.ADMIN, UserRole.SELLER),
    # El despacho (entrega física) lo puede registrar cualquier rol: quien entregue
    # la mercadería. Se lista a todos explícitamente en vez de omitir la entrada.
    (OrderStatus.completed, OrderStatus.dispatched): (
        UserRole.ADMIN,
        UserRole.SELLER,
        UserRole.OPERATOR,
        UserRole.BANDER,
    ),
}

# Transiciones válidas de la pista de canteado (forward-only; re-aplicar = idempotente).
BANDING_TRANSITIONS: dict[BandingStatus, set[BandingStatus]] = {
    BandingStatus.pending: {BandingStatus.in_progress},
    BandingStatus.in_progress: {BandingStatus.done},
    BandingStatus.done: set(),
}

# Qué roles pueden mover la pista de canteado.
BANDING_TRANSITION_ROLES: tuple[UserRole, ...] = (UserRole.ADMIN, UserRole.BANDER)


class OrderModel(TimestampMixin, AuditMixin, Base):
    """Raíz de agregado: pedido con snapshot inmutable y máquina de estados."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[Optional[str]] = mapped_column(String(32), unique=True, nullable=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    # Sucursal dueña de la orden: hecho histórico inmutable (heredado de la pre-orden
    # al confirmar). Mover de sucursal a un vendedor no reasigna sus órdenes pasadas.
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default=OrderStatus.confirmed.value)

    optimization_snapshot: Mapped[dict] = mapped_column(JSON)
    optimization_hash: Mapped[str] = mapped_column(String(64))

    currency: Mapped[str] = mapped_column(String(8), default="USD")
    # subtotal = suma a precio de lista (tableros + tapacantos); total = subtotal menos
    # el descuento del nivel de precio congelado (price_tier_code/discount_rate). El
    # rate se congela aquí para preservar el histórico aunque luego cambien las tarifas.
    subtotal: Mapped[float] = mapped_column(Float)
    total: Mapped[float] = mapped_column(Float)
    price_tier_code: Mapped[str] = mapped_column(
        String(32), default="consumidor", server_default="consumidor"
    )
    discount_rate: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    discount_amount: Mapped[float] = mapped_column(
        Float, default=0.0, server_default="0"
    )
    total_boards_used: Mapped[int] = mapped_column(Integer)

    external_invoice_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Operador autoasignado: se rellena al transicionar a ``cutting``.
    assigned_to_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assigned_to_label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Despacho (entrega física al cliente): se congela al transicionar a
    # ``dispatched``. La hoja de despacho muestra esta fecha y quién entregó.
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    dispatched_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    dispatched_by_label: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )

    # Forma de pago (informativa): se captura al transicionar de ``confirmed`` a
    # ``queued``. Una orden puede pagarse con ambos métodos a la vez; el método
    # usado se infiere de qué monto es > 0. No afecta precios ni el cobro.
    payment_cash_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    payment_credit_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Pista de CANTEADO (paralela al corte): el canteador marca inicio/fin. Se fija
    # a ``pending`` al crear si la orden lleva tapacantos, si no ``not_applicable``.
    banding_status: Mapped[str] = mapped_column(
        String(16),
        default=BandingStatus.not_applicable.value,
        server_default=BandingStatus.not_applicable.value,
    )
    banding_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    banding_started_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    banding_started_by_label: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    banding_finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    banding_finished_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    banding_finished_by_label: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )

    client: Mapped["ClientModel"] = relationship("ClientModel")  # noqa: F821
    branch: Mapped["BranchModel"] = relationship("BranchModel")  # noqa: F821
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


class OrderLineModel(TimestampMixin, AuditMixin, Base):
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
    # Medio tablero: la línea se cobró a la mitad (ancho/2, costo/2). False para
    # tableros completos y tapacantos.
    half_board: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="lines")


class OrderPieceModel(TimestampMixin, AuditMixin, Base):
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


class OrderBoardModel(TimestampMixin, AuditMixin, Base):
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
    # Medio tablero físico: el operario corta/usa un medio (ancho/2). El ``width`` ya
    # llega partido; este flag lo marca explícito para la vista de taller.
    half_board: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
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


class OrderPlacedPieceModel(TimestampMixin, AuditMixin, Base):
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


class OrderStatusHistoryModel(TimestampMixin, AuditMixin, Base):
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

    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="history")
