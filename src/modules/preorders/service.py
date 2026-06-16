from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.clients.model import ClientModel
from src.modules.optimizations.carrier import ProformaCarrier
from src.modules.optimizations.schemas import OptimizeRequest, OptimizeResponse
from src.modules.optimizations.service import OptimizationService
from src.modules.preorders.model import (
    OPEN_STATUSES,
    PreOrderModel,
    PreOrderStatus,
)
from src.modules.preorders.schemas import PreOrderCreate, PreOrderUpdate
from src.modules.settings.service import SettingsService
from src.shared.database import get_db
from src.shared.exceptions import BusinessRuleError, EntityNotFoundError

_OPEN_VALUES = [s.value for s in OPEN_STATUSES]


class PreOrderService:
    """Gestiona pre-órdenes: CRUD mutable, recálculo cache-first y antiabuso.

    No congela nada: guarda los inputs (``materials`` + ``requirements``) y delega
    el cómputo en ``OptimizationService.compute`` (cache-first) cada vez que hace
    falta mostrar la cotización o el PDF. La Orden inmutable se mintea aparte, al
    confirmar el cliente (ver ``PreOrderReviewService``).
    """

    def __init__(self, db: Session):
        self.db = db
        self.optimization_service = OptimizationService(db)
        self.settings_service = SettingsService(db)

    def get_or_404(self, preorder_id: int) -> PreOrderModel:
        preorder = self.db.get(PreOrderModel, preorder_id)
        if preorder is None:
            raise EntityNotFoundError("PreOrder", preorder_id)
        if self._expire_if_stale(preorder):
            self.db.commit()
            self.db.refresh(preorder)
        return preorder

    def list_preorders(
        self,
        status: Optional[PreOrderStatus] = None,
        client_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[PreOrderModel], int]:
        """Lista pre-órdenes (más recientes primero) con conteo: ``(items, total)``."""
        self._sweep_expired()
        query = self.db.query(PreOrderModel)
        if status is not None:
            query = query.filter(PreOrderModel.status == status.value)
        if client_id is not None:
            query = query.filter(PreOrderModel.client_id == client_id)
        total = query.count()
        items = (
            query.order_by(PreOrderModel.id.desc()).offset(offset).limit(limit).all()
        )
        return items, total

    def create(self, data: PreOrderCreate) -> PreOrderModel:
        """Crea una pre-orden abierta (``draft``) con los inputs del optimizador."""
        if self.db.get(ClientModel, data.client_id) is None:
            raise EntityNotFoundError("Client", data.client_id)
        self._enforce_open_cap(data.client_id)

        validity_days = self.settings_service.get_preorder_config()[
            "preorder_validity_days"
        ]
        now = datetime.utcnow()
        preorder = PreOrderModel(
            client_id=data.client_id,
            status=PreOrderStatus.draft.value,
            materials=[m.model_dump(mode="json") for m in data.materials],
            requirements=[r.model_dump(mode="json") for r in data.requirements],
            source=data.source,
            notes=data.notes,
            created_at=now,
            expires_at=now + timedelta(days=validity_days),
        )
        self.db.add(preorder)
        self.db.flush()  # asigna id para componer el code legible
        preorder.code = f"PRE-{now.year}-{preorder.id:04d}"
        self.db.commit()
        self.db.refresh(preorder)
        return preorder

    def update(self, preorder_id: int, data: PreOrderUpdate) -> PreOrderModel:
        """Edita una pre-orden abierta; rechaza si ya es terminal (confirmed/etc.)."""
        preorder = self.get_or_404(preorder_id)
        self._ensure_open(preorder)
        fields = data.model_dump(exclude_unset=True)
        if data.client_id is not None:
            if self.db.get(ClientModel, data.client_id) is None:
                raise EntityNotFoundError("Client", data.client_id)
            preorder.client_id = data.client_id
        if data.materials is not None:
            preorder.materials = [m.model_dump(mode="json") for m in data.materials]
        if data.requirements is not None:
            preorder.requirements = [
                r.model_dump(mode="json") for r in data.requirements
            ]
        if "notes" in fields:
            preorder.notes = data.notes
        if "source" in fields:
            preorder.source = data.source
        # Si el cliente había pedido cambios, editar = "atendido": la pre-orden
        # vuelve a 'sent' (la pelota regresa al cliente) y se limpia la solicitud.
        if preorder.status == PreOrderStatus.changes_requested.value:
            preorder.status = PreOrderStatus.sent.value
            preorder.client_note = None
        self.db.commit()
        self.db.refresh(preorder)
        return preorder

    def delete(self, preorder_id: int) -> None:
        """Elimina una pre-orden (salvo si ya fue confirmada: tiene una orden viva)."""
        preorder = self.get_or_404(preorder_id)
        if preorder.status == PreOrderStatus.confirmed.value:
            raise BusinessRuleError(
                "No se puede eliminar una pre-orden ya confirmada; la orden generada "
                "es la fuente de verdad."
            )
        self.db.delete(preorder)
        self.db.commit()

    def build_request(self, preorder: PreOrderModel) -> OptimizeRequest:
        """Reconstruye el ``OptimizeRequest`` desde los inputs guardados."""
        return OptimizeRequest(
            materials=preorder.materials,
            requirements=preorder.requirements,
            client_id=preorder.client_id,
        )

    def compute_payload(self, preorder: PreOrderModel) -> Tuple[dict, str]:
        """Payload del optimizador (cache-first) para la pre-orden."""
        return self.optimization_service.compute(self.build_request(preorder))

    def build_optimize_response(self, preorder: PreOrderModel) -> OptimizeResponse:
        """Respuesta de optimización (con cliente) para el detalle interno."""
        return self.optimization_service.optimize_response(self.build_request(preorder))

    def build_carrier(self, preorder: PreOrderModel) -> ProformaCarrier:
        """Portador de proforma (PDF) recalculado para la pre-orden (cotización)."""
        payload, _ = self.compute_payload(preorder)
        return ProformaCarrier.from_payload(
            payload,
            preorder.client,
            reference=preorder.code or f"PRE-{preorder.id:06d}",
            company=self.settings_service.get_company(),
            validity_days=self.settings_service.get_preorder_config()[
                "preorder_validity_days"
            ],
        )

    def _ensure_open(self, preorder: PreOrderModel) -> None:
        if preorder.status not in _OPEN_VALUES:
            raise BusinessRuleError(
                f"La pre-orden está en estado '{preorder.status}' y ya no puede "
                "editarse."
            )

    def _sweep_expired(self) -> None:
        """Expira (y persiste) las abiertas vencidas antes de contar/paginar."""
        stale = (
            self.db.query(PreOrderModel)
            .filter(
                PreOrderModel.status.in_(_OPEN_VALUES),
                PreOrderModel.expires_at < datetime.utcnow(),
            )
            .all()
        )
        if any([self._expire_if_stale(p) for p in stale]):
            self.db.commit()

    def _expire_if_stale(self, preorder: PreOrderModel) -> bool:
        """Marca como ``expired`` una pre-orden abierta cuya vigencia ya venció."""
        if (
            preorder.expires_at is not None
            and preorder.status in _OPEN_VALUES
            and preorder.expires_at < datetime.utcnow()
        ):
            preorder.status = PreOrderStatus.expired.value
            return True
        return False

    def _enforce_open_cap(self, client_id: int) -> None:
        """Bloquea si el cliente excede el tope de pre-órdenes abiertas."""
        candidates = (
            self.db.query(PreOrderModel)
            .filter(
                PreOrderModel.client_id == client_id,
                PreOrderModel.status.in_(_OPEN_VALUES),
            )
            .all()
        )
        if any([self._expire_if_stale(p) for p in candidates]):
            self.db.commit()
        active = sum(1 for p in candidates if p.status in _OPEN_VALUES)
        cap = self.settings_service.get_preorder_config()[
            "max_open_preorders_per_client"
        ]
        if active >= cap:
            raise BusinessRuleError(
                f"El cliente ya tiene {active} pre-orden(es) abierta(s); "
                "ciérrelas o espere a que expiren antes de crear otra."
            )


def preorder_service(db: Session = Depends(get_db)) -> PreOrderService:
    """Provider de ``PreOrderService`` para inyección en rutas."""
    return PreOrderService(db)
