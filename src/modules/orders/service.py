from datetime import datetime
from typing import List, Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.branches.service import resolve_branch_for_create
from src.modules.clients.model import ClientModel
from src.modules.clients.service import require_phone
from src.modules.optimizations.patterns import base_label
from src.modules.optimizations.pricing import build_pricing
from src.modules.optimizations.schemas import OptimizeRequest
from src.modules.optimizations.service import OptimizationService
from src.modules.orders.model import (
    BANDING_MUTABLE_ORDER_STATUSES,
    BANDING_PENDING_STATUSES,
    BANDING_TRANSITION_ROLES,
    BANDING_TRANSITIONS,
    TERMINAL_STATUSES,
    TRANSITION_ROLES,
    TRANSITIONS,
    BandingStatus,
    OrderBoardModel,
    OrderLineModel,
    OrderModel,
    OrderPieceModel,
    OrderPlacedPieceModel,
    OrderStatus,
    OrderStatusHistoryModel,
)
from src.modules.orders.schemas import (
    BandingQueueItem,
    BandingStatusResponse,
    CuttingPlanResponse,
    CuttingProgress,
    OrderBoardResponse,
    OrderCreate,
    OrderExportLine,
    OrderExportResponse,
    PieceCutResponse,
    PlacedPieceResponse,
)
from src.modules.settings.service import SettingsService
from src.shared.audit import Actor, system_actor
from src.shared.branch_scope import BranchScopedMixin
from src.shared.database import get_db
from src.shared.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    EntityNotFoundError,
)


