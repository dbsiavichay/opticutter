from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.models import ClientModel
from src.models.schemas import ClientCreate, ClientUpdate


class ClientService:
    """Service class for Client CRUD operations"""

    @staticmethod
    def create_client(db: Session, client_data: ClientCreate) -> ClientModel:
        """Create a new client"""
        try:
            db_client = ClientModel(
                phone=client_data.phone,
                first_name=client_data.first_name,
                last_name=client_data.last_name,
            )
            db.add(db_client)
            db.commit()
            db.refresh(db_client)
            return db_client
        except IntegrityError as e:
            db.rollback()
            if "phone" in str(e):
                raise HTTPException(
                    status_code=400, detail="Phone number already exists"
                )
            else:
                raise HTTPException(status_code=400, detail="Database integrity error")

    @staticmethod
    def get_client(db: Session, client_id: int) -> Optional[ClientModel]:
        """Get a client by ID"""
        return db.query(ClientModel).filter(ClientModel.id == client_id).first()

    @staticmethod
    def get_client_by_phone(db: Session, phone: str) -> Optional[ClientModel]:
        """Get a client by phone number"""
        return db.query(ClientModel).filter(ClientModel.phone == phone).first()

    @staticmethod
    def get_clients(db: Session, skip: int = 0, limit: int = 100) -> List[ClientModel]:
        """Get all clients with pagination"""
        return db.query(ClientModel).offset(skip).limit(limit).all()

    @staticmethod
    def search_clients(
        db: Session, search: str, skip: int = 0, limit: int = 100
    ) -> List[ClientModel]:
        """Search clients by phone, first name, or last name"""
        search_pattern = f"%{search}%"
        return (
            db.query(ClientModel)
            .filter(
                (ClientModel.phone.ilike(search_pattern))
                | (ClientModel.first_name.ilike(search_pattern))
                | (ClientModel.last_name.ilike(search_pattern))
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_client(
        db: Session, client_id: int, client_data: ClientUpdate
    ) -> Optional[ClientModel]:
        """Update a client"""
        db_client = db.query(ClientModel).filter(ClientModel.id == client_id).first()
        if not db_client:
            return None

        try:
            # Update only provided fields
            update_data = client_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_client, field, value)

            db.commit()
            db.refresh(db_client)
            return db_client
        except IntegrityError as e:
            db.rollback()
            if "phone" in str(e):
                raise HTTPException(
                    status_code=400, detail="Phone number already exists"
                )
            else:
                raise HTTPException(status_code=400, detail="Database integrity error")

    @staticmethod
    def delete_client(db: Session, client_id: int) -> bool:
        """Delete a client"""
        db_client = db.query(ClientModel).filter(ClientModel.id == client_id).first()
        if not db_client:
            return False

        # Check if client has associated optimizations
        if db_client.optimizations:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete client with associated optimizations",
            )

        db.delete(db_client)
        db.commit()
        return True
