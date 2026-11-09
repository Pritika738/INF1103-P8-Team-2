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

from safety_guardrail import SafetyGuardrail
from medical_profile_validator import MedicalProfileValidator
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
# SafetyGuardrail now lives in safety_guardrail.py (imported above).
# ===========================================================================

# ===========================================================================
# MedicalProfileValidator now lives in medical_profile_validator.py.
# ===========================================================================

# ===========================================================================
# ManualVitalsValidator - checks vitals the user typed in by hand
# ===========================================================================

class ManualVitalsValidator:
    """
    Validate one self-logged vitals entry (e.g. a home blood-pressure
    reading) before it is saved. These are plausibility checks to catch
    typing mistakes (e.g. 1200 instead of 120) - NOT clinical judgements;
    those are still made by the normal Rule objects afterwards.

    validate() returns (cleaned, errors) and never mutates its input,
    the same contract as MedicalProfileValidator.
    """

    # key -> (label, lowest plausible, highest plausible)
    PLAUSIBLE_RANGES = {
        "blood_pressure_systolic": ("Systolic blood pressure", 50, 300),
        "blood_pressure_diastolic": ("Diastolic blood pressure", 30, 200),
        "heart_rate": ("Heart rate", 20, 250),
        "blood_glucose": ("Blood glucose", 1.0, 40.0),
    }
    MAX_NOTE_LENGTH = 200

    def validate(self, entry: Dict[str, Any],
                 today: Optional[str] = None) -> Tuple[Dict[str, Any], List[str]]:
        """
        ⁠ entry ⁠ shape: {"date": "YYYY-MM-DD", "time": "HH:MM" or "",
        "metrics": {metric_key: number or None, ...}, "note": str}.
        ⁠ today ⁠ ("YYYY-MM-DD") can be passed in by tests; defaults to the
        real current date.
        """
        errors: List[str] = []
        today = today or datetime.now().date().isoformat()

        # --- Date: required, valid, and not in the future ---
        measured_date = str(entry.get("date") or "").strip()
        try:
            datetime.strptime(measured_date, "%Y-%m-%d")
        except ValueError:
            errors.append("Please enter a valid measurement date.")
            measured_date = ""
        if measured_date and measured_date > today:
            errors.append("The measurement date cannot be in the future.")

        # --- Time: optional, but must be HH:MM if given ---
        measured_time = str(entry.get("time") or "").strip()
        if measured_time:
            try:
                datetime.strptime(measured_time, "%H:%M")
            except ValueError:
                errors.append("Time must be in HH:MM format.")
                measured_time = ""

        # --- Each metric: blank is fine, otherwise a number in range ---
        raw_metrics = entry.get("metrics") or {}
        metrics: Dict[str, Optional[float]] = {}
        for key, (label, low, high) in self.PLAUSIBLE_RANGES.items():
            raw = raw_metrics.get(key)
            if raw is None or str(raw).strip() == "":
                metrics[key] = None
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                errors.append(f"{label} must be a number.")
                metrics[key] = None
                continue
            if not low <= value <= high:
                errors.append(f"{label} of {value:g} looks unlikely - "
                              f"please check it (expected {low}-{high}).")
            metrics[key] = int(value) if value.is_integer() else round(value, 1)

        # --- Blood pressure is only meaningful as a pair ---
        systolic = metrics["blood_pressure_systolic"]
        diastolic = metrics["blood_pressure_diastolic"]
        if (systolic is None) != (diastolic is None):
            errors.append("Please enter both systolic and diastolic blood pressure.")
        elif systolic is not None and systolic <= diastolic:
            errors.append("Systolic (top number) must be higher than diastolic (bottom number).")

        if all(v is None for v in metrics.values()):
            errors.append("Please enter at least one measurement.")

        note = str(entry.get("note") or "").strip()
        if len(note) > self.MAX_NOTE_LENGTH:
            errors.append(f"Notes must be {self.MAX_NOTE_LENGTH} characters or fewer.")

        cleaned = {
            "date": measured_date,
            "time": measured_time,
            "metrics": metrics,
            "note": note,
        }
        return cleaned, errors

