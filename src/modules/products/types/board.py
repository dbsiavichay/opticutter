from typing import Optional

from pydantic import Field, PositiveInt

from src.shared.schemas import CamelModel


class BoardAttributes(CamelModel):
    """Board-specific attributes (input to the cutting optimizer)."""

    height: PositiveInt = Field(
        ..., description="Height (length, first dimension) in mm"
    )
    width: PositiveInt = Field(..., description="Width (second dimension) in mm")
    thickness: PositiveInt = Field(..., description="Thickness in mm")
    grain_direction: Optional[str] = Field(
        None, max_length=4, description="Grain direction"
    )
