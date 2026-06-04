import hashlib
import json
from collections import defaultdict
from typing import Dict, List, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.cutting import (
    CuttingLayout,
    CuttingParameters,
    Material,
    MultiSheetGuillotineOptimizer,
    Piece,
    SplitRule,
)
from src.modules.clients.model import ClientModel
from src.modules.clients.service import require_phone
from src.modules.optimizations.carrier import ProformaCarrier
from src.modules.optimizations.patterns import group_layouts
from src.modules.optimizations.schemas import (
    OptimizeRequest,
    OptimizeResponse,
    Requirement,
)
from src.modules.products.model import ProductModel, ProductType
from src.modules.products.service import ProductService
from src.shared.cache import cache
from src.shared.config import config
from src.shared.database import get_db
from src.shared.exceptions import (
    BusinessRuleError,
    EntityNotFoundError,
    ValidationError,
)


class OptimizationService:
    """Orquesta el dominio de corte (``cutting``) y cachea el resultado por hash.

    El cómputo es determinista y efímero: se cachea por un hash de las entradas y
    **no** se persiste en BD (la orden es la fuente de verdad durable). El hash es
    el identificador con el que se recupera la proforma. Solo los productos de tipo
    ``board`` se optimizan; el insumo se resuelve del catálogo de productos.
    """

    def __init__(self, db: Session):
        self.db = db
        self.product_service = ProductService(db)

    def optimize_response(self, request: OptimizeRequest) -> OptimizeResponse:
        """Calcula (cache-first) y arma la respuesta del endpoint ``POST /optimize``.

        El cómputo es agnóstico del cliente: solo se resuelve (y valida) el cliente
        cuando la petición trae ``client_id``. Sin él, la respuesta es anónima.
        """
        payload, optimization_hash = self.compute(request)
        client = None
        if request.client_id is not None:
            client = self.db.get(ClientModel, request.client_id)
            if client is None:
                raise EntityNotFoundError("Client", request.client_id)
        return OptimizeResponse(
            id=None,
            client=client,
            optimization_hash=optimization_hash,
            total_boards_used=payload["total_boards_used"],
            total_boards_cost=payload["total_boards_cost"],
            layouts=payload["layouts"],
            materials_summary=payload["materials_summary"],
            layout_groups=payload["layout_groups"],
        )

    def get_cached_payload(self, optimization_hash: str) -> dict:
        """Recupera el payload cacheado por hash o lanza 404 si expiró/no existe."""
        payload = cache.get_json(optimization_hash)
        if payload is None:
            raise EntityNotFoundError("Optimization", optimization_hash)
        return payload

    def build_carrier_from_hash(
        self, optimization_hash: str, client_id: int
    ) -> ProformaCarrier:
        """Portador de proforma para una optimización cacheada (por hash).

        La optimización es anónima; el cliente se aporta al renderizar (la proforma
        necesita sus datos para el encabezado del documento).
        """
        payload = self.get_cached_payload(optimization_hash)
        client = self.db.get(ClientModel, client_id)
        if client is None:
            raise EntityNotFoundError("Client", client_id)
        require_phone(client)
        return ProformaCarrier.from_payload(
            payload, client, reference=f"OPT-{optimization_hash[:8]}"
        )

    def compute(self, request: OptimizeRequest) -> Tuple[dict, str]:
        """Calcula (o recupera de caché) el resultado de la optimización.

        Cache-first por un hash determinista de entradas (requerimientos +
        parámetros de corte + precios de los productos). No escribe en BD: lo
        reutiliza el módulo de órdenes para congelar el snapshot sin depender de la
        caché. Devuelve ``(payload, optimization_hash)``.
        """
        if not request.requirements:
            raise ValidationError("La lista de piezas no puede estar vacía")

        requirements_by_product = self._group_requirements_by_product(
            request.requirements
        )

        cutting_params = CuttingParameters(
            kerf=config.KERF,
            top_trim=config.TOP_TRIM,
            bottom_trim=config.BOTTOM_TRIM,
            left_trim=config.LEFT_TRIM,
            right_trim=config.RIGHT_TRIM,
        )

        products: Dict[int, ProductModel] = {}
        for product_id in requirements_by_product:
            product = self.product_service.get(product_id)
            if product is None:
                raise EntityNotFoundError("Product", product_id)
            if product.type != ProductType.BOARD.value:
                raise BusinessRuleError(
                    f"El producto {product.code} no es un tablero optimizable"
                )
            products[product_id] = product

        optimization_hash = self._compute_hash(request, cutting_params, products)

        cached = cache.get_json(optimization_hash)
        if cached is not None:
            return cached, optimization_hash

        product_codes = {pid: product.code for pid, product in products.items()}
        product_names = {pid: product.name for pid, product in products.items()}
        results = [
            self._optimize(
                pieces=requirements_by_product[pid],
                product=products[pid],
                cutting_params=cutting_params,
            )
            for pid in requirements_by_product
        ]

        payload = self._build_result_payload(
            request, results, product_codes, product_names
        )
        cache.set_json(optimization_hash, payload)
        return payload, optimization_hash

    def _compute_hash(
        self,
        request: OptimizeRequest,
        cutting_params: CuttingParameters,
        products: Dict[int, ProductModel],
    ) -> str:
        """Hash sha256 determinista de las entradas que afectan el resultado.

        No incluye ``client_id`` (el cómputo no depende del cliente); la dedupe de
        órdenes sí combina ``client_id`` con este hash.
        """
        digest_input = {
            "requirements": [r.model_dump() for r in request.requirements],
            "params": {
                "kerf": cutting_params.kerf,
                "top_trim": cutting_params.top_trim,
                "bottom_trim": cutting_params.bottom_trim,
                "left_trim": cutting_params.left_trim,
                "right_trim": cutting_params.right_trim,
            },
            "prices": {str(pid): product.price for pid, product in products.items()},
        }
        canonical = json.dumps(digest_input, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _group_requirements_by_product(
        self, requirements: List[Requirement]
    ) -> Dict[int, List[Requirement]]:
        """Agrupa los requerimientos por ID de producto (tablero)."""
        requirements_by_product = defaultdict(list)
        for req in requirements:
            requirements_by_product[req.product_id].append(req)
        return requirements_by_product

    def _optimize(
        self,
        pieces: List[Requirement],
        product: ProductModel,
        cutting_params: CuttingParameters,
        max_sheets: int = 100,
        min_rect_size: float = 0.1,
    ) -> Tuple[List[CuttingLayout], List[Piece]]:
        """Optimiza el layout de corte para un tablero específico."""
        if not pieces:
            raise ValidationError("La lista de piezas no puede estar vacía")

        attrs = product.attributes
        material = Material(
            id=product.id,
            width=attrs["width"],
            height=attrs["height"],
            thickness=attrs["thickness"],
            cost_per_unit=product.price,
        )

        piece_objects = []
        for i, p in enumerate(pieces):
            try:
                piece_objects.append(
                    Piece(
                        id=p.label or f"piece_{i+1}",
                        width=p.width,
                        height=p.height,
                        quantity=p.quantity,
                        can_rotate=p.can_rotate,
                        priority=p.priority,
                    )
                )
            except ValueError as e:
                raise ValidationError(f"Pieza {i} tiene valores inválidos: {e}")

        optimizer = MultiSheetGuillotineOptimizer(
            material_template=material,
            cutting_params=cutting_params,
            split_rule=SplitRule.SHORTER_LEFTOVER_AXIS,
            max_sheets=max_sheets,
            min_rect_size=min_rect_size,
        )
        return optimizer.optimize(piece_objects)

    def _build_materials_summary(
        self,
        results: List[Tuple[List[CuttingLayout], List[Piece]]],
        product_codes: Dict[int, str],
        product_names: Dict[int, str],
    ) -> List[dict]:
        """Agrega los layouts por tipo de tablero con métricas y costos."""
        summary: Dict[int, dict] = {}
        for layouts, _ in results:
            for layout in layouts:
                pid = layout.material.id
                if pid not in summary:
                    summary[pid] = {
                        "product_id": pid,
                        "product_code": product_codes.get(pid, "N/A"),
                        "product_name": product_names.get(pid, "N/A"),
                        "width": layout.material.width,
                        "height": layout.material.height,
                        "thickness": layout.material.thickness,
                        "count": 0,
                        "total_area_m2": 0.0,
                        "_efficiencies": [],
                        "cost_per_unit": layout.material.cost_per_unit,
                        "total_cost": 0.0,
                    }
                entry = summary[pid]
                entry["count"] += 1
                entry["total_area_m2"] += round(layout.material.area / 1_000_000, 4)
                entry["_efficiencies"].append(layout.efficiency * 100)
                entry["total_cost"] += layout.material.cost_per_unit

        result = []
        for entry in summary.values():
            effs = entry.pop("_efficiencies")
            entry["avg_efficiency"] = round(sum(effs) / len(effs), 2) if effs else 0.0
            entry["total_area_m2"] = round(entry["total_area_m2"], 4)
            entry["total_cost"] = round(entry["total_cost"], 2)
            result.append(entry)
        return result

    def _build_result_payload(
        self,
        request: OptimizeRequest,
        results: List[Tuple[List[CuttingLayout], List[Piece]]],
        product_codes: Dict[int, str],
        product_names: Dict[int, str],
    ) -> dict:
        """Arma el payload cacheable/serializable del resultado de optimización.

        Mismas claves que consumen ``proforma`` y el snapshot de las órdenes.
        """
        total_boards_used = sum(len(layouts) for layouts, _ in results)
        total_boards_cost = sum(
            layout.material.cost_per_unit
            for layouts, _ in results
            for layout in layouts
        )
        layout_dicts = [
            layout.to_dict() for layouts, _ in results for layout in layouts
        ]
        return {
            "total_boards_used": total_boards_used,
            "total_boards_cost": total_boards_cost,
            "requirements": [
                {
                    **r.model_dump(),
                    "product_code": product_codes.get(r.product_id, "N/A"),
                }
                for r in request.requirements
            ],
            "layouts": layout_dicts,
            "materials_summary": self._build_materials_summary(
                results, product_codes, product_names
            ),
            "layout_groups": group_layouts(layout_dicts),
        }


def optimization_service(db: Session = Depends(get_db)) -> OptimizationService:
    """Provider de ``OptimizationService`` para inyección en rutas."""
    return OptimizationService(db)
