from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from src.modules.boards.schemas import BoardCreate, BoardResponse, BoardUpdate
from src.modules.boards.service import BoardService, board_service
from src.shared.exceptions import EntityNotFoundError

router = APIRouter(prefix="/boards", tags=["boards"])


@router.post("/", response_model=BoardResponse, status_code=201)
def create_board(data: BoardCreate, svc: BoardService = Depends(board_service)):
    """Crea un nuevo tablero."""
    return svc.create(data)


@router.get("/", response_model=List[BoardResponse])
def list_boards(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    search: Optional[str] = Query(
        None, description="Search query for name, code, or description"
    ),
    svc: BoardService = Depends(board_service),
):
    """Lista tableros con búsqueda y paginación opcionales."""
    if search:
        return svc.search(search, skip, limit)
    return svc.list(skip, limit)


@router.get("/{board_id}", response_model=BoardResponse)
def get_board(board_id: int, svc: BoardService = Depends(board_service)):
    """Obtiene un tablero por ID."""
    return svc.get_or_404(board_id)


@router.get("/code/{code}", response_model=BoardResponse)
def get_board_by_code(code: str, svc: BoardService = Depends(board_service)):
    """Obtiene un tablero por código."""
    board = svc.get_by_code(code)
    if board is None:
        raise EntityNotFoundError("Board", code)
    return board


@router.put("/{board_id}", response_model=BoardResponse)
def update_board(
    board_id: int, data: BoardUpdate, svc: BoardService = Depends(board_service)
):
    """Actualiza un tablero."""
    return svc.update(board_id, data)


@router.delete("/{board_id}", status_code=204)
def delete_board(board_id: int, svc: BoardService = Depends(board_service)):
    """Elimina un tablero."""
    svc.delete(board_id)
