"""Seed script: borra los tableros existentes e inserta la colección Trend 2026."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.modules.products.model import ProductModel, ProductType
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


def main():
    db = SessionLocal()
    try:
        deleted = (
            db.query(ProductModel)
            .filter(ProductModel.type == ProductType.BOARD.value)
            .delete()
        )
        print(f"Eliminados {deleted} tableros existentes.")

        boards = [ProductModel(**data) for data in build_boards()]
        db.add_all(boards)
        db.commit()
        print(f"Insertados {len(boards)} tableros nuevos.")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
