from typing import Optional

from pydantic import Field, PositiveInt, confloat

from src.shared.schemas import CamelModel


class BoardBase(CamelModel):
    code: str = Field(..., min_length=1, max_length=32, description="Unique board code")
    name: str = Field(..., min_length=1, max_length=128, description="Board name")
    description: Optional[str] = Field(
        None, max_length=256, description="Board description"
    )
    length: PositiveInt = Field(..., description="Board length in mm")
    width: PositiveInt = Field(..., description="Board width in mm")
    thickness: PositiveInt = Field(..., description="Board thickness in mm")
    grain_direction: Optional[str] = Field(
        None, description="Grain direction of the board"
    )
    price: confloat(ge=0) = Field(..., description="Board price")


class BoardCreate(BoardBase):
    """Schema for creating a new board."""


class BoardUpdate(CamelModel):
    """Schema for updating an existing board."""

    code: Optional[str] = Field(
        None, min_length=1, max_length=32, description="Unique board code"
    )
    name: Optional[str] = Field(
        None, min_length=1, max_length=128, description="Board name"
    )
    description: Optional[str] = Field(
        None, max_length=256, description="Board description"
    )
    length: Optional[PositiveInt] = Field(None, description="Board length in mm")
    width: Optional[PositiveInt] = Field(None, description="Board width in mm")
    thickness: Optional[PositiveInt] = Field(None, description="Board thickness in mm")
    grain_direction: Optional[str] = Field(
        None, description="Grain direction of the board"
    )
    price: Optional[confloat(ge=0)] = Field(None, description="Board price")


class BoardResponse(BoardBase):
    """Schema for board responses."""

    id: int = Field(..., description="Board ID")
