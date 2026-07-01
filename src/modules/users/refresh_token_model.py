from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base
from src.shared.mixins import AuditMixin, TimestampMixin


class RefreshTokenModel(TimestampMixin, AuditMixin, Base):
    """Refresh token issued at login: renewable pair of the access JWT.

    Only the ``token_hash`` (sha256) is stored, never the plain-text token. Rotation
    revokes the current one and issues another (``revoked_at``); bulk revocation
    (password change, reuse detection) marks ``revoked_at`` in batch. A token is
    valid if it's not revoked and hasn't expired.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
