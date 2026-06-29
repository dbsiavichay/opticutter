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
    AttendanceReport,
    BottleneckReport,
    Breakdown,
    OperationsReport,
    TimeSeries,
    UserProductivityReport,
)
from src.modules.analytics.service import AnalyticsService, analytics_service
from src.modules.users.dependencies import require_permission
from src.modules.users.enums import UserRole
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

_GRANULARITY_QUERY = Query(
    Granularity.day, description="Tamaño de bucket: day | week | month"
)

_ROLE_QUERY = Query(default=None, description="Filtra por rol (vacío = todos)")


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
    granularity: Granularity = _GRANULARITY_QUERY,
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
    """Eficiencia de material (ponderada por área) y merma."""
    return ok(svc.operations(dr, branch_id=branch_id))


@router.get("/bottlenecks", response_model=DataResponse[BottleneckReport])
def get_bottlenecks(
    dr: DateRange = Depends(),
    granularity: Granularity = _GRANULARITY_QUERY,
    branch_id: Optional[int] = _BRANCH_QUERY,
    svc: AnalyticsService = Depends(analytics_service),
):
    """Cuellos de botella: duración por proceso (avg/mediana/p90) y cuándo se ralentiza."""
    return ok(svc.bottlenecks(dr, granularity, branch_id=branch_id))


@router.get("/users", response_model=DataResponse[UserProductivityReport])
def get_user_productivity(
    dr: DateRange = Depends(),
    branch_id: Optional[int] = _BRANCH_QUERY,
    role: Optional[UserRole] = _ROLE_QUERY,
    svc: AnalyticsService = Depends(analytics_service),
):
    """Productividad por usuario: corte, canteado y trabajo comercial."""
    return ok(
        svc.user_productivity(
            dr, branch_id=branch_id, role=role.value if role else None
        )
    )


@router.get("/attendance", response_model=DataResponse[AttendanceReport])
def get_attendance(
    dr: DateRange = Depends(),
    branch_id: Optional[int] = _BRANCH_QUERY,
    role: Optional[UserRole] = _ROLE_QUERY,
    svc: AnalyticsService = Depends(analytics_service),
):
    """Hora de primer login por día y usuario (referencia de hora de entrada)."""
    return ok(
        svc.attendance(dr, branch_id=branch_id, role=role.value if role else None)
    )
