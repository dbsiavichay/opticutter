from typing import List, Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.boards.model import BoardModel
from src.modules.boards.schemas import BoardCreate, BoardUpdate
from src.shared.crud import CRUDService
from src.shared.database import get_db


class BoardService(CRUDService[BoardModel, BoardCreate, BoardUpdate]):
    """CRUD de tableros + búsquedas específicas."""

    model = BoardModel
    conflict_messages = {
        "code": "El código del tablero ya existe",
        "name": "El nombre del tablero ya existe",
    }

    def get_by_code(self, code: str) -> Optional[BoardModel]:
        """Obtiene un tablero por código."""
        return self.db.query(BoardModel).filter(BoardModel.code == code).first()

    def search_paginated(
        self, search: str, limit: int = 20, offset: int = 0
    ) -> Tuple[List[BoardModel], int]:
        """Busca tableros por código o nombre; devuelve ``(items, total)``."""
        pattern = f"%{search}%"
        query = self.db.query(BoardModel).filter(
            BoardModel.code.ilike(pattern) | BoardModel.name.ilike(pattern)
        )
        return self._paginate(query, limit, offset)


def board_service(db: Session = Depends(get_db)) -> BoardService:
    """Provider de ``BoardService`` para inyección en rutas."""
    return BoardService(db)
