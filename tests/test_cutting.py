"""Tests del dominio puro de corte (sin frameworks)."""

import pytest

from src.cutting import (
    CuttingLayout,
    CuttingParameters,
    GuillotineOptimizer,
    Material,
    MultiSheetGuillotineOptimizer,
    PackingStrategy,
    Piece,
    Rectangle,
    SplitRule,
)

# --- Modelos -------------------------------------------------------------


def test_rectangle_area_and_contains():
    rect = Rectangle(x=0, y=0, width=100, height=50)
    assert rect.area == 5000
    assert rect.contains(80, 40) is True
    assert rect.contains(120, 40) is False


def test_rectangle_negative_dimensions_raise():
    with pytest.raises(ValueError):
        Rectangle(x=0, y=0, width=-1, height=10)


def test_piece_validations():
    piece = Piece(id="p1", width=300, height=200, quantity=2)
    assert piece.area == 60000
    with pytest.raises(ValueError):
        Piece(id="bad", width=0, height=10)
    with pytest.raises(ValueError):
        Piece(id="bad", width=10, height=10, quantity=0)


def test_material_validations():
    material = Material(id="m1", width=1220, height=2440, thickness=18)
    assert material.area == 1220 * 2440
    with pytest.raises(ValueError):
        Material(id="bad", width=0, height=10, thickness=18)
    with pytest.raises(ValueError):
        Material(id="bad", width=10, height=10, thickness=-1)


def test_cutting_parameters_reject_negative():
    params = CuttingParameters(kerf=5, top_trim=1)
    assert params.kerf == 5
    with pytest.raises(ValueError):
        CuttingParameters(kerf=-1)
    with pytest.raises(ValueError):
        CuttingParameters(left_trim=-1)


# --- Optimizador de una hoja --------------------------------------------


def test_guillotine_places_pieces_and_reports_efficiency():
    material = Material(id="m1", width=1220, height=2440, thickness=18)
    optimizer = GuillotineOptimizer(
        material=material, cutting_params=CuttingParameters(kerf=4)
    )
    placed, unplaced = optimizer.optimize([Piece(id="a", width=600, height=400)])

    assert len(placed) == 1
    assert unplaced == []

    layout = CuttingLayout(
        material=material,
        placed_pieces=placed,
        remainders=optimizer.remainders,
        sheet_number=1,
    )
    assert layout.used_area == 600 * 400
    assert layout.waste_area == material.area - layout.used_area
    assert 0 < layout.efficiency < 1

    as_dict = layout.to_dict()
    assert as_dict["statistics"]["pieces_count"] == 1
    assert as_dict["material"]["material_key"] == "m1"
    assert as_dict["material"]["sheet_number"] == 1
    # Los cortes de sierra se serializan (los consume la vista de taller).
    assert as_dict["cuts"] == [
        {"x": c.x, "y": c.y, "length": c.length, "is_horizontal": c.is_horizontal}
        for c in layout.cuts
    ]


def test_guillotine_empty_pieces_returns_empty():
    material = Material(id="m1", width=1000, height=1000, thickness=18)
    placed, unplaced = GuillotineOptimizer(material=material).optimize([])
    assert placed == []
    assert unplaced == []


# --- Metros lineales de corte (reconstrucción exacta) --------------------


def test_cut_length_single_piece_vertical_first():
    """SHORTER_LEFTOVER_AXIS con sobrante menor en ancho → ``vertical_first``.

    Pieza 400(ancho)×300(alto) en tablero 1000×1000 (kerf 0): corte horizontal a
    ancho completo (1000) + corte vertical al alto de la pieza (300) = 1300 mm.
    """
    material = Material(id="m1", width=1000, height=1000, thickness=18)
    optimizer = GuillotineOptimizer(
        material=material, cutting_params=CuttingParameters(kerf=0)
    )
    placed, unplaced = optimizer.optimize(
        [Piece(id="p", width=400, height=300, can_rotate=False)]
    )
    assert len(placed) == 1 and unplaced == []

    horizontals = [c for c in optimizer.cuts if c.is_horizontal]
    verticals = [c for c in optimizer.cuts if not c.is_horizontal]
    assert len(horizontals) == 1 and horizontals[0].length == pytest.approx(1000)
    assert len(verticals) == 1 and verticals[0].length == pytest.approx(300)

    layout = CuttingLayout(
        material=material,
        placed_pieces=placed,
        remainders=optimizer.remainders,
        sheet_number=1,
        cuts=optimizer.cuts,
    )
    assert layout.cut_length == pytest.approx(1300)


