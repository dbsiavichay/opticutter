from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.modules.settings.model import SETTINGS_ID, SettingsModel
from src.modules.settings.schemas import CompanySettingsUpdate, CuttingSettingsUpdate
from src.shared.config import config
from src.shared.database import get_db

# Los datos de empresa se exponen en la API como ``name/tagline/...`` pero se
# guardan con prefijo ``company_`` en la fila singleton (que también lleva los
# parámetros de corte). Este mapa traduce el contrato del API a las columnas.
_COMPANY_FIELD_MAP = {
    "name": "company_name",
    "tagline": "company_tagline",
    "email": "company_email",
    "phone": "company_phone",
    "branches": "company_branches",
}


class SettingsService:
    """Acceso a la configuración única (fila singleton) de la aplicación.

    No es un CRUD: la fila se crea de forma perezosa sembrada desde ``config`` y
    solo se lee o se actualiza parcialmente. Es la fuente de verdad en runtime de
    los parámetros de corte y los datos de la empresa.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_or_init(self) -> SettingsModel:
        """Devuelve la fila singleton; la crea sembrada desde ``config`` si falta.

        Idempotente y seguro ante carrera: si dos peticiones casi simultáneas la
        crean a la vez, el unique de la PK hace fallar la segunda y se re-lee la
        ya creada (mismo patrón que ``ClientService.resolve``).
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

    def update_cutting(self, data: CuttingSettingsUpdate) -> SettingsModel:
        """Aplica un PATCH parcial a los parámetros de corte."""
        settings = self.get_or_init()
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(settings, field, value)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def update_company(self, data: CompanySettingsUpdate) -> SettingsModel:
        """Aplica un PATCH parcial a los datos de la empresa."""
        settings = self.get_or_init()
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(settings, _COMPANY_FIELD_MAP[field], value)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def get_company(self) -> dict:
        """Datos de empresa en el contrato del API (``name/tagline/...``).

        Lo consume tanto la respuesta del endpoint como el ``ProformaCarrier`` para
        renderizar el membrete en vivo.
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
    """Provider de ``SettingsService`` para inyección en rutas."""
    return SettingsService(db)
