import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from config import config
from src.models.models import (
    OptimizationBoardModel,
    OptimizationCutModel,
    OptimizationLayoutModel,
    OptimizationModel,
    OptmizationLayoutCutModel,
)
from src.models.schemas import OptimizeRequest
from src.schemas import (
    BoardLayout,
    CostSummary,
    CuttingParameters,
    MaterialCostSummary,
    OptimizationSummary,
    OptimizeResponse,
    PlacedCut,
    WastePiece,
)
from src.services.board_service import BoardService


# Native Python dataclasses for internal optimization logic
@dataclass
class Board:
    """Native Python representation of a board."""

    code: str
    width: int
    length: int
    price: float


@dataclass
class Cut:
    """Native Python representation of a cut requirement."""

    board_code: str
    width: int
    length: int
    label: Optional[str] = None
    allow_rotation: bool = True


@dataclass
class CuttingParams:
    """Native Python representation of cutting parameters."""

    kerf: int = 0
    top_trim: int = 0
    bottom_trim: int = 0
    left_trim: int = 0
    right_trim: int = 0


@dataclass
class PlacedCutData:
    """Native Python representation of a placed cut."""

    x: int
    y: int
    width: int
    length: int
    label: Optional[str] = None


@dataclass
class WastePieceData:
    """Native Python representation of a waste piece."""

    x: int
    y: int
    width: int
    length: int
    reusable: bool = True


@dataclass
class BoardLayoutData:
    """Native Python representation of a board layout."""

    material: str
    index: int
    cuts_placed: List[PlacedCutData]
    utilization_percentage: float
    waste_pieces: List[WastePieceData]


@dataclass
class MaterialCostData:
    """Native Python representation of material cost summary."""

    material: str
    boards_used: int
    unit_cost: float
    total_cost: float


@dataclass
class CostData:
    """Native Python representation of cost summary."""

    materials: List[MaterialCostData]
    total_material_cost: float


@dataclass
class OptimizationData:
    """Native Python representation of optimization summary."""

    total_boards_used: int
    total_cost: float
    total_waste_percentage: float
    optimization_time: str


class Rect:
    __slots__ = ("x", "y", "width", "length")

    def __init__(self, x: int, y: int, width: int, length: int):
        self.x = x
        self.y = y
        self.width = width
        self.length = length

    def area(self) -> int:
        return max(self.width, 0) * max(self.length, 0)

    def fits(self, width: int, length: int) -> bool:
        return width <= self.width and length <= self.length

    def split_after_place(
        self, placed_width: int, placed_length: int, kerf: int
    ) -> List["Rect"]:
        """Assumes the placed rect is anchored at (self.x, self.y).
        Returns two non-overlapping guillotine rectangles: right and bottom, respecting kerf.
        """
        rects: List[Rect] = []
        # Right remainder: to the right of the placed piece, same y, length = placed_length
        right_x = self.x + placed_width + kerf
        right_width = (self.x + self.width) - right_x
        if right_width > 0 and placed_length > 0:
            rects.append(Rect(right_x, self.y, right_width, placed_length))
        # Bottom remainder: below the placed piece, full width of original free rect
        bottom_y = self.y + placed_length + kerf
        bottom_length = (self.y + self.length) - bottom_y
        if bottom_length > 0:
            rects.append(Rect(self.x, bottom_y, self.width, bottom_length))
        return rects


