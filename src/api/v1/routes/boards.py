from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.v1.schemas import BoardCreate, BoardResponse, BoardUpdate
from src.application.services import BoardService
from src.infrastructure.database import get_db

router = APIRouter(prefix="/boards", tags=["boards"])


@router.post("/", response_model=BoardResponse, status_code=201)
async def create_board(board_data: BoardCreate, db: Session = Depends(get_db)):
    """Create a new board"""
    service = BoardService(db)
    return service.create_board(board_data)


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
    service = BoardService(db)
    if search:
        return service.search_boards(search, skip, limit)
    return service.get_boards(skip, limit)


@router.get("/{board_id}", response_model=BoardResponse)
async def get_board(board_id: int, db: Session = Depends(get_db)):
    """Get a board by ID"""
    service = BoardService(db)
    board = service.get_board(board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    return board


@router.get("/code/{code}", response_model=BoardResponse)
async def get_board_by_code(code: str, db: Session = Depends(get_db)):
    """Get a board by code"""
    service = BoardService(db)
    board = service.get_board_by_code(code)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    return board


@router.put("/{board_id}", response_model=BoardResponse)
async def update_board(
    board_id: int, board_data: BoardUpdate, db: Session = Depends(get_db)
):
    """Update a board"""
    service = BoardService(db)
    board = service.update_board(board_id, board_data)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    return board


@router.delete("/{board_id}", status_code=204)
async def delete_board(board_id: int, db: Session = Depends(get_db)):
    """Delete a board"""
    service = BoardService(db)
    success = service.delete_board(board_id)
    if not success:
        raise HTTPException(status_code=404, detail="Board not found")
    return None