def test_cut_length_single_piece_horizontal_first():
    """Sobrante mayor en ancho → ``horizontal_first``.

    Pieza 300(ancho)×600(alto) en tablero 1000×1000 (kerf 0): corte vertical a alto
    completo (1000) + corte horizontal al ancho de la pieza (300) = 1300 mm.
    """
    material = Material(id="m1", width=1000, height=1000, thickness=18)
    optimizer = GuillotineOptimizer(
        material=material, cutting_params=CuttingParameters(kerf=0)
    )
    placed, unplaced = optimizer.optimize(
        [Piece(id="p", width=300, height=600, can_rotate=False)]
    )
    assert len(placed) == 1 and unplaced == []

    horizontals = [c for c in optimizer.cuts if c.is_horizontal]
    verticals = [c for c in optimizer.cuts if not c.is_horizontal]
    assert len(verticals) == 1 and verticals[0].length == pytest.approx(1000)
    assert len(horizontals) == 1 and horizontals[0].length == pytest.approx(300)


def test_cut_length_full_fill_has_no_cuts():
    """Una pieza que llena el tablero exacto no genera cortes (no hay sobrante)."""
    material = Material(id="m1", width=500, height=500, thickness=18)
    optimizer = GuillotineOptimizer(
        material=material, cutting_params=CuttingParameters(kerf=0)
    )
    placed, unplaced = optimizer.optimize(
        [Piece(id="p", width=500, height=500, can_rotate=False)]
    )
    assert len(placed) == 1 and unplaced == []
    assert optimizer.cuts == []


def test_guillotine_trims_exceeding_material_raise():
    material = Material(id="m1", width=100, height=100, thickness=18)
    with pytest.raises(ValueError):
        GuillotineOptimizer(
            material=material,
            cutting_params=CuttingParameters(left_trim=60, right_trim=60),
        )


# --- Optimizador multi-hoja ---------------------------------------------


def test_multisheet_uses_several_sheets_when_needed():
    material = Material(id="board", width=1000, height=1000, thickness=18)
    optimizer = MultiSheetGuillotineOptimizer(
        material_template=material,
        cutting_params=CuttingParameters(kerf=5),
        split_rule=SplitRule.SHORTER_LEFTOVER_AXIS,
        max_sheets=10,
    )
    # 6 piezas grandes que no caben todas en una sola hoja.
    layouts, remaining = optimizer.optimize(
        [Piece(id="big", width=700, height=700, quantity=6)]
    )

    assert len(layouts) >= 2
    assert remaining == []
    assert all(isinstance(layout, CuttingLayout) for layout in layouts)
    # El material conserva el board_id original; el número de hoja vive en el layout.
    assert layouts[0].material.id == "board"
    assert [layout.sheet_number for layout in layouts] == list(
        range(1, len(layouts) + 1)
    )


def test_multisheet_empty_returns_empty():
    material = Material(id="board", width=1000, height=1000, thickness=18)
    layouts, remaining = MultiSheetGuillotineOptimizer(
        material_template=material
    ).optimize([])
    assert layouts == []
    assert remaining == []


def test_multisheet_layouts_track_cut_length():
    """Cada layout reporta su largo de corte (suma de sus segmentos) y es positivo."""
    material = Material(id="board", width=1000, height=1000, thickness=18)
    optimizer = MultiSheetGuillotineOptimizer(
        material_template=material,
        cutting_params=CuttingParameters(kerf=5),
    )
    layouts, remaining = optimizer.optimize(
        [Piece(id="p", width=400, height=300, quantity=3, can_rotate=False)]
    )
    assert layouts and remaining == []
    for layout in layouts:
        assert layout.cut_length == pytest.approx(sum(c.length for c in layout.cuts))
        assert layout.cut_length > 0


# --- Estrategias de empaquetado (PackingStrategy) ------------------------


