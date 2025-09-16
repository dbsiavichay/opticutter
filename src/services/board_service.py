from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.models import BoardModel
from src.models.schemas import BoardCreate, BoardUpdate


class BoardService:
    """Service class for Board CRUD operations"""

    @staticmethod
    def create_board(db: Session, board_data: BoardCreate) -> BoardModel:
        """Create a new board"""
        try:
            db_board = BoardModel(
                code=board_data.code,
                name=board_data.name,
                description=board_data.description,
                length=board_data.length,
                width=board_data.width,
                thickness=board_data.thickness,
                grain_direction=board_data.grain_direction,
                price=board_data.price,
            )
            db.add(db_board)
            db.commit()
            db.refresh(db_board)
            return db_board
        except IntegrityError as e:
            db.rollback()
            if "code" in str(e):
                raise HTTPException(status_code=400, detail="Board code already exists")
            elif "name" in str(e):
                raise HTTPException(status_code=400, detail="Board name already exists")
            else:
                raise HTTPException(status_code=400, detail="Database integrity error")

    @staticmethod
    def get_board(db: Session, board_id: int) -> Optional[BoardModel]:
        """Get a board by ID"""
        return db.query(BoardModel).filter(BoardModel.id == board_id).first()

    @staticmethod
    def get_board_by_code(db: Session, code: str) -> Optional[BoardModel]:
        """Get a board by code"""
        return db.query(BoardModel).filter(BoardModel.code == code).first()

    @staticmethod
    def get_boards(db: Session, skip: int = 0, limit: int = 100) -> List[BoardModel]:
        """Get all boards with pagination"""
        return db.query(BoardModel).offset(skip).limit(limit).all()

    @staticmethod
    def update_board(
        db: Session, board_id: int, board_data: BoardUpdate
    ) -> Optional[BoardModel]:
        """Update a board"""
        db_board = db.query(BoardModel).filter(BoardModel.id == board_id).first()
        if not db_board:
            return None

        try:
            # Update only provided fields
            update_data = board_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_board, field, value)

            db.commit()
            db.refresh(db_board)
            return db_board
        except IntegrityError as e:
            db.rollback()
            if "code" in str(e):
                raise HTTPException(status_code=400, detail="Board code already exists")
            elif "name" in str(e):
                raise HTTPException(status_code=400, detail="Board name already exists")
            else:
                raise HTTPException(status_code=400, detail="Database integrity error")

    @staticmethod
    def delete_board(db: Session, board_id: int) -> bool:
        """Delete a board"""
        db_board = db.query(BoardModel).filter(BoardModel.id == board_id).first()
        if not db_board:
            return False

        try:
            db.delete(db_board)
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="Cannot delete board: it may be referenced by other records",
            )

    @staticmethod
    def search_boards(
        db: Session, query: str, skip: int = 0, limit: int = 100
    ) -> List[BoardModel]:
        """Search boards by name, code, or description"""
        search_filter = f"%{query}%"
        return (
            db.query(BoardModel)
            .filter(
                (BoardModel.name.ilike(search_filter))
                | (BoardModel.code.ilike(search_filter))
                | (BoardModel.description.ilike(search_filter))
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_boards_by_codes(db: Session, codes: List[str]) -> List[BoardModel]:
        """Get boards by a list of codes"""
        return db.query(BoardModel).filter(BoardModel.code.in_(codes)).all()
