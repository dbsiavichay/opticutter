"""Endpoints read-only de analítica para el dashboard.

Cuatro endpoints cohesivos, uno por familia de gráfico. Todos devuelven payloads
agregados listos para graficar, envueltos en ``DataResponse[T]``.
"""

from fastapi import APIRouter, Depends, Query

from src.modules.analytics.constants import Granularity
from src.modules.analytics.dates import DateRange
from src.modules.analytics.schemas import (
    AnalyticsSummary,
    Breakdown,
    OperationsReport,
    TimeSeries,
)
from src.modules.analytics.service import AnalyticsService, analytics_service
from src.shared.responses import ERROR_RESPONSES, DataResponse, ok

router = APIRouter(prefix="/analytics", tags=["analytics"], responses=ERROR_RESPONSES)


@router.get("/summary", response_model=DataResponse[AnalyticsSummary])
def get_summary(
    dr: DateRange = Depends(),
    svc: AnalyticsService = Depends(analytics_service),
):
    """Tarjetas KPI del periodo: operación, pipeline y tendencia base."""
    return ok(svc.summary(dr))


@router.get("/timeseries", response_model=DataResponse[TimeSeries])
def get_timeseries(
    dr: DateRange = Depends(),
    granularity: Granularity = Query(
        Granularity.day, description="Tamaño de bucket: day | week | month"
    ),
    svc: AnalyticsService = Depends(analytics_service),
):
    """Tendencias temporales (eje denso, huecos en cero)."""
    return ok(svc.timeseries(dr, granularity))


@router.get("/breakdown/status", response_model=DataResponse[Breakdown])
def get_breakdown_status(
    dr: DateRange = Depends(),
    svc: AnalyticsService = Depends(analytics_service),
):
    """Embudo de estados: conteo e ingreso por estado (todos los estados, incl. cero)."""
    return ok(svc.breakdown_status(dr))


@router.get("/operations", response_model=DataResponse[OperationsReport])
def get_operations(
    dr: DateRange = Depends(),
    svc: AnalyticsService = Depends(analytics_service),
):
    """Eficiencia de material (ponderada por área), merma y ciclo de vida."""
    return ok(svc.operations(dr))
