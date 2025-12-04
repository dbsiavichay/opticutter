from typing import List, Optional

from sqlalchemy.orm import Session

from src.infrastructure.database.models.client import ClientModel
from src.infrastructure.database.repositories.base import BaseRepository


class ClientRepository(BaseRepository[ClientModel]):
    """Repository para Client con operaciones específicas"""

    def __init__(self, db: Session):
        super().__init__(ClientModel, db)

    def get_by_phone(self, phone: str) -> Optional[ClientModel]:
        """Obtiene un cliente por teléfono"""
        return self.db.query(ClientModel).filter(ClientModel.phone == phone).first()

    def search(self, search: str, skip: int = 0, limit: int = 100) -> List[ClientModel]:
        """Busca clientes por teléfono, nombre o apellido"""
        search_pattern = f"%{search}%"
        return (
            self.db.query(ClientModel)
            .filter(
                (ClientModel.phone.ilike(search_pattern))
                | (ClientModel.first_name.ilike(search_pattern))
                | (ClientModel.last_name.ilike(search_pattern))
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
