"""Endpoints read-only de analítica para el dashboard.

Cuatro endpoints cohesivos, uno por familia de gráfico. Todos devuelven payloads
agregados listos para graficar, envueltos en ``DataResponse[T]``.
"""

from typing import Optional

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
from src.modules.users.dependencies import require_permission
from src.shared.responses import ERROR_RESPONSES, DataResponse, ok

# Analítica del dashboard: solo "administrador" (RESOURCE_ROLES["analytics"]). El
# admin es global, así que ``branchId`` es un filtro OPCIONAL para revisar un almacén.
router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_permission("analytics"))],
)

_BRANCH_QUERY = Query(
    default=None,
    alias="branchId",
    description="Filtra las métricas a una sucursal (vacío = todas)",
)


@router.get("/summary", response_model=DataResponse[AnalyticsSummary])
def get_summary(
    dr: DateRange = Depends(),
    branch_id: Optional[int] = _BRANCH_QUERY,
    svc: AnalyticsService = Depends(analytics_service),
):
    """Tarjetas KPI del periodo: operación, pipeline y tendencia base."""
    return ok(svc.summary(dr, branch_id=branch_id))


@router.get("/timeseries", response_model=DataResponse[TimeSeries])
def get_timeseries(
    dr: DateRange = Depends(),
    granularity: Granularity = Query(
        Granularity.day, description="Tamaño de bucket: day | week | month"
    ),
    branch_id: Optional[int] = _BRANCH_QUERY,
    svc: AnalyticsService = Depends(analytics_service),
):
    """Tendencias temporales (eje denso, huecos en cero)."""
    return ok(svc.timeseries(dr, granularity, branch_id=branch_id))


@router.get("/breakdown/status", response_model=DataResponse[Breakdown])
def get_breakdown_status(
    dr: DateRange = Depends(),
    branch_id: Optional[int] = _BRANCH_QUERY,
    svc: AnalyticsService = Depends(analytics_service),
):
    """Embudo de estados: conteo e ingreso por estado (todos los estados, incl. cero)."""
    return ok(svc.breakdown_status(dr, branch_id=branch_id))


@router.get("/breakdown/branch", response_model=DataResponse[Breakdown])
def get_breakdown_branch(
    dr: DateRange = Depends(),
    svc: AnalyticsService = Depends(analytics_service),
):
    """Comparativo por sucursal: conteo e ingreso por almacén (revisión gerencial)."""
    return ok(svc.breakdown_branch(dr))


@router.get("/operations", response_model=DataResponse[OperationsReport])
def get_operations(
    dr: DateRange = Depends(),
    branch_id: Optional[int] = _BRANCH_QUERY,
    svc: AnalyticsService = Depends(analytics_service),
):
    """Eficiencia de material (ponderada por área), merma y ciclo de vida."""
    return ok(svc.operations(dr, branch_id=branch_id))
