from enum import Enum


class SplitRule(Enum):
    """Reglas para dividir los rectángulos sobrantes después de colocar una pieza"""

    SHORTER_LEFTOVER_AXIS = "shorter_leftover_axis"
    LONGER_LEFTOVER_AXIS = "longer_leftover_axis"
    MINIMIZE_AREA = "minimize_area"
    MAXIMIZE_AREA = "maximize_area"
    SHORTER_AXIS = "shorter_axis"
    LONGER_AXIS = "longer_axis"


class PackingStrategy(str, Enum):
    """Perfil de empaquetado: agrupa las tres decisiones del optimizador.

    ``MAX_EFFICIENCY`` (default) minimiza la merma total pero la fragmenta:
    orden por área descendente + selección Best-Area-Fit + split
    ``SHORTER_LEFTOVER_AXIS``.

    ``LONG_OFFCUTS`` concentra la merma en una tira continua y reutilizable
    apegada al eje largo del tablero: orden por alto/ancho descendente (arma
    columnas) + selección Bottom-Left (pega las piezas a una esquina) + split
    ``LONGER_AXIS`` (conserva el eje largo del rectángulo). Es la heurística de
    "retazos aprovechables" (Cutting Stock Problem with Usable Leftovers).
    """

    MAX_EFFICIENCY = "max_efficiency"
    LONG_OFFCUTS = "long_offcuts"


# Única fuente de la regla de split por estrategia. ``GuillotineOptimizer``
# la usa cuando no se pasa un ``split_rule`` explícito.
PACKING_STRATEGY_SPLIT_RULE = {
    PackingStrategy.MAX_EFFICIENCY: SplitRule.SHORTER_LEFTOVER_AXIS,
    PackingStrategy.LONG_OFFCUTS: SplitRule.LONGER_AXIS,
}
