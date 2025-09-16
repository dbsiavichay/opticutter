from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from config import config
from src.models.models import BoardModel
from src.models.schemas import (
    BoardLayout,
    CostSummary,
    CutRequirement,
    MaterialCostSummary,
    OptimizationSummary,
    OptimizeRequest,
    OptimizeResponse,
    PlacedCut,
    WastePiece,
)
from src.schemas import CuttingParameters
from src.services.board_service import BoardService


class Rect:
    __slots__ = ("x", "y", "w", "l")

    def __init__(self, x: int, y: int, w: int, l: int):
        self.x = x
        self.y = y
        self.w = w
        self.l = l

    def area(self) -> int:
        return max(self.w, 0) * max(self.l, 0)

    def fits(self, w: int, l: int) -> bool:
        return w <= self.w and l <= self.l

    def split_after_place(self, pw: int, pl: int, kerf: int) -> List["Rect"]:
        """Assumes the placed rect is anchored at (self.x, self.y).
        Returns two non-overlapping guillotine rectangles: right and bottom, respecting kerf.
        """
        rects: List[Rect] = []
        # Right remainder: to the right of the placed piece, same y, length = pl
        right_x = self.x + pw + kerf
        right_w = (self.x + self.w) - right_x
        if right_w > 0 and pl > 0:
            rects.append(Rect(right_x, self.y, right_w, pl))
        # Bottom remainder: below the placed piece, full width of original free rect
        bottom_y = self.y + pl + kerf
        bottom_l = (self.y + self.l) - bottom_y
        if bottom_l > 0:
            rects.append(Rect(self.x, bottom_y, self.w, bottom_l))
        return rects


class BoardBin:
    def __init__(
        self,
        board: BoardModel,
        index: int,
        kerf: int,
        trims: Tuple[int, int, int, int],
    ):
        self.board = board
        self.index = index
        left, top, right, bottom = trims
        usable_w = max(board.width - (left + right), 0)
        usable_l = max(board.length - (top + bottom), 0)
        self.usable_w = usable_w
        self.usable_l = usable_l
        self.origin_x = left
        self.origin_y = top
        self.free_rects: List[Rect] = [
            Rect(self.origin_x, self.origin_y, usable_w, usable_l)
        ]
        self.placed: List[PlacedCut] = []
        self.kerf = kerf

    def try_place(self, w: int, l: int, label: Optional[str]) -> Optional[PlacedCut]:
        # Choose smallest area free rect that fits to reduce fragmentation
        candidate_idx = -1
        candidate: Optional[Rect] = None
        candidate_score = None
        for i, r in enumerate(self.free_rects):
            if r.fits(w, l):
                score = r.area()
                if candidate is None or score < candidate_score:  # type: ignore
                    candidate = r
                    candidate_idx = i
                    candidate_score = score
        if candidate is None:
            return None
        # Place at top-left of candidate
        px, py = candidate.x, candidate.y
        placed = PlacedCut(x=px, y=py, width=w, length=l, label=label)
        # remove candidate and split
        del self.free_rects[candidate_idx]
        self.free_rects.extend(candidate.split_after_place(w, l, self.kerf))
        self._merge_free_rects()
        self.placed.append(placed)
        return placed

    def _merge_free_rects(self):
        # simple merge: remove contained rects
        pruned: List[Rect] = []
        for r in self.free_rects:
            if not any(
                (r is not o)
                and (r.x >= o.x)
                and (r.y >= o.y)
                and (r.x + r.w <= o.x + o.w)
                and (r.y + r.l <= o.y + o.l)
                for o in self.free_rects
            ):
                pruned.append(r)
        self.free_rects = pruned

    def utilization(self) -> float:
        area_used = sum(p.width * p.length for p in self.placed)
        area_total = max(self.usable_w, 0) * max(self.usable_l, 0)
        return (area_used / area_total) * 100.0 if area_total > 0 else 0.0

    def waste_pieces(self) -> List[WastePiece]:
        waste: List[WastePiece] = []
        for r in self.free_rects:
            if r.w > 0 and r.l > 0:
                waste.append(
                    WastePiece(x=r.x, y=r.y, width=r.w, length=r.l, reusable=True)
                )
        return waste


