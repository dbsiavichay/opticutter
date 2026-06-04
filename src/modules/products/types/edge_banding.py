from typing import Optional

from pydantic import Field, PositiveInt

from src.shared.schemas import CamelModel


class EdgeBandingAttributes(CamelModel):
    """Atributos de un tapacanto.

    Placeholder para dejar lista la base multi-producto; la lógica de negocio del
    tapacanto (cálculo de metraje, etc.) se implementará en una fase posterior.
    """

    length: PositiveInt = Field(..., description="Largo del rollo en mm")
    width: PositiveInt = Field(..., description="Ancho en mm")
    thickness: PositiveInt = Field(..., description="Grosor en mm")
    color: Optional[str] = Field(None, max_length=64, description="Color/acabado")
