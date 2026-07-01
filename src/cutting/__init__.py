"""Pure domain of the 2D (guillotine) cutting algorithm.

No framework dependencies: just dataclasses and optimization logic.
"""

from src.cutting.enums import (
    PACKING_STRATEGY_SPLIT_RULE,
    PackingStrategy,
    SplitRule,
)
from src.cutting.models import (
    Cut,
    CuttingLayout,
    Material,
    Piece,
    PlacedPiece,
    Rectangle,
)
from src.cutting.optimizer import GuillotineOptimizer, MultiSheetGuillotineOptimizer
from src.cutting.parameters import CuttingParameters

__all__ = [
    "PACKING_STRATEGY_SPLIT_RULE",
    "Cut",
    "CuttingLayout",
    "CuttingParameters",
    "GuillotineOptimizer",
    "Material",
    "MultiSheetGuillotineOptimizer",
    "PackingStrategy",
    "Piece",
    "PlacedPiece",
    "Rectangle",
    "SplitRule",
]
