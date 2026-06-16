from fastapi import APIRouter, Depends

from src.modules.settings.schemas import (
    CompanySettingsResponse,
    CompanySettingsUpdate,
    CuttingSettingsResponse,
    CuttingSettingsUpdate,
    PreOrderSettingsResponse,
    PreOrderSettingsUpdate,
)
from src.modules.settings.service import SettingsService, settings_service
from src.shared.responses import ERROR_RESPONSES, DataResponse, ok

router = APIRouter(prefix="/settings", tags=["settings"], responses=ERROR_RESPONSES)


@router.get("/cutting", response_model=DataResponse[CuttingSettingsResponse])
def get_cutting_settings(svc: SettingsService = Depends(settings_service)):
    """Devuelve los parámetros de corte vigentes (sembrados desde config si faltan)."""
    return ok(svc.get_or_init())


@router.patch("/cutting", response_model=DataResponse[CuttingSettingsResponse])
def update_cutting_settings(
    data: CuttingSettingsUpdate, svc: SettingsService = Depends(settings_service)
):
    """Actualiza (parcialmente) los parámetros de corte."""
    return ok(svc.update_cutting(data))


@router.get("/preorders", response_model=DataResponse[PreOrderSettingsResponse])
def get_preorder_settings(svc: SettingsService = Depends(settings_service)):
    """Devuelve la config de pre-órdenes vigente (sembrada desde config si falta)."""
    return ok(svc.get_or_init())


@router.patch("/preorders", response_model=DataResponse[PreOrderSettingsResponse])
def update_preorder_settings(
    data: PreOrderSettingsUpdate, svc: SettingsService = Depends(settings_service)
):
    """Actualiza (parcialmente) la vigencia y el tope de pre-órdenes."""
    return ok(svc.update_preorders(data))


@router.get("/company", response_model=DataResponse[CompanySettingsResponse])
def get_company_settings(svc: SettingsService = Depends(settings_service)):
    """Devuelve los datos de la empresa (membrete de la proforma)."""
    return ok(svc.get_company())


@router.patch("/company", response_model=DataResponse[CompanySettingsResponse])
def update_company_settings(
    data: CompanySettingsUpdate, svc: SettingsService = Depends(settings_service)
):
    """Actualiza (parcialmente) los datos de la empresa."""
    svc.update_company(data)
    return ok(svc.get_company())
