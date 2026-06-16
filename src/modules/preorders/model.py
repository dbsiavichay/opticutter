from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base


class PreOrderStatus(str, Enum):
    """Estados de una pre-orden (cotización mutable previa a la orden)."""

    draft = "draft"
    sent = "sent"
    changes_requested = "changes_requested"
    confirmed = "confirmed"
    rejected = "rejected"
    expired = "expired"
    cancelled = "cancelled"


# Abiertas (editables): cuentan para el tope antiabuso por cliente y para el
# barrido perezoso de vigencia. ``changes_requested`` es abierta: el cliente pidió
# un ajuste desde el enlace y la pelota vuelve al taller, que la edita y reenvía.
OPEN_STATUSES = {
    PreOrderStatus.draft,
    PreOrderStatus.sent,
    PreOrderStatus.changes_requested,
}

# Sin salida: la pre-orden ya no se transforma.
TERMINAL_STATUSES = {
    PreOrderStatus.confirmed,
    PreOrderStatus.rejected,
    PreOrderStatus.expired,
    PreOrderStatus.cancelled,
}


class ReviewLinkStatus(str, Enum):
    """Estados de un enlace de revisión del cliente."""

    active = "active"
    used = "used"
    revoked = "revoked"


class PreOrderModel(Base):
    """Cotización mutable: inputs del optimizador + enlace de revisión del cliente.

    A diferencia de la Orden (snapshot inmutable congelado), la pre-orden guarda
    solo los **inputs** (``materials`` + ``requirements``, forma de ``OptimizeRequest``)
    y recalcula el resultado bajo demanda (cache-first): así puede editarse libremente
    y sus precios son vivos hasta confirmar. Cuando el cliente da el visto bueno en el
    enlace de revisión, se materializa la Orden inmutable y se enlaza en ``order_id``.
    """

    __tablename__ = "preorders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[Optional[str]] = mapped_column(String(32), unique=True, nullable=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    status: Mapped[str] = mapped_column(String(16), default=PreOrderStatus.draft.value)

    # Inputs del optimizador, tal cual, para recalcular (no se guarda snapshot).
    materials: Mapped[list] = mapped_column(JSON)
    requirements: Mapped[list] = mapped_column(JSON)

    source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # Última solicitud de cambios del cliente (texto libre desde el enlace de
    # revisión); se limpia cuando el taller edita y reenvía la pre-orden.
    client_note: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Orden inmutable creada al confirmar (nula mientras la pre-orden esté abierta).
    order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("orders.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    client: Mapped["ClientModel"] = relationship("ClientModel")  # noqa: F821
    order: Mapped[Optional["OrderModel"]] = relationship(  # noqa: F821
        "OrderModel", foreign_keys=[order_id]
    )
    review_links: Mapped[list["PreOrderReviewLinkModel"]] = relationship(
        "PreOrderReviewLinkModel",
        back_populates="preorder",
        cascade="all, delete-orphan",
        order_by="PreOrderReviewLinkModel.id",
    )


class PreOrderReviewLinkModel(Base):
    """Enlace seguro de revisión del cliente (el token es la credencial).

    Solo se persiste el sha256 del token; el token crudo se devuelve una única vez
    al generarlo y es irrecuperable (perderlo = regenerar, lo que revoca el anterior).
    Un solo enlace ``active`` por pre-orden, garantizado en el servicio.
    """

    __tablename__ = "preorder_review_links"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    preorder_id: Mapped[int] = mapped_column(ForeignKey("preorders.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(
        String(16), default=ReviewLinkStatus.active.value
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Espejo de preorder.expires_at al generar (defensa en profundidad).
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Auditoría de la acción del cliente: {"action", "ip", "user_agent", "note"}.
    used_meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    preorder: Mapped["PreOrderModel"] = relationship(
        "PreOrderModel", back_populates="review_links"
    )
