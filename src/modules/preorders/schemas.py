from datetime import datetime
from typing import List, Optional

from pydantic import Field

from src.modules.branches.schemas import BranchRefResponse
from src.modules.clients.schemas import ClientResponse
from src.modules.optimizations.schemas import (
    MaterialInput,
    OptimizeResponse,
    Requirement,
)
from src.modules.preorders.model import PreOrderStatus, ReviewLinkStatus
from src.shared.schemas import CamelModel


class PreOrderCreate(CamelModel):
    """Crear una pre-orden (cotización mutable): inputs del optimizador + metadatos.

    Misma forma de entrada que ``OptimizeRequest``/``OrderCreate`` (materiales de
    cualquier origen + lista de corte), pero nada se congela: se recalcula al leer.
    """

    materials: List[MaterialInput] = Field(
        ...,
        min_length=1,
        description="Available materials (stock): catalog boards, offcuts or manual",
    )
    requirements: List[Requirement] = Field(
        ..., min_length=1, description="Cut list to optimize"
    )
    client_id: int = Field(..., description="Client the quote is for")
    notes: Optional[str] = Field(default=None, max_length=512)
    source: Optional[str] = Field(default="telegram", max_length=32)
    branch_id: Optional[int] = Field(
        default=None,
        description=(
            "Target branch. Ignored for the operator (forced to their own branch); "
            "optional for the seller (defaults to their base branch, overridable); "
            "required for a global admin."
        ),
    )


class PreOrderUpdate(CamelModel):
    """Editar una pre-orden abierta (solo en ``draft``/``sent``). Todo opcional."""

    materials: Optional[List[MaterialInput]] = Field(default=None, min_length=1)
    requirements: Optional[List[Requirement]] = Field(default=None, min_length=1)
    client_id: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=512)
    source: Optional[str] = Field(default=None, max_length=32)


class PreOrderStatusHistoryResponse(CamelModel):
    """Entrada de auditoría de una transición de estado de la pre-orden."""

    id: int
    from_status: Optional[PreOrderStatus] = None
    to_status: PreOrderStatus
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


class PreOrderResponse(CamelModel):
    """Detalle de una pre-orden con su optimización recalculada (precios vivos)."""

    id: int
    code: Optional[str] = None
    client: ClientResponse = Field(..., description="Client information")
    branch: BranchRefResponse = Field(..., description="Owning branch")
    status: PreOrderStatus
    notes: Optional[str] = None
    client_note: Optional[str] = Field(
        default=None, description="Latest change request typed by the client"
    )
    source: Optional[str] = None
    order_id: Optional[int] = Field(
        default=None, description="Immutable order, set once the client confirms"
    )
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    # Inputs crudos editables (lo que el formulario del optimizador re-renderiza).
    materials: List[MaterialInput] = Field(
        ..., description="Stored material inputs (editable)"
    )
    requirements: List[Requirement] = Field(
        ..., description="Stored cut list inputs (editable)"
    )
    optimization: OptimizeResponse = Field(
        ..., description="Recomputed cutting result with live prices"
    )
    history: List[PreOrderStatusHistoryResponse] = Field(default_factory=list)


class PreOrderSummaryResponse(CamelModel):
    """Resumen liviano para el listado (sin la optimización completa)."""

    id: int
    code: Optional[str] = None
    client: ClientResponse
    branch: BranchRefResponse = Field(..., description="Owning branch")
    status: PreOrderStatus
    source: Optional[str] = None
    order_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Enlace de revisión + proyecciones públicas (las consume el frontend de Maderable)
# ---------------------------------------------------------------------------


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


class ReviewPreOrderResponse(CamelModel):
    """Vista pública sanitizada de la pre-orden: lo que ve el cliente en el enlace.

    Excluye a propósito identificadores internos (id numérico, client_id), datos de
    contacto del cliente, los inputs crudos y metadatos comerciales internos. Los
    precios son vivos (recalculados); el desglose se arma desde la optimización.
    """

    reference: Optional[str] = Field(
        default=None, description="Pre-order code shown to the client (PRE-...)"
    )
    status: PreOrderStatus
    order_code: Optional[str] = Field(
        default=None, description="Resulting order code once the client confirms"
    )
    client_note: Optional[str] = Field(
        default=None, description="The client's own change request, echoed back"
    )
    client_name: Optional[str] = None
    currency: str
    subtotal: float
    total: float
    total_boards_used: int
    created_at: datetime
    sent_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    lines: List[ReviewLineResponse] = Field(default_factory=list)
    pieces: List[ReviewPieceResponse] = Field(default_factory=list)