def _example_setup():
    """Tablero retrato (alto 2440 > ancho 1830) + 8 piezas del ejemplo real."""
    material = Material(id="board", width=1830, height=2440, thickness=15)
    params = CuttingParameters(
        kerf=5, top_trim=10, bottom_trim=10, left_trim=10, right_trim=10
    )
    widths = [300, 500, 302, 303, 304, 305, 306, 307]
    pieces = [
        Piece(id=f"P{i + 1}", width=w, height=500, quantity=1, can_rotate=False)
        for i, w in enumerate(widths)
    ]
    return material, params, pieces


def test_strategy_derives_split_rule_when_not_passed():
    """Sin ``split_rule`` explícito, la estrategia define la regla de split."""
    material = Material(id="m", width=1830, height=2440, thickness=15)
    default = MultiSheetGuillotineOptimizer(material_template=material)
    long_off = MultiSheetGuillotineOptimizer(
        material_template=material, strategy=PackingStrategy.LONG_OFFCUTS
    )
    assert default.strategy == PackingStrategy.MAX_EFFICIENCY
    assert default.split_rule == SplitRule.SHORTER_LEFTOVER_AXIS
    assert long_off.split_rule == SplitRule.LONGER_AXIS
    # Un ``split_rule`` explícito gana sobre el derivado de la estrategia.
    override = GuillotineOptimizer(
        material=material,
        split_rule=SplitRule.MAXIMIZE_AREA,
        strategy=PackingStrategy.LONG_OFFCUTS,
    )
    assert override.split_rule == SplitRule.MAXIMIZE_AREA


def test_default_strategy_preserves_best_area_fit_layout():
    """El default (MAX_EFFICIENCY) conserva el comportamiento histórico (BAF)."""
    material, params, pieces = _example_setup()
    optimizer = MultiSheetGuillotineOptimizer(
        material_template=material, cutting_params=params
    )
    layouts, remaining = optimizer.optimize(pieces)

    assert remaining == []
    layout = layouts[0]
    biggest = max(layout.remainders, key=lambda r: r.area)
    # Retazo mayor del ejemplo real con BAF: 1502 (ancho) x 1915 (alto).
    assert biggest.width == pytest.approx(1502)
    assert biggest.height == pytest.approx(1915)
    # BAF dispersa las piezas a lo ancho (llegan más allá de la mitad derecha).
    assert max(p.x + p.width for p in layout.placed_pieces) > 1700


def test_long_offcuts_leaves_full_height_strip_against_one_side():
    """``LONG_OFFCUTS`` pega las piezas a la izquierda y deja una tira de alto completo."""
    material, params, pieces = _example_setup()
    optimizer = MultiSheetGuillotineOptimizer(
        material_template=material,
        cutting_params=params,
        strategy=PackingStrategy.LONG_OFFCUTS,
    )
    layouts, remaining = optimizer.optimize(pieces)

    assert remaining == []
    layout = layouts[0]
    usable_height = material.height - params.top_trim - params.bottom_trim  # 2420

    # El retazo dominante es una franja que recorre el alto usable completo.
    biggest = max(layout.remainders, key=lambda r: r.area)
    assert biggest.height == pytest.approx(usable_height)
    # Está apegada a un costado: las piezas no la invaden (todas a su izquierda).
    assert all(p.x + p.width <= biggest.x + 1e-6 for p in layout.placed_pieces)
    # Las piezas quedan compactadas contra el lado izquierdo del tablero.
    assert max(p.x + p.width for p in layout.placed_pieces) < material.width / 2


def test_long_offcuts_differs_from_default_layout():
    """Las dos estrategias producen acomodos distintos para la misma entrada."""
    material, params, pieces = _example_setup()
    default = MultiSheetGuillotineOptimizer(
        material_template=material, cutting_params=params
    ).optimize(pieces)[0][0]
    long_off = MultiSheetGuillotineOptimizer(
        material_template=material,
        cutting_params=params,
        strategy=PackingStrategy.LONG_OFFCUTS,
    ).optimize(pieces)[0][0]

    default_xs = sorted((p.piece.id, p.x, p.y) for p in default.placed_pieces)
    long_xs = sorted((p.piece.id, p.x, p.y) for p in long_off.placed_pieces)
    assert default_xs != long_xs
