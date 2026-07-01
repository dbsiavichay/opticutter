from typing import List, Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.clients.model import ClientModel
from src.modules.clients.schemas import ClientCreate, ClientUpdate
from src.shared.crud import CRUDService
from src.shared.database import get_db
from src.shared.exceptions import BusinessRuleError, ConflictError


def require_phone(client: ClientModel) -> None:
    """Require a registered phone number before issuing commercial documents.

    Hard business rule: neither the proforma nor the order can be generated
    without a valid mobile phone number. Email is optional and never blocks.
    """
    if not (client.phone and client.phone.strip()):
        raise BusinessRuleError(
            "El cliente no tiene un número de celular registrado. Solicita y "
            "registra su celular antes de generar la proforma o el pedido."
        )


class ClientService(CRUDService[ClientModel, ClientCreate, ClientUpdate]):
    """Client CRUD + specific search queries."""

    model = ClientModel
    conflict_messages = {"identifier": "El identificador ya existe"}

    def get_by_identifier(self, identifier: str) -> Optional[ClientModel]:
        """Gets a client by identifier."""
        return (
            self.db.query(ClientModel)
            .filter(ClientModel.identifier == identifier)
            .first()
        )

    def resolve(self, data: ClientCreate) -> ClientModel:
        """Gets the client by ``identifier`` or creates it (idempotent).

        Lazy resolution for the bot: the client only materializes once there is
        a commercial action. Safe against races — two near-simultaneous messages
        from the same user — because the ``identifier`` unique constraint fails
        the second creation; the conflict is caught and the already-created
        client is re-read.
        """
        existing = self.get_by_identifier(data.identifier)
        if existing is not None:
            return existing
        try:
            return self.create(data)
        except ConflictError:
            client = self.get_by_identifier(data.identifier)
            if client is None:
                raise
            return client

    def search_paginated(
        self, search: str, limit: int = 20, offset: int = 0
    ) -> Tuple[List[ClientModel], int]:
        """Searches clients by identifier, first name, or last name; ``(items, total)``."""
        pattern = f"%{search}%"
        query = self.db.query(ClientModel).filter(
            ClientModel.identifier.ilike(pattern)
            | ClientModel.first_name.ilike(pattern)
            | ClientModel.last_name.ilike(pattern)
        )
        return self._paginate(query, limit, offset)


def client_service(db: Session = Depends(get_db)) -> ClientService:
    """``ClientService`` provider for route injection."""
    return ClientService(db)
