"""Tests for grouping layouts by cutting pattern (pure logic)."""

from src.modules.optimizations.patterns import (
    base_label,
    group_layouts,
    layout_signature,
)


def _layout(sheet_number, pieces, material_key="b1"):
    """Builds a minimal layout shaped like ``CuttingLayout.to_dict``."""
    return {
        "material": {"material_key": material_key, "sheet_number": sheet_number},
        "placed_pieces": [
            {
                "piece_id": pid,
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "rotated": rot,
            }
            for (pid, x, y, w, h, rot) in pieces
        ],
        "remainders": [],
    }


def test_base_label_strips_single_instance_suffix():
    assert base_label("piece_1#5") == "piece_1"
    assert base_label("Puerta#2") == "Puerta"
    assert base_label("Puerta") == "Puerta"
    assert base_label("") == ""


def test_base_label_preserves_labels_ending_in_underscore_number():
    """``#`` separates the instance: labels ending in ``_<n>`` (auto-label
    ``piece_1`` or user label ``estante_2``) are not mangled."""
    assert base_label("piece_1") == "piece_1"
    assert base_label("estante_2") == "estante_2"
    assert base_label("estante_2#3") == "estante_2"


def test_signature_ignores_instance_suffix_and_sheet_number():
    a = _layout(1, [("Puerta#1", 0, 0, 670, 1700, False)])
    b = _layout(7, [("Puerta#9", 0, 0, 670, 1700, False)])
    assert layout_signature(a) == layout_signature(b)


def test_signature_ignores_piece_order():
    a = _layout(1, [("A", 0, 0, 100, 200, False), ("B", 300, 0, 100, 200, False)])
    b = _layout(1, [("B", 300, 0, 100, 200, False), ("A", 0, 0, 100, 200, False)])
    assert layout_signature(a) == layout_signature(b)


def test_group_collapses_identical_patterns():
    layouts = [
        _layout(1, [("piece_1#1", 0, 0, 670, 1700, False)]),
        _layout(2, [("piece_1#2", 0, 0, 670, 1700, False)]),
        _layout(3, [("piece_1#3", 0, 0, 670, 1700, False)]),
    ]
    groups = group_layouts(layouts)
    assert len(groups) == 1
    group = groups[0]
    assert group["pattern_id"] == 1
    assert group["count"] == 3
    assert group["sheet_numbers"] == [1, 2, 3]
    assert group["material_key"] == "b1"
    assert group["layout"] is layouts[0]


def test_group_keeps_different_labels_separate():
    layouts = [
        _layout(1, [("Puerta", 0, 0, 670, 1700, False)]),
        _layout(2, [("Cajon", 0, 0, 670, 1700, False)]),
    ]
    groups = group_layouts(layouts)
    assert len(groups) == 2
    assert [g["pattern_id"] for g in groups] == [1, 2]
    assert all(g["count"] == 1 for g in groups)


def test_group_keeps_different_geometry_separate():
    layouts = [
        _layout(1, [("A", 0, 0, 670, 1700, False)]),
        _layout(2, [("A", 0, 0, 800, 1700, False)]),
    ]
    groups = group_layouts(layouts)
    assert len(groups) == 2


def test_group_preserves_first_appearance_order():
    layouts = [
        _layout(1, [("A", 0, 0, 100, 100, False)]),
        _layout(2, [("B", 0, 0, 200, 200, False)]),
        _layout(3, [("A", 0, 0, 100, 100, False)]),
    ]
    groups = group_layouts(layouts)
    assert len(groups) == 2
    assert groups[0]["count"] == 2 and groups[0]["sheet_numbers"] == [1, 3]
    assert groups[1]["count"] == 1 and groups[1]["sheet_numbers"] == [2]
