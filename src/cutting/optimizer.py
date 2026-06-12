from typing import List, Tuple

from src.cutting.enums import SplitRule
from src.cutting.models import (
    Cut,
    CuttingLayout,
    Material,
    Piece,
    PlacedPiece,
    Rectangle,
)
from src.cutting.parameters import CuttingParameters


class GuillotineOptimizer:
    """Optimizador de corte usando el algoritmo Guillotine para un solo tablero"""

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
                f"Los trims horizontales ({total_horizontal_trim}) exceden "
                f"el ancho del material ({material.width})"
            )
        if total_vertical_trim >= material.height:
            raise ValueError(
                f"Los trims verticales ({total_vertical_trim}) exceden "
                f"la altura del material ({material.height})"
            )

        usable_width = material.width - self.left_trim - self.right_trim
        usable_height = material.height - self.top_trim - self.bottom_trim

        self.remainders: List[Rectangle] = [
            Rectangle(self.left_trim, self.bottom_trim, usable_width, usable_height)
        ]
        self.placed_pieces: List[PlacedPiece] = []
        self.cuts: List[Cut] = []

    def optimize(self, pieces: List[Piece]) -> Tuple[List[PlacedPiece], List[Piece]]:
        if not pieces:
            return [], []

        expanded_pieces = []
        for piece in pieces:
            for i in range(piece.quantity):
                piece_copy = Piece(
                    # ``#`` es un separador reservado para la instancia: no colisiona
                    # con etiquetas que terminan en ``_<n>`` (ver ``base_label``).
                    id=f"{piece.id}#{i+1}" if piece.quantity > 1 else piece.id,
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

        self._split_remainder(best_rect_index, placed_piece)

        return True

    def _split_remainder(self, rect_index: int, placed: PlacedPiece):
        rect = self.remainders[rect_index]

        self.remainders.pop(rect_index)

        width_leftover = rect.width - placed.width
        height_leftover = rect.height - placed.height

        effective_width = placed.width + (self.kerf if width_leftover > 0 else 0)
        effective_height = placed.height + (self.kerf if height_leftover > 0 else 0)

        new_rects, orientation = self._create_split_rectangles(
            rect,
            placed,
            effective_width,
            effective_height,
            width_leftover,
            height_leftover,
        )

        self.cuts.extend(
            self._cuts_for(rect, placed, width_leftover, height_leftover, orientation)
        )

        new_rects = [
            r
            for r in new_rects
            if r.width >= self.min_rect_size and r.height >= self.min_rect_size
        ]

        self.remainders.extend(new_rects)

        self.remainders.sort(key=lambda r: r.area)

    def _cuts_for(
        self,
        rect: Rectangle,
        placed: PlacedPiece,
        width_leftover: float,
        height_leftover: float,
        orientation: str,
    ) -> List[Cut]:
        """Segmentos de corte que separan la pieza del rectángulo, por orientación.

        ``vertical_first`` deja el sobrante superior a ancho completo (corte
        horizontal de ``rect.width``) y el lateral derecho a la altura de la pieza
        (corte vertical de ``placed.height``). ``horizontal_first`` deja el sobrante
        derecho a alto completo (corte vertical de ``rect.height``) y el superior al
        ancho de la pieza (corte horizontal de ``placed.width``). El ``kerf`` es ancho
        de hoja (perpendicular) y no altera la longitud. Sin sobrante en un eje no hay
        corte en ese eje (ya lo separó un corte previo o el borde del tablero).
        """
        cuts: List[Cut] = []
        if orientation == "vertical_first":
            if height_leftover > 0:
                cuts.append(
                    Cut(rect.x, rect.y + placed.height, rect.width, is_horizontal=True)
                )
            if width_leftover > 0:
                cuts.append(
                    Cut(
                        rect.x + placed.width,
                        rect.y,
                        placed.height,
                        is_horizontal=False,
                    )
                )
        else:  # horizontal_first
            if width_leftover > 0:
                cuts.append(
                    Cut(
                        rect.x + placed.width,
                        rect.y,
                        rect.height,
                        is_horizontal=False,
                    )
                )
            if height_leftover > 0:
                cuts.append(
                    Cut(
                        rect.x,
                        rect.y + placed.height,
                        placed.width,
                        is_horizontal=True,
                    )
                )
        return cuts

    def _create_split_rectangles(
        self,
        rect: Rectangle,
        placed: PlacedPiece,
        effective_width: float,
        effective_height: float,
        width_leftover: float,
        height_leftover: float,
    ) -> Tuple[List[Rectangle], str]:
        """Crea los rectángulos sobrantes y devuelve la orientación de split elegida.

        La orientación (``"vertical_first"`` | ``"horizontal_first"``) la usa
        ``_cuts_for`` para derivar la longitud de los cortes con la topología real.
        """
        new_rects = []
        orientation = "vertical_first"

        if self.split_rule == SplitRule.SHORTER_LEFTOVER_AXIS:
            orientation = (
                "vertical_first"
                if width_leftover <= height_leftover
                else "horizontal_first"
            )

        elif self.split_rule == SplitRule.LONGER_LEFTOVER_AXIS:
            orientation = (
                "vertical_first"
                if width_leftover >= height_leftover
                else "horizontal_first"
            )

        elif self.split_rule == SplitRule.SHORTER_AXIS:
            orientation = (
                "vertical_first" if rect.width <= rect.height else "horizontal_first"
            )

        elif self.split_rule == SplitRule.LONGER_AXIS:
            orientation = (
                "vertical_first" if rect.width >= rect.height else "horizontal_first"
            )

        elif self.split_rule in (SplitRule.MINIMIZE_AREA, SplitRule.MAXIMIZE_AREA):
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

            if self.split_rule == SplitRule.MINIMIZE_AREA:
                use_vertical = max_vertical <= max_horizontal
            else:
                use_vertical = max_vertical >= max_horizontal

            if use_vertical:
                return vertical_rects, "vertical_first"
            return horizontal_rects, "horizontal_first"

        else:
            orientation = (
                "vertical_first"
                if width_leftover <= height_leftover
                else "horizontal_first"
            )

        if orientation == "vertical_first":
            new_rects = self._vertical_split_first(
                rect, effective_width, effective_height, width_leftover, height_leftover
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

        return new_rects, orientation

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
            remaining_width = rect.width - effective_width
            if remaining_width > 0:
                new_rects.append(
                    Rectangle(
                        rect.x + effective_width,
                        rect.y,
                        remaining_width,
                        effective_height - self.kerf
                        if height_leftover > 0
                        else effective_height,
                    )
                )

        if height_leftover > 0:
            remaining_height = rect.height - effective_height
            if remaining_height > 0:
                new_rects.append(
                    Rectangle(
                        rect.x,
                        rect.y + effective_height,
                        rect.width,
                        remaining_height,
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
            remaining_height = rect.height - effective_height
            if remaining_height > 0:
                new_rects.append(
                    Rectangle(
                        rect.x,
                        rect.y + effective_height,
                        effective_width - self.kerf
                        if width_leftover > 0
                        else effective_width,
                        remaining_height,
                    )
                )

        if width_leftover > 0:
            remaining_width = rect.width - effective_width
            if remaining_width > 0:
                new_rects.append(
                    Rectangle(
                        rect.x + effective_width,
                        rect.y,
                        remaining_width,
                        rect.height,
                    )
                )

        return new_rects


class MultiSheetGuillotineOptimizer:
    """Optimizador de corte usando el algoritmo Guillotine para múltiples tableros"""

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
                    # ``#`` es un separador reservado para la instancia: no colisiona
                    # con etiquetas que terminan en ``_<n>`` (ver ``base_label``).
                    id=f"{piece.id}#{i+1}" if piece.quantity > 1 else piece.id,
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
                id=self.material_template.id,
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
                    sheet_number=sheet_count,
                    cuts=optimizer.cuts,
                )
                self.layouts.append(layout)
                remaining_pieces = unplaced
            else:
                break

        return self.layouts, remaining_pieces