class BoardBin:
    def __init__(
        self,
        board: Board,
        index: int,
        kerf: int,
        trims: Tuple[int, int, int, int],
    ):
        self.board = board
        self.index = index
        left, top, right, bottom = trims
        usable_width = max(board.width - (left + right), 0)
        usable_length = max(board.length - (top + bottom), 0)
        self.usable_width = usable_width
        self.usable_length = usable_length
        self.origin_x = left
        self.origin_y = top
        self.free_rects: List[Rect] = [
            Rect(self.origin_x, self.origin_y, usable_width, usable_length)
        ]
        self.placed: List[PlacedCutData] = []
        self.kerf = kerf

    def try_place(
        self, width: int, length: int, label: Optional[str]
    ) -> Optional[PlacedCutData]:
        # Choose smallest area free rect that fits to reduce fragmentation
        candidate_idx = -1
        candidate: Optional[Rect] = None
        candidate_score = None
        for i, rect in enumerate(self.free_rects):
            if rect.fits(width, length):
                score = rect.area()
                if candidate is None or score < candidate_score:  # type: ignore
                    candidate = rect
                    candidate_idx = i
                    candidate_score = score
        if candidate is None:
            return None
        # Place at top-left of candidate
        px, py = candidate.x, candidate.y
        placed = PlacedCutData(x=px, y=py, width=width, length=length, label=label)
        # remove candidate and split
        del self.free_rects[candidate_idx]
        self.free_rects.extend(candidate.split_after_place(width, length, self.kerf))
        self._merge_free_rects()
        self.placed.append(placed)
        return placed

    def _merge_free_rects(self):
        # simple merge: remove contained rects
        pruned: List[Rect] = []
        for rect in self.free_rects:
            if not any(
                (rect is not other)
                and (rect.x >= other.x)
                and (rect.y >= other.y)
                and (rect.x + rect.width <= other.x + other.width)
                and (rect.y + rect.length <= other.y + other.length)
                for other in self.free_rects
            ):
                pruned.append(rect)
        self.free_rects = pruned

    def utilization(self) -> float:
        area_used = sum(p.width * p.length for p in self.placed)
        area_total = max(self.usable_width, 0) * max(self.usable_length, 0)
        return (area_used / area_total) * 100.0 if area_total > 0 else 0.0

    def waste_pieces(self) -> List[WastePieceData]:
        waste: List[WastePieceData] = []
        for rect in self.free_rects:
            if rect.width > 0 and rect.length > 0:
                waste.append(
                    WastePieceData(
                        x=rect.x,
                        y=rect.y,
                        width=rect.width,
                        length=rect.length,
                        reusable=True,
                    )
                )
        return waste


class Optimizer:
    def __init__(
        self,
        cuts: List[Cut],
        boards: List[Board],
        cutting_parameters: CuttingParams,
    ):
        self.cuts = cuts
        self.kerf = cutting_parameters.kerf
        self.trims = (
            cutting_parameters.left_trim,
            cutting_parameters.top_trim,
            cutting_parameters.right_trim,
            cutting_parameters.bottom_trim,
        )
        self.materials = {b.code: b for b in boards}

    def run(self) -> Tuple[List[BoardLayoutData], CostData, OptimizationData]:
        start = datetime.now(timezone.utc)
        # Expand cuts - cuts now come as individual items
        items: List[
            Tuple[str, int, int, str, bool]
        ] = []  # (board_code, width, length, label, allow_rotation)
        for cut in self.cuts:
            items.append(
                (
                    cut.board_code,
                    cut.width,
                    cut.length,
                    cut.label or "",
                    cut.allow_rotation,
                )
            )
        # sort by material then by decreasing max(width,length) then area
        items.sort(key=lambda t: (t[0], -max(t[1], t[2]), -(t[1] * t[2])))

        boards_by_material: dict[str, List[BoardBin]] = {
            code: [] for code in self.materials.keys()
        }

        for mat_code, width, length, label, allow_rotate in items:
            mat = self.materials[mat_code]
            placed = None
            # Orientation candidates
            candidates: List[Tuple[int, int]] = [(width, length)]
            if allow_rotate and (width != length):
                candidates.append((length, width))
            # Try place on existing boards first, preferring reuse of waste
            for board_width, board_length in candidates:
                for bin in boards_by_material[mat_code]:
                    placed = bin.try_place(board_width, board_length, label)
                    if placed:
                        break
                if placed:
                    break
            # If not placed, open a new board and try again
            if not placed:
                bin = BoardBin(
                    mat,
                    index=len(boards_by_material[mat_code]) + 1,
                    kerf=self.kerf,
                    trims=self.trims,
                )
                boards_by_material[mat_code].append(bin)
                for board_width, board_length in candidates:
                    placed = bin.try_place(board_width, board_length, label)
                    if placed:
                        break
            if not placed:
                raise ValueError(
                    f"Unable to place cut {label or ''} {width}x{length} on material {mat_code}"
                )

        # Build layouts and costs
        layout_list: List[BoardLayoutData] = []
        total_boards_used = 0
        material_costs: List[MaterialCostData] = []
        total_cost = 0.0
        total_usable_area = 0
        total_used_area = 0

        for mat_code, bins in boards_by_material.items():
            if not bins:
                continue
            mat = self.materials[mat_code]
            for i, bin in enumerate(bins):
                used_area = sum(p.width * p.length for p in bin.placed)
                board_usable_area = bin.usable_width * bin.usable_length
                total_usable_area += board_usable_area
                total_used_area += used_area
                layout_list.append(
                    BoardLayoutData(
                        material=mat_code,
                        index=i + 1,
                        cuts_placed=bin.placed,
                        utilization_percentage=bin.utilization(),
                        waste_pieces=bin.waste_pieces(),
                    )
                )
            count = len(bins)
            total_boards_used += count
            cost = count * float(mat.price)
            total_cost += cost
            material_costs.append(
                MaterialCostData(
                    material=mat_code,
                    boards_used=count,
                    unit_cost=float(mat.price),
                    total_cost=cost,
                )
            )

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        summary = OptimizationData(
            total_boards_used=total_boards_used,
            total_cost=total_cost,
            total_waste_percentage=(1.0 - (total_used_area / max(total_usable_area, 1)))
            * 100.0,
            optimization_time=f"{elapsed:.3f}s",
        )
        cost_summary = CostData(
            materials=material_costs, total_material_cost=total_cost
        )
        return layout_list, cost_summary, summary


