from enum import Enum
from typing import Optional

from pydantic import Field, PositiveFloat, PositiveInt

from src.shared.schemas import CamelModel

# Spanish input aliases accepted alongside the canonical English value. A safety
# net in case the bot or legacy data sends "Suave"/"Duro": they normalize to the
# enum value (``Soft``/``Hard``) that gets stored and compared.
_SPANISH_ALIASES = {"suave": "Soft", "duro": "Hard"}


class BandType(str, Enum):
    """Edge banding type (closed set).

    ``SOFT`` (soft banding, ~0.45 mm) and ``HARD`` (hard banding, 1.0/1.5 mm);
    the canonical value is English (``"Soft"``/``"Hard"``). ``_missing_`` accepts
    case-insensitive input and translates the Spanish aliases (``"suave"``/``"duro"``)
    to the canonical value, so the field stays closed to these two values both
    when creating/updating products and when filtering in the endpoint.
    """

    SOFT = "Soft"
    HARD = "Hard"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            norm = value.strip().lower()
            for member in cls:
                if member.value.lower() == norm:
                    return member
            if norm in _SPANISH_ALIASES:
                return cls(_SPANISH_ALIASES[norm])
        return None


class EdgeBandingAttributes(CamelModel):
    """Attributes of a PVC edge banding.

    Identified by its thickness and width, and classified by type (Soft/Hard).
    The real thickness is fractional (e.g. 0.45 mm), hence the float. Business
    logic (length calculation, etc.) will be implemented in a later phase.
    """

    thickness: PositiveFloat = Field(
        ..., description="Thickness in mm (e.g. 0.45, 1.0, 1.5)"
    )
    width: PositiveInt = Field(..., description="Width in mm (e.g. 19, 40)")
    band_type: Optional[BandType] = Field(
        None, description="Edge banding type: Soft or Hard"
    )
    color: Optional[str] = Field(
        None, max_length=64, description="Coordinated color/design"
    )
    length: Optional[PositiveInt] = Field(
        None, description="Roll length in mm (if applicable)"
    )
