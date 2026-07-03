from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base
from src.shared.mixins import TimestampMixin


class NotificationModel(TimestampMixin, Base):
    """A single notification addressed to one recipient (fan-out on write).

    One row per (recipient, event): the same order transition materializes N
    rows, one per staff member to notify, each with its own ``read_at``. It is
    system-generated, so it carries only ``TimestampMixin`` (no ``AuditMixin`` —
    there is no acting user to stamp as ``created_by``).
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(128))
    body: Mapped[str] = mapped_column(String(255))
    # Deep-link target; nullable so the model can serve non-order events later.
    order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("orders.id"), index=True, nullable=True
    )
    # Extra machine-readable payload (e.g. orderCode, status) for the frontend.
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # NULL = unread. Indexed to serve the unread badge/count cheaply.
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, index=True, nullable=True
    )
