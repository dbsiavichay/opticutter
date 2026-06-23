"""Rutas públicas de revisión del cliente: el token es la única credencial.

Las consume el frontend de Maderable desde la URL del enlace. No exponen
identificadores internos ni datos de contacto del cliente (ver
``ReviewPreOrderResponse``); el desglose y los precios se recalculan en vivo y los
diagramas de corte se entregan vía el PDF de proforma, también gateado por el token.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from src.modules.optimizations.proforma import ProformaService, pdf_response
from src.modules.preorders.model import PreOrderModel, PreOrderStatus
from src.modules.preorders.review_service import (
    PreOrderReviewService,
    preorder_review_service,
)
from src.modules.preorders.schemas import (
    ReviewActionRequest,
    ReviewLineResponse,
    ReviewPieceResponse,
    ReviewPreOrderResponse,
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


def _to_review_response(
    preorder: PreOrderModel, payload: dict, pricing: dict
) -> ReviewPreOrderResponse:
    """Proyección sanitizada de la pre-orden + su optimización recalculada.

    Las líneas se muestran a precio de lista; el descuento del nivel de precio es un
    único ajuste a nivel documento (``pricing``).
    """
    client = preorder.client
    client_name = (
        " ".join(part for part in [client.first_name, client.last_name] if part) or None
    )
    lines = [
        ReviewLineResponse(
            product_code=m.get("product_code"),
            product_name=m.get("product_name"),
            quantity=m["count"],
            unit_price=m["cost_per_unit"],
            line_total=m["total_cost"],
        )
        for m in payload.get("materials_summary", [])
    ] + [
        ReviewLineResponse(
            product_code=e.get("product_code"),
            product_name=e.get("product_name"),
            quantity=e["billed_linear_m"],
            unit_price=e["price_per_m"],
            line_total=e["total_cost"],
            linear_m=e.get("linear_m"),
        )
        for e in payload.get("edge_bandings_summary", [])
    ]
    pieces = [
        ReviewPieceResponse(
            label=r.get("label"),
            height=r["height"],
            width=r["width"],
            quantity=r["quantity"],
            edges=r.get("edge_banding"),
        )
        for r in payload.get("requirements", [])
    ]
    return ReviewPreOrderResponse(
        reference=preorder.code,
        status=PreOrderStatus(preorder.status),
        order_code=preorder.order.code if preorder.order is not None else None,
        client_note=preorder.client_note,
        client_name=client_name,
        currency="USD",
        subtotal=pricing["subtotal"],
        price_tier_name=pricing.get("price_tier_name"),
        discount_rate=pricing.get("discount_rate", 0.0),
        discount_amount=pricing.get("discount_amount", 0.0),
        total=pricing["total"],
        total_boards_used=payload.get("total_boards_used", 0),
        created_at=preorder.created_at,
        sent_at=preorder.sent_at,
        confirmed_at=preorder.confirmed_at,
        expires_at=preorder.expires_at,
        lines=lines,
        pieces=pieces,
    )


@router.get("/{token}", response_model=DataResponse[ReviewPreOrderResponse])
def get_review(
    token: str, svc: PreOrderReviewService = Depends(preorder_review_service)
):
    """Detalle sanitizado de la cotización asociada al token (precios vivos)."""
    preorder = svc.get_review(token)
    payload, _ = svc.preorders.compute_payload(preorder)
    pricing = svc.preorders.build_pricing_for(preorder, payload)
    return ok(_to_review_response(preorder, payload, pricing))


@router.post("/{token}/confirm", response_model=DataResponse[ReviewPreOrderResponse])
def confirm_review(
    token: str,
    request: Request,
    data: Optional[ReviewActionRequest] = None,
    svc: PreOrderReviewService = Depends(preorder_review_service),
):
    """El cliente confirma: crea la Orden inmutable; reintento benigno."""
    note = data.note if data else None
    preorder = svc.confirm(token, note=note, meta=_client_meta(request))
    payload, _ = svc.preorders.compute_payload(preorder)
    pricing = svc.preorders.build_pricing_for(preorder, payload)
    return ok(_to_review_response(preorder, payload, pricing))


@router.post("/{token}/reject", response_model=DataResponse[ReviewPreOrderResponse])
def reject_review(
    token: str,
    request: Request,
    data: Optional[ReviewActionRequest] = None,
    svc: PreOrderReviewService = Depends(preorder_review_service),
):
    """El cliente rechaza la cotización (``sent → rejected``)."""
    note = data.note if data else None
    preorder = svc.reject(token, note=note, meta=_client_meta(request))
    payload, _ = svc.preorders.compute_payload(preorder)
    pricing = svc.preorders.build_pricing_for(preorder, payload)
    return ok(_to_review_response(preorder, payload, pricing))


@router.post(
    "/{token}/request-changes", response_model=DataResponse[ReviewPreOrderResponse]
)
def request_changes_review(
    token: str,
    data: Optional[ReviewActionRequest] = None,
    svc: PreOrderReviewService = Depends(preorder_review_service),
):
    """El cliente pide ajustes (``sent → changes_requested``); el enlace sigue vivo."""
    note = data.note if data else None
    preorder = svc.request_changes(token, note=note)
    payload, _ = svc.preorders.compute_payload(preorder)
    pricing = svc.preorders.build_pricing_for(preorder, payload)
    return ok(_to_review_response(preorder, payload, pricing))


# Exento de la envoltura JSON: transporte de archivo PDF (igual que en preorders).
@router.get("/{token}/proforma")
def get_review_proforma(
    token: str,
    format: str = _FORMAT_QUERY,
    svc: PreOrderReviewService = Depends(preorder_review_service),
):
    """Proforma PDF de la cotización, gateada por el token de revisión."""
    preorder = svc.get_review(token)
    carrier = svc.preorders.build_carrier(preorder)
    pdf_buffer = ProformaService.generate_proforma_pdf(carrier)
    return pdf_response(
        pdf_buffer, f"proforma_{preorder.code or preorder.id}.pdf", format
    )
