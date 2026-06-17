from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from src.modules.products.model import ProductType
from src.modules.products.schemas import ProductCreate, ProductResponse, ProductUpdate
from src.modules.products.service import ProductService, product_service
from src.modules.products.types.edge_banding import BandType
from src.modules.users.dependencies import require_permission
from src.shared.exceptions import EntityNotFoundError
from src.shared.pagination import PageParams
from src.shared.responses import (
    ERROR_RESPONSES,
    DataResponse,
    PaginatedResponse,
    ok,
    page,
)

router = APIRouter(prefix="/products", tags=["products"], responses=ERROR_RESPONSES)

# Lectura del catálogo: admin + vendedor. Escritura: solo admin.
_READ = Depends(require_permission("products:read"))
_WRITE = Depends(require_permission("products:write"))


@router.post(
    "/",
    response_model=DataResponse[ProductResponse],
    status_code=201,
    dependencies=[_WRITE],
)
def create_product(data: ProductCreate, svc: ProductService = Depends(product_service)):
    """Crea un producto (los ``attributes`` se validan según el ``type``)."""
    return ok(svc.create(data))


@router.get(
    "/", response_model=PaginatedResponse[ProductResponse], dependencies=[_READ]
)
def list_products(
    paging: PageParams = Depends(),
    type: Optional[ProductType] = Query(
        None, description="Filtra por tipo de producto"
    ),
    search: Optional[str] = Query(None, description="Búsqueda por nombre o código"),
    svc: ProductService = Depends(product_service),
):
    """Lista productos con filtro por tipo, búsqueda y paginación opcionales."""
    items, total = svc.search_paginated(search, type, paging.limit, paging.offset)
    return page(items, total, paging.limit, paging.offset)


@router.get(
    "/{board_id}/edge-bandings",
    response_model=DataResponse[List[ProductResponse]],
    dependencies=[_READ],
)
def get_board_edge_bandings(
    board_id: int,
    band_type: Optional[BandType] = Query(
        None, description="Filtra por tipo de canto: Soft o Hard"
    ),
    svc: ProductService = Depends(product_service),
):
    """Tapacantos coordinados con un tablero (mismo diseño y ancho según grosor).

    Empareja por la clave de diseño del código (evita falsos positivos por nombre)
    y aplica la regla grosor→ancho. ``data`` vacío significa que no hay tapacanto
    coordinado para esa combinación.
    """
    return ok(svc.find_edge_bandings_for_board(board_id, band_type))


@router.get(
    "/{product_id}", response_model=DataResponse[ProductResponse], dependencies=[_READ]
)
def get_product(product_id: int, svc: ProductService = Depends(product_service)):
    """Obtiene un producto por ID."""
    return ok(svc.get_or_404(product_id))


@router.get(
    "/code/{code}", response_model=DataResponse[ProductResponse], dependencies=[_READ]
)
def get_product_by_code(code: str, svc: ProductService = Depends(product_service)):
    """Obtiene un producto por código."""
    product = svc.get_by_code(code)
    if product is None:
        raise EntityNotFoundError("Product", code)
    return ok(product)


@router.put(
    "/{product_id}", response_model=DataResponse[ProductResponse], dependencies=[_WRITE]
)
def update_product(
    product_id: int,
    data: ProductUpdate,
    svc: ProductService = Depends(product_service),
):
    """Actualiza un producto."""
    return ok(svc.update(product_id, data))


@router.delete("/{product_id}", status_code=204, dependencies=[_WRITE])
def delete_product(product_id: int, svc: ProductService = Depends(product_service)):
    """Elimina un producto."""
    svc.delete(product_id)
