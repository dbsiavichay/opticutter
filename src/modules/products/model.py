from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base


class ProductType(str, Enum):
    """Tipos de producto comercializados.

    Cada tipo aporta su propio esquema de ``attributes`` (ver ``products.registry``);
    agregar un tipo nuevo no requiere migración de base de datos.
    """

    BOARD = "board"  # tablero de melamina (único insumo del optimizador)
    EDGE_BANDING = "edge_banding"  # tapacanto (futuro)
    HARDWARE = "hardware"  # herraje (futuro)


class ProductModel(Base):
    """Catálogo unificado: columnas comunes + ``attributes`` específicos por tipo.

    Lo común (``code``, ``name``, ``price``, ``type``, ``is_active``) son columnas
    consultables/restringibles; lo específico de cada tipo vive en el JSON
    ``attributes``, validado por su esquema Pydantic en la frontera del API.
    """

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(256))
    price: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
