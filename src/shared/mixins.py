"""Mixins declarativos reutilizables para columnas de auditoría.

``TimestampMixin`` aporta ``created_at``/``updated_at``; ``AuditMixin`` aporta
``created_by``/``updated_by`` (FK nullable a ``users``), que ``CRUDService``
estampa automáticamente desde ``current_user_ctx``.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class TimestampMixin:
    """``created_at`` y ``updated_at`` gestionados por la aplicación."""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AuditMixin:
    """``created_by``/``updated_by``: FK nullable al usuario que tocó la fila.

    Nullable porque los flujos públicos (cliente) o del sistema crean/modifican
    filas sin un usuario autenticado. ``declared_attr`` da a cada tabla su propia
    ``ForeignKey`` en vez de compartir el objeto entre modelos.
    """

    @declared_attr
    def created_by(cls) -> Mapped[Optional[int]]:
        return mapped_column(ForeignKey("users.id"), nullable=True)

    @declared_attr
    def updated_by(cls) -> Mapped[Optional[int]]:
        return mapped_column(ForeignKey("users.id"), nullable=True)
