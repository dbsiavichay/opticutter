"""Half-board detection (charged at half price + markup) as a post-optimization step.

The business sells half catalog boards, split **lengthwise** (the
length/``height`` is kept and the width/``width`` is cut in half). The client
doesn't request them explicitly: they request pieces. So, after optimizing
against full boards, this module checks each sheet (layout) and, if **all**
of its pieces fit on a single half board, replaces it with the half-board
layout (re-packed geometry + cuts) and charges ``price/2 * (1 + markup)``.

It's deterministic given its inputs — the resolved material's cost/dimensions,
the cutting parameters, and ``half_board_markup_pct`` — all of which the caller
(``OptimizationService._compute_hash``) must include in the Redis cache-key
hash; a caller that forgets to do so will serve stale markup values from
cache. It reuses the pure cutting engine, so the half board flows through to
costs, summary, discount, order snapshot and cutting plan. It only applies to
**catalog** materials: offcuts/manual measurements are already charged at cost.
"""

from typing import Dict, List, Optional, Tuple

from src.cutting.enums import PackingStrategy
from src.cutting.models import CuttingLayout, Material
from src.cutting.optimizer import GuillotineOptimizer
from src.cutting.parameters import CuttingParameters
from src.modules.optimizations.materials import ResolvedMaterial

# Per-material result: edge-banding/length maps (indexed by piece id) + layouts.
MaterialResult = Tuple[Dict[str, object], Dict[str, float], List[CuttingLayout]]


def apply_half_boards(
    results: List[MaterialResult],
    resolved: Dict[str, ResolvedMaterial],
    cutting_params: CuttingParameters,
    strategy: PackingStrategy,
    half_board_markup_pct: float,
    min_rect_size: float = 0.1,
) -> None:
    """Replaces in place the catalog sheets that fit on a half board.

    Each layout whose content fully fits on a half board (same length, width/2)
    is replaced by the half-board layout: ``half_board=True``, half width,
    ``price/2 * (1 + half_board_markup_pct)`` cost, and pieces re-placed by the
    re-pack. ``material.id`` (= ``material_key``) is preserved, so the board
    stays linked to its product; the full/half distinction lives solely in the
    ``half_board`` flag.
    """
    for _edge_map, _net_map, layouts in results:
        # Per-layout: a pooled group mixes catalog and offcut sheets in one
        # ``layouts`` list, so the catalog check can't key off ``layouts[0]``.
        for idx, layout in enumerate(layouts):
            rm = resolved.get(layout.material.id)
            # Catalog boards only; offcuts/manual are charged at cost (no halves).
            if rm is None or not rm.is_catalog:
                continue
            half = _fit_on_half_board(
                layout,
                rm,
                cutting_params,
                strategy,
                half_board_markup_pct,
                min_rect_size,
            )
            if half is not None:
                layouts[idx] = half


def _fit_on_half_board(
    layout: CuttingLayout,
    rm: ResolvedMaterial,
    cutting_params: CuttingParameters,
    strategy: PackingStrategy,
    half_board_markup_pct: float,
    min_rect_size: float,
) -> Optional[CuttingLayout]:
    """Returns the half-board layout if every piece fits; otherwise ``None``."""
    pieces = [pp.piece for pp in layout.placed_pieces]
    if not pieces:
        return None

    half_material = Material(
        id=layout.material.id,
        width=rm.width / 2.0,
        height=rm.height,
        thickness=rm.thickness,
        cost_per_unit=round(rm.cost_per_unit / 2.0 * (1 + half_board_markup_pct), 2),
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
        # Trims exceed width/2 (half board too narrow): not viable.
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
