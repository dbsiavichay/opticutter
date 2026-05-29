from dataclasses import dataclass


@dataclass
class CuttingParameters:
    """Parámetros de corte para el optimizador"""

    kerf: float = 0.0
    top_trim: float = 0.0
    bottom_trim: float = 0.0
    left_trim: float = 0.0
    right_trim: float = 0.0

    def __post_init__(self):
        if self.kerf < 0:
            raise ValueError(f"Kerf no puede ser negativo: {self.kerf}")
        if self.top_trim < 0:
            raise ValueError(f"Top trim no puede ser negativo: {self.top_trim}")
        if self.bottom_trim < 0:
            raise ValueError(f"Bottom trim no puede ser negativo: {self.bottom_trim}")
        if self.left_trim < 0:
            raise ValueError(f"Left trim no puede ser negativo: {self.left_trim}")
        if self.right_trim < 0:
            raise ValueError(f"Right trim no puede ser negativo: {self.right_trim}")
