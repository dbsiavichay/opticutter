from enum import Enum


class SplitRule(Enum):
    """Reglas para dividir los rectángulos sobrantes después de colocar una pieza"""

    SHORTER_LEFTOVER_AXIS = "shorter_leftover_axis"
    LONGER_LEFTOVER_AXIS = "longer_leftover_axis"
    MINIMIZE_AREA = "minimize_area"
    MAXIMIZE_AREA = "maximize_area"
    SHORTER_AXIS = "shorter_axis"
    LONGER_AXIS = "longer_axis"
