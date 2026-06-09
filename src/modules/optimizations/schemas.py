from enum import Enum
from typing import Annotated, List, Literal, Optional, Union

from pydantic import (
    Field,
    NonNegativeInt,
    PositiveInt,
    confloat,
    field_validator,
    model_validator,
)

from src.modules.clients.schemas import ClientResponse
from src.shared.schemas import CamelModel


class MaterialSource(str, Enum):
    """Origen del material a optimizar.

    El motor de corte es agnóstico al origen: solo necesita dimensiones y costo.
    ``catalog`` resuelve un tablero del catálogo de productos; el resto aporta sus
    dimensiones inline. Una fuente nueva = un valor más + su rama en la unión.
    """

    catalog = "catalog"
    company_offcut = "companyOffcut"
    client_offcut = "clientOffcut"
    manual = "manual"


class MaterialSummary(CamelModel):
    material_key: str
    source: MaterialSource
    product_id: Optional[int] = None
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    height: float
    width: float
    thickness: float
    count: int
    total_area_m2: float
    avg_efficiency: float
    cost_per_unit: float
    total_cost: float


class EdgeSide(str, Enum):
    """Lados nominales de una pieza (marco sin rotar).

    ``top``/``bottom`` son los lados de longitud ``width`` (ancho); ``left``/
    ``right`` los de longitud ``height`` (alto).
    """

    top = "top"
    bottom = "bottom"
    left = "left"
    right = "right"


class EdgeBandingSpec(CamelModel):
    """Tapacanto a aplicar en una pieza: un producto y los lados a tapar."""

    product_id: int = Field(
        ..., description="Edge banding product ID (type=edge_banding)"
    )
    sides: List[EdgeSide] = Field(
        ...,
        min_length=1,
        description="Nominal sides to band (top/bottom=ancho, left/right=alto)",
    )

    @field_validator("sides")
    @classmethod
    def _unique_sides(cls, sides: List[EdgeSide]) -> List[EdgeSide]:
        if len(set(sides)) != len(sides):
            raise ValueError("sides must not contain duplicates")
        return sides


class EdgeBandingSummary(CamelModel):
    product_id: int
    product_code: str
    product_name: str
    thickness: float
    color: Optional[str] = None
    net_linear_m: float = Field(
        ..., description="Net linear meters (sum of banded sides)"
    )
    linear_m: float = Field(..., description="Linear meters including waste factor")
    billed_linear_m: int = Field(..., description="Whole meters charged (rounded up)")
    price_per_m: float = Field(..., description="Frozen price per linear meter")
    total_cost: float


class CatalogMaterialInput(CamelModel):
    """Material del catálogo de productos (tablero)."""

    key: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Stable key referenced by requirements via materialKey",
    )
    source: Literal[MaterialSource.catalog]
    product_id: int = Field(..., description="Board product ID (type=board)")


class InlineMaterialInput(CamelModel):
    """Material con dimensiones inline: retazo de empresa/cliente o medida manual.

    Comparten forma; solo difieren en ``source``. ``quantity`` se acepta pero no se
    enforca todavía (suministro infinito en Fase 1).
    """

    key: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Stable key referenced by requirements via materialKey",
    )
    source: Literal[
        MaterialSource.company_offcut,
        MaterialSource.client_offcut,
        MaterialSource.manual,
    ]
    height: PositiveInt = Field(..., description="Material height (alto) in mm")
    width: PositiveInt = Field(..., description="Material width (ancho) in mm")
    thickness: PositiveInt = Field(..., description="Material thickness in mm")
    cost_per_unit: confloat(ge=0) = Field(
        default=0.0, description="Unit cost of the material (0 if unknown)"
    )
    label: Optional[str] = Field(
        default=None, max_length=128, description="Human-friendly material label"
    )
    quantity: Optional[PositiveInt] = Field(
        default=None, description="Available units (not enforced in phase 1)"
    )


# Unión discriminada por ``source`` (mismo patrón que ``products/schemas.py``):
# Pydantic v2 elige y valida la rama según el ``source`` enviado. Una fuente nueva
# = un valor en ``MaterialSource`` + su rama aquí (o reusar la rama inline).
MaterialInput = Annotated[
    Union[CatalogMaterialInput, InlineMaterialInput],
    Field(discriminator="source"),
]


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
    material_key: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Key of the material (from `materials`) to cut this piece from",
    )
    label: Optional[str] = Field(default=None, description="Human-friendly piece label")
    can_rotate: bool = Field(
        default=True,
        description=(
            "If true, the optimizer may swap height↔width (rotate 90°) to improve "
            "yield. Set false for pieces with a fixed orientation (grain/pattern). "
            "Edge banding is remapped to the rotated sides, so it does not block "
            "rotation."
        ),
    )
    edge_banding: Optional[EdgeBandingSpec] = Field(
        default=None, description="Optional edge banding for this piece"
    )


class OptimizeRequest(CamelModel):
    materials: List[MaterialInput] = Field(
        ...,
        min_length=1,
        description="Available materials (stock): catalog boards, offcuts or manual",
    )
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

    @model_validator(mode="after")
    def _validate_material_refs(self) -> "OptimizeRequest":
        """Las keys de materiales son únicas y cada requerimiento referencia una."""
        keys = [m.key for m in self.materials]
        if len(set(keys)) != len(keys):
            raise ValueError("material keys must be unique")
        keyset = set(keys)
        for req in self.requirements:
            if req.material_key not in keyset:
                raise ValueError(
                    f"requirement references unknown materialKey '{req.material_key}'"
                )
        return self


class Material(CamelModel):
    material_key: str = Field(
        ..., description="Key of the material (from `materials`) this sheet came from"
    )
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
    edges: Optional[dict] = Field(
        default=None,
        description="Edge banding on the geometric sides of the placed piece",
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
    cut_linear_m: float = Field(
        default=0.0, description="Linear meters of cut (saw travel) for this sheet"
    )
    edge_banding_linear_m: float = Field(
        default=0.0,
        description="Net linear meters of edge banding on this sheet (informational)",
    )


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
    material_key: str = Field(
        ..., description="Key of the material the pattern is cut from"
    )
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
    total_edge_banding_cost: float = Field(
        default=0.0, description="Total cost of edge banding used"
    )
    total_cut_linear_m: float = Field(
        default=0.0, description="Total linear meters of cut across all sheets"
    )
    total_edge_banding_linear_m: float = Field(
        default=0.0,
        description="Total net linear meters of edge banding across all sheets",
    )
    layouts: List[Layout] = Field(
        ..., description="Per-sheet cutting layouts of the optimization"
    )
    materials_summary: Optional[List[MaterialSummary]] = Field(
        default=None, description="Aggregated materials grouped by board type"
    )
    edge_bandings_summary: Optional[List[EdgeBandingSummary]] = Field(
        default=None, description="Aggregated edge banding grouped by type"
    )
    layout_groups: Optional[List[LayoutGroup]] = Field(
        default=None, description="Cutting layouts deduplicated by identical pattern"
    )
