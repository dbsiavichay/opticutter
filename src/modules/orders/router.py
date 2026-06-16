from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.modules.optimizations.carrier import ProformaCarrier
from src.modules.optimizations.proforma import ProformaService, pdf_response
from src.modules.orders.model import OrderStatus
from src.modules.orders.schemas import (
    CuttingPlanResponse,
    OrderCreate,
    OrderExportResponse,
    OrderInvoiceUpdate,
    OrderResponse,
    OrderStatusUpdate,
    PieceCutResponse,
    PieceCutUpdate,
)
from src.modules.orders.service import OrderService, order_service
from src.shared.pagination import PageParams
from src.shared.responses import (
    ERROR_RESPONSES,
    DataResponse,
    PaginatedResponse,
    ok,
    page,
)

router = APIRouter(prefix="/orders", tags=["orders"], responses=ERROR_RESPONSES)

_FORMAT_QUERY = Query(
    default="pdf",
    description="Formato de salida: 'pdf' (archivo) o 'base64' (JSON)",
    pattern="^(pdf|base64)$",
)


@router.post("/", response_model=DataResponse[OrderResponse], status_code=201)
def create_order(data: OrderCreate, svc: OrderService = Depends(order_service)):
    """Crea (o recupera, por idempotencia) una orden congelando el snapshot."""
    return ok(svc.create(data))


@router.get("/", response_model=PaginatedResponse[OrderResponse])
def list_orders(
    status: Optional[OrderStatus] = Query(
        default=None, description="Filtra órdenes por estado"
    ),
    paging: PageParams = Depends(),
    svc: OrderService = Depends(order_service),
):
    """Lista órdenes con filtro por estado y paginación opcionales."""
    items, total = svc.list_orders(
        status=status, limit=paging.limit, offset=paging.offset
    )
    return page(items, total, paging.limit, paging.offset)


@router.get("/{order_id}", response_model=DataResponse[OrderResponse])
def get_order(order_id: int, svc: OrderService = Depends(order_service)):
    """Obtiene una orden por ID."""
    return ok(svc.get_or_404(order_id))


@router.patch("/{order_id}/status", response_model=DataResponse[OrderResponse])
def update_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    svc: OrderService = Depends(order_service),
):
    """Transiciona el estado de una orden validando la máquina de estados."""
    return ok(svc.transition(order_id, data.status, actor="sales", note=data.note))


@router.get(
    "/{order_id}/cutting-plan", response_model=DataResponse[CuttingPlanResponse]
)
def get_cutting_plan(order_id: int, svc: OrderService = Depends(order_service)):
    """Plan de corte para la vista de taller: tableros físicos, piezas y avance."""
    return ok(svc.get_cutting_plan(order_id))


@router.patch(
    "/{order_id}/cutting-plan/pieces/{piece_id}",
    response_model=DataResponse[PieceCutResponse],
)
def mark_piece_cut(
    order_id: int,
    piece_id: int,
    data: PieceCutUpdate,
    svc: OrderService = Depends(order_service),
):
    """Marca (o desmarca, ``cut=false``) una pieza colocada como cortada.

    Solo con la orden ``in_production``. Idempotente: re-marcar no cambia nada.
    """
    return ok(svc.mark_piece_cut(order_id, piece_id, data.cut))


@router.post("/{order_id}/invoice", response_model=DataResponse[OrderResponse])
def set_order_invoice(
    order_id: int,
    data: OrderInvoiceUpdate,
    svc: OrderService = Depends(order_service),
):
    """Asocia el ID de la factura externa (costura con el proveedor de facturación)."""
    return ok(svc.set_external_invoice_id(order_id, data.external_invoice_id))


@router.get("/{order_id}/export", response_model=DataResponse[OrderExportResponse])
def export_order(order_id: int, svc: OrderService = Depends(order_service)):
    """Documento de facturación neutral para el proveedor externo (cobro=tableros)."""
    return ok(svc.build_export(order_id))


# Exentos de la envoltura JSON: transporte de archivo PDF (StreamingResponse) y su
# variante base64 son "el archivo, transportado", no recursos JSON de dominio.
@router.get("/{order_id}/proforma")
def get_order_proforma(
    order_id: int,
    format: str = _FORMAT_QUERY,
    svc: OrderService = Depends(order_service),
):
    """Proforma comercial (con precios congelados) renderizada desde el snapshot."""
    order = svc.get_or_404(order_id)
    carrier = ProformaCarrier.from_order(order)
    pdf_buffer = ProformaService.generate_proforma_pdf(carrier)
    return pdf_response(pdf_buffer, f"proforma_{order.code or order.id}.pdf", format)


@router.get("/{order_id}/production-sheet")
def get_order_production_sheet(
    order_id: int,
    format: str = _FORMAT_QUERY,
    svc: OrderService = Depends(order_service),
):
    """Hoja de producción (lista de corte y disposición, SIN precios) para el taller."""
    order = svc.get_or_404(order_id)
    carrier = ProformaCarrier.from_order(order)
    pdf_buffer = ProformaService.generate_production_sheet_pdf(carrier)
    return pdf_response(pdf_buffer, f"produccion_{order.code or order.id}.pdf", format)
