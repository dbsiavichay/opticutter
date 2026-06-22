from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.modules.optimizations.proforma import ProformaService, pdf_response
from src.modules.preorders.model import PreOrderModel, PreOrderStatus
from src.modules.preorders.review_service import (
    PreOrderReviewService,
    preorder_review_service,
)
from src.modules.preorders.schemas import (
    PreOrderCreate,
    PreOrderResponse,
    PreOrderSummaryResponse,
    PreOrderUpdate,
    ReviewLinkInfoResponse,
    ReviewLinkResponse,
)
from src.modules.preorders.service import PreOrderService, preorder_service
from src.modules.users.dependencies import (
    get_branch_scope,
    get_current_user,
    require_permission,
)
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

# Pre-órdenes (cotización interna): "administrador" y "vendedor"
# (RESOURCE_ROLES["preorders"]). El flujo público del cliente vive en
# ``public_router.py`` y se autentica solo por el token del enlace.
router = APIRouter(
    prefix="/preorders",
    tags=["preorders"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_permission("preorders"))],
)

_FORMAT_QUERY = Query(
    default="pdf",
    description="Formato de salida: 'pdf' (archivo) o 'base64' (JSON)",
    pattern="^(pdf|base64)$",
)


def _detail(svc: PreOrderService, preorder: PreOrderModel) -> PreOrderResponse:
    """Detalle de la pre-orden con su optimización recalculada (precios vivos)."""
    return PreOrderResponse(
        id=preorder.id,
        code=preorder.code,
        client=preorder.client,
        branch=preorder.branch,
        status=PreOrderStatus(preorder.status),
        notes=preorder.notes,
        client_note=preorder.client_note,
        source=preorder.source,
        order_id=preorder.order_id,
        created_at=preorder.created_at,
        updated_at=preorder.updated_at,
        sent_at=preorder.sent_at,
        confirmed_at=preorder.confirmed_at,
        expires_at=preorder.expires_at,
        materials=preorder.materials,
        requirements=preorder.requirements,
        optimization=svc.build_optimize_response(preorder),
        history=preorder.history,
    )


@router.post("/", response_model=DataResponse[PreOrderResponse], status_code=201)
def create_preorder(
    data: PreOrderCreate,
    svc: PreOrderService = Depends(preorder_service),
    current_user: UserModel = Depends(get_current_user),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Crea una pre-orden (cotización mutable) con los inputs del optimizador.

    El operador la crea en su sucursal; el vendedor la predetermina en su sucursal base
    (puede sobrescribirla con ``branchId``); el admin debe indicar ``branchId``.
    """
    return ok(
        _detail(
            svc,
            svc.create(
                data,
                actor=staff_actor(current_user),
                branch_scope=branch_scope,
                default_branch_id=current_user.branch_id,
            ),
        )
    )


@router.get("/", response_model=PaginatedResponse[PreOrderSummaryResponse])
def list_preorders(
    status: Optional[PreOrderStatus] = Query(
        default=None, description="Filtra pre-órdenes por estado"
    ),
    client_id: Optional[int] = Query(
        default=None, alias="clientId", description="Filtra por cliente"
    ),
    branch_id: Optional[int] = Query(
        default=None,
        alias="branchId",
        description="Solo roles globales (admin/vendedor): estrecha el listado a una "
        "sucursal (vacío = todas)",
    ),
    paging: PageParams = Depends(),
    svc: PreOrderService = Depends(preorder_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Lista pre-órdenes (resumen liviano) con filtros y paginación opcionales.

    El operador solo ve las de su sucursal; los roles globales (admin/vendedor) ven
    todas (o filtran con ``branchId``).
    """
    items, total = svc.list_preorders(
        status=status,
        client_id=client_id,
        branch_scope=branch_scope,
        branch_filter=branch_id,
        limit=paging.limit,
        offset=paging.offset,
    )
    return page(items, total, paging.limit, paging.offset)


@router.get("/{preorder_id}", response_model=DataResponse[PreOrderResponse])
def get_preorder(
    preorder_id: int,
    svc: PreOrderService = Depends(preorder_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Obtiene una pre-orden por ID con su optimización recalculada."""
    return ok(_detail(svc, svc.get_scoped_or_404(preorder_id, branch_scope)))


@router.put("/{preorder_id}", response_model=DataResponse[PreOrderResponse])
def update_preorder(
    preorder_id: int,
    data: PreOrderUpdate,
    svc: PreOrderService = Depends(preorder_service),
    current_user: UserModel = Depends(get_current_user),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Edita una pre-orden abierta (draft/sent)."""
    return ok(
        _detail(
            svc,
            svc.update(
                preorder_id,
                data,
                actor=staff_actor(current_user),
                branch_scope=branch_scope,
            ),
        )
    )


@router.delete("/{preorder_id}", status_code=204)
def delete_preorder(
    preorder_id: int,
    svc: PreOrderService = Depends(preorder_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Elimina una pre-orden (salvo si ya fue confirmada)."""
    svc.delete(preorder_id, branch_scope=branch_scope)


@router.post(
    "/{preorder_id}/review-link",
    response_model=DataResponse[ReviewLinkResponse],
    status_code=201,
)
def create_review_link(
    preorder_id: int,
    svc: PreOrderReviewService = Depends(preorder_review_service),
    current_user: UserModel = Depends(get_current_user),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Genera el enlace de revisión del cliente (revoca el anterior si existía).

    Transiciona la pre-orden a ``sent``. El token solo se expone en esta respuesta;
    si se pierde, se regenera.
    """
    link, raw_token = svc.generate(
        preorder_id, actor=staff_actor(current_user), branch_scope=branch_scope
    )
    return ok(
        ReviewLinkResponse(
            token=raw_token,
            url=svc.build_url(raw_token),
            status=link.status,
            expires_at=link.expires_at,
            created_at=link.created_at,
        )
    )


@router.get(
    "/{preorder_id}/review-link", response_model=DataResponse[ReviewLinkInfoResponse]
)
def get_review_link_info(
    preorder_id: int,
    svc: PreOrderReviewService = Depends(preorder_review_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Metadatos del último enlace de revisión (sin el token, irrecuperable)."""
    return ok(svc.get_latest_info(preorder_id, branch_scope=branch_scope))


# Exento de la envoltura JSON: transporte de archivo PDF (StreamingResponse/base64).
@router.get("/{preorder_id}/proforma")
def get_preorder_proforma(
    preorder_id: int,
    format: str = _FORMAT_QUERY,
    svc: PreOrderService = Depends(preorder_service),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Proforma comercial recalculada (precios vivos) de la pre-orden."""
    preorder = svc.get_scoped_or_404(preorder_id, branch_scope)
    carrier = svc.build_carrier(preorder)
    pdf_buffer = ProformaService.generate_proforma_pdf(carrier)
    return pdf_response(
        pdf_buffer, f"proforma_{preorder.code or preorder.id}.pdf", format
    )
