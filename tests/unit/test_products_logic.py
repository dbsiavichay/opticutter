"""Unit: board<->edge-banding coordination in ``ProductService`` (no DB).

``_design_key`` and the thickness->width map are pure logic; the matching in
``find_edge_bandings_for_board`` is tested with ``mock_session`` returning fake
candidates, without touching the real catalog.
"""

from types import SimpleNamespace

import pytest

from src.modules.products.service import (
    BOARD_THICKNESS_TO_EDGE_WIDTH,
    ProductService,
)
from src.modules.products.types.edge_banding import BandType
from src.shared.exceptions import BusinessRuleError


# --- Pure logic ---------------------------------------------------------------
@pytest.mark.parametrize(
    "code,expected",
    [
        ("MDP-SL-CSH-15", "SL-CSH"),
        ("TAP-SL-CSH-045", "SL-CSH"),
        ("MDP", None),
        ("MDP-SL", None),
    ],
)
def test_design_key(code, expected):
    assert ProductService._design_key(code) == expected


def test_thickness_to_edge_width_map():
    assert BOARD_THICKNESS_TO_EDGE_WIDTH[15] == 19
    assert BOARD_THICKNESS_TO_EDGE_WIDTH[36] == 40


# --- Matching with a mocked session --------------------------------------------
def _board(code="MDP-SL-CSH-15", thickness=15):
    return SimpleNamespace(code=code, type="board", attributes={"thickness": thickness})


def _band(code, width, *, band_type="Soft", thickness=0.45):
    return SimpleNamespace(
        code=code,
        type="edge_banding",
        attributes={"width": width, "bandType": band_type, "thickness": thickness},
    )


def _candidates(mock_session, items):
    mock_session.query.return_value.filter.return_value.all.return_value = items


def test_matches_by_design_key_and_thickness_width(mock_session):
    mock_session.get.return_value = _board()  # 15mm board => target width 19
    _candidates(
        mock_session,
        [
            _band("TAP-SL-CSH-019", 19),  # matches
            _band("TAP-SL-CSH-040", 40),  # wrong width for 15mm
            _band("TAP-OT-XXX-019", 19),  # different design
        ],
    )
    result = ProductService(mock_session).find_edge_bandings_for_board(1)
    assert [p.code for p in result] == ["TAP-SL-CSH-019"]


def test_filters_by_band_type(mock_session):
    mock_session.get.return_value = _board()
    _candidates(
        mock_session,
        [
            _band("TAP-SL-CSH-019", 19, band_type="Soft"),
            _band("TAP-SL-CSH-019D", 19, band_type="Hard"),
        ],
    )
    result = ProductService(mock_session).find_edge_bandings_for_board(
        1, band_type=BandType.SOFT
    )
    assert [p.code for p in result] == ["TAP-SL-CSH-019"]


def test_non_board_product_is_rejected(mock_session):
    mock_session.get.return_value = SimpleNamespace(
        code="TAP-SL-CSH-019", type="edge_banding", attributes={}
    )
    with pytest.raises(BusinessRuleError):
        ProductService(mock_session).find_edge_bandings_for_board(1)
