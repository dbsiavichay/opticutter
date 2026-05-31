from collections import defaultdict
from typing import Dict, List, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.cutting import (
    CuttingLayout,
    CuttingParameters,
    Material,
    MultiSheetGuillotineOptimizer,
    Piece,
    SplitRule,
)
from src.modules.boards.model import BoardModel
from src.modules.boards.service import BoardService
from src.modules.optimizations.model import OptimizationModel
from src.modules.optimizations.schemas import OptimizeRequest, Requirement
from src.shared.config import config
from src.shared.database import get_db
from src.shared.exceptions import EntityNotFoundError, ValidationError


class OptimizationService:
    """Orquesta el dominio de corte (``cutting``) y persiste optimizaciones."""

    def __init__(self, db: Session):
        self.db = db
        self.board_service = BoardService(db)

    def get_or_404(self, optimization_id: int) -> OptimizationModel:
        """Obtiene una optimización por ID o lanza 404."""
        optimization = self.db.get(OptimizationModel, optimization_id)
        if optimization is None:
            raise EntityNotFoundError("Optimization", optimization_id)
        return optimization

    def execute(self, request: OptimizeRequest) -> OptimizationModel:
        """Ejecuta la optimización: agrupa por tablero, corta y persiste."""
        if not request.requirements:
            raise ValidationError("La lista de piezas no puede estar vacía")

        requirements_by_board = self._group_requirements_by_board(request.requirements)

        cutting_params = CuttingParameters(
            kerf=config.KERF,
            top_trim=config.TOP_TRIM,
            bottom_trim=config.BOTTOM_TRIM,
            left_trim=config.LEFT_TRIM,
            right_trim=config.RIGHT_TRIM,
        )

        solutions = []
        board_codes: Dict[int, str] = {}
        for board_id, board_requirements in requirements_by_board.items():
            board = self.board_service.get(board_id)
            if board is None:
                raise EntityNotFoundError("Board", board_id)

            board_codes[board_id] = board.code
            solutions.append(
                self._optimize(
                    pieces=board_requirements,
                    board=board,
                    cutting_params=cutting_params,
                )
            )

        return self._save_optimization(request, solutions, board_codes)

    def _group_requirements_by_board(
        self, requirements: List[Requirement]
    ) -> Dict[int, List[Requirement]]:
        """Agrupa los requerimientos por ID de tablero."""
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
        """Optimiza el layout de corte para un tablero específico."""
        if not pieces:
            raise ValidationError("La lista de piezas no puede estar vacía")

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
                piece_objects.append(
                    Piece(
                        id=p.label or f"piece_{i+1}",
                        width=p.width,
                        height=p.height,
                        quantity=p.quantity,
                        can_rotate=p.allow_rotation,
                        priority=p.index,
                    )
                )
            except ValueError as e:
                raise ValidationError(f"Pieza {i} tiene valores inválidos: {e}")

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
        board_codes: Dict[int, str],
    ) -> OptimizationModel:
        """Guarda los resultados de la optimización en la base de datos."""
        total_boards_used = sum(len(layouts) for layouts, _ in solutions)
        total_boards_cost = sum(
            layout.material.cost_per_unit
            for layouts, _ in solutions
            for layout in layouts
        )

        optimization = OptimizationModel(
            total_boards_used=total_boards_used,
            total_boards_cost=total_boards_cost,
            requirements=[
                {**r.model_dump(), "board_code": board_codes.get(r.board_id, "N/A")}
                for r in request.requirements
            ],
            solution=[
                layout.to_dict() for layouts, _ in solutions for layout in layouts
            ],
            client_id=request.client_id,
        )
        self.db.add(optimization)
        self.db.commit()
        self.db.refresh(optimization)
        return optimization


def optimization_service(db: Session = Depends(get_db)) -> OptimizationService:
    """Provider de ``OptimizationService`` para inyección en rutas."""
    return OptimizationService(db)