# ===========================================================================
# The engine - LogicManager (replaces process_ai_record)
# ===========================================================================

class LogicManager:
    """
    Orchestrates the business rules over an AI-extracted reading and the
    user's history, then scores and routes the outcome. Holds its rules
    by AGGREGATION (passed in, independently reusable) and runs them
    POLYMORPHICALLY - it never checks a rule's concrete type.

    The single public entry point, process(), keeps the exact same
    input/output contract as the old logic_manager.process_ai_record(),
    so data_manager and the IO layer need no changes to consume it.
    """

    # Specs shared across rules (one per tracked metric), in a fixed,
    # predictable order matching the old TRACKED_METRICS list.
    _SPECS = [
        SystolicBloodPressure(),
        DiastolicBloodPressure(),
        BloodGlucose(),
        HeartRate(),
    ]

    def __init__(self, rules: List[Rule], guardrail: Optional[SafetyGuardrail] = None):
        # Aggregation: the rules exist on their own and are handed in.
        self._rules = list(rules)
        # Composition: the manager owns its guardrail helper.
        self._guardrail = guardrail or SafetyGuardrail()
        self._spec_by_key = {spec.key: spec for spec in self._SPECS}

    @classmethod
    def default(cls) -> "LogicManager":
        """
        Build a LogicManager wired with the project's current rule set.
        Adding/removing a rule here is the ONLY change needed to change
        the system's behaviour (OCP) - the engine code below is closed
        for modification.
        """
        rules: List[Rule] = []
        for spec in cls._SPECS:
            rules.append(UrgentThresholdRule(spec))
            rules.append(PersistentTrendRule(spec))
            rules.append(RecentChangeRule(spec))
        return cls(rules)
# ----- shape helpers (same behaviour as the old module functions) -----
    @staticmethod
    def _flatten_ai_metrics(ai_extracted: Optional[Dict[str, Any]]) -> Dict[str, Optional[float]]:
        """Nested AI shape -> flat metric keys. Mirrors flatten_ai_metrics()."""
        keys = ["blood_pressure_systolic", "blood_pressure_diastolic",
                "blood_glucose", "heart_rate"]
        if not isinstance(ai_extracted, dict):
            return {k: None for k in keys}
        bp = ai_extracted.get("blood_pressure") or {}
        return {
            "heart_rate": ai_extracted.get("heart_rate"),
            "blood_pressure_systolic": bp.get("systolic"),
            "blood_pressure_diastolic": bp.get("diastolic"),
            "blood_glucose": ai_extracted.get("blood_glucose"),
        }

    @staticmethod
    def _extract_report_date(ai_extracted: Optional[Dict[str, Any]]) -> Optional[str]:
        """Mirrors _extract_report_date(): validated 'YYYY-MM-DD' or None."""
        if not isinstance(ai_extracted, dict):
            return None
        report_date = ai_extracted.get("report_date")
        if not isinstance(report_date, str):
            return None
        try:
            datetime.strptime(report_date, "%Y-%m-%d")
        except ValueError:
            return None
        return report_date

    @staticmethod
    def _history_values(historical_records: List[Dict[str, Any]], metric: str,
                        skip_missing: bool = False) -> List[Optional[float]]:
        """
        This metric's past readings, oldest to newest, reading from
        either a flat CLI record or an AI-pipeline record nested under
        'metrics' - mirrors the old _get_metric_value() per record.

        skip_missing=True drops entries that don't contain this metric.
        Self-logged entries often hold only one measurement (e.g. just
        blood pressure), so without this a glucose-only entry would hide
        yesterday's blood pressure from today's comparison.
        """
        values: List[Optional[float]] = []
        for record in historical_records:
            if isinstance(record.get("metrics"), dict):
                value = record["metrics"].get(metric)
            else:
                value = record.get(metric)
            if skip_missing and value is None:
                continue
            values.append(value)
        return values

    # ----- the polymorphic evaluation loop (the heart of the refactor) ----
    def evaluate(self, current_metrics: Dict[str, Optional[float]],
                 historical_records: List[Dict[str, Any]],
                 skip_missing: bool = False) -> List[Finding]:

        """
        Run every rule over every applicable reading. No type checks on
        the rules - each is asked, uniformly, to evaluate(). Returns all
        raised Findings (URGENT / FLAGGED / CHANGED).
        """
        findings: List[Finding] = []
        for rule in self._rules:
            metric_key = rule.spec.key
            current_value = current_metrics.get(metric_key)
            history_values = self._history_values(historical_records, metric_key, skip_missing)
            finding = rule.evaluate(current_value, history_values)
            if finding is not None:
                findings.append(finding)
        return findings