class OrderService(BranchScopedMixin):
    """Crea órdenes (snapshot inmutable), gestiona estados y antiabuso.

    Aislada por sucursal (``BranchScopedMixin``): los listados y accesos por id se
    filtran por la sucursal del usuario; el administrador (scope ``None``) ve todas.
    """

    model = OrderModel

    def __init__(self, db: Session):
        self.db = db
        self.optimization_service = OptimizationService(db)
        self.settings_service = SettingsService(db)

    def get_or_404(self, order_id: int) -> OrderModel:
        order = self.db.get(OrderModel, order_id)
        if order is None:
            raise EntityNotFoundError("Order", order_id)
        return order

    def list_orders(
        self,
        status: Optional[List[OrderStatus]] = None,
        branch_scope: Optional[int] = None,
        branch_filter: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[OrderModel], int]:
        """Lista órdenes (más recientes primero) con conteo total: ``(items, total)``.

        ``status`` filtra por uno o varios estados (lista vacía/``None`` = todos).
        ``branch_scope`` aísla al staff a su sucursal; el admin (``None``) ve todas y
        puede estrechar a una con ``branch_filter``.
        """
        query = self.db.query(OrderModel)
        if status:
            query = query.filter(OrderModel.status.in_([s.value for s in status]))
        query = self._apply_branch_scope(query, branch_scope, branch_filter)
        total = query.count()
        orders = query.order_by(OrderModel.id.desc()).offset(offset).limit(limit).all()
        return orders, total

    def create(self, data: OrderCreate, actor: Optional[Actor] = None) -> OrderModel:
        """Recalcula (cache-first), congela el snapshot y crea la orden.

        Idempotente: un re-POST idéntico devuelve la orden activa existente.
        ``actor`` audita el origen (cliente al confirmar la pre-orden, o sistema).
        """
        actor = actor or system_actor()
        # Regla de negocio: el cliente debe existir y tener un celular registrado
        # antes de congelar cualquier pedido (también bloquea re-POST sin celular).
        client = self.db.get(ClientModel, data.client_id)
        if client is None:
            raise EntityNotFoundError("Client", data.client_id)
        require_phone(client)
        # La sucursal viene del llamador de confianza (la pre-orden al confirmar);
        # se valida que exista y esté activa. ``branch_scope=None`` ⇒ exige branchId.
        branch_id = resolve_branch_for_create(self.db, None, data.branch_id)

        opt_request = OptimizeRequest(
            materials=data.materials,
            requirements=data.requirements,
            client_id=data.client_id,
            strategy=data.strategy,
        )
        payload, optimization_hash = self.optimization_service.compute(opt_request)

        # Las órdenes admiten materiales fuera del catálogo (retazos/manual): se
        # congelan tal cual el snapshot. Sus líneas/piezas quedan con ``product_id``
        # nulo y se identifican por ``product_code``/``product_name``.

        # Nivel de precio: se valida y se congela su rate (auditoría histórica). El
        # descuento entra en la dedupe porque dos órdenes idénticas en geometría pero
        # de distinto nivel NO son la misma (el nivel no está en el hash).
        tier = self.settings_service.resolve_price_tier(data.price_tier_code)
        existing = self._find_active_duplicate(
            branch_id, data.client_id, optimization_hash, tier["code"]
        )
        if existing is not None:
            return existing

        # Descuento a nivel documento (solo tableros de catálogo). Las líneas se
        # congelan a precio de lista; el snapshot embebe `pricing` para autocontención.
        pricing = build_pricing(payload, tier)
        snapshot = {**payload, "pricing": pricing}

        # La orden nace 'confirmed' (la revisión previa del cliente, antes 'quoted',
        # vive ahora en la pre-orden, que mintea esta orden al confirmar).
        # Pista de canteado: arranca 'pending' si la orden lleva tapacantos (algo que
        # cantear), si no 'not_applicable' (no participa del gate de cierre).
        has_banding = bool(payload.get("edge_bandings_summary"))
        banding_status = (
            BandingStatus.pending if has_banding else BandingStatus.not_applicable
        )
        now = datetime.utcnow()
        order = OrderModel(
            client_id=data.client_id,
            branch_id=branch_id,
            status=data.status.value,
            banding_status=banding_status.value,
            optimization_snapshot=snapshot,
            optimization_hash=optimization_hash,
            currency="USD",
            subtotal=pricing["subtotal"],
            total=pricing["total"],
            price_tier_code=tier["code"],
            discount_rate=tier["rate"],
            discount_amount=pricing["discount_amount"],
            total_boards_used=payload["total_boards_used"],
            source=data.source,
            notes=data.notes,
            created_at=now,
            confirmed_at=now,
            created_by=actor.user_id,
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
        # Plan de corte = tableros físicos con cada pieza colocada (la unidad que
        # el operario marca en el taller; estado mutable fuera del snapshot).
        _attach_cutting_plan(order, payload)
        order.history = [
            OrderStatusHistoryModel(
                from_status=None,
                to_status=data.status.value,
                actor=actor.type,
                actor_user_id=actor.user_id,
                actor_label=actor.label,
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
        actor: Optional[Actor] = None,
        note: Optional[str] = None,
        branch_scope: Optional[int] = None,
    ) -> OrderModel:
        """Valida y aplica una transición de estado, registrando el historial.

        Verifica que el rol del actor esté autorizado para la transición concreta
        (TRANSITION_ROLES). Gate de producción: pasar a ``cut`` exige que todas
        las piezas del plan de corte estén marcadas.
        """
        actor = actor or system_actor()
        order = self.get_scoped_or_404(order_id, branch_scope)
        current = OrderStatus(order.status)

        # Validación de rol por transición antes de tocar el estado.
        if actor.role is not None:
            allowed = TRANSITION_ROLES.get((current, to_status), ())
            if allowed and actor.role not in (r.value for r in allowed):
                raise AuthorizationError(
                    f"Tu rol no puede ejecutar la transición "
                    f"'{current.value}' → '{to_status.value}'"
                )

        # Gate: todas las piezas deben estar cortadas antes de cerrar el corte.
        if to_status == OrderStatus.cut and order.status == OrderStatus.cutting.value:
            self._ensure_cutting_plan(order)
            pending = (
                self.db.query(OrderPlacedPieceModel)
                .filter(
                    OrderPlacedPieceModel.order_id == order.id,
                    OrderPlacedPieceModel.cut_at.is_(None),
                )
                .count()
            )
            if pending:
                raise BusinessRuleError(f"Faltan {pending} pieza(s) por cortar")

        # Gate de cierre: si la orden lleva tapacantos, el canteado debe estar
        # terminado antes de completarla (las órdenes sin canteado pasan directo).
        if (
            to_status == OrderStatus.completed
            and BandingStatus(order.banding_status) in BANDING_PENDING_STATUSES
        ):
            raise BusinessRuleError("Falta terminar el canteado")

        self._apply_transition(order, to_status, actor=actor, note=note)

        # Asignación al transicionar a ``cutting``; limpieza al regresar a ``queued``.
        if to_status == OrderStatus.cutting:
            order.assigned_to_id = actor.user_id
            order.assigned_at = datetime.utcnow()
            order.assigned_to_label = actor.label
        elif to_status == OrderStatus.queued and current == OrderStatus.cutting:
            order.assigned_to_id = None
            order.assigned_at = None
            order.assigned_to_label = None

        # Despacho: congela fecha y quién entregó (lo muestra la hoja de despacho).
        if to_status == OrderStatus.dispatched:
            order.dispatched_at = datetime.utcnow()
            order.dispatched_by = actor.user_id
            order.dispatched_by_label = actor.label

        self.db.commit()
        self.db.refresh(order)
        return order

    def get_cutting_plan(
        self, order_id: int, branch_scope: Optional[int] = None
    ) -> CuttingPlanResponse:
        """Plan de corte para la vista de taller: tableros físicos + avance."""
        order = self.get_scoped_or_404(order_id, branch_scope)
        self._ensure_cutting_plan(order)
        boards = [
            OrderBoardResponse(
                id=board.id,
                sheet_number=board.sheet_number,
                material_key=board.material_key,
                product_code=board.product_code,
                product_name=board.product_name,
                width=board.width,
                height=board.height,
                thickness=board.thickness,
                progress=_progress(board.pieces),
                pieces=[_piece_response(p) for p in board.pieces],
                remainders=board.remainders or [],
                cuts=board.cuts or [],
            )
            for board in order.boards
        ]
        all_pieces = [p for board in order.boards for p in board.pieces]
        return CuttingPlanResponse(
            order_id=order.id,
            order_code=order.code,
            status=OrderStatus(order.status),
            progress=_progress(all_pieces),
            boards=boards,
        )

    def mark_piece_cut(
        self,
        order_id: int,
        placed_piece_id: int,
        cut: bool,
        actor: Optional[Actor] = None,
        branch_scope: Optional[int] = None,
    ) -> PieceCutResponse:
        """Marca (o desmarca) una pieza colocada como cortada, idempotente.

        Solo con la orden en ``cutting``: antes no hay nada que cortar y después el
        corte ya quedó cerrado por la transición. ``actor`` registra quién la cortó
        (FK + etiqueta), en sincronía con ``cut_at``.
        """
        actor = actor or system_actor()
        order = self.get_scoped_or_404(order_id, branch_scope)
        self._ensure_cutting_plan(order)
        if order.status != OrderStatus.cutting.value:
            raise BusinessRuleError(
                "Solo se pueden marcar piezas con la orden en corte (cutting)"
            )
        piece = self.db.get(OrderPlacedPieceModel, placed_piece_id)
        if piece is None or piece.order_id != order.id:
            raise EntityNotFoundError("OrderPlacedPiece", placed_piece_id)
        if cut and piece.cut_at is None:
            piece.cut_at = datetime.utcnow()
            piece.cut_by = actor.user_id
            piece.cut_by_label = actor.label
        elif not cut:
            piece.cut_at = None
            piece.cut_by = None
            piece.cut_by_label = None
        self.db.commit()
        self.db.refresh(piece)
        all_pieces = [p for board in order.boards for p in board.pieces]
        return PieceCutResponse(
            piece=_piece_response(piece),
            progress=_progress(all_pieces),
            board_progress=_progress(piece.board.pieces),
        )

    def list_banding_queue(
        self, branch_scope: Optional[int] = None
    ) -> List[BandingQueueItem]:
        """Cola de canteado: órdenes con canteado pendiente y corte ya iniciado.

        Vista mínima para el canteador (sin precios ni detalle): solo las órdenes en
        ``cutting``/``cut`` cuyo canteado aún no terminó. Aislada por sucursal.
        """
        query = self.db.query(OrderModel).filter(
            OrderModel.status.in_([s.value for s in BANDING_MUTABLE_ORDER_STATUSES]),
            OrderModel.banding_status.in_([s.value for s in BANDING_PENDING_STATUSES]),
        )
        query = self._apply_branch_scope(query, branch_scope, None)
        orders = query.order_by(OrderModel.id.desc()).all()
        return [
            BandingQueueItem(
                order_id=o.id,
                order_code=o.code,
                status=OrderStatus(o.status),
                banding_status=BandingStatus(o.banding_status),
                created_at=o.created_at,
            )
            for o in orders
        ]

    def transition_banding(
        self,
        order_id: int,
        to_status: BandingStatus,
        actor: Optional[Actor] = None,
        branch_scope: Optional[int] = None,
    ) -> BandingStatusResponse:
        """Avanza la pista de canteado (``in_progress``/``done``), idempotente.

        Pista paralela e independiente del corte: solo exige que la orden ya esté en
        ``cutting``/``cut`` (hay piezas liberadas que cantear). Forward-only; re-aplicar
        el estado actual no cambia nada. Sella inicio/fin con timestamp + actor.
        """
        actor = actor or system_actor()
        order = self.get_scoped_or_404(order_id, branch_scope)

        if actor.role is not None and actor.role not in (
            r.value for r in BANDING_TRANSITION_ROLES
        ):
            raise AuthorizationError("Tu rol no puede registrar el canteado")

        current = BandingStatus(order.banding_status)
        if current == BandingStatus.not_applicable:
            raise BusinessRuleError("Esta orden no lleva tapacantos")
        if OrderStatus(order.status) not in BANDING_MUTABLE_ORDER_STATUSES:
            raise BusinessRuleError(
                "El canteado solo se registra con la orden en corte o cortada"
            )

        # Idempotente: re-aplicar el estado actual es un no-op (no re-sella timestamps).
        if to_status != current:
            if to_status not in BANDING_TRANSITIONS.get(current, set()):
                raise BusinessRuleError(
                    f"Transición de canteado inválida de '{current.value}' a "
                    f"'{to_status.value}'"
                )
            now = datetime.utcnow()
            if to_status == BandingStatus.in_progress:
                order.banding_started_at = now
                order.banding_started_by = actor.user_id
                order.banding_started_by_label = actor.label
            elif to_status == BandingStatus.done:
                order.banding_finished_at = now
                order.banding_finished_by = actor.user_id
                order.banding_finished_by_label = actor.label
            order.banding_status = to_status.value
            self.db.commit()
            self.db.refresh(order)

        return BandingStatusResponse(
            order_id=order.id,
            order_code=order.code,
            banding_status=BandingStatus(order.banding_status),
            banding_started_at=order.banding_started_at,
            banding_finished_at=order.banding_finished_at,
        )

    def _ensure_cutting_plan(self, order: OrderModel) -> None:
        """Materializa el plan de corte desde el snapshot si aún no existe.

        Cubre las órdenes creadas antes de esta funcionalidad sin backfill: la
        primera lectura/marcado reconstruye las filas desde ``layouts``.
        """
        if order.boards:
            return
        _attach_cutting_plan(order, order.optimization_snapshot or {})
        if order.boards:
            self.db.commit()
            self.db.refresh(order)

    def _apply_transition(
        self,
        order: OrderModel,
        to_status: OrderStatus,
        actor: Actor,
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
                actor=actor.type,
                actor_user_id=actor.user_id,
                actor_label=actor.label,
                note=note,
            )
        )
        order.status = to_status.value

    def set_external_invoice_id(
        self,
        order_id: int,
        external_invoice_id: str,
        branch_scope: Optional[int] = None,
    ) -> OrderModel:
        """Asocia (costura de facturación) el ID de la factura externa a la orden.

        Idempotente con el mismo ID; si ya hay otro asociado lanza ``ConflictError``
        para no pisar una factura ya emitida.
        """
        order = self.get_scoped_or_404(order_id, branch_scope)
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

    def build_export(
        self, order_id: int, branch_scope: Optional[int] = None
    ) -> OrderExportResponse:
        """Proyecta la orden como documento de facturación neutral (cobro=tableros)."""
        order = self.get_scoped_or_404(order_id, branch_scope)
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
            price_tier_code=order.price_tier_code,
            discount_rate=order.discount_rate,
            discount_amount=order.discount_amount,
            total=order.total,
            external_invoice_id=order.external_invoice_id,
        )

    def _find_active_duplicate(
        self,
        branch_id: int,
        client_id: int,
        optimization_hash: str,
        price_tier_code: str,
    ) -> Optional[OrderModel]:
        """Orden no terminal de la misma sucursal+cliente con igual hash (idempotencia).

        Incluye la sucursal en la clave: el mismo cliente puede pedir lo mismo en dos
        sucursales y son órdenes distintas. Incluye el nivel de precio: el descuento no
        forma parte del hash, así que el mismo corte a distinto nivel son dos órdenes.
        """
        terminal = [s.value for s in TERMINAL_STATUSES]
        return (
            self.db.query(OrderModel)
            .filter(
                OrderModel.branch_id == branch_id,
                OrderModel.client_id == client_id,
                OrderModel.optimization_hash == optimization_hash,
                OrderModel.price_tier_code == price_tier_code,
                OrderModel.status.not_in(terminal),
            )
            .first()
        )


