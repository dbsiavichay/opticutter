from typing import List

from fastapi import APIRouter, Depends

from src.modules.settings.schemas import (
    CompanySettingsResponse,
    CompanySettingsUpdate,
    CuttingSettingsResponse,
    CuttingSettingsUpdate,
    PreOrderSettingsResponse,
    PreOrderSettingsUpdate,
    PriceTier,
    PriceTiersUpdate,
)
from src.modules.settings.service import SettingsService, settings_service
from src.modules.users.dependencies import require_permission
from src.shared.responses import ERROR_RESPONSES, DataResponse, ok

# System configuration: "administrador" only (RESOURCE_ROLES["settings:manage"]).
router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_permission("settings:manage"))],
)

# Price-tier reads are needed by whoever quotes (admin/vendedor) to populate the
# selector, so they live in a separate router gated by the "preorders" permission
# instead of the "settings:manage" (admin only) used by the configuration router.
tiers_router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_permission("preorders"))],
)


@tiers_router.get("/price-tiers", response_model=DataResponse[List[PriceTier]])
def get_price_tiers(svc: SettingsService = Depends(settings_service)):
    """Active price tiers (for the quote selector), ordered by ``sortOrder``."""
    tiers = [t for t in svc.get_price_tiers() if t.get("is_active", True)]
    tiers.sort(key=lambda t: t.get("sort_order", 0))
    return ok(tiers)


@router.get("/cutting", response_model=DataResponse[CuttingSettingsResponse])
def get_cutting_settings(svc: SettingsService = Depends(settings_service)):
    """Returns the current cutting parameters (seeded from config if missing)."""
    return ok(svc.get_or_init())


@router.patch("/cutting", response_model=DataResponse[CuttingSettingsResponse])
def update_cutting_settings(
    data: CuttingSettingsUpdate, svc: SettingsService = Depends(settings_service)
):
    """Partially updates the cutting parameters."""
    return ok(svc.update_cutting(data))


@router.get("/preorders", response_model=DataResponse[PreOrderSettingsResponse])
def get_preorder_settings(svc: SettingsService = Depends(settings_service)):
    """Returns the current pre-order config (seeded from config if missing)."""
    return ok(svc.get_or_init())


@router.patch("/preorders", response_model=DataResponse[PreOrderSettingsResponse])
def update_preorder_settings(
    data: PreOrderSettingsUpdate, svc: SettingsService = Depends(settings_service)
):
    """Partially updates the pre-order validity period and cap."""
    return ok(svc.update_preorders(data))


@router.get("/company", response_model=DataResponse[CompanySettingsResponse])
def get_company_settings(svc: SettingsService = Depends(settings_service)):
    """Returns the company data (proforma letterhead)."""
    return ok(svc.get_company())


@router.patch("/company", response_model=DataResponse[CompanySettingsResponse])
def update_company_settings(
    data: CompanySettingsUpdate, svc: SettingsService = Depends(settings_service)
):
    """Partially updates the company data."""
    svc.update_company(data)
    return ok(svc.get_company())


@router.patch("/price-tiers", response_model=DataResponse[List[PriceTier]])
def update_price_tiers(
    data: PriceTiersUpdate, svc: SettingsService = Depends(settings_service)
):
    """Replaces the price-tier list (admin only)."""
    settings = svc.update_price_tiers(data)
    return ok(settings.price_tiers)
