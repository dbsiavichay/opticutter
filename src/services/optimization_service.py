from collections import defaultdict
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from config import config
from src.schemas.cutting import CuttingParameters
from src.services.board_service import BoardService

from .guillotine import (
    CuttingLayout,
    Material,
    MultiSheetGuillotineOptimizer,
    Piece,
    SplitRule,
)


class OptimizationService:
    @staticmethod
    def _get_pieces_by_material(pieces: List[Dict]) -> Dict[str, List[Dict]]:
        pieces_by_material = defaultdict(list)
        for piece in pieces:
            pieces_by_material[piece["material_id"]].append(piece)
        return pieces_by_material

    @staticmethod
    def _optimize(
        pieces: List[Dict],
        material_id: str,
        material_width: float,
        material_height: float,
        material_thickness: float,
        cutting_params: CuttingParameters,
        cost_per_unit: float = 0.0,
        max_sheets: int = 100,
        min_rect_size: float = 0.1,
    ) -> Tuple[List[CuttingLayout], List[Piece]]:
        if not pieces:
            raise ValueError("La lista de piezas no puede estar vacía")

        material = Material(
            id=material_id,
            width=material_width,
            height=material_height,
            thickness=material_thickness,
            cost_per_unit=cost_per_unit,
        )
        piece_objects = []
        for i, p in enumerate(pieces):
            try:
                piece = Piece(
                    id=p.get("id", f"piece_{i+1}"),
                    width=p["width"],
                    height=p["height"],
                    quantity=p.get("quantity", 1),
                    can_rotate=p.get("can_rotate", True),
                    priority=p.get("priority", 0),
                )
                piece_objects.append(piece)
            except KeyError as e:
                raise ValueError(f"Pieza {i} falta el campo requerido: {e}")
            except ValueError as e:
                raise ValueError(f"Pieza {i} tiene valores inválidos: {e}")

        optimizer = MultiSheetGuillotineOptimizer(
            material_template=material,
            cutting_params=cutting_params,
            split_rule=SplitRule.SHORTER_LEFTOVER_AXIS,
            max_sheets=max_sheets,
            min_rect_size=min_rect_size,
        )
        return optimizer.optimize(piece_objects)

    @staticmethod
    def _build_response(results: List[Tuple[List[CuttingLayout], List[Piece]]]) -> Dict:
        return {
            "solution": {
                "total_boards_used": sum(len(layouts) for layouts, _ in results),
                "layouts": [
                    layout.to_dict() for layouts, _ in results for layout in layouts
                ],
            }
        }

    @staticmethod
    def execute(
        db: Session,
        pieces: List[Dict],
        max_sheets: int = 100,
        min_rect_size: float = 0.1,
    ) -> Dict:
        if not pieces:
            raise ValueError("La lista de piezas no puede estar vacía")

        pieces_by_material = OptimizationService._get_pieces_by_material(pieces)

        cutting_params = CuttingParameters(
            kerf=getattr(config, "KERF", 5.0),
            top_trim=getattr(config, "TOP_TRIM", 0.0),
            bottom_trim=getattr(config, "BOTTOM_TRIM", 0.0),
            left_trim=getattr(config, "LEFT_TRIM", 0.0),
            right_trim=getattr(config, "RIGHT_TRIM", 0.0),
        )
        results = []
        for material_id, material_pieces in pieces_by_material.items():
            board = BoardService.get_board_by_code(db, material_id)
            optimized_result = OptimizationService._optimize(
                pieces=material_pieces,
                material_id=material_id,
                material_width=board.width,
                material_height=board.length,
                material_thickness=board.thickness,
                cutting_params=cutting_params,
                cost_per_unit=board.price,
                max_sheets=max_sheets,
                min_rect_size=min_rect_size,
            )
            results.append(optimized_result)

        return OptimizationService._build_response(results)
