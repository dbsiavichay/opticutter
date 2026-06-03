from typing import List, Optional

from pydantic import Field, NonNegativeInt, PositiveInt

from src.modules.clients.schemas import ClientResponse
from src.shared.schemas import CamelModel


class MaterialSummary(CamelModel):
    board_id: int
    board_code: str
    board_name: str
    height: float
    width: float
    thickness: float
    count: int
    total_area_m2: float
    avg_efficiency: float
    cost_per_unit: float
    total_cost: float


class Requirement(CamelModel):
    priority: NonNegativeInt = Field(
        ..., description="Cutting priority; higher values are placed first"
    )
    height: PositiveInt = Field(
        ..., description="Piece height (alto, primera medida) in mm"
    )
    width: PositiveInt = Field(
        ..., description="Piece width (ancho, segunda medida) in mm"
    )
    quantity: PositiveInt = Field(default=1, le=10000)
    board_id: int = Field(..., description="Target board ID for this piece")
    label: Optional[str] = Field(default=None, description="Human-friendly piece label")
    can_rotate: bool = Field(
        default=True,
        description=(
            "If true, the optimizer may swap height↔width (rotate 90°) to improve "
            "yield. Set false for pieces with a fixed orientation (grain/pattern)."
        ),
    )


class OptimizeRequest(CamelModel):
    requirements: List[Requirement] = Field(
        ..., min_length=1, description="List of cuts to optimize"
    )
    client_id: Optional[int] = Field(
        default=None,
        description=(
            "Optional client ID. The optimization is client-agnostic (the result "
            "and its hash do not depend on the client); only proformas and orders "
            "require a client, resolved at that point."
        ),
    )


class Material(CamelModel):
    board_id: int = Field(..., description="Board ID this sheet was cut from")
    sheet_number: int = Field(
        ..., description="Sheet number within the board (1-based)"
    )
    height: float = Field(..., description="Height of the material (alto)")
    width: float = Field(..., description="Width of the material (ancho)")
    thickness: float = Field(..., description="Thickness of the material")
    area: float = Field(..., description="Area of the material")


class PlacedPiece(CamelModel):
    piece_id: str = Field(..., description="Unique identifier for the placed piece")
    x: float = Field(..., description="X position of the placed piece")
    y: float = Field(..., description="Y position of the placed piece")
    height: float = Field(
        ..., description="Height of the placed piece (alto, after rotation)"
    )
    width: float = Field(
        ..., description="Width of the placed piece (ancho, after rotation)"
    )
    rotated: bool = Field(..., description="Indicates if the piece is rotated")
    original_height: float = Field(
        ..., description="Piece height (alto) before rotation"
    )
    original_width: float = Field(
        ..., description="Piece width (ancho) before rotation"
    )


class Remainder(CamelModel):
    x: float = Field(..., description="X position of the remainder")
    y: float = Field(..., description="Y position of the remainder")
    height: float = Field(..., description="Height of the remainder (alto)")
    width: float = Field(..., description="Width of the remainder (ancho)")


class LayoutStatistics(CamelModel):
    used_area: float = Field(..., description="Total area occupied by placed pieces")
    waste_area: float = Field(..., description="Unused area of the sheet")
    efficiency: float = Field(..., description="Material usage efficiency (percentage)")
    pieces_count: int = Field(..., description="Number of pieces placed on the sheet")


class Layout(CamelModel):
    material: Material = Field(..., description="Material/sheet used in this layout")
    placed_pieces: List[PlacedPiece] = Field(
        ..., description="Pieces placed on this sheet"
    )
    statistics: LayoutStatistics = Field(
        ..., description="Usage metrics for this sheet"
    )
    remainders: List[Remainder] = Field(
        ..., description="Leftover rectangles on this sheet"
    )


class LayoutGroup(CamelModel):
    pattern_id: int = Field(..., description="1-based index of the unique cut pattern")
    count: int = Field(..., description="Number of sheets sharing this pattern")
    sheet_numbers: List[int] = Field(
        ..., description="Sheet numbers that use this pattern"
    )
    board_id: int = Field(..., description="Board ID the pattern is cut from")
    layout: Layout = Field(..., description="Representative layout for this pattern")


class OptimizeResponse(CamelModel):
    id: Optional[int] = Field(
        default=None,
        description="Deprecated: optimizations are no longer persisted; use the hash",
    )
    client: Optional[ClientResponse] = Field(
        default=None, description="Client information (only when a client_id is sent)"
    )
    optimization_hash: Optional[str] = Field(
        default=None, description="Deterministic hash of the optimization inputs"
    )
    total_boards_used: int = Field(..., description="Total number of boards used")
    total_boards_cost: float = Field(..., description="Total cost of boards used")
    layouts: List[Layout] = Field(
        ..., description="Per-sheet cutting layouts of the optimization"
    )
    materials_summary: Optional[List[MaterialSummary]] = Field(
        default=None, description="Aggregated materials grouped by board type"
    )
    layout_groups: Optional[List[LayoutGroup]] = Field(
        default=None, description="Cutting layouts deduplicated by identical pattern"
    )
