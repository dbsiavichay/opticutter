from datetime import datetime
from typing import List, Literal, Optional

from pydantic import Field

from src.modules.branches.schemas import BranchRefResponse
from src.modules.clients.schemas import ClientResponse
from src.modules.optimizations.schemas import (
    CutSegment,
    MaterialInput,
    OptimizationStrategy,
    Remainder,
    Requirement,
)
from src.modules.orders.model import BandingStatus, OrderStatus
from src.shared.schemas import CamelModel


class OrderCreate(CamelModel):
    """Create an order: same shape as ``OptimizeRequest`` + metadata."""

    materials: List[MaterialInput] = Field(
        ...,
        min_length=1,
        description="Available materials (stock): catalog boards, offcuts or manual",
    )
    requirements: List[Requirement] = Field(
        ..., min_length=1, description="Cut list to optimize and freeze into the order"
    )
    client_id: int = Field(..., description="Client ID placing the order")
    branch_id: Optional[int] = Field(
        default=None,
        description="Owning branch (inherited from the pre-order on confirmation)",
    )
    price_tier_code: Optional[str] = Field(
        default="consumidor",
        max_length=32,
        description="Price tier to freeze: consumidor (0%)|carpintero (2%)|efectivo (5%)",
    )
    strategy: OptimizationStrategy = Field(
        default=OptimizationStrategy.default,
        description=(
            "Packing heuristic to use when recomputing and freezing the snapshot "
            "(default | longOffcuts). Inherited from the pre-order on confirmation."
        ),
    )
    notes: Optional[str] = Field(default=None, max_length=512)
    source: Optional[str] = Field(default="telegram", max_length=32)
    status: Literal[OrderStatus.confirmed] = Field(
        default=OrderStatus.confirmed,
        description=(
            "Born status: the order is born 'confirmed'. The client's prior review "
            "(formerly 'quoted') now lives in the pre-order."
        ),
    )


class OrderPaymentInput(CamelModel):
    """Payment method (informational only), registered when moving to ``queued``.

    An order can be paid with both methods at once; the method used is
    inferred from which amount is > 0. Doesn't affect pricing or the order's billing.
    """

    cash_amount: Optional[float] = Field(
        default=None, ge=0, description="Amount paid in cash"
    )
    credit_amount: Optional[float] = Field(
        default=None, ge=0, description="Amount paid on credit"
    )


class OrderStatusUpdate(CamelModel):
    """Requested state transition."""

    status: OrderStatus = Field(..., description="Target status to transition to")
    note: Optional[str] = Field(default=None, max_length=512)
    payment: Optional[OrderPaymentInput] = Field(
        default=None,
        description=(
            "Payment method, required when moving from 'confirmed' to 'queued' "
            "(at least one amount > 0)"
        ),
    )


class OrderInvoiceUpdate(CamelModel):
    """Associates the invoice ID issued by the external billing provider."""

    external_invoice_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Invoice ID assigned by the external billing provider",
    )


class OrderExportLine(CamelModel):
    """Invoice line for the external provider (billed by product)."""

    description: str = Field(..., description="Human-readable line description")
    product_code: Optional[str] = None
    quantity: int = Field(..., description="Number of units charged")
    unit_price: float
    line_total: float


class OrderExportResponse(CamelModel):
    """Neutral billing document: consumed by the billing provider."""

    order_code: Optional[str] = None
    status: OrderStatus
    issued_at: datetime = Field(..., description="When the order was frozen/confirmed")
    currency: str
    client: ClientResponse
    lines: List[OrderExportLine]
    subtotal: float = Field(..., description="Sum at list price (before the discount)")
    price_tier_code: Optional[str] = None
    discount_rate: float = Field(default=0.0, description="Frozen discount (0.02 = 2%)")
    discount_amount: float = Field(default=0.0)
    total: float = Field(..., description="Subtotal minus the discount")
    external_invoice_id: Optional[str] = None


class OrderLineResponse(CamelModel):
    id: int
    product_id: Optional[int] = None  # null if the material isn't from the catalog
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
    half_board: bool = Field(
        default=False, description="True if this board line was charged as a half board"
    )


class OrderPieceResponse(CamelModel):
    id: int
    product_id: Optional[int] = None  # null if the material isn't from the catalog
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
    actor: Optional[str] = Field(
        default=None, description="Actor type: staff | client | system"
    )
    actor_user_id: Optional[int] = Field(
        default=None, description="Staff user id (null for client/system)"
    )
    actor_label: Optional[str] = Field(
        default=None, description="Frozen actor name at the time of the action"
    )
    note: Optional[str] = None
    created_at: datetime


