from datetime import datetime
from typing import List, Literal, Optional

from pydantic import Field

from src.modules.clients.schemas import ClientResponse
from src.modules.optimizations.schemas import MaterialInput, Requirement
from src.modules.orders.model import OrderStatus, ReviewLinkStatus
from src.shared.schemas import CamelModel


class OrderCreate(CamelModel):
    """Crear una orden: misma forma que ``OptimizeRequest`` + metadatos."""

    materials: List[MaterialInput] = Field(
        ...,
        min_length=1,
        description="Available materials (stock): catalog boards, offcuts or manual",
    )
    requirements: List[Requirement] = Field(
        ..., min_length=1, description="Cut list to optimize and freeze into the order"
    )
    client_id: int = Field(..., description="Client ID placing the order")
    notes: Optional[str] = Field(default=None, max_length=512)
    source: Optional[str] = Field(default="telegram", max_length=32)
    status: Literal[OrderStatus.quoted, OrderStatus.confirmed] = Field(
        default=OrderStatus.confirmed,
        description=(
            "Born status: 'quoted' (cotización para revisión del cliente) o "
            "'confirmed' (orden directa, default retrocompatible)"
        ),
    )


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
    """Línea de factura para el proveedor externo (cobro por producto)."""

    description: str = Field(..., description="Human-readable line description")
    product_code: Optional[str] = None
    quantity: int = Field(..., description="Number of units charged")
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
    product_id: int
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    quantity: int = Field(
        ...,
        description="Units charged: boards for tableros, whole linear meters for edge banding",
    )
    unit_price_snapshot: float
    line_total: float
    avg_efficiency: Optional[float] = None
    total_area_m2: Optional[float] = None
    linear_m: Optional[float] = Field(
        default=None, description="Exact linear meters (incl. waste) for edge banding"
    )


class OrderPieceResponse(CamelModel):
    id: int
    product_id: int
    label: Optional[str] = None
    height: int
    width: int
    quantity: int
    priority: int
    can_rotate: bool
    edges: Optional[dict] = Field(
        default=None, description="Edge banding spec (nominal sides + product)"
    )


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


class ReviewLinkResponse(CamelModel):
    """Enlace de revisión recién generado: única respuesta que expone el token."""

    token: str = Field(..., description="Raw token, returned only at generation time")
    url: str = Field(..., description="Full review URL for the Maderable frontend")
    status: ReviewLinkStatus
    expires_at: Optional[datetime] = None
    created_at: datetime


class ReviewLinkInfoResponse(CamelModel):
    """Metadatos del enlace vigente, sin el token (irrecuperable por diseño)."""

    status: ReviewLinkStatus
    created_at: datetime
    expires_at: Optional[datetime] = None
    used_at: Optional[datetime] = None


class ReviewActionRequest(CamelModel):
    """Acción del cliente sobre la cotización (confirmar/rechazar)."""

    note: Optional[str] = Field(default=None, max_length=512)


class ReviewLineResponse(CamelModel):
    """Línea de cobro proyectada para la revisión pública del cliente."""

    product_code: Optional[str] = None
    product_name: Optional[str] = None
    quantity: int
    unit_price: float
    line_total: float
    linear_m: Optional[float] = None


class ReviewPieceResponse(CamelModel):
    """Pieza de la lista de corte proyectada para la revisión pública."""

    label: Optional[str] = None
    height: int
    width: int
    quantity: int
    edges: Optional[dict] = None


class ReviewOrderResponse(CamelModel):
    """Vista pública sanitizada de la orden: lo que ve el cliente en el enlace.

    Excluye a propósito identificadores internos (id numérico, client_id),
    datos de contacto (identifier/phone/email), el snapshot/hash de optimización
    y metadatos comerciales internos (notes, source, factura externa).
    """

    order_code: Optional[str] = None
    status: OrderStatus
    client_name: Optional[str] = None
    currency: str
    subtotal: float
    total: float
    total_boards_used: int
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    lines: List[ReviewLineResponse] = Field(default_factory=list)
    pieces: List[ReviewPieceResponse] = Field(default_factory=list)
