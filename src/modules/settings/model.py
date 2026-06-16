from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base

# La configuración es única: una sola fila con este id fijo (patrón singleton).
SETTINGS_ID = 1


class SettingsModel(Base):
    """Configuración única de la aplicación (fila singleton, ``id=1``).

    Persiste lo que antes vivía solo en variables de entorno: los parámetros de
    corte y los datos de la empresa (membrete de la proforma). La fila se siembra
    perezosamente desde ``config`` en la primera lectura, por lo que el despliegue
    es retrocompatible. La fuente de verdad en runtime es esta tabla; ``config``
    solo aporta los valores iniciales.
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Parámetros de corte (mm)
    kerf: Mapped[float] = mapped_column(Float)
    top_trim: Mapped[float] = mapped_column(Float)
    bottom_trim: Mapped[float] = mapped_column(Float)
    left_trim: Mapped[float] = mapped_column(Float)
    right_trim: Mapped[float] = mapped_column(Float)
    edge_banding_waste_factor: Mapped[float] = mapped_column(Float)

    # Pre-órdenes (cotización mutable): vigencia y tope de abiertas por cliente
    preorder_validity_days: Mapped[int] = mapped_column(Integer)
    max_open_preorders_per_client: Mapped[int] = mapped_column(Integer)

    # Datos de la empresa (membrete de la proforma)
    company_name: Mapped[str] = mapped_column(String(128))
    company_tagline: Mapped[str] = mapped_column(String(256))
    company_email: Mapped[str] = mapped_column(String(128))
    company_phone: Mapped[str] = mapped_column(String(128))
    company_branches: Mapped[list] = mapped_column(JSON, default=list)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
