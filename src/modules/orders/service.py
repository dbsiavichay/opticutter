from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.clients.model import ClientModel
from src.modules.clients.service import require_phone
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
from src.modules.orders.schemas import OrderCreate, OrderExportLine, OrderExportResponse
from src.shared.config import config
from src.shared.database import get_db
from src.shared.exceptions import BusinessRuleError, ConflictError, EntityNotFoundError


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
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[OrderModel], int]:
        """Lista órdenes (más recientes primero) con conteo total: ``(items, total)``.

        Barre primero las pendientes vencidas (las marca ``expired`` y persiste)
        para que el filtro por estado, el total y la página reflejen el estado ya
        expirado, sin que una expiración perezosa desbalancee el conteo.
        """
        self._sweep_expired()
        query = self.db.query(OrderModel)
        if status is not None:
            query = query.filter(OrderModel.status == status.value)
        total = query.count()
        orders = query.order_by(OrderModel.id.desc()).offset(offset).limit(limit).all()
        return orders, total

    def create(self, data: OrderCreate) -> OrderModel:
        """Recalcula (cache-first), congela el snapshot y crea la orden.

        Idempotente: un re-POST idéntico devuelve la orden activa existente.
        """
        # Regla de negocio: el cliente debe existir y tener un celular registrado
        # antes de congelar cualquier pedido (también bloquea re-POST sin celular).
        client = self.db.get(ClientModel, data.client_id)
        if client is None:
            raise EntityNotFoundError("Client", data.client_id)
        require_phone(client)

        opt_request = OptimizeRequest(
            materials=data.materials,
            requirements=data.requirements,
            client_id=data.client_id,
        )
        payload, optimization_hash = self.optimization_service.compute(opt_request)

        # Las órdenes admiten materiales fuera del catálogo (retazos/manual): se
        # congelan tal cual el snapshot. Sus líneas/piezas quedan con ``product_id``
        # nulo y se identifican por ``product_code``/``product_name``.

        existing = self._find_active_duplicate(data.client_id, optimization_hash)
        if existing is not None:
            return existing

        self._enforce_pending_cap(data.client_id)

        total_boards_cost = payload["total_boards_cost"]
        total_edge_banding_cost = payload.get("total_edge_banding_cost", 0.0)
        grand_total = round(total_boards_cost + total_edge_banding_cost, 2)

        # Estado de nacimiento: 'confirmed' (flujo directo, default) congela la
        # confirmación ya; 'quoted' deja la cotización abierta a revisión del
        # cliente (expires_at = vigencia de la cotización).
        born_quoted = data.status == OrderStatus.quoted

        now = datetime.utcnow()
        order = OrderModel(
            client_id=data.client_id,
            status=data.status.value,
            optimization_snapshot=payload,
            optimization_hash=optimization_hash,
            currency="USD",
            subtotal=grand_total,
            total=grand_total,
            total_boards_used=payload["total_boards_used"],
            source=data.source,
            notes=data.notes,
            created_at=now,
            confirmed_at=None if born_quoted else now,
            expires_at=now + timedelta(days=config.ORDER_VALIDITY_DAYS),
        )
        # Líneas de cobro = tableros usados + tapacantos (productos consumidos).
        order.lines = [
            OrderLineModel(
                product_id=m["product_id"],
                product_code=m.get("product_code"),
                product_name=m.get("product_name"),
                quantity=m["count"],
                unit_price_snapshot=m["cost_per_unit"],
                line_total=m["total_cost"],
                avg_efficiency=m.get("avg_efficiency"),
                total_area_m2=m.get("total_area_m2"),
            )
            for m in payload["materials_summary"]
        ] + [
            OrderLineModel(
                product_id=e["product_id"],
                product_code=e.get("product_code"),
                product_name=e.get("product_name"),
                quantity=e["billed_linear_m"],
                unit_price_snapshot=e["price_per_m"],
                line_total=e["total_cost"],
                linear_m=e.get("linear_m"),
            )
            for e in payload.get("edge_bandings_summary", [])
        ]
        # Lista de corte = piezas (insumo de producción; no se cobra). El producto
        # se resuelve por la key del material (nulo si el material no es de catálogo).
        product_id_by_key = {
            m["material_key"]: m["product_id"] for m in payload.get("materials", [])
        }
        order.pieces = [
            OrderPieceModel(
                product_id=product_id_by_key[r["material_key"]],
                label=r.get("label"),
                height=r["height"],
                width=r["width"],
                quantity=r["quantity"],
                priority=r.get("priority", 0),
                can_rotate=r.get("can_rotate", True),
                edges=r.get("edge_banding"),
            )
            for r in payload["requirements"]
        ]
        order.history = [
            OrderStatusHistoryModel(
                from_status=None,
                to_status=data.status.value,
                actor="sales" if born_quoted else "system",
                note="Cotización creada" if born_quoted else "Orden creada",
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
        self._apply_transition(order, to_status, actor=actor, note=note)
        self.db.commit()
        self.db.refresh(order)
        return order

    def _apply_transition(
        self,
        order: OrderModel,
        to_status: OrderStatus,
        actor: str = "system",
        note: Optional[str] = None,
    ) -> None:
        """Valida y aplica la transición sin commit (el llamador persiste).

        Permite componer la transición con otros cambios (p. ej. marcar el
        enlace de revisión como usado) en una sola transacción atómica.
        """
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

    def set_external_invoice_id(
        self, order_id: int, external_invoice_id: str
    ) -> OrderModel:
        """Asocia (costura de facturación) el ID de la factura externa a la orden.

        Idempotente con el mismo ID; si ya hay otro asociado lanza ``ConflictError``
        para no pisar una factura ya emitida.
        """
        order = self.get_or_404(order_id)
        if (
            order.external_invoice_id is not None
            and order.external_invoice_id != external_invoice_id
        ):
            raise ConflictError(
                "La orden ya tiene una factura externa asociada "
                f"({order.external_invoice_id})"
            )
        order.external_invoice_id = external_invoice_id
        self.db.commit()
        self.db.refresh(order)
        return order

    def build_export(self, order_id: int) -> OrderExportResponse:
        """Proyecta la orden como documento de facturación neutral (cobro=tableros)."""
        order = self.get_or_404(order_id)
        lines = [
            OrderExportLine(
                description=_line_description(line),
                product_code=line.product_code,
                quantity=line.quantity,
                unit_price=line.unit_price_snapshot,
                line_total=line.line_total,
            )
            for line in order.lines
        ]
        return OrderExportResponse(
            order_code=order.code,
            status=OrderStatus(order.status),
            issued_at=order.confirmed_at or order.created_at,
            currency=order.currency,
            client=order.client,
            lines=lines,
            subtotal=order.subtotal,
            total=order.total,
            external_invoice_id=order.external_invoice_id,
        )

    def _sweep_expired(self) -> None:
        """Expira (y persiste) las pendientes vencidas antes de contar/paginar.

        Acotado a las pendientes con vigencia vencida, no a toda la tabla.
        """
        stale = (
            self.db.query(OrderModel)
            .filter(
                OrderModel.status.in_([s.value for s in PENDING_STATUSES]),
                OrderModel.expires_at < datetime.utcnow(),
            )
            .all()
        )
        if any([self._expire_if_stale(o) for o in stale]):
            self.db.commit()

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


def _line_description(line: OrderLineModel) -> str:
    """Descripción legible de una línea de cobro para la factura externa."""
    if line.product_code and line.product_name:
        return f"{line.product_name} ({line.product_code})"
    return line.product_name or line.product_code or f"Producto {line.product_id}"


def order_service(db: Session = Depends(get_db)) -> OrderService:
    """Provider de ``OrderService`` para inyección en rutas."""
    return OrderService(db)