class Optimizer:
    def __init__(
        self,
        cuts: List[CutRequirement],
        boards: List[BoardModel],
        cutting_parameters: CuttingParameters,
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

    def run(self) -> Tuple[List[BoardLayout], CostSummary, OptimizationSummary]:
        start = datetime.now(timezone.utc)
        # Expand cuts by quantity
        items: List[
            Tuple[str, int, int, str, bool]
        ] = []  # (board_code, w, l, label, allow_rotation)
        for c in self.cuts:
            for _ in range(c.quantity):
                items.append(
                    (
                        c.board_code,
                        c.width,
                        c.length,
                        c.label,
                        c.allow_rotation,
                    )
                )
        # sort by material then by decreasing max(w,l) then area
        items.sort(key=lambda t: (t[0], -max(t[1], t[2]), -(t[1] * t[2])))

        # boards_layout: List[BoardLayout] = []
        boards_by_material: dict[str, List[BoardBin]] = {
            code: [] for code in self.materials.keys()
        }

        for mat_code, w, l, label, allow_rotate in items:
            mat = self.materials[mat_code]
            placed = None
            # Orientation candidates
            candidates: List[Tuple[int, int]] = [(w, l)]
            if allow_rotate and (w != l):
                candidates.append((l, w))
            # Try place on existing boards first, preferring reuse of waste
            for bw, bl in candidates:
                for bin in boards_by_material[mat_code]:
                    placed = bin.try_place(bw, bl, label)
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
                for bw, bl in candidates:
                    placed = bin.try_place(bw, bl, label)
                    if placed:
                        break
            if not placed:
                raise ValueError(
                    f"Unable to place cut {label or ''} {w}x{l} on material {mat_code}"
                )

        # Build layouts and costs
        layout_list: List[BoardLayout] = []
        total_boards_used = 0
        material_costs: List[MaterialCostSummary] = []
        total_cost = 0.0
        total_usable_area = 0
        total_used_area = 0

        for mat_code, bins in boards_by_material.items():
            if not bins:
                continue
            mat = self.materials[mat_code]
            for i, bin in enumerate(bins):
                used_area = sum(p.width * p.length for p in bin.placed)
                board_usable_area = bin.usable_w * bin.usable_l
                total_usable_area += board_usable_area
                total_used_area += used_area
                layout_list.append(
                    BoardLayout(
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
                MaterialCostSummary(
                    material=mat_code,
                    boards_used=count,
                    unit_cost=float(mat.price),
                    total_cost=cost,
                )
            )

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        summary = OptimizationSummary(
            total_boards_used=total_boards_used,
            total_cost=total_cost,
            total_waste_percentage=(1.0 - (total_used_area / max(total_usable_area, 1)))
            * 100.0,
            optimization_time=f"{elapsed:.3f}s",
        )
        cost_summary = CostSummary(
            materials=material_costs, total_material_cost=total_cost
        )
        return layout_list, cost_summary, summary


async def optimize_cuts(request: OptimizeRequest, db: Session) -> OptimizeResponse:
    board_codes = {r.board_code for r in request.cuts}
    boards = BoardService.get_boards_by_codes(db, tuple(board_codes))
    if len(boards) != len(board_codes):
        missing = board_codes - {b.code for b in boards}
        raise ValueError(f"Board codes not found: {', '.join(missing)}")

    for cut in request.cuts:
        board = next((b for b in boards if b.code == cut.board_code), None)
        if cut.length > board.length or cut.width > board.width:
            raise ValueError(
                f"Cut {cut.label or ''} {cut.length}x{cut.width} exceeds board {board.code} size {board.length}x{board.width}"
            )

    cutting_params = CuttingParameters(
        kerf=getattr(config, "KERF", 5.0),
        top_trim=getattr(config, "TOP_TRIM", 0.0),
        bottom_trim=getattr(config, "BOTTOM_TRIM", 0.0),
        left_trim=getattr(config, "LEFT_TRIM", 0.0),
        right_trim=getattr(config, "RIGHT_TRIM", 0.0),
    )

    # Compute
    optimizer = Optimizer(request.cuts, boards, cutting_params)
    boards_layout, cost_summary, summary = optimizer.run()
    resp = OptimizeResponse(
        optimization_summary=summary,
        cost_summary=cost_summary,
        boards_layout=boards_layout,
    )
    return resp
