from typing import Annotated, Literal, Optional, Union

from pydantic import Field, confloat

from src.modules.products.model import ProductType
from src.modules.products.types.board import BoardAttributes
from src.modules.products.types.edge_banding import EdgeBandingAttributes
from src.shared.schemas import CamelModel


class ProductBase(CamelModel):
    """Campos comunes a todos los productos del catálogo."""

    code: str = Field(..., min_length=1, max_length=32, description="Código único")
    name: str = Field(..., min_length=1, max_length=128, description="Nombre único")
    description: Optional[str] = Field(None, max_length=256, description="Descripción")
    price: confloat(ge=0) = Field(..., description="Precio de venta")
    is_active: bool = Field(True, description="Si el producto está activo")


class BoardProductCreate(ProductBase):
    type: Literal[ProductType.BOARD]
    attributes: BoardAttributes


class EdgeBandingProductCreate(ProductBase):
    type: Literal[ProductType.EDGE_BANDING]
    attributes: EdgeBandingAttributes


# Unión discriminada por ``type``: FastAPI/Pydantic v2 eligen y validan el esquema
# de ``attributes`` correcto según el tipo enviado. Un tipo nuevo = una rama más.
ProductCreate = Annotated[
    Union[BoardProductCreate, EdgeBandingProductCreate],
    Field(discriminator="type"),
]


class ProductUpdate(CamelModel):
    """Actualización parcial; ``attributes`` se valida contra el esquema del tipo
    existente en el servicio (el tipo de un producto no cambia tras crearse)."""

    code: Optional[str] = Field(None, min_length=1, max_length=32)
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=256)
    price: Optional[confloat(ge=0)] = None
    is_active: Optional[bool] = None
    attributes: Optional[dict] = None


class ProductResponse(CamelModel):
    """Respuesta del catálogo: campos comunes + el bag de atributos del tipo."""

    id: int
    type: ProductType
    code: str
    name: str
    description: Optional[str] = None
    price: float
    is_active: bool
    attributes: dict
