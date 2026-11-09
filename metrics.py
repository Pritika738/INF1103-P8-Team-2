"""
metrics.py

The MetricSpec abstraction and its concrete metric subclasses
(HeartRate, SystolicBloodPressure, DiastolicBloodPressure,
BloodGlucose), extracted from logic_manager.py so the whole metric
family lives together in one cohesive module. Thresholds and
classification behaviour are unchanged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from enums import Tier


class MetricSpec(ABC):
    """
    Abstract description of one tracked health metric: its storage key,
    human label, unit, and the thresholds used to classify a single
    reading of it. Subclasses supply the metric-specific numbers.

    This replaces the four parallel module-level dicts in the old file
    (METRIC_LABELS, URGENT_THRESHOLDS, TREND_FLAG_THRESHOLDS,
    RECENT_CHANGE_TOLERANCES) with one cohesive object per metric, so a
    metric's data can never drift out of sync across four dicts.

    All four tracked metrics currently use "higher is worse" thresholds,
    so the shared classify()/is_improvement() logic lives here in the
    base class; a future "lower is worse" metric would override them.
    """

    def __init__(self, key: str, label: str, unit: str,
                 urgent_at: float, flag_above: float, tolerance: float):
        self._key = key
        self._label = label
        self._unit = unit
        self._urgent_at = urgent_at
        self._flag_above = flag_above
        self._tolerance = tolerance

    @property
    def key(self) -> str:
        return self._key

    @property
    def label(self) -> str:
        return self._label

    @property
    def unit(self) -> str:
        return self._unit

    @property
    def flag_above(self) -> float:
        return self._flag_above

    @property
    def tolerance(self) -> float:
        return self._tolerance

    def classify(self, value: Optional[float]) -> Optional[Tier]:
        """Classify a single reading into a Tier - OOP _metric_classification()."""
        if value is None:
            return None
        if value >= self._urgent_at:
            return Tier.SEVERE
        if value > self._flag_above:
            return Tier.ELEVATED
        return Tier.NORMAL

    def is_urgent(self, value: Optional[float]) -> bool:
        """True if a single current reading alone is urgent."""
        return value is not None and value >= self._urgent_at

    def is_improvement(self, delta: float) -> bool:
        """For 'higher is worse' metrics a decrease improves. Overridable (LSP)."""
        return delta < 0
class HeartRate(MetricSpec):
    def __init__(self):
        super().__init__(
            key="heart_rate", label="Heart Rate", unit="bpm",
            urgent_at=130, flag_above=100, tolerance=5,
        )


class SystolicBloodPressure(MetricSpec):
    def __init__(self):
        super().__init__(
            key="blood_pressure_systolic", label="Systolic Blood Pressure",
            unit="mmHg", urgent_at=180, flag_above=130, tolerance=5,
        )


class DiastolicBloodPressure(MetricSpec):
    def __init__(self):
        super().__init__(
            key="blood_pressure_diastolic", label="Diastolic Blood Pressure",
            unit="mmHg", urgent_at=120, flag_above=80, tolerance=4,
        )


class BloodGlucose(MetricSpec):
    def __init__(self):
        super().__init__(
            key="blood_glucose", label="Blood Glucose", unit="mmol/L",
            urgent_at=13.9, flag_above=7.0, tolerance=0.5,
        )
