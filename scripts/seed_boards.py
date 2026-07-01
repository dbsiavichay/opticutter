"""Seed script: deletes existing boards and edge bandings and inserts the Trend 2026 collection."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.modules.products.model import ProductModel, ProductType
from src.modules.users.model import (
    UserModel,  # noqa: F401 — registers users table for FK resolution
)
from src.shared.database import SessionLocal

TEXTURE_DESC = {
    "BS": "acabado Bureau Structure, superficie estructurada suave",
    "SU": "acabado Super Matt, superficie ultra mate sin brillo",
    "PE": "acabado Pearl, superficie perlada de tacto sedoso",
    "PW": "acabado Pure Wood, textura madera pura de alta definición",
    "RW": "acabado Rift Wood, veta rift de madera aserrada",
    "SN": "acabado Super Natural, textura ultrarrealista imitación madera",
}

# (abbr, display_name, category, grain_direction, texture)
DESIGNS = [
    # Solids
    ("CSH", "Cashmere", "SL", None, "BS"),
    ("GRT", "Gris Ratón", "SL", None, "SU"),
    ("ANT", "Antracita", "SL", None, "PE"),
    ("NGR", "Negro", "SL", None, "PE"),
    ("BNV", "Blanco Nieve", "SL", None, "BS"),
    # Oaks
    ("COE", "Costa Evoke", "RO", "H", "PW"),
    ("ARD", "Artesanal Dorado", "RO", "H", "PW"),
    ("BRD", "Barroco Dorado", "RO", "H", "RW"),
    ("BRA", "Barroco Ámbar", "RO", "H", "RW"),
    ("BRR", "Barroco Ristretto", "RO", "H", "RW"),
    # Lights
    ("IBZ", "Ibiza Lineal", "CL", "H", "SN"),
    ("CHA", "Chantillí", "CL", "H", "SN"),
    ("JAP", "Japandi", "CL", "H", "SN"),
    # Cremonas
    ("COT", "Cotta", "CR", "H", "PW"),
    ("TOR", "Torro", "CR", "H", "PW"),
    ("CAN", "Cannolo", "CR", "H", "PW"),
]

CATEGORY_LABEL = {"SL": "Sólido", "RO": "Roble", "CL": "Claro", "CR": "Cremona"}

PRICES = {
    ("SL", 15, False): 48.00,
    ("SL", 15, True): 56.00,
    ("SL", 36, False): 95.00,
    ("SL", 36, True): 112.00,
    ("RO", 15, False): 62.00,
    ("RO", 15, True): 72.00,
    ("RO", 36, False): 122.00,
    ("RO", 36, True): 140.00,
    ("CL", 15, False): 58.00,
    ("CL", 15, True): 68.00,
    ("CL", 36, False): 115.00,
    ("CL", 36, True): 132.00,
    ("CR", 15, False): 64.00,
    ("CR", 15, True): 75.00,
    ("CR", 36, False): 126.00,
    ("CR", 36, True): 145.00,
}


def make_board(
    abbr,
    name,
    cat,
    grain,
    texture,
    thickness,
    rh,
    height=2800,
    width=2070,
    name_suffix="",
):
    rh_label = " RH" if rh else ""
    rh_text = ", resistente a la humedad" if rh else ""
    description = f"MDP {CATEGORY_LABEL[cat]} {name}, {thickness}mm, {TEXTURE_DESC[texture]}{rh_text}"
    return {
        "type": ProductType.BOARD.value,
        "code": f"MDP-{cat}-{abbr}-{thickness}{'-RH' if rh else ''}",
        "name": f"MDP {thickness}mm {name}{name_suffix}{rh_label}",
        "description": description[:256],
        "price": PRICES[(cat, thickness, rh)],
        "is_active": True,
        # Attributes in the products catalog's canonical camelCase shape.
        "attributes": {
            "height": height,
            "width": width,
            "thickness": thickness,
            "grainDirection": grain,
        },
    }


def build_boards():
    boards = []
    for abbr, name, cat, grain, texture in DESIGNS:
        for thickness in (15, 36):
            for rh in (False, True):
                boards.append(
                    make_board(abbr, name, cat, grain, texture, thickness, rh)
                )
    # Blanco Nieve special 2440 mm format
    for thickness in (15, 36):
        for rh in (False, True):
            boards.append(
                make_board(
                    "BNV-SP",
                    "Blanco Nieve",
                    "SL",
                    None,
                    "BS",
                    thickness,
                    rh,
                    height=2440,
                    width=2070,
                    name_suffix=" Especial",
                )
            )
    return boards


# --- Edge bandings ---------------------------------------------------------
#
# Each board design has a coordinated PVC edge banding (1:1 mapping with
# DESIGNS). Except for Blanco, all come in the 3 standard sizes. The "type" is
# the Spanish label the client sees in the name/description; the value stored
# in attributes.bandType is its canonical English equivalent (see
# BAND_TYPE_VALUE), which is what the endpoint filters on.
#   (type, thickness_mm, width_mm)
EDGE_BAND_VARIANTS = [
    ("Suave", 0.45, 19),
    ("Duro", 1.00, 40),
    ("Duro", 1.50, 19),
]

# Spanish label (client-facing) -> canonical English value of the BandType enum.
BAND_TYPE_VALUE = {"Suave": "Soft", "Duro": "Hard"}

# TODO: PLACEHOLDER prices (not provided). Replace with the real ones.
EDGE_PRICES = {
    (0.45, 19): 12.00,
    (1.00, 40): 22.00,
    (1.50, 19): 15.00,
}


def edge_label(abbr, name, cat):
    """Commercial label of the edge banding based on the design's category."""
    if abbr == "BNV":  # the edge banding is named "Blanco", not "Blanco Nieve"
        name = "Blanco"
    if cat == "RO":
        return f"Roble {name}"
    if cat == "CR":
        return f"{name} Cremona"
    return name


