"""Identidad del actor para las tablas de historial (append-only).

Un ``Actor`` describe quién origina una transición auditada: ``staff`` (con FK al
usuario + etiqueta congelada), ``client`` (acción pública vía enlace de revisión)
o ``system`` (automatismos como la expiración). Las tablas de historial guardan
``actor`` (el tipo), ``actor_user_id`` (FK nullable) y ``actor_label`` (snapshot
legible que sobrevive a borrados/renombrados del usuario).
"""

from dataclasses import dataclass
from typing import Optional

ACTOR_STAFF = "staff"
ACTOR_CLIENT = "client"
ACTOR_SYSTEM = "system"


@dataclass(frozen=True)
class Actor:
    """Origen de una acción auditada (tipo + atribución opcional)."""

    type: str
    user_id: Optional[int] = None
    label: Optional[str] = None


def staff_actor(user) -> Actor:
    """Actor de staff a partir del ``UserModel`` autenticado (FK + snapshot)."""
    return Actor(ACTOR_STAFF, user_id=user.id, label=user.full_name or user.email)


def client_actor(label: Optional[str] = None) -> Actor:
    """Actor de cliente (acción pública por enlace de revisión)."""
    return Actor(ACTOR_CLIENT, label=label or "Cliente")


def system_actor() -> Actor:
    """Actor del sistema (automatismos sin usuario, p. ej. expiración)."""
    return Actor(ACTOR_SYSTEM)
