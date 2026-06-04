"""Registro de tipos de producto: mapea cada ``ProductType`` a su esquema de atributos.

Punto único de extensión. Para soportar un tipo nuevo: crear su esquema en
``products/types/<tipo>.py``, registrarlo aquí y añadir su rama a la unión
discriminada de ``products/schemas.py``. No requiere migración de base de datos.
"""

from typing import Type

from src.modules.products.model import ProductType
from src.modules.products.types.board import BoardAttributes
from src.modules.products.types.edge_banding import EdgeBandingAttributes
from src.shared.schemas import CamelModel

ATTRIBUTE_SCHEMAS: dict[ProductType, Type[CamelModel]] = {
    ProductType.BOARD: BoardAttributes,
    ProductType.EDGE_BANDING: EdgeBandingAttributes,
}


def attributes_schema_for(product_type: str | ProductType) -> Type[CamelModel]:
    """Devuelve el esquema de atributos registrado para un tipo de producto."""
    return ATTRIBUTE_SCHEMAS[ProductType(product_type)]
