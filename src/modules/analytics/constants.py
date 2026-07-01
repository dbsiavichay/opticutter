"""Shared analytics semantics: revenue states, granularity and utilities.

This is the module's backbone: every endpoint agrees on which states count as
realized/booked/lost revenue. Reuses ``OrderStatus`` and the sets already
defined in the orders module instead of repeating strings.
"""

from enum import Enum
from typing import Iterable

from src.modules.orders.model import OrderStatus

# Realized revenue: the order reached its productive end (completed or already dispatched).
REALIZED_STATUSES = {OrderStatus.completed, OrderStatus.dispatched}

# Lost revenue: will never be charged.
LOST_STATUSES = {OrderStatus.cancelled}

# Booked pipeline: committed but not yet completed.
BOOKED_STATUSES = {
    OrderStatus.confirmed,
    OrderStatus.queued,
    OrderStatus.cutting,
    OrderStatus.cut,
}

# Pending (open, pre-production): committed but not yet in the workshop.
PENDING_STATUSES = {OrderStatus.confirmed}

# Readable label per status for breakdowns (funnel axis). User-facing copy.
STATUS_LABELS = {
    OrderStatus.confirmed: "Confirmada",
    OrderStatus.queued: "En cola",
    OrderStatus.cutting: "En corte",
    OrderStatus.cut: "Cortada",
    OrderStatus.completed: "Completada",
    OrderStatus.dispatched: "Despachada",
    OrderStatus.cancelled: "Cancelada",
}

# --- Process stages (bottlenecks) ----------------------------------------------
# Five stages are derived from consecutive pairs in the status history; the sixth
# (``banding``) comes from the banding columns (parallel track, outside the history).
# User-facing labels below.
STAGE_LABELS = {
    "confirm": "Confirmación → Cola",
    "queue_wait": "Espera en cola (taller)",
    "cutting": "Corte",
    "finishing": "Cortada → Completada",
    "dispatch_wait": "Espera de despacho",
    "banding": "Canteado",
}

# Display order (process flow); the report then sorts by duration.
STAGE_ORDER = list(STAGE_LABELS.keys())

# (from_status, to_status) pair from the history → named stage.
STATUS_PAIR_TO_STAGE = {
    (OrderStatus.confirmed.value, OrderStatus.queued.value): "confirm",
    (OrderStatus.queued.value, OrderStatus.cutting.value): "queue_wait",
    (OrderStatus.cutting.value, OrderStatus.cut.value): "cutting",
    (OrderStatus.cut.value, OrderStatus.completed.value): "finishing",
    (OrderStatus.completed.value, OrderStatus.dispatched.value): "dispatch_wait",
}


class Granularity(str, Enum):
    """Bucket size for the time series."""

    day = "day"
    week = "week"
    month = "month"


def status_values(statuses: Iterable[OrderStatus]) -> list[str]:
    """Projects a set of statuses to their string values (for ``.in_(...)``)."""
    return [s.value for s in statuses]


def safe_div(num: float, denom: float) -> float:
    """Safe division: returns ``0.0`` if the denominator is zero."""
    return num / denom if denom else 0.0


def percentile(values: list[float], q: float) -> float:
    """``q`` percentile (0..1) via linear interpolation; ``0.0`` if there are no samples.

    Useful for spotting bottlenecks: p90 reveals the slow tail that the
    average hides (a few orders that took much longer).
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
