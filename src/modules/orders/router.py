from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from src.modules.branches.service import branch_letterhead
from src.modules.optimizations.carrier import ProformaCarrier
from src.modules.optimizations.proforma import ProformaService, pdf_response
from src.modules.orders.model import OrderStatus
from src.modules.orders.schemas import (
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

# Lectura/proforma: admin + vendedor + operador. Escritura (crear, factura, export):
# admin + vendedor. Transición de estado: admin + vendedor + operador (TRANSITION_ROLES
# filtra por transición específica en el servicio). Plan de corte (ver + hoja de
# producción): admin + vendedor + operador. Marcar piezas: admin + operador.
_READ = Depends(require_permission("orders:read"))
_WRITE = Depends(require_permission("orders:write"))
_TRANSITION = Depends(require_permission("orders:transition"))
_CUTTING = Depends(require_permission("cutting_plan"))
_CUT = Depends(require_permission("orders:cut"))

_FORMAT_QUERY = Query(
    default="pdf",
    description="Formato de salida: 'pdf' (archivo) o 'base64' (JSON)",
    pattern="^(pdf|base64)$",
)


@router.get("/", response_model=PaginatedResponse[OrderResponse], dependencies=[_READ])
def list_orders(
    status: Optional[List[OrderStatus]] = Query(
        default=None,
        description="Filtra órdenes por uno o varios estados (repetir el parámetro)",
    ),
    branch_id: Optional[int] = Query(
        default=None,
        alias="branchId",
        description="Solo admin: estrecha el listado a una sucursal (vacío = todas)",
    ),
    paging: PageParams = Depends(),
    svc: OrderService = Depends(order_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Lista órdenes con filtro por estado y paginación opcionales.

    El staff solo ve las de su sucursal; el admin ve todas (o filtra con ``branchId``).
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
    "/{order_id}", response_model=DataResponse[OrderResponse], dependencies=[_READ]
)
def get_order(
    order_id: int,
    svc: OrderService = Depends(order_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Obtiene una orden por ID (404 si es de otra sucursal y no eres admin)."""
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
    """Transiciona el estado de una orden validando la máquina de estados."""
    return ok(
        svc.transition(
            order_id,
            data.status,
            actor=staff_actor(current_user),
            note=data.note,
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
    """Plan de corte para la vista de taller: tableros físicos, piezas y avance."""
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
    """Marca (o desmarca, ``cut=false``) una pieza colocada como cortada.

    Solo con la orden ``in_production``. Idempotente: re-marcar no cambia nada.
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
    """Asocia el ID de la factura externa (costura con el proveedor de facturación)."""
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
    """Documento de facturación neutral para el proveedor externo (cobro=tableros)."""
    return ok(svc.build_export(order_id, branch_scope=branch_scope))


# Exentos de la envoltura JSON: transporte de archivo PDF (StreamingResponse) y su
# variante base64 son "el archivo, transportado", no recursos JSON de dominio.
@router.get("/{order_id}/proforma", dependencies=[_READ])
def get_order_proforma(
    order_id: int,
    format: str = _FORMAT_QUERY,
    svc: OrderService = Depends(order_service),
    settings_svc: SettingsService = Depends(settings_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Proforma comercial (con precios congelados) renderizada desde el snapshot."""
    order = svc.get_scoped_or_404(order_id, branch_scope)
    carrier = ProformaCarrier.from_order(
        order,
        company=settings_svc.get_company(),
        branch=branch_letterhead(svc.db, order.branch_id),
    )
    pdf_buffer = ProformaService.generate_proforma_pdf(carrier)
    return pdf_response(pdf_buffer, f"proforma_{order.code or order.id}.pdf", format)


@router.get("/{order_id}/production-sheet", dependencies=[_CUTTING])
def get_order_production_sheet(
    order_id: int,
    format: str = _FORMAT_QUERY,
    svc: OrderService = Depends(order_service),
    settings_svc: SettingsService = Depends(settings_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Hoja de producción (lista de corte y disposición, SIN precios) para el taller."""
    order = svc.get_scoped_or_404(order_id, branch_scope)
    carrier = ProformaCarrier.from_order(
        order,
        company=settings_svc.get_company(),
        branch=branch_letterhead(svc.db, order.branch_id),
    )
    pdf_buffer = ProformaService.generate_production_sheet_pdf(carrier)
    return pdf_response(pdf_buffer, f"produccion_{order.code or order.id}.pdf", format)
