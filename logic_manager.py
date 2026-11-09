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
from manual_vitals_validator import ManualVitalsValidator
from enums import Tier, Decision
from findings import Finding
from metrics import (MetricSpec, HeartRate, SystolicBloodPressure,
                     DiastolicBloodPressure, BloodGlucose)
from rules import (Rule, UrgentThresholdRule, PersistentTrendRule,
                   RecentChangeRule)
# ===========================================================================
# Tier and Decision enums now live in enums.py (imported above).
# ===========================================================================

# ===========================================================================
# MetricSpec family (MetricSpec + the 4 metric subclasses) now lives
# in metrics.py (imported above).
# ===========================================================================

# ===========================================================================
# Finding value object now lives in findings.py (imported above).
# ===========================================================================

# ===========================================================================
# Rule family (Rule + the 3 rule subclasses) now lives in rules.py
# (imported above).
# ===========================================================================

# ===========================================================================
# SafetyGuardrail now lives in safety_guardrail.py (imported above).
# ===========================================================================

# ===========================================================================
# MedicalProfileValidator now lives in medical_profile_validator.py.
# ===========================================================================

# ===========================================================================
# ManualVitalsValidator now lives in manual_vitals_validator.py.
# ===========================================================================

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