"""Workshop notation for a piece's edge banding (tapacantos)."""

from typing import Iterable, Optional

# Edge-type abbreviation: Soft→CS, Hard→CD (BandType canonical values).
_BAND_TYPE_ABBR = {"Soft": "CS", "Hard": "CD"}

# Readable edge-type label for tables/legends (BandType canonical values).
BAND_TYPE_LABEL = {"Soft": "Suave", "Hard": "Duro"}


def edge_banding_notation(sides: Iterable[str], band_type: Optional[str] = None) -> str:
    """Workshop notation for the banded sides: ``'2L1C CS'`` (long/short + type).

    Classifies by the **nominal** side measurement: ``left``/``right`` are the
    height sides (first dimension) → ``L`` (largo/long); ``top``/``bottom`` are
    the width sides → ``C`` (corto/short). A zero count is omitted (``1L``,
    ``2C``), and the suffix is omitted when the edge type is unknown. When all 4
    sides are banded it's noted as ``4L``. Returns ``''`` if no sides are banded.

    Important: always use the **nominal** sides (the ones from
    ``EdgeBandingSpec``), not the geometric ones remapped by rotation; this keeps
    the count stable under rotation.
    """
    sides = list(sides or [])
    if not sides:
        return ""
    long_count = sum(1 for s in sides if s in ("left", "right"))  # height = Long
    short_count = sum(1 for s in sides if s in ("top", "bottom"))  # width = Short
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
