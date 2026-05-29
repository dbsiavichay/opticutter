"""Tests del dominio puro de corte (sin frameworks)."""

import pytest

from src.cutting import (
    CuttingLayout,
    CuttingParameters,
    GuillotineOptimizer,
    Material,
    MultiSheetGuillotineOptimizer,
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
    )
    assert layout.used_area == 600 * 400
    assert layout.waste_area == material.area - layout.used_area
    assert 0 < layout.efficiency < 1

    as_dict = layout.to_dict()
    assert as_dict["statistics"]["pieces_count"] == 1
    assert as_dict["material"]["id"] == "m1"


def test_guillotine_empty_pieces_returns_empty():
    material = Material(id="m1", width=1000, height=1000, thickness=18)
    placed, unplaced = GuillotineOptimizer(material=material).optimize([])
    assert placed == []
    assert unplaced == []


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
    # El id del material incluye el número de hoja.
    assert layouts[0].material.id == "board_1"


def test_multisheet_empty_returns_empty():
    material = Material(id="board", width=1000, height=1000, thickness=18)
    layouts, remaining = MultiSheetGuillotineOptimizer(
        material_template=material
    ).optimize([])
    assert layouts == []
    assert remaining == []
