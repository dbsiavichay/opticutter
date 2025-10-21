from enum import Enum
from typing import List, Tuple

from src.models.guillotine import CuttingLayout, Material, Piece, PlacedPiece, Rectangle
from src.schemas.cutting import CuttingParameters


class SplitRule(Enum):
    SHORTER_LEFTOVER_AXIS = "shorter_leftover_axis"
    LONGER_LEFTOVER_AXIS = "longer_leftover_axis"
    MINIMIZE_AREA = "minimize_area"
    MAXIMIZE_AREA = "maximize_area"
    SHORTER_AXIS = "shorter_axis"
    LONGER_AXIS = "longer_axis"


class GuillotineOptimizer:
    def __init__(
        self,
        material: Material,
        cutting_params: CuttingParameters = None,
        split_rule: SplitRule = SplitRule.SHORTER_LEFTOVER_AXIS,
        min_rect_size: float = 0.1,
    ):
        self.material = material
        self.split_rule = split_rule
        self.cutting_params = cutting_params or CuttingParameters()
        self.kerf = max(0, self.cutting_params.kerf)
        self.top_trim = max(0, self.cutting_params.top_trim)
        self.bottom_trim = max(0, self.cutting_params.bottom_trim)
        self.left_trim = max(0, self.cutting_params.left_trim)
        self.right_trim = max(0, self.cutting_params.right_trim)
        self.min_rect_size = max(0.01, min_rect_size)

        total_horizontal_trim = self.left_trim + self.right_trim
        total_vertical_trim = self.top_trim + self.bottom_trim

        if total_horizontal_trim >= material.width:
            raise ValueError(
                f"Los trims horizontales ({total_horizontal_trim}) exceden el ancho del material ({material.width})"
            )
        if total_vertical_trim >= material.height:
            raise ValueError(
                f"Los trims verticales ({total_vertical_trim}) exceden la altura del material ({material.height})"
            )

        usable_width = material.width - self.left_trim - self.right_trim
        usable_height = material.height - self.top_trim - self.bottom_trim

        self.remainders: List[Rectangle] = [
            Rectangle(self.left_trim, self.bottom_trim, usable_width, usable_height)
        ]
        self.placed_pieces: List[PlacedPiece] = []

    def optimize(self, pieces: List[Piece]) -> Tuple[List[PlacedPiece], List[Piece]]:
        if not pieces:
            return [], []

        expanded_pieces = []
        for piece in pieces:
            for i in range(piece.quantity):
                piece_copy = Piece(
                    id=f"{piece.id}_{i+1}" if piece.quantity > 1 else piece.id,
                    width=piece.width,
                    height=piece.height,
                    quantity=1,
                    can_rotate=piece.can_rotate,
                    priority=piece.priority,
                )
                expanded_pieces.append(piece_copy)

        sorted_pieces = sorted(expanded_pieces, key=lambda p: (-p.priority, -p.area))

        unplaced_pieces = []

        for piece in sorted_pieces:
            placed = self._place_piece(piece)
            if not placed:
                unplaced_pieces.append(piece)

        return self.placed_pieces, unplaced_pieces

    def _place_piece(self, piece: Piece) -> bool:
        best_rect_index = -1
        best_rotated = False
        best_score = float("inf")

        for i, rect in enumerate(self.remainders):
            if rect.contains(piece.width, piece.height):
                score = rect.area - piece.area
                if score < best_score:
                    best_score = score
                    best_rect_index = i
                    best_rotated = False

            if piece.can_rotate and rect.contains(piece.height, piece.width):
                score = rect.area - piece.area
                if score < best_score:
                    best_score = score
                    best_rect_index = i
                    best_rotated = True

        if best_rect_index == -1:
            return False

        rect = self.remainders[best_rect_index]

        if best_rotated:
            placed_width = piece.height
            placed_height = piece.width
        else:
            placed_width = piece.width
            placed_height = piece.height

        placed_piece = PlacedPiece(
            piece=piece,
            x=rect.x,
            y=rect.y,
            width=placed_width,
            height=placed_height,
            rotated=best_rotated,
        )
        self.placed_pieces.append(placed_piece)

        self._split_free_rectangle(best_rect_index, placed_piece)

        return True

    def _split_free_rectangle(self, rect_index: int, placed: PlacedPiece):
        rect = self.remainders[rect_index]

        self.remainders.pop(rect_index)

        width_leftover = rect.width - placed.width
        height_leftover = rect.height - placed.height

        effective_width = placed.width + (self.kerf if width_leftover > 0 else 0)
        effective_height = placed.height + (self.kerf if height_leftover > 0 else 0)

        new_rects = self._create_split_rectangles(
            rect,
            placed,
            effective_width,
            effective_height,
            width_leftover,
            height_leftover,
        )

        new_rects = [
            r
            for r in new_rects
            if r.width >= self.min_rect_size and r.height >= self.min_rect_size
        ]

        self.remainders.extend(new_rects)

        self.remainders.sort(key=lambda r: r.area)

    def _create_split_rectangles(
        self,
        rect: Rectangle,
        placed: PlacedPiece,
        effective_width: float,
        effective_height: float,
        width_leftover: float,
        height_leftover: float,
    ) -> List[Rectangle]:
        new_rects = []

        if self.split_rule == SplitRule.SHORTER_LEFTOVER_AXIS:
            if width_leftover <= height_leftover:
                new_rects = self._vertical_split_first(
                    rect,
                    effective_width,
                    effective_height,
                    width_leftover,
                    height_leftover,
                )
            else:
                new_rects = self._horizontal_split_first(
                    rect,
                    placed,
                    effective_width,
                    effective_height,
                    width_leftover,
                    height_leftover,
                )

        elif self.split_rule == SplitRule.LONGER_LEFTOVER_AXIS:
            if width_leftover >= height_leftover:
                new_rects = self._vertical_split_first(
                    rect,
                    effective_width,
                    effective_height,
                    width_leftover,
                    height_leftover,
                )
            else:
                new_rects = self._horizontal_split_first(
                    rect,
                    placed,
                    effective_width,
                    effective_height,
                    width_leftover,
                    height_leftover,
                )

        elif self.split_rule == SplitRule.SHORTER_AXIS:
            if rect.width <= rect.height:
                new_rects = self._vertical_split_first(
                    rect,
                    effective_width,
                    effective_height,
                    width_leftover,
                    height_leftover,
                )
            else:
                new_rects = self._horizontal_split_first(
                    rect,
                    placed,
                    effective_width,
                    effective_height,
                    width_leftover,
                    height_leftover,
                )

        elif self.split_rule == SplitRule.LONGER_AXIS:
            if rect.width >= rect.height:
                new_rects = self._vertical_split_first(
                    rect,
                    effective_width,
                    effective_height,
                    width_leftover,
                    height_leftover,
                )
            else:
                new_rects = self._horizontal_split_first(
                    rect,
                    placed,
                    effective_width,
                    effective_height,
                    width_leftover,
                    height_leftover,
                )

        elif self.split_rule == SplitRule.MINIMIZE_AREA:
            vertical_rects = self._vertical_split_first(
                rect, effective_width, effective_height, width_leftover, height_leftover
            )
            horizontal_rects = self._horizontal_split_first(
                rect,
                placed,
                effective_width,
                effective_height,
                width_leftover,
                height_leftover,
            )

            max_vertical = max((r.area for r in vertical_rects), default=0)
            max_horizontal = max((r.area for r in horizontal_rects), default=0)

            new_rects = (
                vertical_rects if max_vertical <= max_horizontal else horizontal_rects
            )

        elif self.split_rule == SplitRule.MAXIMIZE_AREA:
            vertical_rects = self._vertical_split_first(
                rect, effective_width, effective_height, width_leftover, height_leftover
            )
            horizontal_rects = self._horizontal_split_first(
                rect,
                placed,
                effective_width,
                effective_height,
                width_leftover,
                height_leftover,
            )

            max_vertical = max((r.area for r in vertical_rects), default=0)
            max_horizontal = max((r.area for r in horizontal_rects), default=0)

            new_rects = (
                vertical_rects if max_vertical >= max_horizontal else horizontal_rects
            )

        else:
            if width_leftover <= height_leftover:
                new_rects = self._vertical_split_first(
                    rect,
                    effective_width,
                    effective_height,
                    width_leftover,
                    height_leftover,
                )
            else:
                new_rects = self._horizontal_split_first(
                    rect,
                    placed,
                    effective_width,
                    effective_height,
                    width_leftover,
                    height_leftover,
                )

        return new_rects

    def _vertical_split_first(
        self,
        rect: Rectangle,
        effective_width: float,
        effective_height: float,
        width_leftover: float,
        height_leftover: float,
    ) -> List[Rectangle]:
        new_rects = []

        if width_leftover > 0:
            new_rects.append(
                Rectangle(
                    rect.x + effective_width,
                    rect.y,
                    rect.width - effective_width,
                    effective_height - self.kerf
                    if height_leftover > 0
                    else effective_height,
                )
            )

        if height_leftover > 0:
            new_rects.append(
                Rectangle(
                    rect.x,
                    rect.y + effective_height,
                    rect.width,
                    rect.height - effective_height,
                )
            )

        return new_rects

    def _horizontal_split_first(
        self,
        rect: Rectangle,
        placed: PlacedPiece,
        effective_width: float,
        effective_height: float,
        width_leftover: float,
        height_leftover: float,
    ) -> List[Rectangle]:
        new_rects = []

        if height_leftover > 0:
            new_rects.append(
                Rectangle(
                    rect.x,
                    rect.y + effective_height,
                    effective_width - self.kerf
                    if width_leftover > 0
                    else effective_width,
                    rect.height - effective_height,
                )
            )

        if width_leftover > 0:
            new_rects.append(
                Rectangle(
                    rect.x + effective_width,
                    rect.y,
                    rect.width - effective_width,
                    rect.height,
                )
            )

        return new_rects


