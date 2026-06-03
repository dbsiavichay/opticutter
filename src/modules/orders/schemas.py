from datetime import datetime
from typing import List, Optional

from pydantic import Field

from src.modules.clients.schemas import ClientResponse
from src.modules.optimizations.schemas import Requirement
from src.modules.orders.model import OrderStatus
from src.shared.schemas import CamelModel


class OrderCreate(CamelModel):
    """Crear una orden: misma forma que ``OptimizeRequest`` + metadatos."""

    requirements: List[Requirement] = Field(
        ..., min_length=1, description="Cut list to optimize and freeze into the order"
    )
    client_id: int = Field(..., description="Client ID placing the order")
    notes: Optional[str] = Field(default=None, max_length=512)
    source: Optional[str] = Field(default="telegram", max_length=32)


class OrderStatusUpdate(CamelModel):
    """Transición de estado solicitada."""

    status: OrderStatus = Field(..., description="Target status to transition to")
    note: Optional[str] = Field(default=None, max_length=512)


class OrderInvoiceUpdate(CamelModel):
    """Asocia el ID de la factura emitida por el proveedor externo de facturación."""

    external_invoice_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Invoice ID assigned by the external billing provider",
    )


class OrderExportLine(CamelModel):
    """Línea de factura para el proveedor externo (cobro por tablero)."""

    description: str = Field(..., description="Human-readable line description")
    board_code: Optional[str] = None
    quantity: int = Field(..., description="Number of boards charged")
    unit_price: float
    line_total: float


class OrderExportResponse(CamelModel):
    """Documento de facturación neutral: lo consume el proveedor de facturación."""

    order_code: Optional[str] = None
    status: OrderStatus
    issued_at: datetime = Field(..., description="When the order was frozen/confirmed")
    currency: str
    client: ClientResponse
    lines: List[OrderExportLine]
    subtotal: float
    total: float
    external_invoice_id: Optional[str] = None


class OrderLineResponse(CamelModel):
    id: int
    board_id: int
    board_code: Optional[str] = None
    board_name: Optional[str] = None
    quantity: int = Field(..., description="Number of boards charged (cobro=tableros)")
    unit_price_snapshot: float
    line_total: float
    avg_efficiency: Optional[float] = None
    total_area_m2: Optional[float] = None


class OrderPieceResponse(CamelModel):
    id: int
    board_id: int
    label: Optional[str] = None
    height: int
    width: int
    quantity: int
    priority: int
    can_rotate: bool


class OrderStatusHistoryResponse(CamelModel):
    id: int
    from_status: Optional[OrderStatus] = None
    to_status: OrderStatus
    actor: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime


class OrderResponse(CamelModel):
    id: int
    code: Optional[str] = None
    client: ClientResponse = Field(..., description="Client information")
    status: OrderStatus
    currency: str
    subtotal: float
    total: float
    total_boards_used: int
    optimization_hash: str
    external_invoice_id: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    lines: List[OrderLineResponse] = Field(default_factory=list)
    pieces: List[OrderPieceResponse] = Field(default_factory=list)
    history: List[OrderStatusHistoryResponse] = Field(default_factory=list)
