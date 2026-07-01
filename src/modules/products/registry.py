"""Product type registry: maps each ``ProductType`` to its attributes schema.

Single extension point. To support a new type: create its schema in
``products/types/<type>.py``, register it here, and add its branch to the
discriminated union in ``products/schemas.py``. No database migration needed.
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
    """Returns the registered attributes schema for a product type."""
    return ATTRIBUTE_SCHEMAS[ProductType(product_type)]
