"""Seed script: borra tableros y tapacantos existentes e inserta la colección Trend 2026."""

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
    # Sólidos
    ("CSH", "Cashmere", "SL", None, "BS"),
    ("GRT", "Gris Ratón", "SL", None, "SU"),
    ("ANT", "Antracita", "SL", None, "PE"),
    ("NGR", "Negro", "SL", None, "PE"),
    ("BNV", "Blanco Nieve", "SL", None, "BS"),
    # Robles
    ("COE", "Costa Evoke", "RO", "H", "PW"),
    ("ARD", "Artesanal Dorado", "RO", "H", "PW"),
    ("BRD", "Barroco Dorado", "RO", "H", "RW"),
    ("BRA", "Barroco Ámbar", "RO", "H", "RW"),
    ("BRR", "Barroco Ristretto", "RO", "H", "RW"),
    # Claros
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
        # Atributos en la forma canónica camelCase del catálogo de productos.
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
    # Blanco Nieve formato especial 2440 mm
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


# --- Tapacantos -----------------------------------------------------------
#
# Cada diseño de tablero tiene su tapacanto de PVC coordinado (mapeo 1:1 con
# DESIGNS). Salvo el Blanco, todos vienen en las 3 medidas estándar. El "tipo" es
# la etiqueta en español que ve el cliente en el nombre/descripción; el valor que
# se guarda en attributes.bandType es su equivalente canónico en inglés (ver
# BAND_TYPE_VALUE), que es lo que filtra el endpoint.
#   (tipo, espesor_mm, ancho_mm)
EDGE_BAND_VARIANTS = [
    ("Suave", 0.45, 19),
    ("Duro", 1.00, 40),
    ("Duro", 1.50, 19),
]

# Etiqueta español (visible al cliente) -> valor canónico inglés del enum BandType.
BAND_TYPE_VALUE = {"Suave": "Soft", "Duro": "Hard"}

# TODO: precios PLACEHOLDER (no provistos). Reemplazar con los reales.
EDGE_PRICES = {
    (0.45, 19): 12.00,
    (1.00, 40): 22.00,
    (1.50, 19): 15.00,
}


def edge_label(abbr, name, cat):
    """Etiqueta comercial del tapacanto según la categoría del diseño."""
    if abbr == "BNV":  # el tapacanto se llama "Blanco", no "Blanco Nieve"
        name = "Blanco"
    if cat == "RO":
        return f"Roble {name}"
    if cat == "CR":
        return f"{name} Cremona"
    return name


def make_edge_banding(abbr, name, cat, band_type, thickness, width):
    label = edge_label(abbr, name, cat)
    thick_txt = f"{thickness:g}"  # 0.45, 1, 1.5 (sin ceros sobrantes)
    band_value = BAND_TYPE_VALUE[band_type]  # valor canónico inglés (Soft/Hard)
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
        # Atributos en la forma canónica camelCase del catálogo de productos.
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
        # El Blanco no se ofrece en las 3 medidas coordinadas; solo el Suave estándar.
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
            print(f"Eliminados {deleted} {label} existentes.")

            items = [ProductModel(**data) for data in builder()]
            db.add_all(items)
            print(f"Insertados {len(items)} {label} nuevos.")
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
