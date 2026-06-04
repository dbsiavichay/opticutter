from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.modules.clients.schemas import ClientCreate, ClientResponse, ClientUpdate
from src.modules.clients.service import ClientService, client_service
from src.shared.exceptions import EntityNotFoundError
from src.shared.pagination import PageParams
from src.shared.responses import (
    ERROR_RESPONSES,
    DataResponse,
    PaginatedResponse,
    ok,
    page,
)

router = APIRouter(prefix="/clients", tags=["clients"], responses=ERROR_RESPONSES)


@router.post("/", response_model=DataResponse[ClientResponse], status_code=201)
def create_client(data: ClientCreate, svc: ClientService = Depends(client_service)):
    """Crea un nuevo cliente."""
    return ok(svc.create(data))


@router.post("/resolve", response_model=DataResponse[ClientResponse])
def resolve_client(data: ClientCreate, svc: ClientService = Depends(client_service)):
    """Obtiene el cliente por identificador o lo crea (idempotente).

    Pensado para el bot: resuelve al cliente justo antes de una acción comercial
    (proforma u orden) en una sola llamada, sin GET + POST condicional.
    """
    return ok(svc.resolve(data))


@router.get("/", response_model=PaginatedResponse[ClientResponse])
def list_clients(
    paging: PageParams = Depends(),
    search: Optional[str] = Query(
        None, description="Búsqueda por identificador, nombre o apellido"
    ),
    svc: ClientService = Depends(client_service),
):
    """Lista clientes con búsqueda y paginación opcionales."""
    if search:
        items, total = svc.search_paginated(search, paging.limit, paging.offset)
    else:
        items, total = svc.list_paginated(paging.limit, paging.offset)
    return page(items, total, paging.limit, paging.offset)


@router.get("/{client_id}", response_model=DataResponse[ClientResponse])
def get_client(client_id: int, svc: ClientService = Depends(client_service)):
    """Obtiene un cliente por ID."""
    return ok(svc.get_or_404(client_id))


@router.get("/identifier/{identifier}", response_model=DataResponse[ClientResponse])
def get_client_by_identifier(
    identifier: str, svc: ClientService = Depends(client_service)
):
    """Obtiene un cliente por identificador."""
    client = svc.get_by_identifier(identifier)
    if client is None:
        raise EntityNotFoundError("Client", identifier)
    return ok(client)


@router.put("/{client_id}", response_model=DataResponse[ClientResponse])
def update_client(
    client_id: int, data: ClientUpdate, svc: ClientService = Depends(client_service)
):
    """Actualiza un cliente."""
    return ok(svc.update(client_id, data))


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: int, svc: ClientService = Depends(client_service)):
    """Elimina un cliente."""
    svc.delete(client_id)
