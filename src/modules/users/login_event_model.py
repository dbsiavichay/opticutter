from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base
from src.shared.mixins import TimestampMixin


class UserLoginEventModel(TimestampMixin, Base):
    """Login event: one row per successful login on ``/auth/login``.

    Serves as an "arrival time" reference: a user's first event of the day
    approximates their arrival time. NOT recorded on ``/auth/refresh`` (token
    renewal isn't a new entry). ``created_at`` (from the mixin) is the login
    time; ``ip_address``/``user_agent`` are optional context.
    """

    __tablename__ = "user_login_events"
    __table_args__ = (
        # Serves attendance queries (first login per user and day).
        Index("ix_user_login_events_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
