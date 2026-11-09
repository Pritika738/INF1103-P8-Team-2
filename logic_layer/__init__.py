"""Logic support package: value types, metric specs, business rules, validators.

The orchestrating class, LogicManager, lives in the top-level
logic_manager.py (mirroring io_manager.py + io_layer, ai_manager.py +
ai_layer, data_manager.py + data_layer).
"""

from .enums import Tier, Decision
from .findings import Finding
from .metrics import (
    MetricSpec, HeartRate, SystolicBloodPressure,
    DiastolicBloodPressure, BloodGlucose,
)
from .rules import (
    Rule, UrgentThresholdRule, PersistentTrendRule, RecentChangeRule,
)
from .safety_guardrail import SafetyGuardrail
from .medical_profile_validator import MedicalProfileValidator
from .manual_vitals_validator import ManualVitalsValidator

__all__ = [
    "Tier", "Decision",
    "Finding",
    "MetricSpec", "HeartRate", "SystolicBloodPressure",
    "DiastolicBloodPressure", "BloodGlucose",
    "Rule", "UrgentThresholdRule", "PersistentTrendRule", "RecentChangeRule",
    "SafetyGuardrail", "MedicalProfileValidator", "ManualVitalsValidator",
]
