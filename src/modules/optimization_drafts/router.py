from fastapi import APIRouter, Depends

from src.modules.optimization_drafts.schemas import (
    DraftCreate,
    DraftResponse,
    DraftSummaryResponse,
    DraftUpdate,
)
from src.modules.optimization_drafts.service import (
    OptimizationDraftService,
    optimization_draft_service,
)
from src.modules.users.dependencies import require_permission
from src.shared.pagination import PageParams
from src.shared.responses import (
    ERROR_RESPONSES,
    DataResponse,
    PaginatedResponse,
    ok,
    page,
)

# Borradores del optimizador: "administrador" y "vendedor" (RESOURCE_ROLES["optimizer"]).
router = APIRouter(
    prefix="/optimization-drafts",
    tags=["optimization-drafts"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_permission("optimizer"))],
)


@router.post("/", response_model=DataResponse[DraftResponse], status_code=201)
def create_draft(
    data: DraftCreate,
    svc: OptimizationDraftService = Depends(optimization_draft_service),
):
    """Crea un borrador del optimizador."""
    return ok(svc.create(data))


@router.get("/", response_model=PaginatedResponse[DraftSummaryResponse])
def list_drafts(
    paging: PageParams = Depends(),
    svc: OptimizationDraftService = Depends(optimization_draft_service),
):
    """Lista borradores (resumen liviano, sin ``payload``) con paginación."""
    items, total = svc.list_paginated(paging.limit, paging.offset)
    return page(items, total, paging.limit, paging.offset)


@router.get("/{draft_id}", response_model=DataResponse[DraftResponse])
def get_draft(
    draft_id: int,
    svc: OptimizationDraftService = Depends(optimization_draft_service),
):
    """Obtiene un borrador por ID (incluye el ``payload`` completo)."""
    return ok(svc.get_or_404(draft_id))


@router.put("/{draft_id}", response_model=DataResponse[DraftResponse])
def update_draft(
    draft_id: int,
    data: DraftUpdate,
    svc: OptimizationDraftService = Depends(optimization_draft_service),
):
    """Actualiza (sobrescribe) un borrador."""
    return ok(svc.update(draft_id, data))


@router.delete("/{draft_id}", status_code=204)
def delete_draft(
    draft_id: int,
    svc: OptimizationDraftService = Depends(optimization_draft_service),
):
    """Elimina un borrador."""
    svc.delete(draft_id)
