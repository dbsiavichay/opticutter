"""Contratos de respuesta de la analítica (chart-ready, camelCase vía ``CamelModel``).

Convenciones: ningún campo numérico es opcional (rango vacío → ceros, nunca nulos);
las series temporales son arrays paralelos sobre un mismo eje ``buckets``.
"""

from datetime import date, datetime
from typing import List, Optional

from src.modules.analytics.constants import Granularity
from src.shared.schemas import CamelModel


class RangeInfo(CamelModel):
    """Ventana efectivamente aplicada (eco de los defaults resueltos)."""

    date_from: date
    date_to: date


class AnalyticsSummary(CamelModel):
    """Tarjetas KPI: operación, pipeline y tendencia base del periodo."""

    range: RangeInfo
    # Operación (sobre órdenes completadas).
    total_boards_consumed: int
    average_efficiency: float  # ponderada por área, 0..100
    total_area_cut_m2: float
    waste_estimate_m2: float
    # Estados / pipeline.
    pending_orders_count: int
    cancellation_rate: float  # 0..1
    # Tendencia base.
    order_count: int
    realized_revenue: float
    average_ticket: float
    active_clients_count: int


class TimeSeriesData(CamelModel):
    """Series paralelas alineadas al eje ``buckets`` de ``TimeSeries``."""

    revenue: List[float]  # ingreso realizado por bucket
    order_count: List[int]
    boards_consumed: List[int]
    new_clients: List[int]


class TimeSeries(CamelModel):
    """Tendencias temporales con eje denso (huecos en cero)."""

    granularity: Granularity
    buckets: List[str]  # fechas de bucket ISO (eje x)
    series: TimeSeriesData


class BreakdownItem(CamelModel):
    """Una categoría del desglose con sus métricas."""

    key: str
    label: str
    revenue: float
    order_count: int


class Breakdown(CamelModel):
    """Desglose categórico (p. ej. embudo de estados)."""

    dimension: str
    items: List[BreakdownItem]


class OperationsReport(CamelModel):
    """Eficiencia de material de las órdenes (el ciclo de vida vive en ``/bottlenecks``)."""

    average_efficiency: float
    total_area_cut_m2: float
    waste_estimate_m2: float


# ------------------------------------------------------------------ bottlenecks
class StageDuration(CamelModel):
    """Duración agregada de una etapa del proceso (para hallar el cuello de botella)."""

    key: str
    label: str
    avg_hours: float
    median_hours: float
    p90_hours: float  # cola lenta: lo que el promedio esconde
    sample_count: int


class StageSeries(CamelModel):
    """Duración media de una etapa por bucket (cuándo se ralentiza); ceros en huecos."""

    key: str
    label: str
    avg_hours: List[float]  # paralelo a ``buckets`` de ``BottleneckReport``


class BottleneckReport(CamelModel):
    """Qué proceso tarda más (``stages``, el más lento primero) y cuándo (``series``)."""

    stages: List[StageDuration]
    buckets: List[str]
    series: List[StageSeries]


# ----------------------------------------------------------- user productivity
class UserProductivity(CamelModel):
    """Trabajo y velocidad de un usuario en el periodo (no aplica → 0, nunca null)."""

    user_id: int
    full_name: str
    role: str
    branch_name: Optional[str]
    # Corte (operador).
    pieces_cut: int
    area_cut_m2: float
    orders_cut: int
    cutting_hours: float
    pieces_per_hour: float  # throughput
    # Canteado (canteador).
    orders_banded: int
    banding_hours: float
    # Comercial (vendedor).
    orders_created: int
    revenue_generated: float


class UserProductivityReport(CamelModel):
    """Productividad por usuario (taller + comercial)."""

    users: List[UserProductivity]


# --------------------------------------------------------------------- attendance
class AttendanceDay(CamelModel):
    """Asistencia de un usuario en un día: primer login (hora de entrada) y conteo."""

    date: date
    first_login_at: datetime
    login_count: int


class UserAttendance(CamelModel):
    """Días con login de un usuario en el rango (referencia de hora de entrada)."""

    user_id: int
    full_name: str
    role: str
    branch_name: Optional[str]
    days: List[AttendanceDay]


class AttendanceReport(CamelModel):
    """Hora de entrada por usuario y día."""

    users: List[UserAttendance]
