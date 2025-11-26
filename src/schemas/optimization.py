from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, PositiveInt

from src.models.schemas import ClientResponse


class Requirement(BaseModel):
    index: PositiveInt
    height: PositiveInt
    width: PositiveInt
    quantity: PositiveInt = Field(default=1, le=10000)
    board_id: str = Field(..., alias="boardId")
    label: Optional[str] = None
    allow_rotation: bool = Field(default=True, alias="allowRotation")


class OptimizeRequest(BaseModel):
    requirements: List[Requirement] = Field(
        ..., min_length=1, description="List of cuts to optimize"
    )
    client_id: int = Field(
        ..., alias="clientId", description="Client ID for the optimization"
    )


# Response models
class OptimizeResponse(BaseModel):
    id: int
    client: ClientResponse = Field(..., description="Client information")
    total_boards_used: int = Field(
        ..., alias="totalBoardsUsed", description="Total number of boards used"
    )
    total_boards_cost: float = Field(
        ..., alias="totalBoardsCost", description="Total cost of boards used"
    )
    total_waste_percentage: float = Field(
        ..., alias="totalWastePercentage", description="Total waste percentage"
    )
    duration_ms: int = Field(
        ...,
        alias="durationMs",
        description="Duration of the optimization in milliseconds",
    )


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
