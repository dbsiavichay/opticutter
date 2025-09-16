from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.db import get_db
from src.models.schemas import BoardCreate, BoardResponse, BoardUpdate
from src.services.board_service import BoardService

router = APIRouter(prefix="/boards", tags=["boards"])


@router.post("/", response_model=BoardResponse, status_code=201)
async def create_board(board_data: BoardCreate, db: Session = Depends(get_db)):
    """Create a new board"""
    return BoardService.create_board(db, board_data)


@router.get("/", response_model=List[BoardResponse])
async def get_boards(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    search: Optional[str] = Query(
        None, description="Search query for name, code, or description"
    ),
    db: Session = Depends(get_db),
):
    """Get all boards with optional search and pagination"""
    if search:
        return BoardService.search_boards(db, search, skip, limit)
    return BoardService.get_boards(db, skip, limit)


@router.get("/{board_id}", response_model=BoardResponse)
async def get_board(board_id: int, db: Session = Depends(get_db)):
    """Get a board by ID"""
    board = BoardService.get_board(db, board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    return board


@router.get("/code/{code}", response_model=BoardResponse)
async def get_board_by_code(code: str, db: Session = Depends(get_db)):
    """Get a board by code"""
    board = BoardService.get_board_by_code(db, code)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    return board


@router.put("/{board_id}", response_model=BoardResponse)
async def update_board(
    board_id: int, board_data: BoardUpdate, db: Session = Depends(get_db)
):
    """Update a board"""
    board = BoardService.update_board(db, board_id, board_data)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    return board


@router.delete("/{board_id}", status_code=204)
async def delete_board(board_id: int, db: Session = Depends(get_db)):
    """Delete a board"""
    success = BoardService.delete_board(db, board_id)
    if not success:
        raise HTTPException(status_code=404, detail="Board not found")
    return None
