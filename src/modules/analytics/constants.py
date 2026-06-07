"""Semántica compartida de la analítica: estados de ingreso, granularidad y utilidades.

Es la columna vertebral del módulo: todos los endpoints coinciden en qué estados
cuentan como ingreso realizado/comprometido/perdido. Reutiliza ``OrderStatus`` y los
sets ya definidos en el módulo de órdenes en lugar de repetir strings.
"""

from enum import Enum
from typing import Iterable

from src.modules.orders.model import OrderStatus

# Ingreso ganado: la orden llegó a su fin productivo.
REALIZED_STATUSES = {OrderStatus.completed}

# Ingreso perdido: no se cobrará nunca.
LOST_STATUSES = {OrderStatus.cancelled, OrderStatus.expired}

# Pipeline comprometido: vinculado pero aún no completado.
BOOKED_STATUSES = {
    OrderStatus.confirmed,
    OrderStatus.approved,
    OrderStatus.in_production,
    OrderStatus.cut,
}

# ``draft``/``quoted`` se excluyen de todo ingreso (no vinculantes; hoy las órdenes
# nacen en ``confirmed``).

# Etiquetas legibles por estado para los desgloses (eje del embudo).
STATUS_LABELS = {
    OrderStatus.draft: "Borrador",
    OrderStatus.quoted: "Cotizada",
    OrderStatus.confirmed: "Confirmada",
    OrderStatus.approved: "Aprobada",
    OrderStatus.in_production: "En producción",
    OrderStatus.cut: "Cortada",
    OrderStatus.completed: "Completada",
    OrderStatus.cancelled: "Cancelada",
    OrderStatus.expired: "Expirada",
}


class Granularity(str, Enum):
    """Tamaño de bucket para las series temporales."""

    day = "day"
    week = "week"
    month = "month"


def status_values(statuses: Iterable[OrderStatus]) -> list[str]:
    """Proyecta un conjunto de estados a sus valores string (para ``.in_(...)``)."""
    return [s.value for s in statuses]


def safe_div(num: float, denom: float) -> float:
    """División protegida: devuelve ``0.0`` si el denominador es cero."""
    return num / denom if denom else 0.0
