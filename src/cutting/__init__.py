"""Dominio puro del algoritmo de corte 2D (guillotina).

Sin dependencias de frameworks: solo dataclasses y lógica de optimización.
"""

from src.cutting.enums import SplitRule
from src.cutting.models import CuttingLayout, Material, Piece, PlacedPiece, Rectangle
from src.cutting.optimizer import GuillotineOptimizer, MultiSheetGuillotineOptimizer
from src.cutting.parameters import CuttingParameters

__all__ = [
    "CuttingLayout",
    "CuttingParameters",
    "GuillotineOptimizer",
    "Material",
    "MultiSheetGuillotineOptimizer",
    "Piece",
    "PlacedPiece",
    "Rectangle",
    "SplitRule",
]
