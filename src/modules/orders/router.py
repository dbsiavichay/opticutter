from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from src.modules.orders.model import OrderStatus
from src.modules.orders.schemas import OrderCreate, OrderResponse, OrderStatusUpdate
from src.modules.orders.service import OrderService, order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=OrderResponse, status_code=201)
def create_order(data: OrderCreate, svc: OrderService = Depends(order_service)):
    """Crea (o recupera, por idempotencia) una orden congelando el snapshot."""
    return svc.create(data)


@router.get("/", response_model=List[OrderResponse])
def list_orders(
    status: Optional[OrderStatus] = Query(
        default=None, description="Filter orders by status"
    ),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    svc: OrderService = Depends(order_service),
):
    """Lista órdenes con filtro por estado y paginación opcionales."""
    return svc.list_orders(status=status, skip=skip, limit=limit)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, svc: OrderService = Depends(order_service)):
    """Obtiene una orden por ID."""
    return svc.get_or_404(order_id)


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    svc: OrderService = Depends(order_service),
):
    """Transiciona el estado de una orden validando la máquina de estados."""
    return svc.transition(order_id, data.status, actor="sales", note=data.note)
