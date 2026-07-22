"""Unit tests for the material-pool solver (catalog board + finite offcuts).

Pure functions over the cutting engine — no DB. Cover the three fill orders,
finite offcut supply, the catalog fallback and the determinism of ``auto``.
"""

from src.cutting import CuttingParameters, PackingStrategy
from src.cutting.models import Piece
from src.modules.optimizations.materials import ResolvedMaterial
from src.modules.optimizations.pool import optimize_pool
from src.modules.optimizations.schemas import PoolFillOrder

PARAMS = CuttingParameters(kerf=3, top_trim=0, bottom_trim=0, left_trim=0, right_trim=0)


def _mat(
    key,
    width,
    height,
    *,
    source="catalog",
    cost=0.0,
    quantity=None,
    pool_key=None,
    fill_order=PoolFillOrder.auto,
    product_id=None,
):
    return ResolvedMaterial(
        key=key,
        width=width,
        height=height,
        thickness=18,
        cost_per_unit=cost,
        source=source,
        product_id=product_id,
        quantity=quantity,
        pool_key=pool_key,
        fill_order=fill_order,
    )


def _offcut(key, width, height, *, quantity=1, pool_key="board"):
    return _mat(
        key,
        width,
        height,
        source="clientOffcut",
        quantity=quantity,
        pool_key=pool_key,
    )


def _placed_ids(layouts, material_key):
    return sorted(
        pp.piece.id
        for layout in layouts
        for pp in layout.placed_pieces
        if layout.material.id == material_key
    )


def _count(layouts, material_key):
    return sum(1 for layout in layouts if layout.material.id == material_key)


def _all_placed_ids(layouts):
    return sorted(pp.piece.id for layout in layouts for pp in layout.placed_pieces)


def _catalog_waste(layouts, catalog_key):
    return sum(
        layout.waste_area for layout in layouts if layout.material.id == catalog_key
    )


def _signature(layouts):
    """Stable fingerprint: (material, sorted placed ids) per sheet, sorted."""
    return sorted(
        (layout.material.id, tuple(sorted(pp.piece.id for pp in layout.placed_pieces)))
        for layout in layouts
    )


def test_offcuts_first_fills_offcut_then_catalog():
    primary = _mat("board", 2440, 1220, fill_order=PoolFillOrder.offcuts_first)
    offcuts = [_offcut("off1", 800, 600)]
    pieces = [
        Piece(id="big", width=2000, height=1000),
        Piece(id="small", width=500, height=400),
    ]

    layouts = optimize_pool(pieces, primary, offcuts, PARAMS)

    # Small piece lands on the client's offcut; the big one on a catalog board.
    assert _placed_ids(layouts, "off1") == ["small"]
    assert "big" in _placed_ids(layouts, "board")
    assert _all_placed_ids(layouts) == ["big", "small"]


def test_no_offcuts_falls_back_to_catalog_only():
    primary = _mat("board", 2440, 1220)
    pieces = [
        Piece(id="a", width=700, height=500),
        Piece(id="b", width=700, height=500),
    ]

    layouts = optimize_pool(pieces, primary, [], PARAMS)

    assert layouts, "expected at least one catalog sheet"
    assert all(layout.material.id == "board" for layout in layouts)
    assert _all_placed_ids(layouts) == ["a", "b"]


def test_offcut_finite_quantity_is_respected():
    # Offcut holds a single 700x500 per sheet; only 2 units are available, so the
    # third identical piece must spill onto a catalog board.
    primary = _mat("board", 2440, 1220, fill_order=PoolFillOrder.offcuts_first)
    offcuts = [_offcut("off1", 800, 600, quantity=2)]
    pieces = [Piece(id=f"p{i}", width=700, height=500) for i in range(3)]

    layouts = optimize_pool(pieces, primary, offcuts, PARAMS)

    assert _count(layouts, "off1") == 2
    assert _count(layouts, "board") == 1
    assert _all_placed_ids(layouts) == ["p0", "p1", "p2"]


def test_catalog_first_pushes_residual_onto_offcut():
    # Three 900x900 pieces: one per catalog board (Nc=3). With catalog_first the
    # solver uses the fewest catalog boards such that the offcut absorbs the tail.
    primary = _mat("board", 1000, 1000, fill_order=PoolFillOrder.catalog_first)
    offcuts = [_offcut("off1", 950, 950, quantity=1)]
    pieces = [Piece(id=f"q{i}", width=900, height=900) for i in range(3)]

    layouts = optimize_pool(pieces, primary, offcuts, PARAMS)

    assert _count(layouts, "board") == 2
    assert _count(layouts, "off1") == 1
    assert _all_placed_ids(layouts) == ["q0", "q1", "q2"]


def test_auto_minimizes_catalog_waste_and_is_deterministic():
    pieces = [
        Piece(id="big", width=1900, height=900),
        Piece(id="mid", width=900, height=900),
        Piece(id="tiny", width=300, height=300),
    ]
    offcuts = [_offcut("off1", 1000, 1000, quantity=1)]

    auto = optimize_pool(
        pieces,
        _mat("board", 2000, 1000, fill_order=PoolFillOrder.auto),
        offcuts,
        PARAMS,
    )
    off_first = optimize_pool(
        pieces,
        _mat("board", 2000, 1000, fill_order=PoolFillOrder.offcuts_first),
        offcuts,
        PARAMS,
    )

    # auto keeps whichever candidate wastes the least catalog area.
    assert _catalog_waste(auto, "board") <= _catalog_waste(off_first, "board")
    assert _all_placed_ids(auto) == ["big", "mid", "tiny"]

    # Deterministic: same inputs → identical layout signature (cache-safe hash).
    again = optimize_pool(
        pieces,
        _mat("board", 2000, 1000, fill_order=PoolFillOrder.auto),
        offcuts,
        PARAMS,
    )
    assert _signature(auto) == _signature(again)


def test_long_offcuts_strategy_threads_through():
    # The packing strategy is forwarded to both the offcut and catalog passes.
    primary = _mat("board", 2440, 1220, fill_order=PoolFillOrder.offcuts_first)
    offcuts = [_offcut("off1", 800, 600)]
    pieces = [
        Piece(id="a", width=500, height=400),
        Piece(id="b", width=2000, height=1000),
    ]

    layouts = optimize_pool(
        pieces, primary, offcuts, PARAMS, strategy=PackingStrategy.LONG_OFFCUTS
    )

    assert _all_placed_ids(layouts) == ["a", "b"]
