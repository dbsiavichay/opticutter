from typing import Optional

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.modules.settings.model import SETTINGS_ID, SettingsModel
from src.modules.settings.schemas import (
    CompanySettingsUpdate,
    CuttingSettingsUpdate,
    PreOrderSettingsUpdate,
    PriceTiersUpdate,
)
from src.shared.config import config
from src.shared.context import get_current_user_id
from src.shared.database import get_db
from src.shared.exceptions import ValidationError

# Company data is exposed in the API as ``name/tagline/...`` but stored with a
# ``company_`` prefix on the singleton row (which also carries the cutting
# parameters). This map translates the API contract to the columns.
_COMPANY_FIELD_MAP = {
    "name": "company_name",
    "tagline": "company_tagline",
    "email": "company_email",
    "phone": "company_phone",
    "branches": "company_branches",
}


class SettingsService:
    """Access to the application's single (singleton row) configuration.

    Not a CRUD: the row is lazily created, seeded from ``config``, and only
    ever read or partially updated. It is the runtime source of truth for the
    cutting parameters and company data.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_or_init(self) -> SettingsModel:
        """Returns the singleton row; creates it seeded from ``config`` if missing.

        Idempotent and safe against races: if two near-simultaneous requests
        both try to create it, the PK unique constraint fails the second one
        and the already-created row is re-read (same pattern as
        ``ClientService.resolve``).
        """
        settings = self.db.get(SettingsModel, SETTINGS_ID)
        if settings is not None:
            return settings

        settings = SettingsModel(
            id=SETTINGS_ID,
            kerf=config.KERF,
            top_trim=config.TOP_TRIM,
            bottom_trim=config.BOTTOM_TRIM,
            left_trim=config.LEFT_TRIM,
            right_trim=config.RIGHT_TRIM,
            edge_banding_waste_factor=config.EDGE_BANDING_WASTE_FACTOR,
            preorder_validity_days=config.PREORDER_VALIDITY_DAYS,
            max_open_preorders_per_client=config.MAX_OPEN_PREORDERS_PER_CLIENT,
            price_tiers=config.PRICE_TIERS,
            company_name=config.COMPANY_NAME,
            company_tagline=config.COMPANY_TAGLINE,
            company_email=config.COMPANY_EMAIL,
            company_phone=config.COMPANY_PHONE,
            company_branches=config.COMPANY_BRANCHES,
        )
        try:
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)
            return settings
        except IntegrityError:
            self.db.rollback()
            return self.db.get(SettingsModel, SETTINGS_ID)

    def _stamp_updated_by(self, settings: SettingsModel) -> None:
        """Stamps who edited the singleton row (it doesn't go through ``CRUDService``)."""
        user_id = get_current_user_id()
        if user_id is not None:
            settings.updated_by = user_id

    def update_cutting(self, data: CuttingSettingsUpdate) -> SettingsModel:
        """Applies a partial PATCH to the cutting parameters."""
        settings = self.get_or_init()
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(settings, field, value)
        self._stamp_updated_by(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def update_preorders(self, data: PreOrderSettingsUpdate) -> SettingsModel:
        """Applies a partial PATCH to the pre-order config (validity + cap)."""
        settings = self.get_or_init()
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(settings, field, value)
        self._stamp_updated_by(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def get_preorder_config(self) -> dict:
        """Current pre-order validity and cap (runtime source of truth).

        Consumed by ``PreOrderService`` (expires_at + open-orders cap),
        ``PreOrderReviewService`` (refreshes expires_at when generating the
        link), and the quote carriers (validity shown on the proforma).
        """
        settings = self.get_or_init()
        return {
            "preorder_validity_days": settings.preorder_validity_days,
            "max_open_preorders_per_client": settings.max_open_preorders_per_client,
        }

    def get_price_tiers(self) -> list:
        """Current price tiers (tolerates NULL/legacy by falling back to config default)."""
        settings = self.get_or_init()
        return settings.price_tiers or config.PRICE_TIERS

    def resolve_price_tier(self, code: Optional[str]) -> dict:
        """Resolves an active price tier by its ``code`` (default ``consumidor``).

        This is the single validation point for the ``priceTierCode`` sent by
        the API client: an unknown or inactive code is a 422 (not a silent
        default). Consumed by the optimizer, pre-orders, and orders to
        apply/freeze the discount.
        """
        code = code or "consumidor"
        for tier in self.get_price_tiers():
            if tier.get("code") == code and tier.get("is_active", True):
                return tier
        raise ValidationError(f"Nivel de precio desconocido o inactivo: {code}")

    def update_price_tiers(self, data: PriceTiersUpdate) -> SettingsModel:
        """Replaces the entire price-tier list (admin only)."""
        settings = self.get_or_init()
        settings.price_tiers = [t.model_dump(mode="json") for t in data.price_tiers]
        self._stamp_updated_by(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def update_company(self, data: CompanySettingsUpdate) -> SettingsModel:
        """Applies a partial PATCH to the company data."""
        settings = self.get_or_init()
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(settings, _COMPANY_FIELD_MAP[field], value)
        self._stamp_updated_by(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def get_company(self) -> dict:
        """Company data in the API contract shape (``name/tagline/...``).

        Consumed by both the endpoint response and the ``ProformaCarrier`` to
        render the letterhead live.
        """
        settings = self.get_or_init()
        return {
            "name": settings.company_name,
            "tagline": settings.company_tagline,
            "email": settings.company_email,
            "phone": settings.company_phone,
            "branches": settings.company_branches or [],
        }


def settings_service(db: Session = Depends(get_db)) -> SettingsService:
    """``SettingsService`` provider for route injection."""
    return SettingsService(db)
