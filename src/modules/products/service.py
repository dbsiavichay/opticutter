from typing import List, Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.products.model import ProductModel, ProductType
from src.modules.products.registry import attributes_schema_for
from src.modules.products.schemas import ProductBase, ProductCreate, ProductUpdate
from src.modules.products.types.edge_banding import BandType
from src.shared.crud import CRUDService
from src.shared.database import get_db
from src.shared.exceptions import BusinessRuleError

# Regla de negocio: ancho de tapacanto (mm) coordinado con el grosor del tablero.
# El canto debe cubrir el canto del tablero más un margen, así que un tablero de
# 15 mm usa cinta de 19 mm y uno de 36 mm usa cinta de 40 mm.
BOARD_THICKNESS_TO_EDGE_WIDTH = {15: 19, 36: 40}


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
        # mode="json" garantiza valores JSON-serializables (enums -> su valor)
        # para el bag ``attributes`` que se persiste en la columna JSON.
        payload["attributes"] = data.attributes.model_dump(by_alias=True, mode="json")
        return self._persist(ProductModel(**payload))

    def update(self, id: int, data: ProductUpdate) -> ProductModel:
        obj = self.get_or_404(id)
        fields = data.model_dump(exclude_unset=True)
        if fields.get("attributes") is not None:
            schema = attributes_schema_for(obj.type)
            fields["attributes"] = schema(**fields["attributes"]).model_dump(
                by_alias=True, mode="json"
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

    @staticmethod
    def _design_key(code: str) -> Optional[str]:
        """Clave de diseño compartida por un tablero y su tapacanto coordinado.

        Los códigos siguen ``{prefijo}-{categoría}-{abreviatura}-…`` (p. ej.
        ``MDP-SL-CSH-15`` y ``TAP-SL-CSH-045``), así que ``{categoría}-{abreviatura}``
        (``SL-CSH``) identifica el diseño de forma única —a diferencia del ``name``,
        que comparte tokens entre diseños (p. ej. varios "Barroco")—. Devuelve
        ``None`` si el código no tiene suficientes segmentos.
        """
        parts = code.split("-")
        if len(parts) < 3:
            return None
        return f"{parts[1]}-{parts[2]}"

    def find_edge_bandings_for_board(
        self, board_id: int, band_type: Optional[BandType] = None
    ) -> List[ProductModel]:
        """Tapacantos coordinados con un tablero (mismo diseño y ancho correcto).

        Empareja por la clave de diseño del código (no por nombre, que da falsos
        positivos) y aplica la regla grosor→ancho (``BOARD_THICKNESS_TO_EDGE_WIDTH``).
        Filtra de forma opcional por tipo de canto (``BandType``). Devuelve ``[]`` si
        no hay coordinado para esa combinación (hueco real del catálogo, p. ej. canto
        suave para un tablero de 36 mm).
        """
        board = self.get_or_404(board_id)
        if board.type != ProductType.BOARD.value:
            raise BusinessRuleError(f"El producto {board.code} no es un tablero")

        key = self._design_key(board.code)
        if key is None:
            return []

        target_width = BOARD_THICKNESS_TO_EDGE_WIDTH.get(
            int(board.attributes["thickness"])
        )
        if target_width is None:
            return []

        candidates = (
            self.db.query(ProductModel)
            .filter(
                ProductModel.type == ProductType.EDGE_BANDING.value,
                ProductModel.code.ilike(f"%-{key}-%"),
            )
            .all()
        )

        matches = [
            p
            for p in candidates
            if self._design_key(p.code) == key
            and p.attributes.get("width") == target_width
            and (band_type is None or p.attributes.get("bandType") == band_type.value)
        ]
        return sorted(matches, key=lambda p: p.attributes.get("thickness", 0))


def product_service(db: Session = Depends(get_db)) -> ProductService:
    """Provider de ``ProductService`` para inyección en rutas."""
    return ProductService(db)
