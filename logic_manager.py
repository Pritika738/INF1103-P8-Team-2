"""
logic_manager.py

Responsible for business rules and domain logic only. Acts as the
"Domain Brain": takes a fresh AI-extracted reading plus the user's
stored history, applies clinical threshold rules in plain Python, and
decides an outcome for the record. It never diagnoses a condition,
prescribes a treatment, or replaces professional medical advice - it
only decides what is worth flagging for the user to discuss with a
doctor. It also validates the user's standing medical profile
(medications, blood group, allergies, emergency contacts, hereditary
illness) - reference data, not measurements, so no thresholds/scoring.

Phase 2 - fully object-oriented
-------------------------------
There is no remaining procedural business logic in this module: every
rule, threshold set, classification, and the orchestration itself lives
in a class. The three module-level names other modules still import
(process_ai_record, validate_medical_profile, METRIC_LABELS) are kept
at the bottom purely as thin backwards-compatibility shims that
delegate to the classes, so io_gui.py and data_manager need no change.

Rules for this module:
- No print() or input() calls here (except inside the __main__ demo
  block at the bottom, which only runs when this file is executed
  directly with `python logic_manager.py`, never when imported).
- No network/AI calls here.
- No file operations here.
- Works purely on dicts/lists already handed to it by other modules.

OOP concepts demonstrated here
------------------------------
- Abstract classes / interfaces : MetricSpec, Rule (both ABCs).
- Inheritance                   : HeartRate / SystolicBloodPressure /
                                  DiastolicBloodPressure / BloodGlucose
                                  subclass MetricSpec; the three Rule
                                  subclasses specialise Rule.
- Polymorphism                  : LogicManager.evaluate() calls
                                  rule.evaluate(...) without knowing the
                                  concrete rule; MetricSpec.classify().
- Encapsulation                 : thresholds held as private attrs set
                                  at construction, not mutable globals.
- Aggregation                   : LogicManager holds a list of Rule
                                  objects that exist independently of it.
- Composition                   : a processed report owns its Finding
                                  objects (they have no life outside it);
                                  LogicManager owns its SafetyGuardrail.
- Association                   : each Rule refers to a MetricSpec it
                                  evaluates, without owning its lifecycle.

SOLID evidence
--------------
- SRP : each Rule has one reason to change; LogicManager orchestrates;
        MedicalProfileValidator is wholly separate from vital-sign logic.
- OCP : adding a new clinical rule means writing a new Rule subclass and
        adding it to the list passed to LogicManager - zero edits to the
        engine. See LogicManager.default() for the current rule set.
- LSP : any Rule is substitutable wherever the engine expects one; any
        MetricSpec is substitutable wherever a reading is classified.

Input contract
--------------
Fresh AI output (`ai_extracted`) is whatever ai_manager.call_ai_with_retry()
returns: either None (the AI Manager gave up after retrying), or a dict
shaped like:
    {"heart_rate": number or None,
     "blood_pressure": {"systolic": number or None,
                         "diastolic": number or None} or None,
     "blood_glucose": number or None,
     "report_date": "YYYY-MM-DD" or None,
     "is_medical_report": bool (optional),
     "classification_reason": str (optional)}

Historical records (`historical_records`) are whatever
data_manager.load_health_records() returns: a list of dicts using the
flat key names in config.SUPPORTED_METRICS, assumed sorted oldest to
newest (metric keys may sit at the top level for CLI-entered records,
or under "metrics" for AI-pipeline records).

LogicManager.process() is the single entry point that bridges the AI
shape and history, applies all business rules, and returns one
finalized, JSON-serialisable report dict.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
# ===========================================================================
# Enumerations - small, self-describing value types
# ===========================================================================

class Tier(Enum):
    """
    Severity tier for a single reading, independent of trend history.
    Replaces the old _metric_classification() bare strings ("SEVERE",
    "ELEVATED", "NORMAL") with a proper type.
    """
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    SEVERE = "SEVERE"


class Decision(Enum):
    """
    Final routing outcome for a processed record. Same five string
    values the procedural version produced, so stored/serialised records
    look identical to the old pipeline's output.
    """
    NOT_MEDICAL_REPORT = "NOT_MEDICAL_REPORT"
    REJECTED = "REJECTED"
    URGENT = "URGENT"
    FLAGGED = "FLAGGED"
    ACCEPTED = "ACCEPTED"


# ===========================================================================
# MetricSpec hierarchy - ABSTRACT CLASS + INHERITANCE + ENCAPSULATION
# ===========================================================================

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
    # ===========================================================================
# Value object produced by the rules / engine
# ===========================================================================

class Finding:
    """
    One rule's conclusion about one metric. Replaces the loose
    {"metric", "status", "reason", ...} dicts the old functions built.
    JSON-serialisable via to_dict() so stored records match the
    procedural pipeline's output shape exactly.
    """

    def __init__(self, metric: str, status: str, **extra: Any):
        self._metric = metric
        self._status = status
        self._extra = extra

    @property
    def status(self) -> str:
        return self._status

    @property
    def metric(self) -> str:
        return self._metric

    def to_dict(self) -> Dict[str, Any]:
        return {"metric": self._metric, "status": self._status, **self._extra}

# ===========================================================================
# Rule hierarchy - ABSTRACT CLASS + INHERITANCE + POLYMORPHISM (OCP core)
# ===========================================================================

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

# ===========================================================================
# Safe  ty guardrail - forward-compatible free-text filter
# ===========================================================================

class SafetyGuardrail:
    """
    Check free-text AI-generated explanation text for prohibited
    diagnostic/prescriptive language, and reject it wholesale if found.
    Nothing in the current numeric pipeline calls this (ai_manager's
    output is purely numeric), but it is kept, tested and ready for
    if/when a future AI-generated explanation field is added - the OOP
    equivalent of the old enforce_safety_guardrails().
    """

    _FORBIDDEN_SINGLE_WORDS = ["diagnose", "disease", "prescribe", "treatment"]
    _FORBIDDEN_PHRASES = ["stop taking", "increase dose", "decrease dose"]
    _OVERRIDE_MESSAGE = (
        "Safety Override: The AI generated restricted diagnostic "
        "language. Please discuss these health trends directly with "
        "your doctor."
    )

    def enforce(self, ai_explanation: str) -> str:
        if not ai_explanation:
            return ai_explanation

        text_lower = ai_explanation.lower()

        for word in self._FORBIDDEN_SINGLE_WORDS:
            if re.search(r"\b" + re.escape(word) + r"\w*\b", text_lower):
                return self._OVERRIDE_MESSAGE

        for phrase in self._FORBIDDEN_PHRASES:
            if phrase in text_lower:
                return self._OVERRIDE_MESSAGE

        return ai_explanation

# ===========================================================================
# MedicalProfileValidator - standing reference-data validation (own SRP)
# ===========================================================================

class MedicalProfileValidator:
    """
    Validate and normalise a raw medical-profile dict (medications,
    blood group, allergies, emergency contacts, hereditary illness).

    A separate class from the vital-sign engine because this is
    user-entered reference data, not a measurement - it gets no
    thresholds, trend analysis or scoring, only validation. Mirrors the
    old validate_medical_profile() exactly, including its (cleaned,
    errors) return and its never-mutate-the-input guarantee.
    """

    VALID_BLOOD_GROUPS = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    VALID_ALLERGY_SEVERITIES = ["mild", "moderate", "severe"]
    VALID_DOSAGE_UNITS = [
        "", "mg", "mcg", "g", "ml", "L", "IU", "%",
        "units", "tablet(s)", "drop(s)", "puff(s)", "patch(es)",
    ]
    # Mandatory leading "+" and country code, then digits/spaces/dashes only.
    _PHONE_RE = re.compile(r"^\+[1-9][0-9 \-]{5,18}$")

    def validate(self, profile: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        errors: List[str] = []
        cleaned: Dict[str, Any] = {
            "medications": [],
            "blood_group": "",
            "allergies": [],
            "emergency_contacts": [],
            "hereditary_illness": {
                "diabetes": False, "blood_pressure": False,
                "heart_disease": False, "asthma": False,
                "other": "", "notes": "",
            },
        }

        # --- Blood group: must be one of the known groups (blank = unknown) ---
        blood_group = str(profile.get("blood_group", "")).strip().upper()
        if blood_group in self.VALID_BLOOD_GROUPS:
            cleaned["blood_group"] = blood_group
        else:
            errors.append(f"'{blood_group}' is not a recognised blood group.")



        # --- Medications: name required if row isn't fully blank; dosage, ---
        # --- if given, must be a non-negative number. ---
        for index, med in enumerate(profile.get("medications", []), start=1):
            name = str(med.get("name", "")).strip()
            amount_raw = str(med.get("dosage_amount", "")).strip()
            if not name and not amount_raw:
                continue  # fully blank row - skip silently
            if not name:
                errors.append(f"Medication {index}: a name is required.")
                continue
            amount = None
            if amount_raw:
                try:
                    amount = float(amount_raw)
                except ValueError:
                    errors.append(f"Medication '{name}': dosage must be a number.")
                    continue
                if amount < 0:
                    errors.append(f"Medication '{name}': dosage cannot be negative.")
                    continue
            unit = str(med.get("dosage_unit", "")).strip()
            if unit and unit not in self.VALID_DOSAGE_UNITS:
                errors.append(f"Medication '{name}': '{unit}' is not a recognised dosage unit.")
                unit = ""
            cleaned["medications"].append({
                "name": name,
                "dosage_amount": amount,
                "dosage_unit": unit,
                "frequency": str(med.get("frequency", "")).strip(),
            })

            # --- Allergies: allergen required; severity, if given, must be known ---
        for index, allergy in enumerate(profile.get("allergies", []), start=1):
            allergen = str(allergy.get("allergen", "")).strip()
            if not allergen:
                continue
            severity = str(allergy.get("severity", "")).strip().lower()
            if severity and severity not in self.VALID_ALLERGY_SEVERITIES:
                errors.append(
                    f"Allergy '{allergen}': severity must be mild, moderate or severe."
                )
                severity = ""
            cleaned["allergies"].append({
                "allergen": allergen,
                "reaction": str(allergy.get("reaction", "")).strip(),
                "severity": severity,
            })

        # --- Emergency contacts: name and a plausible phone number required ---
        for index, contact in enumerate(profile.get("emergency_contacts", []), start=1):
            name = str(contact.get("name", "")).strip()
            phone = str(contact.get("phone", "")).strip()
            if not name and not phone:
                continue
            if not name:
                errors.append(f"Emergency contact {index}: a name is required.")
                continue
            if not phone:
                errors.append(f"Emergency contact '{name}': a phone number is required.")
                continue
            if not self._PHONE_RE.fullmatch(phone):
                errors.append(
                    f"Emergency contact '{name}': phone number must include the "
                    "country code, e.g. +65 1234 5678."
                )
                continue
            cleaned["emergency_contacts"].append({
                "name": name,
                "relationship": str(contact.get("relationship", "")).strip(),
                "phone": phone,
                "email": str(contact.get("email", "")).strip(),
            })

