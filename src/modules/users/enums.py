from enum import Enum


class UserRole(str, Enum):
    """Rol de un usuario interno (cerrado a cuatro valores).

    El valor canónico es el español que se almacena en BD (``"administrador"`` /
    ``"vendedor"`` / ``"operador"`` / ``"canteador"``). El ``_missing_`` acepta la
    entrada sin distinguir mayúsculas, replicando el patrón de ``BandType``
    (``src/modules/products/types/edge_banding.py``), de modo que el campo queda
    cerrado a estos valores tanto al crear/actualizar usuarios como al filtrar.

    ``operador`` y ``canteador`` son roles de taller (atados a una sucursal): el
    operador corta; el canteador aplica tapacantos en la pista de canteado.
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