class MultiSheetGuillotineOptimizer:
    def __init__(
        self,
        material_template: Material,
        cutting_params: CuttingParameters = None,
        split_rule: SplitRule = SplitRule.SHORTER_LEFTOVER_AXIS,
        max_sheets: int = 100,
        min_rect_size: float = 0.1,
    ):
        self.material_template = material_template
        self.split_rule = split_rule
        self.cutting_params = cutting_params or CuttingParameters()
        self.max_sheets = max_sheets
        self.min_rect_size = min_rect_size

        self.layouts: List[CuttingLayout] = []

    def optimize(self, pieces: List[Piece]) -> Tuple[List[CuttingLayout], List[Piece]]:
        if not pieces:
            return [], []

        expanded_pieces = []
        for piece in pieces:
            for i in range(piece.quantity):
                piece_copy = Piece(
                    id=f"{piece.id}_{i+1}" if piece.quantity > 1 else piece.id,
                    width=piece.width,
                    height=piece.height,
                    quantity=1,
                    can_rotate=piece.can_rotate,
                    priority=piece.priority,
                )
                expanded_pieces.append(piece_copy)

        remaining_pieces = sorted(expanded_pieces, key=lambda p: (-p.priority, -p.area))

        sheet_count = 0

        while remaining_pieces and sheet_count < self.max_sheets:
            sheet_count += 1

            material = Material(
                id=f"{self.material_template.id}_{sheet_count}",
                width=self.material_template.width,
                height=self.material_template.height,
                thickness=self.material_template.thickness,
                cost_per_unit=self.material_template.cost_per_unit,
            )

            try:
                optimizer = GuillotineOptimizer(
                    material=material,
                    split_rule=self.split_rule,
                    cutting_params=self.cutting_params,
                    min_rect_size=self.min_rect_size,
                )
            except ValueError as e:
                print(f"Error al crear optimizador: {e}")
                break

            placed, unplaced = optimizer.optimize(remaining_pieces)

            if placed:
                layout = CuttingLayout(
                    material=material,
                    placed_pieces=placed,
                    remainders=optimizer.remainders,
                )
                self.layouts.append(layout)
                remaining_pieces = unplaced
            else:
                break

        return self.layouts, remaining_pieces
