from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.optimizations.schemas import OptimizeRequest
from src.modules.optimizations.service import OptimizationService
from src.modules.orders.model import (
    PENDING_STATUSES,
    TERMINAL_STATUSES,
    TRANSITIONS,
    OrderLineModel,
    OrderModel,
    OrderPieceModel,
    OrderStatus,
    OrderStatusHistoryModel,
)
from src.modules.orders.schemas import OrderCreate
from src.shared.config import config
from src.shared.database import get_db
from src.shared.exceptions import BusinessRuleError, EntityNotFoundError


class OrderService:
    """Crea órdenes (snapshot inmutable), gestiona estados y antiabuso."""

    def __init__(self, db: Session):
        self.db = db
        self.optimization_service = OptimizationService(db)

    def get_or_404(self, order_id: int) -> OrderModel:
        order = self.db.get(OrderModel, order_id)
        if order is None:
            raise EntityNotFoundError("Order", order_id)
        if self._expire_if_stale(order):
            self.db.commit()
            self.db.refresh(order)
        return order

    def list_orders(
        self,
        status: Optional[OrderStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[OrderModel]:
        """Lista órdenes (más recientes primero), opcionalmente por estado."""
        query = self.db.query(OrderModel)
        if status is not None:
            query = query.filter(OrderModel.status == status.value)
        orders = query.order_by(OrderModel.id.desc()).offset(skip).limit(limit).all()
        if any([self._expire_if_stale(o) for o in orders]):
            self.db.commit()
        if status is not None:
            # Una orden recién expirada deja de pertenecer al estado consultado.
            orders = [o for o in orders if o.status == status.value]
        return orders

    def create(self, data: OrderCreate) -> OrderModel:
        """Recalcula (cache-first), congela el snapshot y crea la orden.

        Idempotente: un re-POST idéntico devuelve la orden activa existente.
        """
        opt_request = OptimizeRequest(
            requirements=data.requirements, client_id=data.client_id
        )
        payload, optimization_hash = self.optimization_service.compute(opt_request)

        existing = self._find_active_duplicate(data.client_id, optimization_hash)
        if existing is not None:
            return existing

        self._enforce_pending_cap(data.client_id)

        now = datetime.utcnow()
        order = OrderModel(
            client_id=data.client_id,
            status=OrderStatus.confirmed.value,
            optimization_snapshot=payload,
            optimization_hash=optimization_hash,
            currency="USD",
            subtotal=payload["total_boards_cost"],
            total=payload["total_boards_cost"],
            total_boards_used=payload["total_boards_used"],
            source=data.source,
            notes=data.notes,
            created_at=now,
            confirmed_at=now,
            expires_at=now + timedelta(days=config.ORDER_VALIDITY_DAYS),
        )
        # Líneas de cobro = tableros usados (desde materials_summary).
        order.lines = [
            OrderLineModel(
                board_id=m["board_id"],
                board_code=m.get("board_code"),
                board_name=m.get("board_name"),
                quantity=m["count"],
                unit_price_snapshot=m["cost_per_unit"],
                line_total=m["total_cost"],
                avg_efficiency=m.get("avg_efficiency"),
                total_area_m2=m.get("total_area_m2"),
            )
            for m in payload["materials_summary"]
        ]
        # Lista de corte = piezas (insumo de producción; no se cobra).
        order.pieces = [
            OrderPieceModel(
                board_id=r["board_id"],
                label=r.get("label"),
                height=r["height"],
                width=r["width"],
                quantity=r["quantity"],
                priority=r.get("priority", 0),
                can_rotate=r.get("can_rotate", True),
            )
            for r in payload["requirements"]
        ]
        order.history = [
            OrderStatusHistoryModel(
                from_status=None,
                to_status=OrderStatus.confirmed.value,
                actor="system",
                note="Orden creada",
            )
        ]

        self.db.add(order)
        self.db.flush()  # asigna id para componer el code legible
        order.code = f"ORD-{now.year}-{order.id:04d}"
        self.db.commit()
        self.db.refresh(order)
        return order

    def transition(
        self,
        order_id: int,
        to_status: OrderStatus,
        actor: str = "system",
        note: Optional[str] = None,
    ) -> OrderModel:
        """Valida y aplica una transición de estado, registrando el historial."""
        order = self.get_or_404(order_id)
        current = OrderStatus(order.status)
        if to_status not in TRANSITIONS.get(current, set()):
            raise BusinessRuleError(
                f"Transición inválida de '{current.value}' a '{to_status.value}'"
            )
        order.history.append(
            OrderStatusHistoryModel(
                from_status=current.value,
                to_status=to_status.value,
                actor=actor,
                note=note,
            )
        )
        order.status = to_status.value
        self.db.commit()
        self.db.refresh(order)
        return order

    def _expire_if_stale(self, order: OrderModel) -> bool:
        """Marca como ``expired`` una orden pendiente cuya vigencia ya venció.

        Expiración perezosa: se dispara al leer (get/list) o al evaluar el tope de
        pendientes. Solo afecta a estados pendientes (confirmed/approved). No hace
        commit: el llamador decide cuándo persistir el barrido. Devuelve ``True``
        si transicionó la orden.
        """
        if (
            order.expires_at is not None
            and order.status in {s.value for s in PENDING_STATUSES}
            and order.expires_at < datetime.utcnow()
        ):
            order.history.append(
                OrderStatusHistoryModel(
                    from_status=order.status,
                    to_status=OrderStatus.expired.value,
                    actor="system",
                    note="Vigencia vencida",
                )
            )
            order.status = OrderStatus.expired.value
            return True
        return False

    def _find_active_duplicate(
        self, client_id: int, optimization_hash: str
    ) -> Optional[OrderModel]:
        """Orden no terminal del cliente con el mismo hash (idempotencia)."""
        terminal = [s.value for s in TERMINAL_STATUSES]
        candidate = (
            self.db.query(OrderModel)
            .filter(
                OrderModel.client_id == client_id,
                OrderModel.optimization_hash == optimization_hash,
                OrderModel.status.not_in(terminal),
            )
            .first()
        )
        if candidate is not None and self._expire_if_stale(candidate):
            # La duplicada estaba vencida: ya no cuenta, se crea una nueva orden.
            self.db.commit()
            return None
        return candidate

    def _enforce_pending_cap(self, client_id: int) -> None:
        """Bloquea si el cliente excede el tope de órdenes pendientes.

        Primero expira las pendientes vencidas (no cuentan para el tope).
        """
        pending = [s.value for s in PENDING_STATUSES]
        candidates = (
            self.db.query(OrderModel)
            .filter(
                OrderModel.client_id == client_id,
                OrderModel.status.in_(pending),
            )
            .all()
        )
        if any([self._expire_if_stale(o) for o in candidates]):
            self.db.commit()
        active = sum(1 for o in candidates if o.status in pending)
        if active >= config.MAX_PENDING_ORDERS_PER_CLIENT:
            raise BusinessRuleError(
                f"El cliente ya tiene {active} pedido(s) pendiente(s); "
                "resuélvalos o espere a que expiren antes de crear otro."
            )


def order_service(db: Session = Depends(get_db)) -> OrderService:
    """Provider de ``OrderService`` para inyección en rutas."""
    return OrderService(db)
