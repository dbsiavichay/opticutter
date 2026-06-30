"""Notación de taller para los cantos (tapacantos) de una pieza."""

from typing import Iterable, Optional

# Abreviatura del tipo de canto: Suave→CS, Duro→CD (valores canónicos de BandType).
_BAND_TYPE_ABBR = {"Soft": "CS", "Hard": "CD"}

# Etiqueta legible del tipo de canto para tablas/leyendas (valores canónicos de BandType).
BAND_TYPE_LABEL = {"Soft": "Suave", "Hard": "Duro"}


def edge_banding_notation(sides: Iterable[str], band_type: Optional[str] = None) -> str:
    """Notación de taller de los lados canteados: ``'2L1C CS'`` (largos/cortos + tipo).

    Clasifica por la medida del lado **nominal**: ``left``/``right`` son los lados del
    alto (primera medida) → ``L`` (largo); ``top``/``bottom`` son los del ancho →
    ``C`` (corto). Se omite el conteo en cero (``1L``, ``2C``) y, sin tipo de canto
    conocido, se omite el sufijo. Cuando los 4 lados están canteados se nota ``4L``.
    Devuelve ``''`` si no hay lados canteados.

    Importante: usar siempre los lados **nominales** (los del ``EdgeBandingSpec``), no
    los geométricos remapeados por rotación; así el conteo es estable bajo rotación.
    """
    sides = list(sides or [])
    if not sides:
        return ""
    long_count = sum(1 for s in sides if s in ("left", "right"))  # alto = Largo
    short_count = sum(1 for s in sides if s in ("top", "bottom"))  # ancho = Corto
    if long_count == 2 and short_count == 2:
        parts = "4L"
    else:
        parts = ""
        if long_count:
            parts += f"{long_count}L"
        if short_count:
            parts += f"{short_count}C"
    suffix = _BAND_TYPE_ABBR.get(band_type)
    return f"{parts} {suffix}" if (parts and suffix) else parts
