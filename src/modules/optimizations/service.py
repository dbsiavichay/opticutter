import hashlib
import json
import math
from collections import Counter, defaultdict
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
from src.modules.optimizations.labels import edge_banding_notation
from src.modules.optimizations.materials import MaterialResolver, ResolvedMaterial
from src.modules.optimizations.patterns import group_layouts
from src.modules.optimizations.pricing import build_pricing
from src.modules.optimizations.schemas import (
    EdgeBandingSpec,
    EdgeSide,
    OptimizeRequest,
    OptimizeResponse,
    PricingSummary,
    Requirement,
)
from src.modules.products.model import ProductModel, ProductType
from src.modules.products.service import ProductService
from src.modules.settings.service import SettingsService
from src.shared.cache import cache
from src.shared.database import get_db
from src.shared.exceptions import (
    BusinessRuleError,
    EntityNotFoundError,
    ValidationError,
)

# Reubicación de cantos cuando la pieza sale rotada del optimizador. Convención:
# giro de 90° en sentido horario (top→right→bottom→left→top). El optimizador solo
# intercambia ancho↔alto, así que fijamos esta convención para dibujar el canto en
# el lado físico correcto de la pieza ya rotada.
_CW_ROTATION = {"top": "right", "right": "bottom", "bottom": "left", "left": "top"}


