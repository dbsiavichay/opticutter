from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.v1.schemas import ClientCreate, ClientUpdate
from src.infrastructure.database.models import ClientModel
from src.infrastructure.database.repositories import ClientRepository


class ClientService:
    """Service class for Client CRUD operations"""

    def __init__(self, db: Session):
        self.repository = ClientRepository(db)

    def create_client(self, client_data: ClientCreate) -> ClientModel:
        """Create a new client"""
        try:
            client = ClientModel(
                phone=client_data.phone,
                first_name=client_data.first_name,
                last_name=client_data.last_name,
            )
            return self.repository.create(client)
        except IntegrityError as e:
            if "phone" in str(e):
                raise HTTPException(
                    status_code=400, detail="Phone number already exists"
                )
            else:
                raise HTTPException(status_code=400, detail="Database integrity error")

    def get_client(self, client_id: int) -> Optional[ClientModel]:
        """Get a client by ID"""
        return self.repository.get(client_id)

    def get_client_by_phone(self, phone: str) -> Optional[ClientModel]:
        """Get a client by phone number"""
        return self.repository.get_by_phone(phone)

    def get_clients(self, skip: int = 0, limit: int = 100) -> List[ClientModel]:
        """Get all clients with pagination"""
        return self.repository.get_all(skip, limit)

    def search_clients(
        self, search: str, skip: int = 0, limit: int = 100
    ) -> List[ClientModel]:
        """Search clients by phone, first name, or last name"""
        return self.repository.search(search, skip, limit)

    def update_client(
        self, client_id: int, client_data: ClientUpdate
    ) -> Optional[ClientModel]:
        """Update a client"""
        client = self.repository.get(client_id)
        if not client:
            return None

        try:
            update_data = client_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(client, field, value)

            return self.repository.update(client)
        except IntegrityError as e:
            if "phone" in str(e):
                raise HTTPException(
                    status_code=400, detail="Phone number already exists"
                )
            else:
                raise HTTPException(status_code=400, detail="Database integrity error")

    def delete_client(self, client_id: int) -> bool:
        """Delete a client"""
        return self.repository.delete(client_id)
