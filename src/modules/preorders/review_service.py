"""Enlaces de revisión del cliente sobre pre-órdenes: generación y confirmación.

El enlace y la decisión del cliente viven en la **pre-orden** (mutable); la Orden
inmutable se crea recién al confirmar. Seguridad del enlace (el token ES la
credencial; los endpoints públicos no tienen otra autenticación):

- Token de 256 bits CSPRNG (``secrets.token_urlsafe(32)``); adivinarlo es
  infactible, por lo que actúa como capacidad de acceso a una sola pre-orden.
- En reposo solo se guarda su sha256 (un dump de la DB o fuga de logs no produce
  nada reutilizable). Sin salt: un token aleatorio de 256 bits es su propio salt.
- Token desconocido o revocado → 404 uniforme (no se distingue "no existe" de
  "revocado" ni se hace eco del token), para no dar un oráculo de enumeración.
- Un solo enlace activo por pre-orden: regenerar revoca el anterior.
- Notas de despliegue: el token viaja en la URL, el frontend debe usar
  ``Referrer-Policy: no-referrer``; rate limiting en el reverse proxy.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.clients.service import require_phone
from src.modules.orders.schemas import OrderCreate
from src.modules.orders.service import OrderService
from src.modules.preorders.model import (
    OPEN_STATUSES,
    PreOrderModel,
    PreOrderReviewLinkModel,
    PreOrderStatus,
    ReviewLinkStatus,
)
from src.modules.preorders.service import PreOrderService
from src.shared.audit import Actor, client_actor, system_actor
from src.shared.config import config
from src.shared.database import get_db
from src.shared.exceptions import (
    AppError,
    BusinessRuleError,
    ConflictError,
    EntityNotFoundError,
)


class ReviewLinkNotFoundError(AppError):
    """404 uniforme: no distingue token inexistente de revocado."""

    status_code = 404
    code = "NOT_FOUND"

    def __init__(self):
        super().__init__("Enlace de revisión no válido")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class PreOrderReviewService:
    """Gestiona el ciclo de vida del enlace y las acciones del cliente."""

    def __init__(self, db: Session):
        self.db = db
        self.preorders = PreOrderService(db)
        self.orders = OrderService(db)

    def generate(
        self,
        preorder_id: int,
        actor: Optional[Actor] = None,
        branch_scope: Optional[int] = None,
    ) -> Tuple[PreOrderReviewLinkModel, str]:
        """Crea un enlace nuevo (revocando el activo previo) y devuelve el token.

        Solo para pre-órdenes abiertas (``draft``/``sent``); exige que el cliente
        tenga celular (no se envía una cotización a quien no se puede facturar).
        Transiciona la pre-orden a ``sent`` y refresca su vigencia. Devuelve
        ``(link, token_crudo)``; el token solo existe en esta respuesta.
        """
        actor = actor or system_actor()
        preorder = self.preorders.get_scoped_or_404(preorder_id, branch_scope)
        if preorder.status not in {s.value for s in OPEN_STATUSES}:
            raise BusinessRuleError(
                "Solo se puede generar un enlace de revisión para una pre-orden "
                "abierta (no confirmada, rechazada ni vencida)."
            )
        require_phone(preorder.client)
        for previous in preorder.review_links:
            if previous.status == ReviewLinkStatus.active.value:
                previous.status = ReviewLinkStatus.revoked.value

        validity_days = self.preorders.settings_service.get_preorder_config()[
            "preorder_validity_days"
        ]
        now = datetime.utcnow()
        if preorder.status != PreOrderStatus.sent.value:
            self.preorders._record_transition(
                preorder,
                preorder.status,
                PreOrderStatus.sent,
                actor,
                note="Enlace de revisión enviado",
            )
        preorder.status = PreOrderStatus.sent.value
        preorder.sent_at = now
        preorder.expires_at = now + timedelta(days=validity_days)

        raw_token = secrets.token_urlsafe(32)
        link = PreOrderReviewLinkModel(
            preorder_id=preorder.id,
            token_hash=_hash(raw_token),
            status=ReviewLinkStatus.active.value,
            expires_at=preorder.expires_at,
        )
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return link, raw_token

    def get_latest_info(
        self, preorder_id: int, branch_scope: Optional[int] = None
    ) -> PreOrderReviewLinkModel:
        """Último enlace de la pre-orden (metadatos; nunca expone el token)."""
        preorder = self.preorders.get_scoped_or_404(preorder_id, branch_scope)
        if not preorder.review_links:
            raise EntityNotFoundError("ReviewLink de la pre-orden", preorder_id)
        return preorder.review_links[-1]

    def get_review(self, token: str) -> PreOrderModel:
        """Pre-orden asociada al token para la vista pública (dispara expiración)."""
        link = self._get_by_token_or_404(token)
        return self.preorders.get_or_404(link.preorder_id)

    def confirm(
        self, token: str, note: Optional[str] = None, meta: Optional[dict] = None
    ) -> PreOrderModel:
        """El cliente confirma: mintea la Orden inmutable y enlaza ``order_id``.

        La Orden se crea desde los inputs vigentes (precios vivos del catálogo).
        Idempotente: si la pre-orden ya está confirmada, un reintento devuelve su
        estado actual sin error. La dedupe por ``(client_id, hash)`` de
        ``OrderService.create`` evita órdenes duplicadas ante doble clic o un
        reintento tras una caída entre los dos commits.
        """
        link = self._get_by_token_or_404(token)
        preorder = self.preorders.get_or_404(link.preorder_id)
        status = PreOrderStatus(preorder.status)

        if status == PreOrderStatus.expired:
            raise BusinessRuleError("La cotización expiró; solicita una nueva.")
        if status in {PreOrderStatus.rejected, PreOrderStatus.cancelled}:
            raise BusinessRuleError("La cotización fue retirada; solicita una nueva.")
        if status == PreOrderStatus.confirmed:
            return preorder  # ya confirmada: reintento benigno

        actor = client_actor()
        order = self.orders.create(
            OrderCreate(
                materials=preorder.materials,
                requirements=preorder.requirements,
                client_id=preorder.client_id,
                branch_id=preorder.branch_id,
                price_tier_code=preorder.price_tier_code,
                strategy=preorder.strategy,
                notes=preorder.notes,
                source=preorder.source,
            ),
            actor=actor,
        )

        now = datetime.utcnow()
        self.preorders._record_transition(
            preorder, preorder.status, PreOrderStatus.confirmed, actor, note=note
        )
        preorder.status = PreOrderStatus.confirmed.value
        preorder.confirmed_at = now
        preorder.order_id = order.id
        self._mark_used(link, "confirmed", now, note, meta)
        self.db.commit()
        self.db.refresh(preorder)
        return preorder

    def reject(
        self, token: str, note: Optional[str] = None, meta: Optional[dict] = None
    ) -> PreOrderModel:
        """El cliente rechaza la cotización: pre-orden ``sent → rejected``.

        Libera de inmediato el cupo de abiertas. Si ya confirmó, el rechazo
        contradictorio pasa por ventas (409): la orden puede estar en producción.
        """
        link = self._get_by_token_or_404(token)
        preorder = self.preorders.get_or_404(link.preorder_id)
        status = PreOrderStatus(preorder.status)

        if status in {PreOrderStatus.rejected, PreOrderStatus.cancelled}:
            return preorder  # ya retirada: reintento benigno
        if status == PreOrderStatus.expired:
            raise BusinessRuleError("La cotización expiró; no hay nada que rechazar.")
        if status == PreOrderStatus.confirmed:
            raise ConflictError(
                "La cotización ya fue confirmada; para anularla contacta a ventas."
            )

        now = datetime.utcnow()
        self.preorders._record_transition(
            preorder,
            preorder.status,
            PreOrderStatus.rejected,
            client_actor(),
            note=note,
        )
        preorder.status = PreOrderStatus.rejected.value
        self._mark_used(link, "rejected", now, note, meta)
        self.db.commit()
        self.db.refresh(preorder)
        return preorder

    def request_changes(self, token: str, note: Optional[str] = None) -> PreOrderModel:
        """El cliente pide un ajuste: pre-orden ``sent → changes_requested``.

        Ni descarta (a diferencia de ``reject``) ni compromete: la pelota vuelve al
        taller, que editará la pre-orden. **No consume el enlace** (sigue activo): el
        cliente usará el mismo token para ver la versión editada y luego confirmar o
        rechazar. La nota (qué cambiar) queda en ``client_note``.
        """
        link = self._get_by_token_or_404(token)
        preorder = self.preorders.get_or_404(link.preorder_id)
        status = PreOrderStatus(preorder.status)

        if status == PreOrderStatus.expired:
            raise BusinessRuleError("La cotización expiró; solicita una nueva.")
        if status in {PreOrderStatus.rejected, PreOrderStatus.cancelled}:
            raise BusinessRuleError("La cotización fue retirada; solicita una nueva.")
        if status == PreOrderStatus.confirmed:
            raise ConflictError(
                "La cotización ya fue confirmada; para cambios contacta a ventas."
            )

        # 'sent' o 'changes_requested': registra/actualiza la solicitud y mantiene
        # el enlace activo (sin marcarlo usado).
        if preorder.status != PreOrderStatus.changes_requested.value:
            self.preorders._record_transition(
                preorder,
                preorder.status,
                PreOrderStatus.changes_requested,
                client_actor(),
                note=note,
            )
        preorder.status = PreOrderStatus.changes_requested.value
        preorder.client_note = note
        self.db.commit()
        self.db.refresh(preorder)
        return preorder

    def build_url(self, raw_token: str) -> str:
        """URL completa de revisión que abre el cliente (frontend de Maderable)."""
        return f"{config.FRONTEND_BASE_URL.rstrip('/')}/review/{raw_token}"

    def _mark_used(
        self,
        link: PreOrderReviewLinkModel,
        action: str,
        now: datetime,
        note: Optional[str],
        meta: Optional[dict],
    ) -> None:
        link.status = ReviewLinkStatus.used.value
        link.used_at = now
        link.used_meta = {"action": action, "note": note, **(meta or {})}

    def _get_by_token_or_404(self, token: str) -> PreOrderReviewLinkModel:
        """Busca por hash del token; 404 uniforme si no existe o fue revocado.

        Un enlace ``used`` sigue siendo legible: el cliente puede volver a la
        página después de confirmar y ver el estado real de su cotización.
        """
        link = (
            self.db.query(PreOrderReviewLinkModel)
            .filter(PreOrderReviewLinkModel.token_hash == _hash(token))
            .first()
        )
        if link is None or link.status == ReviewLinkStatus.revoked.value:
            raise ReviewLinkNotFoundError()
        return link


def preorder_review_service(db: Session = Depends(get_db)) -> PreOrderReviewService:
    """Provider de ``PreOrderReviewService`` para inyección en rutas."""
    return PreOrderReviewService(db)
