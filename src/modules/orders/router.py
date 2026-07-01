from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from src.modules.branches.service import branch_letterhead
from src.modules.optimizations.carrier import ProformaCarrier
from src.modules.optimizations.proforma import ProformaService, pdf_response
from src.modules.orders.model import OrderStatus
from src.modules.orders.schemas import (
    BandingQueueItem,
    BandingStatusResponse,
    BandingUpdate,
    CuttingPlanResponse,
    OrderExportResponse,
    OrderInvoiceUpdate,
    OrderResponse,
    OrderStatusUpdate,
    PieceCutResponse,
    PieceCutUpdate,
)
from src.modules.orders.service import OrderService, order_service
from src.modules.settings.service import SettingsService, settings_service
from src.modules.users.dependencies import get_branch_scope, require_permission
from src.modules.users.model import UserModel
from src.shared.audit import staff_actor
from src.shared.pagination import PageParams
from src.shared.responses import (
    ERROR_RESPONSES,
    DataResponse,
    PaginatedResponse,
    ok,
    page,
)

router = APIRouter(prefix="/orders", tags=["orders"], responses=ERROR_RESPONSES)

# Read/proforma: admin + seller + operator. Write (create, invoice, export):
# admin + seller. State transition: admin + seller + operator (TRANSITION_ROLES
# filters by specific transition in the service). Cutting plan (view + production
# sheet): admin + seller + operator. Marking pieces: admin + operator.
_READ = Depends(require_permission("orders:read"))
_WRITE = Depends(require_permission("orders:write"))
_TRANSITION = Depends(require_permission("orders:transition"))
_CUTTING = Depends(require_permission("cutting_plan"))
_CUT = Depends(require_permission("orders:cut"))
_BAND = Depends(require_permission("orders:band"))

_FORMAT_QUERY = Query(
    default="pdf",
    description="Output format: 'pdf' (file) or 'base64' (JSON)",
    pattern="^(pdf|base64)$",
)


