from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Rectangle:
    """Representa un rectángulo con posición y dimensiones"""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self):
        """Valida las dimensiones del rectángulo"""
        if self.width < 0 or self.height < 0:
            raise ValueError(
                f"Las dimensiones no pueden ser negativas: width={self.width}, height={self.height}"
            )

    @property
    def area(self) -> float:
        """Calcula el área del rectángulo"""
        return self.width * self.height

    def contains(self, width: float, height: float) -> bool:
        """Verifica si un rectángulo puede contener dimensiones dadas"""
        return self.width >= width and self.height >= height

    def __repr__(self) -> str:
        return f"Rect(x={self.x}, y={self.y}, w={self.width}, h={self.height})"


@dataclass
class Piece:
    """Representa una pieza a cortar"""

    id: str
    width: float
    height: float
    quantity: int = 1
    can_rotate: bool = True
    priority: int = 0

    def __post_init__(self):
        """Valida las dimensiones de la pieza"""
        if self.width <= 0 or self.height <= 0:
            raise ValueError(
                f"Las dimensiones deben ser positivas: width={self.width}, height={self.height}"
            )
        if self.quantity < 1:
            raise ValueError(
                f"La cantidad debe ser al menos 1: quantity={self.quantity}"
            )

    @property
    def area(self) -> float:
        """Calcula el área de la pieza"""
        return self.width * self.height

    def __repr__(self) -> str:
        return f"Piece(id={self.id}, w={self.width}, h={self.height})"


@dataclass
class PlacedPiece:
    """Representa una pieza ya colocada en el material"""

    piece: Piece
    x: float
    y: float
    width: float
    height: float
    rotated: bool = False

    def to_dict(self) -> Dict:
        """Convierte a diccionario para serialización"""
        return {
            "piece_id": self.piece.id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "rotated": self.rotated,
            "original_width": self.piece.width,
            "original_height": self.piece.height,
        }


@dataclass
class Material:
    """Representa un material/tablero donde se cortarán las piezas"""

    id: str
    width: float
    height: float
    thickness: float
    cost_per_unit: float = 0.0

    def __post_init__(self):
        """Valida las dimensiones del material"""
        if self.width <= 0 or self.height <= 0:
            raise ValueError(
                f"Las dimensiones deben ser positivas: width={self.width}, height={self.height}"
            )
        if self.thickness < 0:
            raise ValueError(
                f"El grosor no puede ser negativo: thickness={self.thickness}"
            )

    @property
    def area(self) -> float:
        """Calcula el área del material"""
        return self.width * self.height

    def __repr__(self) -> str:
        return f"Material(id={self.id}, w={self.width}, h={self.height}, t={self.thickness})"


@dataclass
class CuttingLayout:
    """Representa el layout de corte de un material"""

    material: Material
    placed_pieces: List[PlacedPiece] = field(default_factory=list)
    remainders: List[Rectangle] = field(default_factory=list)

    @property
    def used_area(self) -> float:
        """Calcula el área utilizada (sin considerar kerf)"""
        return sum(p.width * p.height for p in self.placed_pieces)

    @property
    def efficiency(self) -> float:
        """Calcula la eficiencia de uso del material (0-1)"""
        if self.material.area == 0:
            return 0.0
        return self.used_area / self.material.area

    @property
    def waste_area(self) -> float:
        """Calcula el área desperdiciada"""
        return self.material.area - self.used_area

    def to_dict(self) -> Dict:
        """Convierte a diccionario para serialización"""
        return {
            "material": {
                "id": self.material.id,
                "width": self.material.width,
                "height": self.material.height,
                "thickness": self.material.thickness,
                "area": self.material.area,
            },
            "placed_pieces": [p.to_dict() for p in self.placed_pieces],
            "statistics": {
                "used_area": self.used_area,
                "waste_area": self.waste_area,
                "efficiency": round(self.efficiency * 100, 2),
                "pieces_count": len(self.placed_pieces),
            },
            "remainders": [
                {"x": r.x, "y": r.y, "width": r.width, "height": r.height}
                for r in self.remainders
            ],
        }