# ----- scoring / routing (same formula as the old pipeline) -----------
    @staticmethod
    def _score(urgent: List[Finding], flagged: List[Finding]) -> int:
        return len(urgent) * 2 + len(flagged)

    def _summary(self, changes, urgent, flagged) -> str:
        """Deterministic, template-only summary - mirrors generate_dynamic_summary()."""
        if not changes and not urgent and not flagged:
            return "All tracked metrics are stable with no notable changes recorded."

        parts = []
        if urgent:
            metrics = ", ".join(f.metric for f in urgent)
            parts.append(
                f"Urgent: {metrics} at a level that usually warrants "
                "prompt medical attention"
            )
        if flagged:
            metrics = ", ".join(f.metric for f in flagged)
            parts.append(f"Persistent upward trend detected in: {metrics}")

        increases = [c.to_dict() for c in changes if "increased" in c.to_dict()["feedback"]]
        decreases = [c.to_dict() for c in changes if "decreased" in c.to_dict()["feedback"]]
        if increases:
            parts.append("Increased since last visit: "
                         + ", ".join(c["metric"] for c in increases))
        if decreases:
            parts.append("Decreased since last visit: "
                         + ", ".join(c["metric"] for c in decreases))

        parts.append("Please discuss these results with your doctor at "
                     "your next consultation.")
        return " | ".join(parts)

        # ----- single public entry point -------------------------------------
    def process(self, ai_extracted: Optional[Dict[str, Any]],
                historical_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Main pipeline entry point - the OOP replacement for
        process_ai_record(). Returns a dict with the identical keys and
        value shapes the procedural version produced, so stored records
        and the UI need no changes.
        """
        # Deterministic acceptance rule: AI already classified the doc.
        if isinstance(ai_extracted, dict) and ai_extracted.get("is_medical_report") is False:
            reason = ai_extracted.get("classification_reason") or (
                "The uploaded file does not appear to be a medical report."
            )
            return {
                "metrics": self._flatten_ai_metrics(None),
                "ai_extracted_date": None,
                "urgent_findings": [],
                "flagged_trends": [],
                "recent_changes": [],
                "risk_score": 0,
                "decision": Decision.NOT_MEDICAL_REPORT.value,
                "recommended_action": (
                    "The uploaded file does not appear to be a medical "
                    "report. Please upload a valid medical report "
                    "containing health-related examination or test "
                    "information."
                ),
                "requires_doctor_review": False,
                "summary": reason,
            }

        current_metrics = self._flatten_ai_metrics(ai_extracted)
        ai_extracted_date = self._extract_report_date(ai_extracted)

        if all(value is None for value in current_metrics.values()):
            return {
                "metrics": current_metrics,
                "ai_extracted_date": ai_extracted_date,
                "urgent_findings": [],
                "flagged_trends": [],
                "recent_changes": [],
                "risk_score": 0,
                "decision": Decision.REJECTED.value,
                "recommended_action": (
                    "No reliable measurements could be extracted from this "
                    "report. Please try uploading a clearer copy."
                ),
                "requires_doctor_review": False,
                "summary": (
                    "No usable measurements were extracted from this report."
                ),
            }

        findings = self.evaluate(current_metrics, historical_records)
        return self._finalise(current_metrics, ai_extracted_date, findings)

    def _finalise(self, current_metrics: Dict[str, Optional[float]],
                  ai_extracted_date: Optional[str],
                  findings: List[Finding]) -> Dict[str, Any]:
        """Score and route a list of findings into the final record dict.
        Shared by process() (medical reports) and process_manual_reading()
        (self-logged vitals) so both are judged by exactly the same rules."""
        urgent = [f for f in findings if f.status == "URGENT"]
        flagged = [f for f in findings if f.status == "FLAGGED"]
        changes = [f for f in findings if f.status == "CHANGED"]

        risk_score = self._score(urgent, flagged)

        if urgent:
            decision = Decision.URGENT
            recommended_action = (
                "These readings fall outside typical safe ranges. Consider "
                "contacting a healthcare professional promptly rather than "
                "waiting for your next scheduled visit."
            )
        elif flagged:
            decision = Decision.FLAGGED
            recommended_action = (
                "Discuss these trends with your doctor at your next "
                "consultation."
            )
        else:
            decision = Decision.ACCEPTED
            recommended_action = "No action needed - keep up with regular check-ups."

        summary = self._summary(changes, urgent, flagged)

        return {
            "metrics": current_metrics,
            "ai_extracted_date": ai_extracted_date,
            "urgent_findings": [f.to_dict() for f in urgent],
            "flagged_trends": [f.to_dict() for f in flagged],
            "recent_changes": [f.to_dict() for f in changes],
            "risk_score": risk_score,
            "decision": decision.value,
            "recommended_action": recommended_action,
            "requires_doctor_review": bool(urgent or flagged),
            "summary": summary,
        }

    def process_manual_reading(
        self,
        current_metrics: Dict[str, Optional[float]],
        previous_entries: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate one self-logged vitals entry against the user's
        earlier self-logged entries only.
        """
        findings = self.evaluate(
            current_metrics,
            previous_entries,
            skip_missing=True
        )

        return self._finalise(
            current_metrics,
            None,
            findings
        )

# ===========================================================================
# Backwards-compatibility shims
# ---------------------------------------------------------------------------
# All real logic above is object-oriented. These thin module-level names
# are kept only so existing callers (io_gui.py's process_ai_record /
# validate_medical_profile / METRIC_LABELS usage, and data_manager's
# docstrings) keep working unchanged. Each just delegates to a class.
# ===========================================================================

# METRIC_LABELS used to be a module-level dict; io_gui.py reads it as
# logic_manager.METRIC_LABELS.get(key, key). Rebuilt here from the
# MetricSpec objects so there is still a single source of truth.
METRIC_LABELS = {spec.key: spec.label for spec in LogicManager._SPECS}

# One shared default engine / validator / guardrail for the shims.
_default_logic_manager = LogicManager.default()
_default_profile_validator = MedicalProfileValidator()
_default_guardrail = SafetyGuardrail()


def process_ai_record(ai_extracted, historical_records):
    """Backwards-compatible shim -> LogicManager.process()."""
    return _default_logic_manager.process(ai_extracted, historical_records)

def validate_medical_profile(profile):
    """Backwards-compatible shim -> MedicalProfileValidator.validate()."""
    return _default_profile_validator.validate(profile)


def enforce_safety_guardrails(ai_explanation):
    """Backwards-compatible shim -> SafetyGuardrail.enforce()."""
    return _default_guardrail.enforce(ai_explanation)

# ==========================================
# DEMO (local execution only)
# ==========================================
if __name__ == "__main__":
    import json

    mock_ai_extracted = {
        "heart_rate": 138,
        "blood_pressure": {"systolic": 188, "diastolic": 122},
        "blood_glucose": 15.4,
        "report_date": "2026-09-22",
    }
    mock_history = [
        {
            "date": "2026-07-01",
            "blood_pressure_systolic": 132,
            "blood_pressure_diastolic": 85,
            "blood_glucose": 6.6,
            "heart_rate": 104,
        },
        {
            "date": "2026-08-01",
            "blood_pressure_systolic": 148,
            "blood_pressure_diastolic": 96,
            "blood_glucose": 9.2,
            "heart_rate": 118,
        },
    ]

    engine = LogicManager.default()
    print("--- Simulating an urgent + persistent-trend reading (OOP) ---")
    result = engine.process(mock_ai_extracted, mock_history)
    print(json.dumps(result, indent=4))