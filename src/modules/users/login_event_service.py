"""Registro de eventos de login: alimenta la analítica de "hora de entrada".

Cada login exitoso en ``/auth/login`` inserta una fila en ``user_login_events``.
La hora del primer evento del día de un usuario aproxima su hora de llegada. La
renovación de token (``/auth/refresh``) no pasa por aquí: no es una entrada nueva.
"""

from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.users.login_event_model import UserLoginEventModel
from src.shared.database import get_db


class LoginEventService:
    """Persiste eventos de login contra la tabla ``user_login_events``."""

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        user_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Registra un login exitoso (hora = ``created_at`` del row)."""
        self.db.add(
            UserLoginEventModel(
                user_id=user_id,
                ip_address=(ip_address or None) and ip_address[:64],
                user_agent=(user_agent or None) and user_agent[:256],
            )
        )
        self.db.commit()


def login_event_service(db: Session = Depends(get_db)) -> LoginEventService:
    """Provider de ``LoginEventService`` para inyección en rutas."""
    return LoginEventService(db)
