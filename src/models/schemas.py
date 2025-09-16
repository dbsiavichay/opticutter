from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, PositiveInt, confloat, conint, model_validator


class GrainDirection(str, Enum):
    horizontal = "h"
    vertical = "v"


class CutItem(BaseModel):
    width: PositiveInt
    height: PositiveInt
    quantity: PositiveInt = Field(1, ge=1, le=10000)
    material: str
    label: Optional[str] = None
    # If explicitly forced orientation for this piece
    force_grain: Optional[GrainDirection] = None


class Material(BaseModel):
    code: str
    width: PositiveInt
    height: PositiveInt
    price: confloat(ge=0) = 0.0
    # Grain of the board itself. If none -> free rotation allowed for boards
    grain_direction: Optional[GrainDirection] = None


class CuttingParameters(BaseModel):
    kerf: conint(ge=0) = 0
    top_trim: conint(ge=0) = 0
    bottom_trim: conint(ge=0) = 0
    left_trim: conint(ge=0) = 0
    right_trim: conint(ge=0) = 0


class OptimizeRequest(BaseModel):
    project_name: str
    cuts: List[CutItem]
    materials: List[Material]
    cutting_parameters: CuttingParameters

    @model_validator(mode="after")
    def validate_sizes(self) -> "OptimizeRequest":
        materials_by_code = {m.code: m for m in self.materials}
        if not self.cuts:
            raise ValueError("No se han proporcionado cortes")
        if not self.materials:
            raise ValueError("No se han proporcionado materiales")
        for c in self.cuts:
            if c.material not in materials_by_code:
                raise ValueError(f"Cut references unknown material: {c.material}")
            m = materials_by_code[c.material]
            # quick physical feasibility (ignoring kerf and trims here; the algorithm will enforce them) # NOQA
            if c.width > m.width and c.height > m.height:
                # Even with rotation won't fit raw board
                raise ValueError(
                    f"Cut {c.label or ''} {c.width}x{c.height} cannot fit in board {m.code} {m.width}x{m.height}"  # NOQA
                )
        return self


# Response models
class PlacedCut(BaseModel):
    x: int
    y: int
    width: int
    height: int
    label: Optional[str] = None


class WastePiece(BaseModel):
    x: int
    y: int
    width: int
    height: int
    reusable: bool = True


class BoardLayout(BaseModel):
    material: str
    index: int  # board index per material
    cuts_placed: List[PlacedCut]
    utilization_percentage: float
    waste_pieces: List[WastePiece] = []


class MaterialCostSummary(BaseModel):
    material: str
    boards_used: int
    unit_cost: float
    total_cost: float


class CostSummary(BaseModel):
    materials: List[MaterialCostSummary]
    total_material_cost: float


class OptimizationSummary(BaseModel):
    project_name: str
    total_boards_used: int
    total_cost: float
    total_waste_percentage: float
    optimization_time: str


class OptimizeResponse(BaseModel):
    optimization_summary: OptimizationSummary
    cost_summary: CostSummary
    boards_layout: List[BoardLayout]
    cached: bool = False
    request_hash: Optional[str] = None


class CacheEntry(BaseModel):
    request_hash: str
    timestamp_utc: str
    result: OptimizeResponse


class OptimizationsListResponse(BaseModel):
    total: int
    items: List[CacheEntry]


class RetrieveOptimizationResponse(BaseModel):
    cached: bool
    item: Optional[CacheEntry]


class OptimizationImageResponse(BaseModel):
    """Response containing the optimization visualization image."""

    image_base64: str
    content_type: str = "image/png"
    request_hash: str
    project_name: str


# Board schemas for CRUD operations
class BoardBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=32, description="Unique board code")
    name: str = Field(..., min_length=1, max_length=128, description="Board name")
    description: Optional[str] = Field(
        None, max_length=256, description="Board description"
    )
    length: PositiveInt = Field(..., description="Board length in mm")
    width: PositiveInt = Field(..., description="Board width in mm")
    thickness: PositiveInt = Field(..., description="Board thickness in mm")
    grain_direction: Optional[GrainDirection] = Field(
        None, description="Grain direction of the board"
    )
    price: confloat(ge=0) = Field(..., description="Board price")


class BoardCreate(BoardBase):
    """Schema for creating a new board"""


class BoardUpdate(BaseModel):
    """Schema for updating an existing board"""

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
    grain_direction: Optional[GrainDirection] = Field(
        None, description="Grain direction of the board"
    )
    price: Optional[confloat(ge=0)] = Field(None, description="Board price")


class BoardResponse(BoardBase):
    """Schema for board responses"""

    id: int = Field(..., description="Board ID")

    class Config:
        from_attributes = True
