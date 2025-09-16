from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.db import get_db
from src.models.schemas import ClientCreate, ClientResponse, ClientUpdate
from src.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(client_data: ClientCreate, db: Session = Depends(get_db)):
    """Create a new client"""
    return ClientService.create_client(db, client_data)


@router.get("/", response_model=List[ClientResponse])
async def get_clients(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    search: Optional[str] = Query(
        None, description="Search query for phone, first name, or last name"
    ),
    db: Session = Depends(get_db),
):
    """Get all clients with optional search and pagination"""
    if search:
        return ClientService.search_clients(db, search, skip, limit)
    return ClientService.get_clients(db, skip, limit)


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int, db: Session = Depends(get_db)):
    """Get a client by ID"""
    client = ClientService.get_client(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("/phone/{phone}", response_model=ClientResponse)
async def get_client_by_phone(phone: str, db: Session = Depends(get_db)):
    """Get a client by phone number"""
    client = ClientService.get_client_by_phone(db, phone)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int, client_data: ClientUpdate, db: Session = Depends(get_db)
):
    """Update a client"""
    client = ClientService.update_client(db, client_id, client_data)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.delete("/{client_id}", status_code=204)
async def delete_client(client_id: int, db: Session = Depends(get_db)):
    """Delete a client"""
    success = ClientService.delete_client(db, client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Client not found")
