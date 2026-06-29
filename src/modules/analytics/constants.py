"""Semántica compartida de la analítica: estados de ingreso, granularidad y utilidades.

Es la columna vertebral del módulo: todos los endpoints coinciden en qué estados
cuentan como ingreso realizado/comprometido/perdido. Reutiliza ``OrderStatus`` y los
sets ya definidos en el módulo de órdenes en lugar de repetir strings.
"""

from enum import Enum
from typing import Iterable

from src.modules.orders.model import OrderStatus

# Ingreso ganado: la orden llegó a su fin productivo (completada o ya despachada).
REALIZED_STATUSES = {OrderStatus.completed, OrderStatus.dispatched}

# Ingreso perdido: no se cobrará nunca.
LOST_STATUSES = {OrderStatus.cancelled}

# Pipeline comprometido: vinculado pero aún no completado.
BOOKED_STATUSES = {
    OrderStatus.confirmed,
    OrderStatus.queued,
    OrderStatus.cutting,
    OrderStatus.cut,
}

# Pendientes (abiertas, pre-producción): vinculadas pero aún sin entrar a taller.
PENDING_STATUSES = {OrderStatus.confirmed}

# Etiquetas legibles por estado para los desgloses (eje del embudo).
STATUS_LABELS = {
    OrderStatus.confirmed: "Confirmada",
    OrderStatus.queued: "En cola",
    OrderStatus.cutting: "En corte",
    OrderStatus.cut: "Cortada",
    OrderStatus.completed: "Completada",
    OrderStatus.dispatched: "Despachada",
    OrderStatus.cancelled: "Cancelada",
}

# --- Etapas del proceso (cuellos de botella) ----------------------------------
# Cinco etapas se derivan de pares consecutivos del historial de estados; la sexta
# (``banding``) sale de las columnas de canteado (pista paralela, fuera del historial).
STAGE_LABELS = {
    "confirm": "Confirmación → Cola",
    "queue_wait": "Espera en cola (taller)",
    "cutting": "Corte",
    "finishing": "Cortada → Completada",
    "dispatch_wait": "Espera de despacho",
    "banding": "Canteado",
}

# Orden de presentación (flujo del proceso); el reporte luego ordena por duración.
STAGE_ORDER = list(STAGE_LABELS.keys())

# Par (from_status, to_status) del historial → etapa nombrada.
STATUS_PAIR_TO_STAGE = {
    (OrderStatus.confirmed.value, OrderStatus.queued.value): "confirm",
    (OrderStatus.queued.value, OrderStatus.cutting.value): "queue_wait",
    (OrderStatus.cutting.value, OrderStatus.cut.value): "cutting",
    (OrderStatus.cut.value, OrderStatus.completed.value): "finishing",
    (OrderStatus.completed.value, OrderStatus.dispatched.value): "dispatch_wait",
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


def percentile(values: list[float], q: float) -> float:
    """Percentil ``q`` (0..1) por interpolación lineal; ``0.0`` si no hay muestras.

    Útil para detectar cuellos de botella: el p90 revela la cola lenta que el
    promedio esconde (pocas órdenes muy demoradas).
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)
