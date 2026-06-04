from typing import Optional

from pydantic import Field, PositiveFloat, PositiveInt

from src.shared.schemas import CamelModel


class EdgeBandingAttributes(CamelModel):
    """Atributos de un tapacanto de PVC.

    Se identifica por su grosor y ancho, y se clasifica por tipo (Suave/Duro). El
    grosor real es fraccionario (p. ej. 0.45 mm), de ahí el float. La lógica de
    negocio (cálculo de metraje, etc.) se implementará en una fase posterior.
    """

    thickness: PositiveFloat = Field(
        ..., description="Grosor en mm (p. ej. 0.45, 1.0, 1.5)"
    )
    width: PositiveInt = Field(..., description="Ancho en mm (p. ej. 19, 40)")
    band_type: Optional[str] = Field(
        None, max_length=16, description="Tipo de tapacanto: Suave o Duro"
    )
    color: Optional[str] = Field(
        None, max_length=64, description="Color/diseño coordinado"
    )
    length: Optional[PositiveInt] = Field(
        None, description="Largo del rollo en mm (si aplica)"
    )
