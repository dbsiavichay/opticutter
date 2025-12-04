from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.v1.schemas import BoardCreate, BoardUpdate
from src.infrastructure.database.models import BoardModel
from src.infrastructure.database.repositories import BoardRepository


class BoardService:
    """Service class for Board CRUD operations"""

    def __init__(self, db: Session):
        self.repository = BoardRepository(db)

    def create_board(self, board_data: BoardCreate) -> BoardModel:
        """Create a new board"""
        try:
            board = BoardModel(
                code=board_data.code,
                name=board_data.name,
                description=board_data.description,
                length=board_data.length,
                width=board_data.width,
                thickness=board_data.thickness,
                grain_direction=board_data.grain_direction,
                price=board_data.price,
            )
            return self.repository.create(board)
        except IntegrityError as e:
            if "code" in str(e):
                raise HTTPException(status_code=400, detail="Board code already exists")
            elif "name" in str(e):
                raise HTTPException(status_code=400, detail="Board name already exists")
            else:
                raise HTTPException(status_code=400, detail="Database integrity error")

    def get_board(self, board_id: int) -> Optional[BoardModel]:
        """Get a board by ID"""
        return self.repository.get(board_id)

    def get_board_by_code(self, code: str) -> Optional[BoardModel]:
        """Get a board by code"""
        return self.repository.get_by_code(code)

    def get_boards(self, skip: int = 0, limit: int = 100) -> List[BoardModel]:
        """Get all boards with pagination"""
        return self.repository.get_all(skip, limit)

    def update_board(
        self, board_id: int, board_data: BoardUpdate
    ) -> Optional[BoardModel]:
        """Update a board"""
        board = self.repository.get(board_id)
        if not board:
            return None

        try:
            update_data = board_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(board, field, value)

            return self.repository.update(board)
        except IntegrityError as e:
            if "code" in str(e):
                raise HTTPException(status_code=400, detail="Board code already exists")
            elif "name" in str(e):
                raise HTTPException(status_code=400, detail="Board name already exists")
            else:
                raise HTTPException(status_code=400, detail="Database integrity error")

    def delete_board(self, board_id: int) -> bool:
        """Delete a board"""
        try:
            return self.repository.delete(board_id)
        except IntegrityError:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete board: it may be referenced by other records",
            )

    def search_boards(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[BoardModel]:
        """Search boards by name, code, or description"""
        return self.repository.search(query, skip, limit)
