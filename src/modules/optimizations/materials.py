"""Resolución de materiales agnóstica al origen para el motor de corte.

El optimizador solo necesita dimensiones y costo. Este resolver traduce cada
``MaterialInput`` (catálogo / retazo / manual) a un ``ResolvedMaterial`` uniforme,
aislando en un único punto el acoplamiento con el catálogo de productos. Para
soportar una fuente nueva basta con añadir su ``source`` y su rama (en
``schemas.py`` y aquí); el dominio ``cutting`` no cambia.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.modules.optimizations.schemas import (
    CatalogMaterialInput,
    InlineMaterialInput,
    MaterialInput,
    MaterialSource,
)
from src.modules.products.model import ProductType
from src.modules.products.service import ProductService
from src.shared.exceptions import BusinessRuleError, EntityNotFoundError


@dataclass
class ResolvedMaterial:
    """Material listo para el optimizador: geometría + costo + metadatos de origen.

    ``product_id``/``code``/``name`` solo se pueblan para materiales de catálogo
    (insumo del cobro de órdenes y de la proforma); las fuentes inline los dejan en
    ``None`` (``name`` puede llevar la etiqueta libre del material).
    """

    key: str
    width: float
    height: float
    thickness: float
    cost_per_unit: float
    source: str
    product_id: Optional[int] = None
    code: Optional[str] = None
    name: Optional[str] = None

    @property
    def is_catalog(self) -> bool:
        return self.source == MaterialSource.catalog.value

    def to_dict(self) -> dict:
        """Forma serializable para el snapshot/payload de la optimización."""
        return {
            "material_key": self.key,
            "source": self.source,
            "product_id": self.product_id,
            "product_code": self.code,
            "product_name": self.name,
            "width": self.width,
            "height": self.height,
            "thickness": self.thickness,
            "cost_per_unit": self.cost_per_unit,
        }


class MaterialResolver:
    """Resuelve cada ``MaterialInput`` a un ``ResolvedMaterial`` según su ``source``."""

    def __init__(self, db: Session):
        self.product_service = ProductService(db)

    def resolve_all(
        self, materials: List[MaterialInput]
    ) -> Dict[str, ResolvedMaterial]:
        """Resuelve la lista de materiales a un mapa ``key -> ResolvedMaterial``."""
        return {m.key: self.resolve(m) for m in materials}

    def resolve(self, material: MaterialInput) -> ResolvedMaterial:
        if isinstance(material, CatalogMaterialInput):
            return self._resolve_catalog(material)
        return self._resolve_inline(material)

    def _resolve_catalog(self, material: CatalogMaterialInput) -> ResolvedMaterial:
        """Resuelve un tablero del catálogo: 404 si no existe, 422 si no es board."""
        product = self.product_service.get(material.product_id)
        if product is None:
            raise EntityNotFoundError("Product", material.product_id)
        if product.type != ProductType.BOARD.value:
            raise BusinessRuleError(
                f"El producto {product.code} no es un tablero optimizable"
            )
        attrs = product.attributes
        return ResolvedMaterial(
            key=material.key,
            width=attrs["width"],
            height=attrs["height"],
            thickness=attrs["thickness"],
            cost_per_unit=product.price,
            source=MaterialSource.catalog.value,
            product_id=product.id,
            code=product.code,
            name=product.name,
        )

    def _resolve_inline(self, material: InlineMaterialInput) -> ResolvedMaterial:
        """Retazo (empresa/cliente) o medida manual: dimensiones y costo del input."""
        return ResolvedMaterial(
            key=material.key,
            width=material.width,
            height=material.height,
            thickness=material.thickness,
            cost_per_unit=material.cost_per_unit,
            source=material.source.value,
            product_id=None,
            code=None,
            name=material.label,
        )
