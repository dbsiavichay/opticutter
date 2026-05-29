from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from src.modules.clients.schemas import ClientCreate, ClientResponse, ClientUpdate
from src.modules.clients.service import ClientService, client_service
from src.shared.exceptions import EntityNotFoundError

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("/", response_model=ClientResponse, status_code=201)
def create_client(data: ClientCreate, svc: ClientService = Depends(client_service)):
    """Crea un nuevo cliente."""
    return svc.create(data)


@router.get("/", response_model=List[ClientResponse])
def list_clients(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    search: Optional[str] = Query(
        None, description="Search query for phone, first name, or last name"
    ),
    svc: ClientService = Depends(client_service),
):
    """Lista clientes con búsqueda y paginación opcionales."""
    if search:
        return svc.search(search, skip, limit)
    return svc.list(skip, limit)


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: int, svc: ClientService = Depends(client_service)):
    """Obtiene un cliente por ID."""
    return svc.get_or_404(client_id)


@router.get("/phone/{phone}", response_model=ClientResponse)
def get_client_by_phone(phone: str, svc: ClientService = Depends(client_service)):
    """Obtiene un cliente por teléfono."""
    client = svc.get_by_phone(phone)
    if client is None:
        raise EntityNotFoundError("Client", phone)
    return client


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: int, data: ClientUpdate, svc: ClientService = Depends(client_service)
):
    """Actualiza un cliente."""
    return svc.update(client_id, data)


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: int, svc: ClientService = Depends(client_service)):
    """Elimina un cliente."""
    svc.delete(client_id)
