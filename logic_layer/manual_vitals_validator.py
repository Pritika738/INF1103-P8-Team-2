"""
manual_vitals_validator.py

Plausibility validation for one self-logged vitals entry, extracted
from logic_manager.py so that each class lives in its own module.
logic_manager.py imports the ManualVitalsValidator class from here;
its public behaviour is unchanged.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


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
