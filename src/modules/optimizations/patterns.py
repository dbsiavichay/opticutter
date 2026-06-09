"""Agrupación de layouts por patrón de corte.

Varias hojas pueden compartir exactamente la misma disposición de cortes (misma
geometría y mismas etiquetas de pieza). Estas utilidades detectan esos patrones
repetidos para deduplicar la representación visual y el resumen, sin alterar el
conteo físico de tableros.
"""

import re
from typing import List, Tuple

# El optimizador expande las piezas con sufijo de instancia ``_{i+1}`` cuando
# ``quantity > 1`` (ver ``src/cutting/optimizer.py``). Para comparar patrones nos
# interesa la etiqueta base, no la instancia concreta.
_INSTANCE_SUFFIX = re.compile(r"_\d+$")


def base_label(piece_id: str) -> str:
    """Devuelve la etiqueta base quitando un único sufijo de instancia ``_N``."""
    return _INSTANCE_SUFFIX.sub("", piece_id or "")


def layout_signature(layout: dict) -> Tuple:
    """Firma canónica del patrón de corte de un layout.

    Dos layouts con la misma firma comparten geometría y etiquetas base de pieza.
    Ignora el número de hoja, los remanentes (derivados de las piezas) y el sufijo
    de instancia del ``piece_id``.
    """
    material_key = layout.get("material", {}).get("material_key")
    pieces = [
        (
            base_label(str(piece.get("piece_id", ""))),
            piece.get("x"),
            piece.get("y"),
            piece.get("width"),
            piece.get("height"),
            bool(piece.get("rotated", False)),
        )
        for piece in layout.get("placed_pieces", [])
    ]
    pieces.sort(key=lambda p: (p[1], p[2], p[3], p[4], p[0]))
    return (material_key, tuple(pieces))


def group_layouts(layouts: List[dict]) -> List[dict]:
    """Agrupa los layouts por patrón de corte preservando el orden de aparición.

    Devuelve una lista de grupos; cada grupo conserva el layout representativo
    (el primero del patrón) y cuántas hojas lo comparten::

        {
            "pattern_id": 1,
            "count": 5,
            "sheet_numbers": [1, 2, 3, 4, 5],
            "material_key": "b1",
            "layout": { ...layout representativo... },
        }
    """
    groups: List[dict] = []
    index_by_signature: dict = {}

    for layout in layouts:
        signature = layout_signature(layout)
        sheet_number = layout.get("material", {}).get("sheet_number")

        if signature in index_by_signature:
            group = groups[index_by_signature[signature]]
            group["count"] += 1
            group["sheet_numbers"].append(sheet_number)
            continue

        index_by_signature[signature] = len(groups)
        groups.append(
            {
                "pattern_id": len(groups) + 1,
                "count": 1,
                "sheet_numbers": [sheet_number],
                "material_key": layout.get("material", {}).get("material_key"),
                "layout": layout,
            }
        )

    return groups
