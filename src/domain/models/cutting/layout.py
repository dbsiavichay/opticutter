from dataclasses import dataclass, field
from typing import Dict, List

from . import Material, PlacedPiece, Rectangle


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