@router.get("/", response_model=PaginatedResponse[OrderResponse], dependencies=[_READ])
def list_orders(
    status: Optional[List[OrderStatus]] = Query(
        default=None,
        description="Filter orders by one or more statuses (repeat the parameter)",
    ),
    branch_id: Optional[int] = Query(
        default=None,
        alias="branchId",
        description="Global roles only (admin/seller): narrows the listing to a "
        "branch (empty = all)",
    ),
    paging: PageParams = Depends(),
    svc: OrderService = Depends(order_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Lists orders with optional status filter and pagination.

    The operator only sees their branch's orders; global roles (admin/seller)
    see all of them (or filter with ``branchId``).
    """
    items, total = svc.list_orders(
        status=status,
        branch_scope=branch_scope,
        branch_filter=branch_id,
        limit=paging.limit,
        offset=paging.offset,
    )
    return page(items, total, paging.limit, paging.offset)


@router.get(
    "/banding-queue",
    response_model=DataResponse[List[BandingQueueItem]],
    dependencies=[_BAND],
)
def get_banding_queue(
    svc: OrderService = Depends(order_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Bander's banding queue: orders with pending banding (their branch).

    Declared before ``/{order_id}`` so the parametric route doesn't capture it.
    """
    return ok(svc.list_banding_queue(branch_scope=branch_scope))


@router.get(
    "/{order_id}", response_model=DataResponse[OrderResponse], dependencies=[_READ]
)
def get_order(
    order_id: int,
    svc: OrderService = Depends(order_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Gets an order by ID (404 if it belongs to another branch and you're not admin)."""
    return ok(svc.get_scoped_or_404(order_id, branch_scope))


@router.patch(
    "/{order_id}/status",
    response_model=DataResponse[OrderResponse],
)
def update_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    svc: OrderService = Depends(order_service),
    current_user: UserModel = Depends(require_permission("orders:transition")),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Transitions an order's state, validating the state machine."""
    return ok(
        svc.transition(
            order_id,
            data.status,
            actor=staff_actor(current_user),
            note=data.note,
            payment=data.payment,
            branch_scope=branch_scope,
        )
    )


@router.patch(
    "/{order_id}/banding",
    response_model=DataResponse[BandingStatusResponse],
)
def update_order_banding(
    order_id: int,
    data: BandingUpdate,
    svc: OrderService = Depends(order_service),
    current_user: UserModel = Depends(require_permission("orders:band")),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Registers the start/finish of banding (track parallel to cutting).

    The bander advances ``in_progress`` (start) → ``done`` (finish) without
    touching the cutting status; runs while the order is in ``cutting``/``cut``.
    """
    return ok(
        svc.transition_banding(
            order_id,
            data.status,
            actor=staff_actor(current_user),
            branch_scope=branch_scope,
        )
    )


@router.get(
    "/{order_id}/cutting-plan",
    response_model=DataResponse[CuttingPlanResponse],
    dependencies=[_CUTTING],
)
def get_cutting_plan(
    order_id: int,
    svc: OrderService = Depends(order_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Cutting plan for the workshop view: physical boards, pieces and progress."""
    return ok(svc.get_cutting_plan(order_id, branch_scope=branch_scope))


@router.patch(
    "/{order_id}/cutting-plan/pieces/{piece_id}",
    response_model=DataResponse[PieceCutResponse],
)
def mark_piece_cut(
    order_id: int,
    piece_id: int,
    data: PieceCutUpdate,
    svc: OrderService = Depends(order_service),
    current_user: UserModel = Depends(require_permission("orders:cut")),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Marks (or unmarks, ``cut=false``) a placed piece as cut.

    Only with the order in ``cutting``. Idempotent: re-marking changes nothing.
    """
    return ok(
        svc.mark_piece_cut(
            order_id,
            piece_id,
            data.cut,
            actor=staff_actor(current_user),
            branch_scope=branch_scope,
        )
    )


@router.post(
    "/{order_id}/invoice",
    response_model=DataResponse[OrderResponse],
    dependencies=[_WRITE],
)
def set_order_invoice(
    order_id: int,
    data: OrderInvoiceUpdate,
    svc: OrderService = Depends(order_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Associates the external invoice ID (stitches with the billing provider)."""
    return ok(
        svc.set_external_invoice_id(
            order_id, data.external_invoice_id, branch_scope=branch_scope
        )
    )


@router.get(
    "/{order_id}/export",
    response_model=DataResponse[OrderExportResponse],
    dependencies=[_WRITE],
)
def export_order(
    order_id: int,
    svc: OrderService = Depends(order_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Neutral billing document for the external provider (billing=boards)."""
    return ok(svc.build_export(order_id, branch_scope=branch_scope))


# Exempt from the JSON envelope: PDF file transport (StreamingResponse) and its
# base64 variant are "the file, transported", not domain JSON resources.
@router.get("/{order_id}/document", dependencies=[_READ])
def get_order_document(
    order_id: int,
    format: str = _FORMAT_QUERY,
    svc: OrderService = Depends(order_service),
    settings_svc: SettingsService = Depends(settings_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Order document (committed document, frozen prices) from the snapshot.

    Not a proforma (non-binding quote): it's the document for an already
    confirmed order, hence the header reads "ORDEN DE PEDIDO".
    """
    order = svc.get_scoped_or_404(order_id, branch_scope)
    carrier = ProformaCarrier.from_order(
        order,
        company=settings_svc.get_company(),
        branch=branch_letterhead(svc.db, order.branch_id),
    )
    pdf_buffer = ProformaService.generate_proforma_pdf(carrier, title="ORDEN DE PEDIDO")
    return pdf_response(
        pdf_buffer, f"orden_pedido_{order.code or order.id}.pdf", format
    )


@router.get("/{order_id}/production-sheet", dependencies=[_CUTTING])
def get_order_production_sheet(
    order_id: int,
    format: str = _FORMAT_QUERY,
    svc: OrderService = Depends(order_service),
    settings_svc: SettingsService = Depends(settings_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Production sheet (cut list and layout, NO prices) for the workshop."""
    order = svc.get_scoped_or_404(order_id, branch_scope)
    carrier = ProformaCarrier.from_order(
        order,
        company=settings_svc.get_company(),
        branch=branch_letterhead(svc.db, order.branch_id),
    )
    pdf_buffer = ProformaService.generate_production_sheet_pdf(carrier)
    return pdf_response(pdf_buffer, f"produccion_{order.code or order.id}.pdf", format)


@router.get("/{order_id}/dispatch-sheet", dependencies=[_READ])
def get_order_dispatch_sheet(
    order_id: int,
    format: str = _FORMAT_QUERY,
    svc: OrderService = Depends(order_service),
    settings_svc: SettingsService = Depends(settings_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Dispatch sheet (handover to the client): pieces with NO prices, a liability
    disclaimer and signatures. Shows the snapshot's dispatch date/responsible party."""
    order = svc.get_scoped_or_404(order_id, branch_scope)
    carrier = ProformaCarrier.from_order(
        order,
        company=settings_svc.get_company(),
        branch=branch_letterhead(svc.db, order.branch_id),
    )
    pdf_buffer = ProformaService.generate_dispatch_sheet_pdf(carrier)
    return pdf_response(pdf_buffer, f"despacho_{order.code or order.id}.pdf", format)
