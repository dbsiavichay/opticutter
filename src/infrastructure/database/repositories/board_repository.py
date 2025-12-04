from typing import List, Optional

from sqlalchemy.orm import Session

from src.infrastructure.database.models.board import BoardModel
from src.infrastructure.database.repositories.base import BaseRepository


class BoardRepository(BaseRepository[BoardModel]):
    """Repository para Board con operaciones específicas"""

    def __init__(self, db: Session):
        super().__init__(BoardModel, db)

    def get_by_code(self, code: str) -> Optional[BoardModel]:
        """Obtiene un tablero por código"""
        return self.db.query(BoardModel).filter(BoardModel.code == code).first()

    def search(self, search: str, skip: int = 0, limit: int = 100) -> List[BoardModel]:
        """Busca tableros por código o nombre"""
        search_pattern = f"%{search}%"
        return (
            self.db.query(BoardModel)
            .filter(
                (BoardModel.code.ilike(search_pattern))
                | (BoardModel.name.ilike(search_pattern))
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
