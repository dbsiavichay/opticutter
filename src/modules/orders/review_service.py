"""Enlaces de revisión del cliente: generación, consulta y confirmación/rechazo.

Seguridad del enlace (el token ES la credencial; los endpoints públicos no
tienen otra autenticación):

- Token de 256 bits CSPRNG (``secrets.token_urlsafe(32)``); adivinarlo es
  infactible, por lo que actúa como capacidad de acceso a una sola orden.
- En reposo solo se guarda su sha256 (un dump de la DB o fuga de logs no
  produce nada reutilizable). Sin salt: un token aleatorio de 256 bits es su
  propio salt.
- Token desconocido o revocado → 404 uniforme con mensaje fijo (no se
  distingue "no existe" de "revocado" ni se hace eco del token), para no dar
  un oráculo de enumeración.
- Un solo enlace activo por orden: regenerar revoca el anterior (remedio ante
  fuga o pérdida; el token es irrecuperable por diseño).
- Notas de despliegue: el token viaja en la URL, el frontend debe usar
  ``Referrer-Policy: no-referrer``; rate limiting en el reverse proxy.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.orders.model import (
    OrderModel,
    OrderReviewLinkModel,
    OrderStatus,
    ReviewLinkStatus,
)
from src.modules.orders.service import OrderService
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


class ReviewLinkService:
    """Gestiona el ciclo de vida del enlace y las acciones del cliente."""

    def __init__(self, db: Session):
        self.db = db
        self.orders = OrderService(db)

    def generate(self, order_id: int) -> Tuple[OrderReviewLinkModel, str]:
        """Crea un enlace nuevo (revocando el activo previo) y devuelve el token.

        Solo para cotizaciones (``quoted``): una orden ya confirmada no tiene
        nada que revisar. Devuelve ``(link, token_crudo)``; el token solo
        existe en esta respuesta.
        """
        order = self.orders.get_or_404(order_id)
        if order.status != OrderStatus.quoted.value:
            raise BusinessRuleError(
                "Solo se puede generar un enlace de revisión para una "
                "cotización (estado 'quoted')."
            )
        for previous in order.review_links:
            if previous.status == ReviewLinkStatus.active.value:
                previous.status = ReviewLinkStatus.revoked.value
        raw_token = secrets.token_urlsafe(32)
        link = OrderReviewLinkModel(
            order_id=order.id,
            token_hash=_hash(raw_token),
            status=ReviewLinkStatus.active.value,
            expires_at=order.expires_at,
        )
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return link, raw_token

    def get_latest_info(self, order_id: int) -> OrderReviewLinkModel:
        """Último enlace de la orden (metadatos; nunca expone el token)."""
        order = self.orders.get_or_404(order_id)
        if not order.review_links:
            raise EntityNotFoundError("ReviewLink de la orden", order_id)
        return order.review_links[-1]

    def get_review(self, token: str) -> OrderModel:
        """Orden asociada al token para la vista pública (dispara expiración)."""
        link = self._get_by_token_or_404(token)
        return self.orders.get_or_404(link.order_id)

    def confirm(
        self, token: str, note: Optional[str] = None, meta: Optional[dict] = None
    ) -> OrderModel:
        """El cliente confirma la cotización: ``quoted → confirmed``, atómico.

        Idempotente para el cliente: si la orden ya está confirmada (o más
        adelante en el proceso), un reintento devuelve el estado actual sin
        error; el doble clic no debe producir fallos fantasma.
        """
        link = self._get_by_token_or_404(token)
        order = self.orders.get_or_404(link.order_id)
        status = OrderStatus(order.status)

        if status == OrderStatus.expired:
            raise BusinessRuleError("La cotización expiró; solicita una nueva.")
        if status == OrderStatus.cancelled:
            raise BusinessRuleError("La cotización fue retirada; solicita una nueva.")
        if status != OrderStatus.quoted:
            return order  # ya confirmada (o en producción): reintento benigno

        now = datetime.utcnow()
        self.orders._apply_transition(
            order,
            OrderStatus.confirmed,
            actor="client",
            note=note or "Confirmado por el cliente",
        )
        order.confirmed_at = now
        # La vigencia corre desde la confirmación, igual que una orden directa.
        order.expires_at = now + timedelta(days=config.ORDER_VALIDITY_DAYS)
        self._mark_used(link, "confirmed", now, note, meta)
        self.db.commit()
        self.db.refresh(order)
        return order

    def reject(
        self, token: str, note: Optional[str] = None, meta: Optional[dict] = None
    ) -> OrderModel:
        """El cliente rechaza la cotización: ``quoted → cancelled``.

        Libera de inmediato el cupo de pendientes en vez de esperar la
        expiración. Si ya confirmó, el rechazo contradictorio debe pasar por
        ventas (409), no cancelar una orden posiblemente en producción.
        """
        link = self._get_by_token_or_404(token)
        order = self.orders.get_or_404(link.order_id)
        status = OrderStatus(order.status)

        if status == OrderStatus.cancelled:
            return order  # ya cancelada: reintento benigno
        if status == OrderStatus.expired:
            raise BusinessRuleError("La cotización expiró; no hay nada que rechazar.")
        if status != OrderStatus.quoted:
            raise ConflictError(
                "La orden ya fue confirmada; para anularla contacta a ventas."
            )

        now = datetime.utcnow()
        self.orders._apply_transition(
            order,
            OrderStatus.cancelled,
            actor="client",
            note=note or "Rechazado por el cliente",
        )
        self._mark_used(link, "rejected", now, note, meta)
        self.db.commit()
        self.db.refresh(order)
        return order

    def build_url(self, raw_token: str) -> str:
        """URL completa de revisión que abre el cliente (frontend de Maderable)."""
        return f"{config.FRONTEND_BASE_URL.rstrip('/')}/review/{raw_token}"

    def _mark_used(
        self,
        link: OrderReviewLinkModel,
        action: str,
        now: datetime,
        note: Optional[str],
        meta: Optional[dict],
    ) -> None:
        link.status = ReviewLinkStatus.used.value
        link.used_at = now
        link.used_meta = {"action": action, "note": note, **(meta or {})}

    def _get_by_token_or_404(self, token: str) -> OrderReviewLinkModel:
        """Busca por hash del token; 404 uniforme si no existe o fue revocado.

        Un enlace ``used`` sigue siendo legible: el cliente puede volver a la
        página después de confirmar y ver el estado real de su pedido.
        """
        link = (
            self.db.query(OrderReviewLinkModel)
            .filter(OrderReviewLinkModel.token_hash == _hash(token))
            .first()
        )
        if link is None or link.status == ReviewLinkStatus.revoked.value:
            raise ReviewLinkNotFoundError()
        return link


def review_link_service(db: Session = Depends(get_db)) -> ReviewLinkService:
    """Provider de ``ReviewLinkService`` para inyección en rutas."""
    return ReviewLinkService(db)
