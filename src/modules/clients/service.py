from typing import List, Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.clients.model import ClientModel
from src.modules.clients.schemas import ClientCreate, ClientUpdate
from src.shared.crud import CRUDService
from src.shared.database import get_db


class ClientService(CRUDService[ClientModel, ClientCreate, ClientUpdate]):
    """CRUD de clientes + búsquedas específicas."""

    model = ClientModel
    conflict_messages = {"identifier": "El identificador ya existe"}

    def get_by_identifier(self, identifier: str) -> Optional[ClientModel]:
        """Obtiene un cliente por identificador."""
        return (
            self.db.query(ClientModel)
            .filter(ClientModel.identifier == identifier)
            .first()
        )

    def search(self, search: str, skip: int = 0, limit: int = 100) -> List[ClientModel]:
        """Busca clientes por identificador, nombre o apellido."""
        pattern = f"%{search}%"
        return (
            self.db.query(ClientModel)
            .filter(
                ClientModel.identifier.ilike(pattern)
                | ClientModel.first_name.ilike(pattern)
                | ClientModel.last_name.ilike(pattern)
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


def client_service(db: Session = Depends(get_db)) -> ClientService:
    """Provider de ``ClientService`` para inyección en rutas."""
    return ClientService(db)
