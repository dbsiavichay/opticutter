"""Rutas públicas de revisión del cliente: el token es la única credencial.

Las consume el frontend de Maderable desde la URL del enlace. No exponen
identificadores internos ni datos de contacto del cliente (ver
``ReviewOrderResponse``); los diagramas de corte se entregan vía el PDF de
proforma, también gateado por el token.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from src.modules.optimizations.carrier import ProformaCarrier
from src.modules.optimizations.proforma import ProformaService, pdf_response
from src.modules.orders.model import OrderModel, OrderStatus
from src.modules.orders.review_service import ReviewLinkService, review_link_service
from src.modules.orders.schemas import (
    ReviewActionRequest,
    ReviewLineResponse,
    ReviewOrderResponse,
    ReviewPieceResponse,
)
from src.shared.responses import ERROR_RESPONSES, DataResponse, ok

router = APIRouter(
    prefix="/public/review", tags=["public-review"], responses=ERROR_RESPONSES
)

_FORMAT_QUERY = Query(
    default="pdf",
    description="Formato de salida: 'pdf' (archivo) o 'base64' (JSON)",
    pattern="^(pdf|base64)$",
)


def _client_meta(request: Request) -> dict:
    """IP y user-agent del cliente para auditoría de la acción."""
    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    return {"ip": ip, "user_agent": request.headers.get("user-agent")}


def _to_review_response(order: OrderModel) -> ReviewOrderResponse:
    """Proyección sanitizada de la orden para la vista pública del cliente."""
    client_name = (
        " ".join(
            part for part in [order.client.first_name, order.client.last_name] if part
        )
        or None
    )
    return ReviewOrderResponse(
        order_code=order.code,
        status=OrderStatus(order.status),
        client_name=client_name,
        currency=order.currency,
        subtotal=order.subtotal,
        total=order.total,
        total_boards_used=order.total_boards_used,
        created_at=order.created_at,
        confirmed_at=order.confirmed_at,
        expires_at=order.expires_at,
        lines=[
            ReviewLineResponse(
                product_code=line.product_code,
                product_name=line.product_name,
                quantity=line.quantity,
                unit_price=line.unit_price_snapshot,
                line_total=line.line_total,
                linear_m=line.linear_m,
            )
            for line in order.lines
        ],
        pieces=[
            ReviewPieceResponse(
                label=piece.label,
                height=piece.height,
                width=piece.width,
                quantity=piece.quantity,
                edges=piece.edges,
            )
            for piece in order.pieces
        ],
    )


@router.get("/{token}", response_model=DataResponse[ReviewOrderResponse])
def get_review(token: str, svc: ReviewLinkService = Depends(review_link_service)):
    """Detalle sanitizado de la cotización/orden asociada al token."""
    return ok(_to_review_response(svc.get_review(token)))


@router.post("/{token}/confirm", response_model=DataResponse[ReviewOrderResponse])
def confirm_review(
    token: str,
    request: Request,
    data: Optional[ReviewActionRequest] = None,
    svc: ReviewLinkService = Depends(review_link_service),
):
    """El cliente confirma la cotización (``quoted → confirmed``); reintento benigno."""
    note = data.note if data else None
    order = svc.confirm(token, note=note, meta=_client_meta(request))
    return ok(_to_review_response(order))


@router.post("/{token}/reject", response_model=DataResponse[ReviewOrderResponse])
def reject_review(
    token: str,
    request: Request,
    data: Optional[ReviewActionRequest] = None,
    svc: ReviewLinkService = Depends(review_link_service),
):
    """El cliente rechaza la cotización (``quoted → cancelled``)."""
    note = data.note if data else None
    order = svc.reject(token, note=note, meta=_client_meta(request))
    return ok(_to_review_response(order))


# Exento de la envoltura JSON: transporte de archivo PDF (igual que en orders).
@router.get("/{token}/proforma")
def get_review_proforma(
    token: str,
    format: str = _FORMAT_QUERY,
    svc: ReviewLinkService = Depends(review_link_service),
):
    """Proforma PDF de la cotización, gateada por el token de revisión."""
    order = svc.get_review(token)
    carrier = ProformaCarrier.from_order(order)
    pdf_buffer = ProformaService.generate_proforma_pdf(carrier)
    return pdf_response(pdf_buffer, f"proforma_{order.code or order.id}.pdf", format)
