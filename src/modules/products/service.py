from typing import List, Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.products.model import ProductModel, ProductType
from src.modules.products.registry import attributes_schema_for
from src.modules.products.schemas import ProductBase, ProductCreate, ProductUpdate
from src.shared.crud import CRUDService
from src.shared.database import get_db


class ProductService(CRUDService[ProductModel, ProductBase, ProductUpdate]):
    """CRUD del catálogo de productos + búsquedas y validación de atributos por tipo.

    ``create``/``update`` se sobrescriben porque el payload trae un submodelo
    ``attributes`` discriminado por ``type`` que se persiste como JSON (en la forma
    canónica camelCase del API).
    """

    model = ProductModel
    conflict_messages = {
        "code": "El código del producto ya existe",
        "name": "El nombre del producto ya existe",
    }

    def create(self, data: ProductCreate) -> ProductModel:
        payload = data.model_dump()
        payload["type"] = data.type.value
        payload["attributes"] = data.attributes.model_dump(by_alias=True)
        return self._persist(ProductModel(**payload))

    def update(self, id: int, data: ProductUpdate) -> ProductModel:
        obj = self.get_or_404(id)
        fields = data.model_dump(exclude_unset=True)
        if fields.get("attributes") is not None:
            schema = attributes_schema_for(obj.type)
            fields["attributes"] = schema(**fields["attributes"]).model_dump(
                by_alias=True
            )
        for field, value in fields.items():
            setattr(obj, field, value)
        return self._persist(obj)

    def get_by_code(self, code: str) -> Optional[ProductModel]:
        """Obtiene un producto por su código."""
        return self.db.query(ProductModel).filter(ProductModel.code == code).first()

    def search_paginated(
        self,
        search: Optional[str] = None,
        type: Optional[ProductType] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[ProductModel], int]:
        """Lista productos filtrando por tipo y/o texto (código/nombre)."""
        query = self.db.query(ProductModel)
        if type is not None:
            query = query.filter(ProductModel.type == ProductType(type).value)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                ProductModel.code.ilike(pattern) | ProductModel.name.ilike(pattern)
            )
        return self._paginate(query, limit, offset)


def product_service(db: Session = Depends(get_db)) -> ProductService:
    """Provider de ``ProductService`` para inyección en rutas."""
    return ProductService(db)
