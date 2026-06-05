from enum import Enum
from typing import Optional

from pydantic import Field, PositiveFloat, PositiveInt

from src.shared.schemas import CamelModel

# Alias de entrada en español aceptados además del valor canónico inglés. Es una
# red de seguridad por si el bot o datos antiguos envían "Suave"/"Duro": se
# normalizan al valor del enum (``Soft``/``Hard``) que se almacena y compara.
_SPANISH_ALIASES = {"suave": "Soft", "duro": "Hard"}


class BandType(str, Enum):
    """Tipo de tapacanto (cerrado).

    ``SOFT`` (canto suave, ~0.45 mm) y ``HARD`` (canto duro, 1.0/1.5 mm); el valor
    canónico es inglés (``"Soft"``/``"Hard"``). El ``_missing_`` acepta la entrada
    sin distinguir mayúsculas y traduce los alias en español (``"suave"``/``"duro"``)
    al valor canónico, así que el campo queda cerrado a estos dos valores tanto al
    crear/actualizar productos como al filtrar en el endpoint.
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
    """Atributos de un tapacanto de PVC.

    Se identifica por su grosor y ancho, y se clasifica por tipo (Soft/Hard). El
    grosor real es fraccionario (p. ej. 0.45 mm), de ahí el float. La lógica de
    negocio (cálculo de metraje, etc.) se implementará en una fase posterior.
    """

    thickness: PositiveFloat = Field(
        ..., description="Grosor en mm (p. ej. 0.45, 1.0, 1.5)"
    )
    width: PositiveInt = Field(..., description="Ancho en mm (p. ej. 19, 40)")
    band_type: Optional[BandType] = Field(
        None, description="Tipo de tapacanto: Soft o Hard"
    )
    color: Optional[str] = Field(
        None, max_length=64, description="Color/diseño coordinado"
    )
    length: Optional[PositiveInt] = Field(
        None, description="Largo del rollo en mm (si aplica)"
    )
