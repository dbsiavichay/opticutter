from enum import Enum


class SplitRule(Enum):
    """Rules for splitting leftover rectangles after placing a piece"""

    SHORTER_LEFTOVER_AXIS = "shorter_leftover_axis"
    LONGER_LEFTOVER_AXIS = "longer_leftover_axis"
    MINIMIZE_AREA = "minimize_area"
    MAXIMIZE_AREA = "maximize_area"
    SHORTER_AXIS = "shorter_axis"
    LONGER_AXIS = "longer_axis"


class PackingStrategy(str, Enum):
    """Packing profile: groups the optimizer's three decisions.

    ``MAX_EFFICIENCY`` (default) minimizes total waste but fragments it:
    area-decreasing sort + Best-Area-Fit selection + ``SHORTER_LEFTOVER_AXIS``
    split.

    ``LONG_OFFCUTS`` concentrates the waste into one continuous, reusable strip
    along the board's long axis: height/width-decreasing sort (builds columns)
    + Bottom-Left selection (pushes pieces into a corner) + ``LONGER_AXIS``
    split (preserves the rectangle's long axis). This is the "usable offcuts"
    heuristic (Cutting Stock Problem with Usable Leftovers).
    """

    MAX_EFFICIENCY = "max_efficiency"
    LONG_OFFCUTS = "long_offcuts"


# Single source of truth for the split rule per strategy. ``GuillotineOptimizer``
# uses it when no explicit ``split_rule`` is passed.
PACKING_STRATEGY_SPLIT_RULE = {
    PackingStrategy.MAX_EFFICIENCY: SplitRule.SHORTER_LEFTOVER_AXIS,
    PackingStrategy.LONG_OFFCUTS: SplitRule.LONGER_AXIS,
}