class OptimizationService:
    """Orquesta el dominio de corte (``cutting``) y cachea el resultado por hash.

    El cómputo es determinista y efímero: se cachea por un hash de las entradas y
    **no** se persiste en BD (la orden es la fuente de verdad durable). El hash es
    el identificador con el que se recupera la proforma. El material es agnóstico al
    origen: un ``MaterialResolver`` traduce catálogo/retazo/manual a dimensiones y
    costo antes de optimizar, de modo que ``cutting`` solo ve geometría.
    """

    def __init__(self, db: Session):
        self.db = db
        self.product_service = ProductService(db)
        self.material_resolver = MaterialResolver(db)
        self.settings_service = SettingsService(db)

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
        # El descuento se aplica fuera de la caché de geometría: cada nivel reusa el
        # mismo payload (cache-first) y solo difiere en el bloque `pricing`.
        tier = self.settings_service.resolve_price_tier(request.price_tier_code)
        pricing = build_pricing(payload, tier)
        return OptimizeResponse(
            id=None,
            client=client,
            optimization_hash=optimization_hash,
            total_boards_used=payload["total_boards_used"],
            total_boards_cost=payload["total_boards_cost"],
            total_edge_banding_cost=payload.get("total_edge_banding_cost", 0.0),
            total_cut_linear_m=payload.get("total_cut_linear_m", 0.0),
            total_edge_banding_linear_m=payload.get("total_edge_banding_linear_m", 0.0),
            layouts=payload["layouts"],
            materials_summary=payload["materials_summary"],
            edge_bandings_summary=payload.get("edge_bandings_summary"),
            layout_groups=payload["layout_groups"],
            pricing=PricingSummary(**pricing),
        )

    def get_cached_payload(self, optimization_hash: str) -> dict:
        """Recupera el payload cacheado por hash o lanza 404 si expiró/no existe."""
        payload = cache.get_json(optimization_hash)
        if payload is None:
            raise EntityNotFoundError("Optimization", optimization_hash)
        return payload

    def build_carrier_from_hash(
        self,
        optimization_hash: str,
        client_id: int,
        price_tier_code: str = "consumidor",
    ) -> ProformaCarrier:
        """Portador de proforma para una optimización cacheada (por hash).

        La optimización es anónima; el cliente se aporta al renderizar (la proforma
        necesita sus datos para el encabezado del documento). El nivel de precio no es
        parte del hash, por lo que se aporta aquí para aplicar el descuento.
        """
        payload = self.get_cached_payload(optimization_hash)
        client = self.db.get(ClientModel, client_id)
        if client is None:
            raise EntityNotFoundError("Client", client_id)
        require_phone(client)
        tier = self.settings_service.resolve_price_tier(price_tier_code)
        priced_payload = {**payload, "pricing": build_pricing(payload, tier)}
        return ProformaCarrier.from_payload(
            priced_payload,
            client,
            reference=f"OPT-{optimization_hash[:8]}",
            company=self.settings_service.get_company(),
            validity_days=self.settings_service.get_preorder_config()[
                "preorder_validity_days"
            ],
        )

    def compute(self, request: OptimizeRequest) -> Tuple[dict, str]:
        """Calcula (o recupera de caché) el resultado de la optimización.

        Cache-first por un hash determinista de entradas (materiales resueltos +
        requerimientos + parámetros de corte + precios de tapacanto). No escribe en
        BD: lo reutiliza el módulo de órdenes para congelar el snapshot sin depender
        de la caché. Devuelve ``(payload, optimization_hash)``.
        """
        if not request.requirements:
            raise ValidationError("La lista de piezas no puede estar vacía")

        requirements_by_key = self._group_requirements_by_material_key(
            request.requirements
        )

        settings = self.settings_service.get_or_init()
        cutting_params = CuttingParameters(
            kerf=settings.kerf,
            top_trim=settings.top_trim,
            bottom_trim=settings.bottom_trim,
            left_trim=settings.left_trim,
            right_trim=settings.right_trim,
        )
        waste_factor = settings.edge_banding_waste_factor

        # Resuelve a dimensiones+costo solo los materiales realmente referenciados,
        # agnóstico al origen (catálogo/retazo/manual). Aquí vive el único punto que
        # conoce el catálogo; ``cutting`` solo ve geometría.
        materials_by_key = {m.key: m for m in request.materials}
        resolved: Dict[str, ResolvedMaterial] = {
            key: self.material_resolver.resolve(materials_by_key[key])
            for key in requirements_by_key
        }

        eb_products = self._resolve_edge_banding_products(request.requirements)

        optimization_hash = self._compute_hash(
            request, cutting_params, resolved, eb_products, waste_factor
        )

        cached = cache.get_json(optimization_hash)
        if cached is not None:
            return cached, optimization_hash

        results = []
        for key, reqs in requirements_by_key.items():
            pieces, edge_map, net_map = self._build_pieces(reqs)
            layouts = self._optimize(
                pieces=pieces,
                material=resolved[key],
                cutting_params=cutting_params,
            )[0]
            results.append((edge_map, net_map, layouts))

        payload = self._build_result_payload(
            request, results, resolved, eb_products, waste_factor
        )
        cache.set_json(optimization_hash, payload)
        return payload, optimization_hash

    def _resolve_edge_banding_products(
        self, requirements: List[Requirement]
    ) -> Dict[int, ProductModel]:
        """Resuelve y valida los productos de tapacanto referenciados por las piezas.

        Mismo contrato que la validación de tableros: 404 si no existe, regla de
        negocio si el producto no es de tipo ``edge_banding``.
        """
        eb_products: Dict[int, ProductModel] = {}
        for req in requirements:
            if req.edge_banding is None:
                continue
            pid = req.edge_banding.product_id
            if pid in eb_products:
                continue
            product = self.product_service.get(pid)
            if product is None:
                raise EntityNotFoundError("Product", pid)
            if product.type != ProductType.EDGE_BANDING.value:
                raise BusinessRuleError(
                    f"El producto {product.code} no es un tapacanto"
                )
            eb_products[pid] = product
        return eb_products

    def _compute_hash(
        self,
        request: OptimizeRequest,
        cutting_params: CuttingParameters,
        resolved: Dict[str, ResolvedMaterial],
        eb_products: Dict[int, ProductModel],
        waste_factor: float,
    ) -> str:
        """Hash sha256 determinista de las entradas que afectan el resultado.

        No incluye ``client_id`` (el cómputo no depende del cliente); la dedupe de
        órdenes sí combina ``client_id`` con este hash. Se calcula sobre los
        materiales resueltos (origen, dimensiones y costo), los requerimientos, los
        parámetros de corte y los precios de tapacanto, para invalidar la caché
        cuando cualquiera cambia.
        """
        materials = {
            key: {
                "source": rm.source,
                "width": rm.width,
                "height": rm.height,
                "thickness": rm.thickness,
                "cost_per_unit": rm.cost_per_unit,
                "product_id": rm.product_id,
            }
            for key, rm in resolved.items()
        }
        edge_prices = {str(pid): p.price for pid, p in eb_products.items()}
        digest_input = {
            "materials": materials,
            "requirements": [r.model_dump(mode="json") for r in request.requirements],
            "params": {
                "kerf": cutting_params.kerf,
                "top_trim": cutting_params.top_trim,
                "bottom_trim": cutting_params.bottom_trim,
                "left_trim": cutting_params.left_trim,
                "right_trim": cutting_params.right_trim,
                "edge_banding_waste_factor": waste_factor,
            },
            "edge_prices": edge_prices,
        }
        canonical = json.dumps(digest_input, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _group_requirements_by_material_key(
        self, requirements: List[Requirement]
    ) -> Dict[str, List[Requirement]]:
        """Agrupa los requerimientos por la key del material a optimizar."""
        requirements_by_key = defaultdict(list)
        for req in requirements:
            requirements_by_key[req.material_key].append(req)
        return requirements_by_key

    def _optimize(
        self,
        pieces: List[Piece],
        material: ResolvedMaterial,
        cutting_params: CuttingParameters,
        max_sheets: int = 100,
        min_rect_size: float = 0.1,
    ) -> Tuple[List[CuttingLayout], List[Piece]]:
        """Optimiza el layout de corte para un material resuelto (cualquier origen).

        Recibe las piezas de dominio ya expandidas y con id único (ver
        ``_build_pieces``): cada instancia física llega con ``quantity=1`` para que el
        optimizador conserve el id tal cual y la atribución de canto por pieza no
        dependa de etiquetas ambiguas.
        """
        if not pieces:
            raise ValidationError("La lista de piezas no puede estar vacía")

        domain_material = Material(
            id=material.key,
            width=material.width,
            height=material.height,
            thickness=material.thickness,
            cost_per_unit=material.cost_per_unit,
        )

        optimizer = MultiSheetGuillotineOptimizer(
            material_template=domain_material,
            cutting_params=cutting_params,
            split_rule=SplitRule.SHORTER_LEFTOVER_AXIS,
            max_sheets=max_sheets,
            min_rect_size=min_rect_size,
        )
        return optimizer.optimize(pieces)

    def _build_pieces(
        self, reqs: List[Requirement]
    ) -> Tuple[List[Piece], Dict[str, EdgeBandingSpec], Dict[str, float]]:
        """Expande los requerimientos a piezas de dominio con id único por instancia.

        El id de pieza es la identidad con la que se atribuye el canto y el metraje a
        cada pieza colocada, así que **debe** ser único: dos requerimientos distintos
        con la misma etiqueta (p. ej. varias "Puerta" con cantos diferentes) ya no se
        colapsan en una sola entrada. Se sufija ``#N`` cuando una etiqueta base tiene
        más de una instancia física en el grupo —sea por ``quantity > 1`` o por
        etiquetas repetidas—, unificando ambos casos en una sola regla (antes el
        optimizador solo sufijaba el caso ``quantity > 1``). Devuelve
        ``(pieces, edge_map, net_map)`` con los mapas indexados por ese id único; el
        metraje neto es por instancia (``width`` para ``top/bottom``, ``height`` para
        ``left/right``, independiente de la rotación), sin multiplicar por cantidad.
        """
        base = [p.label or f"piece_{i+1}" for i, p in enumerate(reqs)]
        totals: Counter = Counter()
        for label, p in zip(base, reqs):
            totals[label] += p.quantity

        seen: Counter = Counter()
        pieces: List[Piece] = []
        edge_map: Dict[str, EdgeBandingSpec] = {}
        net_map: Dict[str, float] = {}
        for i, p in enumerate(reqs):
            for _ in range(p.quantity):
                seen[base[i]] += 1
                uid = f"{base[i]}#{seen[base[i]]}" if totals[base[i]] > 1 else base[i]
                try:
                    pieces.append(
                        Piece(
                            id=uid,
                            width=p.width,
                            height=p.height,
                            quantity=1,
                            can_rotate=p.can_rotate,
                            priority=p.priority,
                        )
                    )
                except ValueError as e:
                    raise ValidationError(f"Pieza {i} tiene valores inválidos: {e}")
                if p.edge_banding is not None:
                    edge_map[uid] = p.edge_banding
                    net_map[uid] = sum(
                        p.width if side in (EdgeSide.top, EdgeSide.bottom) else p.height
                        for side in p.edge_banding.sides
                    )
        return pieces, edge_map, net_map

    def _geometric_edges(
        self, spec: EdgeBandingSpec, eb_products: Dict[int, ProductModel], rotated: bool
    ) -> dict:
        """Traduce los lados nominales a los lados geométricos de la pieza dibujada.

        Sin rotar: identidad. Rotada: el optimizador solo intercambia ancho↔alto
        (un bounding box, sin sentido de giro), así que adoptamos por convención un
        giro de 90° horario y reubicamos cada canto (``_CW_ROTATION``). Una
        rotación pura siempre es físicamente realizable, por lo que el canteado
        asimétrico no impide rotar: simplemente se intercambian los lados.
        """
        nominal = {s.value for s in spec.sides}
        sides = {_CW_ROTATION[s] for s in nominal} if rotated else nominal
        geo = [s for s in ("top", "bottom", "left", "right") if s in sides]
        product = eb_products.get(spec.product_id)
        attrs = (product.attributes if product else None) or {}
        return {
            "sides": geo,
            "product_id": spec.product_id,
            "code": product.code if product else None,
            "color": attrs.get("color"),
            # Tipo canónico (``Soft``/``Hard``) para diferenciar la franja en el
            # diagrama (suave = sólida, duro = rayada). ``None`` en snapshots viejos.
            "band_type": attrs.get("bandType"),
            # Notación de taller calculada desde los lados NOMINALES (estable bajo
            # rotación); ``geo`` solo sirve para pintar las bandas en el lado correcto.
            # ``attributes`` se persiste en camelCase → ``bandType``.
            "notation": edge_banding_notation(nominal, attrs.get("bandType")),
        }

    def _enrich_layout_pieces(
        self,
        layout_dict: dict,
        edge_map: Dict[str, EdgeBandingSpec],
        eb_products: Dict[int, ProductModel],
    ) -> None:
        """Añade ``edges`` (lados geométricos canteados) a cada pieza colocada.

        El ``edge_map`` se indexa por el id único de pieza (ver ``_build_pieces``), así
        que la búsqueda es por el ``piece_id`` exacto de la pieza colocada.
        """
        for placed in layout_dict.get("placed_pieces", []):
            spec = edge_map.get(str(placed.get("piece_id", "")))
            if spec is None:
                continue
            placed["edges"] = self._geometric_edges(
                spec, eb_products, bool(placed.get("rotated"))
            )

    def _build_edge_bandings_summary(
        self,
        requirements: List[Requirement],
        eb_products: Dict[int, ProductModel],
        waste_factor: float,
    ) -> Tuple[List[dict], float]:
        """Agrega el metraje de tapacanto por tipo y devuelve ``(summary, total)``.

        El metraje neto es la suma de los lados tapados (``width`` para
        ``top/bottom``, ``height`` para ``left/right``) por la cantidad; es
        independiente de la rotación. Se aplica la merma configurada y se redondea
        al metro entero que se cobra.
        """
        waste = waste_factor
        net_mm: Dict[int, float] = defaultdict(float)
        for req in requirements:
            spec = req.edge_banding
            if spec is None:
                continue
            per_piece = sum(
                req.width if side in (EdgeSide.top, EdgeSide.bottom) else req.height
                for side in spec.sides
            )
            net_mm[spec.product_id] += per_piece * req.quantity

        summary: List[dict] = []
        total_cost = 0.0
        for pid, mm in net_mm.items():
            product = eb_products[pid]
            attrs = product.attributes or {}
            net_m = mm / 1000.0
            with_waste = net_m * (1 + waste)
            billed = math.ceil(with_waste)
            cost = round(billed * product.price, 2)
            total_cost += cost
            summary.append(
                {
                    "product_id": pid,
                    "product_code": product.code,
                    "product_name": product.name,
                    "thickness": attrs.get("thickness"),
                    "color": attrs.get("color"),
                    "band_type": attrs.get("bandType"),
                    "net_linear_m": round(net_m, 2),
                    "linear_m": round(with_waste, 2),
                    "billed_linear_m": billed,
                    "price_per_m": product.price,
                    "total_cost": cost,
                }
            )
        return summary, round(total_cost, 2)

    def _build_materials_summary(
        self,
        layouts: List[CuttingLayout],
        resolved: Dict[str, ResolvedMaterial],
    ) -> List[dict]:
        """Agrega los layouts por material con métricas y costos (cualquier origen).

        Lleva la metadata de origen (``material_key``/``source`` y, solo para
        catálogo, ``product_id``/``product_code``/``product_name``). Para materiales
        inline cae a la key como código y a las dimensiones como nombre legible, de
        modo que la proforma renderiza sin tratamiento especial.
        """
        summary: Dict[str, dict] = {}
        for layout in layouts:
            key = layout.material.id
            if key not in summary:
                rm = resolved.get(key)
                dims_label = f"{layout.material.width:g}×{layout.material.height:g}"
                summary[key] = {
                    "material_key": key,
                    "source": rm.source if rm else None,
                    "product_id": rm.product_id if rm else None,
                    "product_code": (rm.code if rm and rm.code else key),
                    "product_name": (rm.name if rm and rm.name else dims_label),
                    "width": layout.material.width,
                    "height": layout.material.height,
                    "thickness": layout.material.thickness,
                    "count": 0,
                    "total_area_m2": 0.0,
                    "_efficiencies": [],
                    "cost_per_unit": layout.material.cost_per_unit,
                    "total_cost": 0.0,
                }
            entry = summary[key]
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

    @staticmethod
    def _dump_requirement(
        req: Requirement,
        resolved: Dict[str, ResolvedMaterial],
        eb_products: Dict[int, ProductModel],
    ) -> dict:
        """Vuelca un requirement al payload y le anexa ``band_type`` del tapacanto.

        ``product_code`` lleva la etiqueta del material (código de catálogo, o el
        nombre/key para orígenes inline) que la proforma muestra en la columna
        "Tablero". El ``band_type`` vive en los atributos del producto, no en el
        ``EdgeBandingSpec``; se inyecta aquí para que la proforma arme la notación de
        cantos (``2L1C CS``) sin volver a resolver el producto al renderizar.
        """
        rm = resolved.get(req.material_key)
        material_label = (rm.code or rm.name) if rm else None
        data = {
            **req.model_dump(mode="json"),
            "product_code": material_label or req.material_key,
        }
        if req.edge_banding is not None and data.get("edge_banding"):
            product = eb_products.get(req.edge_banding.product_id)
            attrs = (product.attributes if product else None) or {}
            # ``attributes`` se persiste en camelCase → ``bandType``.
            data["edge_banding"]["band_type"] = attrs.get("bandType")
        return data

    def _build_result_payload(
        self,
        request: OptimizeRequest,
        results: List[
            Tuple[Dict[str, EdgeBandingSpec], Dict[str, float], List[CuttingLayout]]
        ],
        resolved: Dict[str, ResolvedMaterial],
        eb_products: Dict[int, ProductModel],
        waste_factor: float,
    ) -> dict:
        """Arma el payload cacheable/serializable del resultado de optimización.

        Mismas claves que consumen ``proforma`` y el snapshot de las órdenes.
        ``results`` agrupa por material como ``(edge_map, net_map, layouts)`` (mapas
        indexados por el id único de pieza de ``_build_pieces``) para enriquecer cada
        pieza colocada con sus lados canteados y su metraje sin colisión de ids.
        """
        all_layouts = [layout for _, _, layouts in results for layout in layouts]
        total_boards_used = len(all_layouts)
        total_boards_cost = sum(layout.material.cost_per_unit for layout in all_layouts)

        # Métricas por plancha (corte = recorrido de sierra; canto = metraje neto de
        # las piezas colocadas) acumuladas a totales generales. Se inyectan en las
        # estadísticas del layout antes de ``group_layouts`` para que los patrones
        # deduplicados hereden las cifras.
        layout_dicts: List[dict] = []
        total_cut_linear_m = 0.0
        total_edge_banding_linear_m = 0.0
        for edge_map, net_map, layouts in results:
            for layout in layouts:
                layout_dict = layout.to_dict()
                if edge_map:
                    self._enrich_layout_pieces(layout_dict, edge_map, eb_products)
                cut_linear_m = round(layout.cut_length / 1000.0, 2)
                eb_mm = sum(
                    net_map.get(str(p.get("piece_id", "")), 0.0)
                    for p in layout_dict.get("placed_pieces", [])
                )
                eb_linear_m = round(eb_mm / 1000.0, 2)
                stats = layout_dict["statistics"]
                stats["cut_linear_m"] = cut_linear_m
                stats["edge_banding_linear_m"] = eb_linear_m
                total_cut_linear_m += cut_linear_m
                total_edge_banding_linear_m += eb_linear_m
                layout_dicts.append(layout_dict)

        edge_bandings_summary, total_edge_banding_cost = (
            self._build_edge_bandings_summary(
                request.requirements, eb_products, waste_factor
            )
        )
        return {
            "total_boards_used": total_boards_used,
            "total_boards_cost": total_boards_cost,
            "total_edge_banding_cost": total_edge_banding_cost,
            "total_cut_linear_m": round(total_cut_linear_m, 2),
            "total_edge_banding_linear_m": round(total_edge_banding_linear_m, 2),
            "materials": [rm.to_dict() for rm in resolved.values()],
            "requirements": [
                self._dump_requirement(r, resolved, eb_products)
                for r in request.requirements
            ],
            "layouts": layout_dicts,
            "materials_summary": self._build_materials_summary(all_layouts, resolved),
            "edge_bandings_summary": edge_bandings_summary,
            "layout_groups": group_layouts(layout_dicts),
        }


def optimization_service(db: Session = Depends(get_db)) -> OptimizationService:
    """Provider de ``OptimizationService`` para inyección en rutas."""
    return OptimizationService(db)
