"""Reusable declarative mixins for audit columns.

``TimestampMixin`` provides ``created_at``/``updated_at``; ``AuditMixin``
provides ``created_by``/``updated_by`` (nullable FK to ``users``), which
``CRUDService`` stamps automatically from ``current_user_ctx``.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class TimestampMixin:
    """``created_at`` and ``updated_at`` managed by the application.

    ``server_default=func.now()`` also fills them at the DB level, so rows
    inserted outside the ORM (raw SQL, bulk loads) don't violate the NOT NULL.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.now(),
    )


class AuditMixin:
    """``created_by``/``updated_by``: nullable FK to the user who touched the row.

    Nullable because public (client) or system flows create/modify rows without
    an authenticated user. ``declared_attr`` gives each table its own
    ``ForeignKey`` instead of sharing the object across models. ``ON DELETE SET
    NULL`` lets a user be deleted without blocking on their audit trail: the
    references null out instead of raising a FK violation (the history rows stay).
    """

    @declared_attr
    def created_by(cls) -> Mapped[Optional[int]]:
        return mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    @declared_attr
    def updated_by(cls) -> Mapped[Optional[int]]:
        return mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
