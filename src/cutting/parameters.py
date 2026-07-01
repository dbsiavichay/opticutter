from dataclasses import dataclass


@dataclass
class CuttingParameters:
    """Cutting parameters for the optimizer"""

    kerf: float = 0.0
    top_trim: float = 0.0
    bottom_trim: float = 0.0
    left_trim: float = 0.0
    right_trim: float = 0.0

    def __post_init__(self):
        if self.kerf < 0:
            raise ValueError(f"Kerf cannot be negative: {self.kerf}")
        if self.top_trim < 0:
            raise ValueError(f"Top trim cannot be negative: {self.top_trim}")
        if self.bottom_trim < 0:
            raise ValueError(f"Bottom trim cannot be negative: {self.bottom_trim}")
        if self.left_trim < 0:
            raise ValueError(f"Left trim cannot be negative: {self.left_trim}")
        if self.right_trim < 0:
            raise ValueError(f"Right trim cannot be negative: {self.right_trim}")
