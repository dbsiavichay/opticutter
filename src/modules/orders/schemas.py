from datetime import datetime
from typing import List, Literal, Optional

from pydantic import Field

from src.modules.clients.schemas import ClientResponse
from src.modules.optimizations.schemas import (
    CutSegment,
    MaterialInput,
    Remainder,
    Requirement,
)
from src.modules.orders.model import OrderStatus
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
    status: Literal[OrderStatus.confirmed] = Field(
        default=OrderStatus.confirmed,
        description=(
            "Born status: la orden nace 'confirmed'. La revisión previa del cliente "
            "(antes 'quoted') vive ahora en la pre-orden."
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
    product_id: Optional[int] = None  # nulo si el material no es de catálogo
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
    product_id: Optional[int] = None  # nulo si el material no es de catálogo
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
    lines: List[OrderLineResponse] = Field(default_factory=list)
    pieces: List[OrderPieceResponse] = Field(default_factory=list)
    history: List[OrderStatusHistoryResponse] = Field(default_factory=list)


class PlacedPieceResponse(CamelModel):
    """Pieza colocada en un tablero físico, con su estado de corte."""

    id: int
    piece_id: str = Field(..., description="Instance identity from snapshot (label#N)")
    label: str
    x: float
    y: float
    width: float
    height: float
    original_width: float
    original_height: float
    rotated: bool
    edges: Optional[dict] = Field(
        default=None, description="Geometric edge-banded sides (as drawn)"
    )
    cut: bool = Field(..., description="Whether the piece was already cut")
    cut_at: Optional[datetime] = None


class CuttingProgress(CamelModel):
    """Avance de corte: piezas cortadas sobre el total."""

    cut_pieces: int
    total_pieces: int


class OrderBoardResponse(CamelModel):
    """Tablero físico del plan de corte con sus piezas y avance."""

    id: int
    sheet_number: int = Field(..., description="Global sheet sequence within the order")
    material_key: str
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    width: float
    height: float
    thickness: float
    progress: CuttingProgress
    pieces: List[PlacedPieceResponse] = Field(default_factory=list)
    remainders: List[Remainder] = Field(
        default_factory=list, description="Leftover rectangles (waste/offcuts)"
    )
    cuts: List[CutSegment] = Field(
        default_factory=list,
        description="Guillotine saw cuts; empty for orders frozen before this field",
    )


class CuttingPlanResponse(CamelModel):
    """Plan de corte de la orden: tableros físicos para la vista de taller."""

    order_id: int
    order_code: Optional[str] = None
    status: OrderStatus
    progress: CuttingProgress
    boards: List[OrderBoardResponse] = Field(default_factory=list)


class PieceCutUpdate(CamelModel):
    """Marca (o desmarca, con ``cut=false``) una pieza colocada como cortada."""

    cut: bool = Field(default=True, description="True = cut, False = undo")


class PieceCutResponse(CamelModel):
    """Resultado de marcar una pieza: estado de la pieza + avance actualizado."""

    piece: PlacedPieceResponse
    progress: CuttingProgress = Field(..., description="Order-level progress")
    board_progress: CuttingProgress = Field(..., description="Affected board progress")