class OrderResponse(CamelModel):
    id: int
    code: Optional[str] = None
    client: ClientResponse = Field(..., description="Client information")
    branch: BranchRefResponse = Field(..., description="Owning branch")
    status: OrderStatus
    currency: str
    subtotal: float = Field(..., description="Sum at list price (before the discount)")
    price_tier_code: str = Field(default="consumidor")
    discount_rate: float = Field(default=0.0, description="Frozen discount (0.02 = 2%)")
    discount_amount: float = Field(default=0.0)
    total: float = Field(..., description="Subtotal minus the discount")
    total_boards_used: int
    optimization_hash: str
    external_invoice_id: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    assigned_to_id: Optional[int] = Field(
        default=None,
        description="Operator who self-assigned the order (set on cutting)",
    )
    assigned_at: Optional[datetime] = Field(
        default=None, description="When the operator took the order"
    )
    assigned_to_label: Optional[str] = Field(
        default=None, description="Frozen operator name at assignment time"
    )
    dispatched_at: Optional[datetime] = Field(
        default=None, description="When the order was dispatched (handed to client)"
    )
    dispatched_by: Optional[int] = Field(
        default=None, description="User id who registered the dispatch"
    )
    dispatched_by_label: Optional[str] = Field(
        default=None, description="Frozen name of who dispatched the order"
    )
    payment_cash_amount: Optional[float] = Field(
        default=None, description="Cash amount (registered on confirmed → queued)"
    )
    payment_credit_amount: Optional[float] = Field(
        default=None, description="Credit amount (registered on confirmed → queued)"
    )
    banding_status: BandingStatus = Field(
        default=BandingStatus.not_applicable,
        description="Parallel edge-banding track (not_applicable if no edge banding)",
    )
    banding_started_at: Optional[datetime] = None
    banding_started_by: Optional[int] = Field(
        default=None, description="User id who started banding (null while pending)"
    )
    banding_started_by_label: Optional[str] = Field(
        default=None, description="Frozen name of who started banding"
    )
    banding_finished_at: Optional[datetime] = None
    banding_finished_by: Optional[int] = Field(
        default=None, description="User id who finished banding"
    )
    banding_finished_by_label: Optional[str] = Field(
        default=None, description="Frozen name of who finished banding"
    )
    lines: List[OrderLineResponse] = Field(default_factory=list)
    pieces: List[OrderPieceResponse] = Field(default_factory=list)
    history: List[OrderStatusHistoryResponse] = Field(default_factory=list)


class PlacedPieceResponse(CamelModel):
    """Piece placed on a physical board, with its cutting status."""

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
    cut_by: Optional[int] = Field(
        default=None, description="User id who cut the piece (null while pending)"
    )
    cut_by_label: Optional[str] = Field(
        default=None, description="Frozen name of who cut the piece"
    )


class CuttingProgress(CamelModel):
    """Cutting progress: pieces cut out of the total."""

    cut_pieces: int
    total_pieces: int


class OrderBoardResponse(CamelModel):
    """Physical board of the cutting plan, with its pieces and progress."""

    id: int
    sheet_number: int = Field(..., description="Global sheet sequence within the order")
    material_key: str
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    width: float
    height: float
    thickness: float
    half_board: bool = Field(
        default=False, description="True if this physical board is a half board"
    )
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
    """Order's cutting plan: physical boards for the workshop view."""

    order_id: int
    order_code: Optional[str] = None
    status: OrderStatus
    progress: CuttingProgress
    boards: List[OrderBoardResponse] = Field(default_factory=list)


class PieceCutUpdate(CamelModel):
    """Marks (or unmarks, with ``cut=false``) a placed piece as cut."""

    cut: bool = Field(default=True, description="True = cut, False = undo")


class PieceCutResponse(CamelModel):
    """Result of marking a piece: piece status + updated progress."""

    piece: PlacedPieceResponse
    progress: CuttingProgress = Field(..., description="Order-level progress")
    board_progress: CuttingProgress = Field(..., description="Affected board progress")


class BandingUpdate(CamelModel):
    """Banding-track transition requested by the bander."""

    status: BandingStatus = Field(
        ..., description="Target banding status: in_progress (start) | done (finish)"
    )
    note: Optional[str] = Field(default=None, max_length=512)


class BandingStatusResponse(CamelModel):
    """Minimal banding view for the bander (no prices or order detail)."""

    order_id: int
    order_code: Optional[str] = None
    banding_status: BandingStatus
    banding_started_at: Optional[datetime] = None
    banding_finished_at: Optional[datetime] = None


class BandingQueueItem(CamelModel):
    """Banding queue item: the minimum needed for the bander to identify the order."""

    order_id: int
    order_code: Optional[str] = None
    status: OrderStatus = Field(..., description="Cutting-track status of the order")
    banding_status: BandingStatus
    created_at: datetime
    client: ClientResponse = Field(..., description="Client the order belongs to")
    board_names: List[str] = Field(
        default_factory=list,
        description="Distinct board names (product_name, falling back to "
        "product_code/material_key) used in the order",
    )
