from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, PositiveInt, confloat


class GrainDirection(str, Enum):
    horizontal = "h"
    vertical = "v"


class CutRequirement(BaseModel):
    index: PositiveInt
    length: PositiveInt
    width: PositiveInt
    quantity: PositiveInt = Field(1, ge=1, le=10000)
    board_code: str
    label: Optional[str] = None
    allow_rotation: bool = True


class OptimizeRequest(BaseModel):
    cuts: List[CutRequirement] = Field(
        ..., min_length=1, description="List of cuts to optimize"
    )
    client_id: int = Field(..., description="Client ID for the optimization")


# Response models
class PlacedCut(BaseModel):
    x: int
    y: int
    width: int
    length: int
    label: Optional[str] = None


class WastePiece(BaseModel):
    x: int
    y: int
    width: int
    length: int
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
    total_boards_used: int
    total_cost: float
    total_waste_percentage: float
    optimization_time: str


class OptimizeResponse(BaseModel):
    id: int
    optimization_summary: OptimizationSummary
    cost_summary: CostSummary
    boards_layout: List[BoardLayout]


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


# Client schemas for CRUD operations
class ClientBase(BaseModel):
    phone: str = Field(
        ..., min_length=1, max_length=32, description="Client phone number"
    )
    first_name: Optional[str] = Field(
        None, max_length=64, description="Client first name"
    )
    last_name: Optional[str] = Field(
        None, max_length=64, description="Client last name"
    )


class ClientCreate(ClientBase):
    """Schema for creating a new client"""


class ClientUpdate(BaseModel):
    """Schema for updating an existing client"""

    phone: Optional[str] = Field(
        None, min_length=1, max_length=32, description="Client phone number"
    )
    first_name: Optional[str] = Field(
        None, max_length=64, description="Client first name"
    )
    last_name: Optional[str] = Field(
        None, max_length=64, description="Client last name"
    )


class ClientResponse(ClientBase):
    """Schema for client responses"""

    id: int = Field(..., description="Client ID")

    class Config:
        from_attributes = True
