"""Login event log: feeds the "arrival time" analytics.

Each successful login on ``/auth/login`` inserts a row into ``user_login_events``.
The time of a user's first event of the day approximates their arrival time. Token
renewal (``/auth/refresh``) doesn't go through here: it's not a new entry.
"""

from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.users.login_event_model import UserLoginEventModel
from src.shared.database import get_db


class LoginEventService:
    """Persists login events against the ``user_login_events`` table."""

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        user_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Records a successful login (time = the row's ``created_at``)."""
        self.db.add(
            UserLoginEventModel(
                user_id=user_id,
                ip_address=(ip_address or None) and ip_address[:64],
                user_agent=(user_agent or None) and user_agent[:256],
            )
        )
        self.db.commit()


def login_event_service(db: Session = Depends(get_db)) -> LoginEventService:
    """``LoginEventService`` provider for route injection."""
    return LoginEventService(db)
