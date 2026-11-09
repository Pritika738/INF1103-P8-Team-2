"""
rules.py

The Rule abstraction and its concrete business rules
(UrgentThresholdRule, PersistentTrendRule, RecentChangeRule),
extracted from logic_manager.py so the whole rule family lives
together in one cohesive module. Each Rule refers to a MetricSpec
(association) and produces Finding objects; behaviour is unchanged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from metrics import MetricSpec
from findings import Finding


class Rule(ABC):
    """
    Abstract business rule for ONE metric. Subclasses implement
    evaluate(); the engine runs them without checking concrete type
    (polymorphism), so a new rule can be added without touching
    LogicManager (OCP). Association: a Rule refers to the MetricSpec it
    evaluates but does not own it (specs are shared across rules).
    """

    def __init__(self, spec: MetricSpec):
        self._spec = spec

    @property
    def spec(self) -> MetricSpec:
        return self._spec

    @abstractmethod
    def evaluate(self, current_value: Optional[float],
                 history_values: List[Optional[float]]) -> Optional[Finding]:
        """
        Return a Finding if this rule fires for the given reading, else
        None. `history_values` is this metric's past readings, oldest to
        newest (so the most recent past reading is history_values[-1]).
        """
        raise NotImplementedError


class UrgentThresholdRule(Rule):
    """
    Tier 1: a single CURRENT reading at/above the urgent threshold is
    flagged immediately, regardless of trend history. Not multi-
    conditional by design - one dangerously high reading shouldn't wait
    for a pattern to emerge across visits.
    """

    def evaluate(self, current_value, history_values):
        if not self._spec.is_urgent(current_value):
            return None
        return Finding(
            metric=self._spec.label,
            status="URGENT",
            reason=(
                f"{self._spec.label} reading of {current_value} is at a "
                "level that usually warrants prompt medical attention."
            ),
        )
class PersistentTrendRule(Rule):
    """
    Tier 2 - the genuinely MULTI-CONDITION rule the brief requires
    preserved. Fires only when BOTH hold:
      (a) the current reading exceeds the lower flag threshold, AND
      (b) it has been strictly increasing across the last three
          consecutive readings (today > previous visit > the one before).
    Either condition alone is not enough.
    """

    def __init__(self, spec: MetricSpec, visits: int = 3):
        super().__init__(spec)
        self._visits = visits

    def evaluate(self, current_value, history_values):
        if current_value is None:
            return None
        if current_value <= self._spec.flag_above:
            return None
        # An urgent reading is already handled by UrgentThresholdRule.
        if self._spec.is_urgent(current_value):
            return None
        if len(history_values) < 2:
            return None

        past_1 = history_values[-1]
        past_2 = history_values[-2]

        if (past_1 is not None and past_2 is not None
                and current_value > past_1 > past_2):
            return Finding(
                metric=self._spec.label,
                status="FLAGGED",
                reason=(
                    f"{self._spec.label} ({current_value}) is elevated and "
                    "has been rising for three consecutive readings."
                ),
            )
        return None

class RecentChangeRule(Rule):
    """
    Compare the current reading against only the single most recent past
    reading. Deltas within this metric's tolerance are normal
    fluctuation and ignored - UNLESS the reading crossed a classification
    boundary (e.g. severe to normal), which is always notable even if
    numerically small.
    """

    def evaluate(self, current_value, history_values):
        if current_value is None or not history_values:
            return None

        past_val = history_values[-1]
        if past_val is None:
            return None	

        delta = current_value - past_val
        past_class = self._spec.classify(past_val)
        current_class = self._spec.classify(current_value)
        classification_changed = past_class != current_class

        if abs(delta) <= self._spec.tolerance and not classification_changed:
            return None  # within normal day-to-day fluctuation

        label = self._spec.label
        direction = "increased" if delta > 0 else "decreased"
        improved = self._spec.is_improvement(delta)
        assessment = "improved" if improved else "worsened"

        if classification_changed:
            feedback = (
                f"Your {label.lower()} has changed from "
                f"{past_class.value.lower()} ({past_val}) to "
                f"{current_class.value.lower()} ({current_value}) "
                "since your last record."
            )
        else:
            moved = "closer to" if improved else "further from"
            feedback = (
                f"Your {label.lower()} has {direction} from {past_val} "
                f"to {current_value} since your last record "
                f"({assessment} - moved {moved} the typical reference "
                "range)."
            )

        return Finding(
            metric=label,
            status="CHANGED",
            assessment=assessment,
            classification_changed=classification_changed,
            previous_classification=(past_class.value if past_class else None),
            current_classification=(current_class.value if current_class else None),
            feedback=feedback,
        )
