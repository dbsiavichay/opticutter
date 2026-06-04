from typing import Optional

from pydantic import Field, PositiveInt

from src.shared.schemas import CamelModel


class BoardAttributes(CamelModel):
    """Atributos específicos de un tablero (insumo del optimizador de cortes)."""

    height: PositiveInt = Field(..., description="Alto (largo, primera medida) en mm")
    width: PositiveInt = Field(..., description="Ancho (segunda medida) en mm")
    thickness: PositiveInt = Field(..., description="Grosor en mm")
    grain_direction: Optional[str] = Field(
        None, max_length=4, description="Dirección de veta"
    )
