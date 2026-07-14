"""Print-agent authentication.

``get_current_agent`` resolves the agent from the ``Authorization: Bearer
<agent_token>`` header by matching the token's sha256 hash against the stored
``token_hash`` (an indexed equality lookup). Parallel to ``users.dependencies``'s
``get_current_user`` but for the machine-to-machine long-poll endpoints — the
agent carries an opaque device token, not a JWT.
"""

from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.modules.print_jobs.model import PrintAgentModel
from src.shared.database import get_db
from src.shared.exceptions import AuthenticationError
from src.shared.security import hash_token

# auto_error=False: we raise AuthenticationError ourselves so the 401 travels
# through the uniform {errors, meta} envelope (same as the user bearer).
bearer = HTTPBearer(auto_error=False)


def get_current_agent(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> PrintAgentModel:
    """Resolves the active print agent from its device token, or 401."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Falta el token del agente de impresión")
    agent = (
        db.query(PrintAgentModel)
        .filter(
            PrintAgentModel.token_hash == hash_token(credentials.credentials),
            PrintAgentModel.is_active.is_(True),
        )
        .first()
    )
    if agent is None:
        raise AuthenticationError("Token de agente inválido o inactivo")
    return agent
