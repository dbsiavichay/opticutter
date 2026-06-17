from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.modules.branches.schemas import BranchCreate, BranchResponse, BranchUpdate
from src.modules.branches.service import BranchService, branch_service
from src.modules.users.dependencies import require_permission
from src.shared.pagination import PageParams
from src.shared.responses import (
    ERROR_RESPONSES,
    DataResponse,
    PaginatedResponse,
    ok,
    page,
)

router = APIRouter(prefix="/branches", tags=["branches"], responses=ERROR_RESPONSES)

# Administración (CRUD): solo "administrador". Lectura/listado: cualquier staff
# (para selectores y mostrar el nombre de la sucursal propia).
_READ = Depends(require_permission("branches:read"))
_WRITE = Depends(require_permission("branches:manage"))


@router.post(
    "/",
    response_model=DataResponse[BranchResponse],
    status_code=201,
    dependencies=[_WRITE],
)
def create_branch(data: BranchCreate, svc: BranchService = Depends(branch_service)):
    """Crea una sucursal."""
    return ok(svc.create(data))


@router.get("/", response_model=PaginatedResponse[BranchResponse], dependencies=[_READ])
def list_branches(
    paging: PageParams = Depends(),
    search: Optional[str] = Query(None, description="Búsqueda por código o nombre"),
    svc: BranchService = Depends(branch_service),
):
    """Lista sucursales con búsqueda y paginación opcionales."""
    if search:
        items, total = svc.search_paginated(search, paging.limit, paging.offset)
    else:
        items, total = svc.list_paginated(paging.limit, paging.offset)
    return page(items, total, paging.limit, paging.offset)


@router.get(
    "/{branch_id}", response_model=DataResponse[BranchResponse], dependencies=[_READ]
)
def get_branch(branch_id: int, svc: BranchService = Depends(branch_service)):
    """Obtiene una sucursal por ID."""
    return ok(svc.get_or_404(branch_id))


@router.put(
    "/{branch_id}", response_model=DataResponse[BranchResponse], dependencies=[_WRITE]
)
def update_branch(
    branch_id: int, data: BranchUpdate, svc: BranchService = Depends(branch_service)
):
    """Actualiza una sucursal (incluye baja lógica vía ``isActive``)."""
    return ok(svc.update(branch_id, data))


@router.delete("/{branch_id}", status_code=204, dependencies=[_WRITE])
def delete_branch(branch_id: int, svc: BranchService = Depends(branch_service)):
    """Elimina una sucursal."""
    svc.delete(branch_id)
