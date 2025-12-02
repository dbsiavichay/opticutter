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
class Material(BaseModel):
    id: int = Field(..., description="Unique identifier for the material")
    width: float = Field(..., description="Width of the material")
    height: float = Field(..., description="Height of the material")
    thickness: float = Field(..., description="Thickness of the material")
    area: float = Field(..., description="Area of the material")


class PlacedPiece(BaseModel):
    piece_id: str = Field(
        ...,
        serialization_alias="pieceId",
        description="Unique identifier for the placed piece",
    )
    x: float = Field(..., description="X position of the placed piece")
    y: float = Field(..., description="Y position of the placed piece")
    width: float = Field(..., description="Width of the placed piece")
    height: float = Field(..., description="Height of the placed piece")
    rotated: bool = Field(..., description="Indicates if the piece is rotated")


class Remainder(BaseModel):
    x: float = Field(..., description="X position of the remainder")
    y: float = Field(..., description="Y position of the remainder")
    width: float = Field(..., description="Width of the remainder")
    height: float = Field(..., description="Height of the remainder")


class Solution(BaseModel):
    material: Material = Field(..., description="Material used in the solution")
    placed_pieces: List[PlacedPiece] = Field(
        ...,
        serialization_alias="placedPieces",
        description="List of placed pieces in the solution",
    )
    remainders: List[Remainder] = Field(
        ..., description="List of remainders in the solution"
    )


class OptimizeResponse(BaseModel):
    id: int
    client: ClientResponse = Field(..., description="Client information")
    total_boards_used: int = Field(
        ...,
        serialization_alias="totalBoardsUsed",
        description="Total number of boards used",
    )
    total_boards_cost: float = Field(
        ...,
        serialization_alias="totalBoardsCost",
        description="Total cost of boards used",
    )
    solution: List[Solution] = Field(..., description="Optimization solution details")