def _attach_cutting_plan(order: OrderModel, payload: dict) -> None:
    """Expande ``payload["layouts"]`` en tableros físicos + piezas colocadas.

    Cada layout del snapshot es una hoja real; ``sheet_number`` se reasigna como
    secuencia global (el del snapshot se reinicia por material). Las piezas
    quedan ligadas también a la orden para contar avance sin joins.
    """
    materials_by_key = {m["material_key"]: m for m in payload.get("materials", [])}
    for seq, layout in enumerate(payload.get("layouts", []), start=1):
        material = layout.get("material", {})
        resolved = materials_by_key.get(material.get("material_key"), {})
        board = OrderBoardModel(
            sheet_number=seq,
            material_key=material.get("material_key", ""),
            product_id=resolved.get("product_id"),
            product_code=resolved.get("product_code"),
            product_name=resolved.get("product_name"),
            width=material.get("width", 0.0),
            height=material.get("height", 0.0),
            thickness=material.get("thickness", 0.0),
            remainders=layout.get("remainders") or None,
            # Snapshots previos a la serialización de ``cuts`` no traen la clave.
            cuts=layout.get("cuts") or None,
        )
        for placed in layout.get("placed_pieces", []):
            piece_id = str(placed.get("piece_id", ""))
            board.pieces.append(
                OrderPlacedPieceModel(
                    order=order,
                    piece_id=piece_id,
                    label=base_label(piece_id),
                    x=placed["x"],
                    y=placed["y"],
                    width=placed["width"],
                    height=placed["height"],
                    original_width=placed.get("original_width", placed["width"]),
                    original_height=placed.get("original_height", placed["height"]),
                    rotated=bool(placed.get("rotated", False)),
                    edges=placed.get("edges"),
                )
            )
        order.boards.append(board)


