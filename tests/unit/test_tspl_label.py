"""Unit: the TSPL label renderer (no DB).

Validates the emitted TSPL job's structure and that the BITMAP byte count matches
the declared width/height, plus the extraction of ``LabelData`` from an order +
placed piece (duck-typed, so no ORM/session needed).
"""

from types import SimpleNamespace

from src.modules.print_jobs import label
from src.modules.print_jobs.label import LabelData, build_label_data


def _sample() -> LabelData:
    return LabelData(
        order_code="ORD-000042",
        client_name="Juan Pérez",
        piece_label="estante",
        width_mm=600,
        height_mm=400,
        notation="2L1C CS",
        sides={"top", "left"},
    )


def test_render_label_emits_a_tspl_job():
    out = label.render_label(_sample())
    assert out.startswith(b"SIZE ")
    assert b"GAP " in out
    assert b"CLS\r\n" in out
    assert b"BITMAP 0,0," in out
    assert out.rstrip().endswith(b"PRINT 1,1")


def test_bitmap_byte_count_matches_declared_size():
    """The raster between the BITMAP header and the trailing PRINT must be exactly
    ``width_bytes * height`` bytes — otherwise the printer mis-reads the image."""
    out = label.render_label(_sample())
    marker = b"BITMAP 0,0,"
    rest = out[out.index(marker) + len(marker) :]
    params, _, raster_and_tail = rest.partition(b",0,")
    width_bytes, height = (int(x) for x in params.split(b","))
    assert width_bytes > 0 and height > 0
    # The row width is byte-aligned (multiple of 8 dots).
    assert raster_and_tail[width_bytes * height :] == b"\r\nPRINT 1,1\r\n"


def test_invert_flips_every_bit(monkeypatch):
    from src.shared.config import config

    normal = label.render_label(_sample())
    monkeypatch.setattr(config, "PRINT_LABEL_INVERT", True)
    inverted = label.render_label(_sample())
    # Same length/headers, but the raster region differs (bits flipped).
    assert len(normal) == len(inverted)
    assert normal != inverted


def test_build_label_data_from_order_and_piece():
    client = SimpleNamespace(first_name="Ada", last_name="Lovelace")
    order = SimpleNamespace(code="ORD-7", id=7, client=client)
    piece = SimpleNamespace(
        label="puerta",
        original_width=600.4,
        original_height=399.6,
        edges={"sides": ["top"], "band_type": "Soft"},
    )
    data = build_label_data(order, piece)
    assert data.order_code == "ORD-7"
    assert data.client_name == "Ada Lovelace"
    assert (data.width_mm, data.height_mm) == (600, 400)  # rounded
    assert data.sides == {"top"}
    assert data.notation  # derived from the edges


def test_build_label_data_falls_back_to_synthetic_code_and_no_edges():
    client = SimpleNamespace(first_name="", last_name="")
    order = SimpleNamespace(code=None, id=42, client=client)
    piece = SimpleNamespace(
        label="x", original_width=100, original_height=50, edges=None
    )
    data = build_label_data(order, piece)
    assert data.order_code == "ORD-000042"
    assert data.client_name == ""
    assert data.notation == "" and data.sides == set()
