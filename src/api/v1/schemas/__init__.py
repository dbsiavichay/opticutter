from .base import CamelModel
from .board import BoardCreate, BoardResponse, BoardUpdate
from .client import ClientCreate, ClientResponse, ClientUpdate
from .cutting import CuttingParameters
from .optimization import (
    Material,
    OptimizeRequest,
    OptimizeResponse,
    PlacedPiece,
    Remainder,
    Requirement,
    Solution,
)

__all__ = [
    "CamelModel",
    "BoardCreate",
    "BoardResponse",
    "BoardUpdate",
    "ClientCreate",
    "ClientResponse",
    "ClientUpdate",
    "CuttingParameters",
    "Material",
    "OptimizeRequest",
    "OptimizeResponse",
    "PlacedPiece",
    "Remainder",
    "Requirement",
    "Solution",
]
