"""Detección de medios tableros (cobro a la mitad) como post-paso del optimizado.

El negocio vende medios tableros del catálogo, divididos **a lo largo** (se conserva
el largo/``height`` y se parte el ancho/``width`` a la mitad). El cliente no los pide
explícitamente: pide piezas. Por eso, tras optimizar contra tableros completos, este
módulo revisa cada plancha (layout) y, si **todas** sus piezas caben en un solo medio
tablero, la reemplaza por el layout de medio (geometría + cortes del re-encaje) y su
costo pasa a la mitad.

Es determinista (depende solo de entradas ya incluidas en el hash de la caché) y reusa
el motor de corte puro, así que el medio fluye solo a costos, resumen, descuento,
snapshot de la orden y plan de corte. Solo aplica a materiales de **catálogo**: los
retazos/medidas manuales ya se cobran a costo.
"""

from typing import Dict, List, Optional, Tuple

from src.cutting.enums import PackingStrategy
from src.cutting.models import CuttingLayout, Material
from src.cutting.optimizer import GuillotineOptimizer
from src.cutting.parameters import CuttingParameters
from src.modules.optimizations.materials import ResolvedMaterial

# Resultado por material: mapas de canto/metraje (indexados por id de pieza) + layouts.
MaterialResult = Tuple[Dict[str, object], Dict[str, float], List[CuttingLayout]]


def apply_half_boards(
    results: List[MaterialResult],
    resolved: Dict[str, ResolvedMaterial],
    cutting_params: CuttingParameters,
    strategy: PackingStrategy,
    min_rect_size: float = 0.1,
) -> None:
    """Reemplaza in situ las planchas de catálogo que caben en un medio tablero.

    Cada layout cuyo contenido encaje completo en un medio (mismo largo, ancho/2) se
    sustituye por el layout de medio: ``half_board=True``, ancho y costo a la mitad,
    y las piezas reubicadas por el re-encaje. La ``material.id`` (= ``material_key``)
    se conserva, de modo que el tablero sigue ligado a su producto; la distinción
    completo/medio vive solo en el flag ``half_board``.
    """
    for _edge_map, _net_map, layouts in results:
        if not layouts:
            continue
        key = layouts[0].material.id
        rm = resolved.get(key)
        # Solo tableros de catálogo; retazos/manual se cobran a costo (sin medios).
        if rm is None or not rm.is_catalog:
            continue
        for idx, layout in enumerate(layouts):
            half = _fit_on_half_board(
                layout, rm, cutting_params, strategy, min_rect_size
            )
            if half is not None:
                layouts[idx] = half


def _fit_on_half_board(
    layout: CuttingLayout,
    rm: ResolvedMaterial,
    cutting_params: CuttingParameters,
    strategy: PackingStrategy,
    min_rect_size: float,
) -> Optional[CuttingLayout]:
    """Devuelve el layout de medio tablero si todas las piezas caben; si no, ``None``."""
    pieces = [pp.piece for pp in layout.placed_pieces]
    if not pieces:
        return None

    half_material = Material(
        id=layout.material.id,
        width=rm.width / 2.0,
        height=rm.height,
        thickness=rm.thickness,
        cost_per_unit=rm.cost_per_unit / 2.0,
        half_board=True,
    )

    try:
        optimizer = GuillotineOptimizer(
            material=half_material,
            cutting_params=cutting_params,
            strategy=strategy,
            min_rect_size=min_rect_size,
        )
    except ValueError:
        # Los trims exceden el ancho/2 (medio demasiado angosto): no es viable.
        return None

    placed, unplaced = optimizer.optimize(pieces)
    if unplaced:
        return None

    return CuttingLayout(
        material=half_material,
        placed_pieces=placed,
        remainders=optimizer.remainders,
        sheet_number=layout.sheet_number,
        cuts=optimizer.cuts,
    )
