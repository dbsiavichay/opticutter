from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.modules.boards.schemas import BoardCreate, BoardResponse, BoardUpdate
from src.modules.boards.service import BoardService, board_service
from src.shared.exceptions import EntityNotFoundError
from src.shared.pagination import PageParams
from src.shared.responses import (
    ERROR_RESPONSES,
    DataResponse,
    PaginatedResponse,
    ok,
    page,
)

router = APIRouter(prefix="/boards", tags=["boards"], responses=ERROR_RESPONSES)


@router.post("/", response_model=DataResponse[BoardResponse], status_code=201)
def create_board(data: BoardCreate, svc: BoardService = Depends(board_service)):
    """Crea un nuevo tablero."""
    return ok(svc.create(data))


@router.get("/", response_model=PaginatedResponse[BoardResponse])
def list_boards(
    paging: PageParams = Depends(),
    search: Optional[str] = Query(None, description="Búsqueda por nombre o código"),
    svc: BoardService = Depends(board_service),
):
    """Lista tableros con búsqueda y paginación opcionales."""
    if search:
        items, total = svc.search_paginated(search, paging.limit, paging.offset)
    else:
        items, total = svc.list_paginated(paging.limit, paging.offset)
    return page(items, total, paging.limit, paging.offset)


@router.get("/{board_id}", response_model=DataResponse[BoardResponse])
def get_board(board_id: int, svc: BoardService = Depends(board_service)):
    """Obtiene un tablero por ID."""
    return ok(svc.get_or_404(board_id))


@router.get("/code/{code}", response_model=DataResponse[BoardResponse])
def get_board_by_code(code: str, svc: BoardService = Depends(board_service)):
    """Obtiene un tablero por código."""
    board = svc.get_by_code(code)
    if board is None:
        raise EntityNotFoundError("Board", code)
    return ok(board)


@router.put("/{board_id}", response_model=DataResponse[BoardResponse])
def update_board(
    board_id: int, data: BoardUpdate, svc: BoardService = Depends(board_service)
):
    """Actualiza un tablero."""
    return ok(svc.update(board_id, data))


@router.delete("/{board_id}", status_code=204)
def delete_board(board_id: int, svc: BoardService = Depends(board_service)):
    """Elimina un tablero."""
    svc.delete(board_id)
