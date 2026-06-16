"""Contratos de respuesta de la analítica (chart-ready, camelCase vía ``CamelModel``).

Convenciones: ningún campo numérico es opcional (rango vacío → ceros, nunca nulos);
las series temporales son arrays paralelos sobre un mismo eje ``buckets``.
"""

from datetime import date
from typing import List

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


class DwellTime(CamelModel):
    """Tiempo medio que las órdenes pasan en ``from_status`` antes de ``to_status``."""

    from_status: str
    to_status: str
    avg_hours: float
    sample_count: int  # transiciones observadas (transparencia de muestra)


class OperationsReport(CamelModel):
    """Eficiencia de material y ciclo de vida de las órdenes."""

    average_efficiency: float
    total_area_cut_m2: float
    waste_estimate_m2: float
    lifecycle: List[DwellTime]
