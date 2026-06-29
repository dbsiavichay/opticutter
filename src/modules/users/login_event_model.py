from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base
from src.shared.mixins import TimestampMixin


class UserLoginEventModel(TimestampMixin, Base):
    """Evento de inicio de sesión: un row por login exitoso en ``/auth/login``.

    Sirve como referencia de "hora de entrada": el primer evento del día de un
    usuario aproxima su hora de llegada. NO se registra en ``/auth/refresh`` (la
    renovación de token no es una entrada nueva). ``created_at`` (del mixin) es la
    hora del login; ``ip_address``/``user_agent`` son contexto opcional.
    """

    __tablename__ = "user_login_events"
    __table_args__ = (
        # Sirve las consultas de asistencia (primer login por usuario y día).
        Index("ix_user_login_events_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