def _progress(pieces: List[OrderPlacedPieceModel]) -> CuttingProgress:
    """Avance de corte sobre un conjunto de piezas colocadas."""
    return CuttingProgress(
        cut_pieces=sum(1 for p in pieces if p.cut_at is not None),
        total_pieces=len(pieces),
    )


def _piece_response(piece: OrderPlacedPieceModel) -> PlacedPieceResponse:
    """Proyección API de una pieza colocada (``cut`` derivado de ``cut_at``)."""
    return PlacedPieceResponse(
        id=piece.id,
        piece_id=piece.piece_id,
        label=piece.label,
        x=piece.x,
        y=piece.y,
        width=piece.width,
        height=piece.height,
        original_width=piece.original_width,
        original_height=piece.original_height,
        rotated=piece.rotated,
        edges=piece.edges,
        cut=piece.cut_at is not None,
        cut_at=piece.cut_at,
        cut_by=piece.cut_by,
        cut_by_label=piece.cut_by_label,
    )


def _line_description(line: OrderLineModel) -> str:
    """Descripción legible de una línea de cobro para la factura externa."""
    if line.product_code and line.product_name:
        return f"{line.product_name} ({line.product_code})"
    return line.product_name or line.product_code or f"Producto {line.product_id}"


def order_service(db: Session = Depends(get_db)) -> OrderService:
    """Provider de ``OrderService`` para inyección en rutas."""
    return OrderService(db)
