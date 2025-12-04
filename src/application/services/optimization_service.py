from collections import defaultdict
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from src.api.v1.schemas import CuttingParameters, OptimizeRequest, Requirement
from src.application.services.board_service import BoardService
from src.core.config import config
from src.domain.models.cutting import Material, Piece
from src.domain.models.cutting.enums import SplitRule
from src.domain.models.cutting.layout import CuttingLayout
from src.domain.services.guillotine_optimizer import MultiSheetGuillotineOptimizer
from src.infrastructure.database.models import BoardModel, OptimizationModel
from src.infrastructure.database.repositories import OptimizationRepository


class OptimizationService:
    """Service class for Optimization operations"""

    def __init__(self, db: Session):
        self.db = db
        self.repository = OptimizationRepository(db)
        self.board_service = BoardService(db)

    def _group_requirements_by_board(
        self, requirements: List[Requirement]
    ) -> Dict[str, List[Requirement]]:
        """Group requirements by board ID"""
        requirements_by_board = defaultdict(list)
        for req in requirements:
            requirements_by_board[req.board_id].append(req)
        return requirements_by_board

    def _optimize(
        self,
        pieces: List[Requirement],
        board: BoardModel,
        cutting_params: CuttingParameters,
        max_sheets: int = 100,
        min_rect_size: float = 0.1,
    ) -> Tuple[List[CuttingLayout], List[Piece]]:
        """Optimize cutting layout for a specific board"""
        if not pieces:
            raise ValueError("La lista de piezas no puede estar vacía")

        material = Material(
            id=board.id,
            width=board.width,
            height=board.length,
            thickness=board.thickness,
            cost_per_unit=board.price,
        )

        piece_objects = []
        for i, p in enumerate(pieces):
            try:
                piece = Piece(
                    id=p.board_id or f"piece_{i+1}",
                    width=p.width,
                    height=p.height,
                    quantity=p.quantity,
                    can_rotate=p.allow_rotation,
                    priority=p.index,
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

    def _save_optimization(
        self,
        request: OptimizeRequest,
        solutions: List[Tuple[List[CuttingLayout], List[Piece]]],
    ) -> OptimizationModel:
        """Save optimization results to database"""
        total_boards_used = sum(len(layouts) for layouts, _ in solutions)

        optimization = OptimizationModel(
            total_boards_used=total_boards_used,
            total_boards_cost=0,
            requirements=[r.model_dump() for r in request.requirements],
            solution=[
                layout.to_dict() for layouts, _ in solutions for layout in layouts
            ],
            client_id=request.client_id,
        )
        return self.repository.create(optimization)

    def execute(self, request: OptimizeRequest) -> Dict:
        """Execute optimization request"""
        if not request.requirements:
            raise ValueError("La lista de piezas no puede estar vacía")

        requirements_by_board = self._group_requirements_by_board(request.requirements)

        cutting_params = CuttingParameters(
            kerf=getattr(config, "KERF", 5.0),
            top_trim=getattr(config, "TOP_TRIM", 0.0),
            bottom_trim=getattr(config, "BOTTOM_TRIM", 0.0),
            left_trim=getattr(config, "LEFT_TRIM", 0.0),
            right_trim=getattr(config, "RIGHT_TRIM", 0.0),
        )

        solutions = []
        for board_id, board_requirements in requirements_by_board.items():
            board = self.board_service.get_board_by_code(board_id)
            if not board:
                continue

            optimized_result = self._optimize(
                pieces=board_requirements,
                board=board,
                cutting_params=cutting_params,
                max_sheets=100,
                min_rect_size=0.1,
            )
            solutions.append(optimized_result)

        return self._save_optimization(request, solutions)
