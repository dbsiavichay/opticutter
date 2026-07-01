from enum import Enum


class UserRole(str, Enum):
    """Role of an internal user (closed to four values).

    The canonical value is the Spanish string stored in the DB (``"administrador"`` /
    ``"vendedor"`` / ``"operador"`` / ``"canteador"``). ``_missing_`` accepts the
    input case-insensitively, replicating the ``BandType`` pattern
    (``src/modules/products/types/edge_banding.py``), so the field stays closed
    to these values both when creating/updating users and when filtering.

    ``operador`` and ``canteador`` are workshop roles (bound to a branch): the
    operator cuts; the bander applies edge banding on the banding line.
    """

    ADMIN = "administrador"
    SELLER = "vendedor"
    OPERATOR = "operador"
    BANDER = "canteador"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            norm = value.strip().lower()
            for member in cls:
                if member.value.lower() == norm:
                    return member
        return None
