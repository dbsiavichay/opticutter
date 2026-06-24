from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base
from src.shared.mixins import AuditMixin, TimestampMixin


class RefreshTokenModel(TimestampMixin, AuditMixin, Base):
    """Refresh token emitido al iniciar sesión: par renovable del access JWT.

    Solo se guarda el ``token_hash`` (sha256), nunca el token en claro. La rotación
    revoca el actual y emite otro (``revoked_at``); la revocación masiva (cambio de
    contraseña, detección de reúso) marca ``revoked_at`` en lote. Un token sirve si
    no está revocado y no ha expirado.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