def make_edge_banding(abbr, name, cat, band_type, thickness, width):
    label = edge_label(abbr, name, cat)
    thick_txt = f"{thickness:g}"  # 0.45, 1, 1.5 (no trailing zeros)
    band_value = BAND_TYPE_VALUE[band_type]  # canonical English value (Soft/Hard)
    description = (
        f"Tapacanto PVC {label}, tipo {band_type}, {thick_txt}mm x {width}mm, "
        f"coordinado con tablero MDP {label}"
    )
    return {
        "type": ProductType.EDGE_BANDING.value,
        "code": f"TAP-{cat}-{abbr}-{int(round(thickness * 100)):03d}",
        "name": f"Tapacanto PVC {label} {band_type} {thick_txt}x{width}mm",
        "description": description[:256],
        "price": EDGE_PRICES[(thickness, width)],
        "is_active": True,
        # Attributes in the products catalog's canonical camelCase shape.
        "attributes": {
            "bandType": band_value,
            "thickness": thickness,
            "width": width,
            "color": label,
        },
    }


def build_edge_bandings():
    bands = []
    for abbr, name, cat, _grain, _texture in DESIGNS:
        # Blanco isn't offered in all 3 coordinated sizes; only the standard Suave.
        variants = [EDGE_BAND_VARIANTS[0]] if abbr == "BNV" else EDGE_BAND_VARIANTS
        for band_type, thickness, width in variants:
            bands.append(
                make_edge_banding(abbr, name, cat, band_type, thickness, width)
            )
    return bands


def main():
    db = SessionLocal()
    try:
        for product_type, builder, label in (
            (ProductType.BOARD, build_boards, "tableros"),
            (ProductType.EDGE_BANDING, build_edge_bandings, "tapacantos"),
        ):
            deleted = (
                db.query(ProductModel)
                .filter(ProductModel.type == product_type.value)
                .delete()
            )
            print(f"Deleted {deleted} existing {label}.")

            items = [ProductModel(**data) for data in builder()]
            db.add_all(items)
            print(f"Inserted {len(items)} new {label}.")
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