async def optimize_cuts(request: OptimizeRequest, db: Session) -> OptimizeResponse:
    start_time = time.time()
    board_codes = {request_cut.board_code for request_cut in request.cuts}
    boards = BoardService.get_boards_by_codes(db, tuple(board_codes))
    if len(boards) != len(board_codes):
        missing = board_codes - {board.code for board in boards}
        raise ValueError(f"Board codes not found: {', '.join(missing)}")

    for cut in request.cuts:
        board = next((board for board in boards if board.code == cut.board_code), None)
        if cut.length > board.length or cut.width > board.width:
            raise ValueError(
                f"Cut {cut.label or ''} {cut.length}x{cut.width} exceeds board {board.code} size {board.length}x{board.width}"
            )

    # Convert Pydantic CuttingParameters to native CuttingParams
    cutting_params_pydantic = CuttingParameters(
        kerf=getattr(config, "KERF", 5.0),
        top_trim=getattr(config, "TOP_TRIM", 0.0),
        bottom_trim=getattr(config, "BOTTOM_TRIM", 0.0),
        left_trim=getattr(config, "LEFT_TRIM", 0.0),
        right_trim=getattr(config, "RIGHT_TRIM", 0.0),
    )

    cutting_params = CuttingParams(
        kerf=cutting_params_pydantic.kerf,
        top_trim=cutting_params_pydantic.top_trim,
        bottom_trim=cutting_params_pydantic.bottom_trim,
        left_trim=cutting_params_pydantic.left_trim,
        right_trim=cutting_params_pydantic.right_trim,
    )

    # Convert BoardModel to Board dataclass
    boards_native = [
        Board(
            code=board.code,
            width=board.width,
            length=board.length,
            price=board.price,
        )
        for board in boards
    ]

    # Convert CutRequirement to Cut dataclass (expand by quantity)
    cuts_native = []
    for cut_req in request.cuts:
        for _ in range(cut_req.quantity):
            cuts_native.append(
                Cut(
                    board_code=cut_req.board_code,
                    width=cut_req.width,
                    length=cut_req.length,
                    label=cut_req.label,
                    allow_rotation=cut_req.allow_rotation,
                )
            )

    # Compute optimization
    optimizer = Optimizer(cuts_native, boards_native, cutting_params)
    boards_layout_data, cost_data, optimization_data = optimizer.run()
    duration_ms = int((time.time() - start_time) * 1000)

    # Convert native dataclasses back to Pydantic models for database storage
    boards_layout = [
        BoardLayout(
            material=layout.material,
            index=layout.index,
            cuts_placed=[
                PlacedCut(
                    x=cut.x,
                    y=cut.y,
                    width=cut.width,
                    length=cut.length,
                    label=cut.label,
                )
                for cut in layout.cuts_placed
            ],
            utilization_percentage=layout.utilization_percentage,
            waste_pieces=[
                WastePiece(
                    x=waste.x,
                    y=waste.y,
                    width=waste.width,
                    length=waste.length,
                    reusable=waste.reusable,
                )
                for waste in layout.waste_pieces
            ],
        )
        for layout in boards_layout_data
    ]

    cost_summary = CostSummary(
        materials=[
            MaterialCostSummary(
                material=mat.material,
                boards_used=mat.boards_used,
                unit_cost=mat.unit_cost,
                total_cost=mat.total_cost,
            )
            for mat in cost_data.materials
        ],
        total_material_cost=cost_data.total_material_cost,
    )

    summary = OptimizationSummary(
        total_boards_used=optimization_data.total_boards_used,
        total_cost=optimization_data.total_cost,
        total_waste_percentage=optimization_data.total_waste_percentage,
        optimization_time=optimization_data.optimization_time,
    )

    # Save to database
    optimization = OptimizationModel(
        total_boards_used=summary.total_boards_used,
        total_boards_cost=summary.total_cost,
        total_waste_percentage=summary.total_waste_percentage,
        duration_ms=duration_ms,
        client_id=request.client_id,
    )
    db.add(optimization)
    db.flush()  # Get the ID

    # Save cuts
    for cut_req in request.cuts:
        board = next(board for board in boards if board.code == cut_req.board_code)
        cut_model = OptimizationCutModel(
            index=cut_req.index,
            length=cut_req.length,
            width=cut_req.width,
            quantity=cut_req.quantity,
            label=cut_req.label,
            allow_rotation=cut_req.allow_rotation,
            board_id=board.id,
            optimization_id=optimization.id,
        )
        db.add(cut_model)

    # Save layouts
    for layout in boards_layout:
        board = next(board for board in boards if board.code == layout.material)
        layout_model = OptimizationLayoutModel(
            index=layout.index,
            quantity=1,  # Assuming 1 for now
            utilization_percentage=layout.utilization_percentage,
            board_id=board.id,
            optimization_id=optimization.id,
        )
        db.add(layout_model)
        db.flush()  # Get layout ID

        # Save layout cuts
        for cut in layout.cuts_placed:
            cut_model = OptmizationLayoutCutModel(
                x=cut.x,
                y=cut.y,
                length=cut.length,
                width=cut.width,
                label=cut.label,
                type="cut",
                optimization_layout_id=layout_model.id,
            )
            db.add(cut_model)

        # Save waste pieces
        for waste in layout.waste_pieces:
            waste_model = OptmizationLayoutCutModel(
                x=waste.x,
                y=waste.y,
                length=waste.length,
                width=waste.width,
                type="waste",
                optimization_layout_id=layout_model.id,
            )
            db.add(waste_model)

    # Save boards used
    for material_cost in cost_summary.materials:
        board = next(board for board in boards if board.code == material_cost.material)
        board_model = OptimizationBoardModel(
            used=material_cost.boards_used,
            unit_cost=material_cost.unit_cost,
            total_cost=material_cost.total_cost,
            board_id=board.id,
            optimization_id=optimization.id,
        )
        db.add(board_model)

    db.commit()

    return OptimizeResponse(
        id=optimization.id,
        client=optimization.client,
        totalBoardsUsed=summary.total_boards_used,
        totalBoardsCost=summary.total_cost,
        totalWastePercentage=summary.total_waste_percentage,
        durationMs=duration_ms,
    )
