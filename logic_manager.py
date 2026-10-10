"""
logic_manager.py

Responsible for business rules and domain logic only. Acts as the
"Domain Brain": takes a fresh AI-extracted reading plus the user's
stored history, applies clinical threshold rules in plain Python, and
decides an outcome for the record. It never diagnoses a condition,
prescribes a treatment, or replaces professional medical advice - it
only decides what is worth flagging for the user to discuss with a
doctor.

Rules for this module:
- No print() or input() calls here (except inside the __main__ demo
  block at the bottom, which only runs when this file is executed
  directly with `python logic_manager.py`, never when imported).
- No network/AI calls here.
- No file operations here (the demo block's optional mock-file loader
  is the one exception, and it is isolated inside __main__ too).
- Works purely on dicts/lists already handed to it by other modules.

Input contract
--------------
Fresh AI output (`ai_extracted`) is whatever ai_manager.call_ai_with_retry()
returns: either None (the AI Manager gave up after retrying), or a dict
shaped like:
    {"heart_rate": number or None,
     "blood_pressure": {"systolic": number or None,
                         "diastolic": number or None} or None,
     "blood_glucose": number or None}

Historical records (`historical_records`) are whatever
data_manager.load_health_records() returns: a list of dicts using the
flat key names in config.SUPPORTED_METRICS (blood_pressure_systolic,
blood_pressure_diastolic, heart_rate, blood_glucose, ...), assumed
sorted oldest to newest.

process_ai_record() is the single entry point that bridges these two
shapes (via flatten_ai_metrics()) and returns one finalized,
JSON-serialisable report dict.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional


# --- Tracked metrics -----------------------------------------------------
# Strictly limited to the three measurements ai_manager.py extracts.
# Blood pressure is tracked as two separate numbers throughout this
# module (matching config.SUPPORTED_METRICS), even though ai_manager's
# raw output nests them under one "blood_pressure" key - see
# flatten_ai_metrics() below.

TRACKED_METRICS = [
    "blood_pressure_systolic",
    "blood_pressure_diastolic",
    "blood_glucose",
    "heart_rate",
]
# ADDING METRIC LABELS
METRIC_LABELS = {
    "blood_pressure_systolic": "Systolic Blood Pressure",
    "blood_pressure_diastolic": "Diastolic Blood Pressure",
    "blood_glucose": "Blood Glucose",
    "heart_rate": "Heart Rate",
}


# --- Clinical thresholds --------------------------------------------------
# These are business-rule cutoffs used only to decide what is worth
# flagging for discussion with a doctor - commonly-cited reference
# points for a student project demo, not a medical guideline, and never
# used to name or diagnose a condition.

# A single CURRENT reading at or above these values is treated as an
# immediate, high-severity concern regardless of trend history (e.g.
# systolic/diastolic >= these values is widely cited as "hypertensive
# crisis" territory; glucose >= 13.9 mmol/L / ~250 mg/dL is a commonly
# cited threshold for concern; heart_rate >= 130 bpm is sustained
# tachycardia).
URGENT_THRESHOLDS = {
    "blood_pressure_systolic": 180,
    "blood_pressure_diastolic": 120,
    "blood_glucose": 13.9,
    "heart_rate": 130,
}

# A current reading above these, WITH a persistent 3-visit upward trend,
# is flagged as worth discussing at the next consultation (not urgent).
TREND_FLAG_THRESHOLDS = {
    "blood_pressure_systolic": 130,
    "blood_pressure_diastolic": 80,
    "blood_glucose": 7.0,
    "heart_rate": 100,
}

# Day-to-day deltas within these bounds are normal fluctuation and are
# NOT reported as a "CHANGED" metric by analyze_recent_changes() - UNLESS
# the classification itself changed (see _metric_classification() and
# classification_changed below), since even a small numeric move across
# a threshold boundary is a notable change, not noise. This tolerance
# has no effect on evaluate_health_metrics(), which uses the thresholds
# above instead.
RECENT_CHANGE_TOLERANCES = {
    "blood_pressure_systolic": 5,
    "blood_pressure_diastolic": 4,
    "blood_glucose": 0.5,
    "heart_rate": 5,
}


def _metric_classification(metric, value):
    """
    Classify a single reading into a severity tier using the existing
    approved thresholds above - independent of trend history. This is
    only used to detect when a reading crosses from one classification
    to another between two visits (e.g. "severe" to "normal"); it is
    not the same thing as evaluate_health_metrics()'s overall FLAGGED
    tier, which additionally requires a persistent 3-visit trend.

    Returns "SEVERE" (at/above URGENT_THRESHOLDS), "ELEVATED" (above
    TREND_FLAG_THRESHOLDS but below URGENT_THRESHOLDS), "NORMAL"
    (at/below TREND_FLAG_THRESHOLDS), or None if `value` is None.
    """
    if value is None:
        return None
    if value >= URGENT_THRESHOLDS[metric]:
        return "SEVERE"
    if value > TREND_FLAG_THRESHOLDS[metric]:
        return "ELEVATED"
    return "NORMAL"


def flatten_ai_metrics(ai_extracted: Optional[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """
    Convert ai_manager's nested extraction shape into the flat key
    names used everywhere else in this module (TRACKED_METRICS), which
    also match how data_manager stores historical records - so a fresh
    reading and past readings can be compared using identical keys.

    Args:
        ai_extracted: the dict ai_manager.call_ai_with_retry() returned,
            or None if the AI Manager gave up after retrying.

    Returns:
        A flat dict with exactly the keys in TRACKED_METRICS. Always
        returns all four keys - missing/unavailable ones are None -
        even if `ai_extracted` itself is None or malformed.
    """
    if not isinstance(ai_extracted, dict):
        return {metric: None for metric in TRACKED_METRICS}

    blood_pressure = ai_extracted.get("blood_pressure") or {}

    return {
        "heart_rate": ai_extracted.get("heart_rate"),
        "blood_pressure_systolic": blood_pressure.get("systolic"),
        "blood_pressure_diastolic": blood_pressure.get("diastolic"),
        "blood_glucose": ai_extracted.get("blood_glucose"),
    }


def _extract_report_date(ai_extracted: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Safely read the AI Manager's extracted "report_date" out of the raw
    extraction dict, if present.

    ai_manager.validate_schema() and verify_source() have already
    checked this is a genuine, source-backed "YYYY-MM-DD" date (or
    None) by the time it normally reaches this module - this function
    re-checks the format defensively anyway, so calling
    process_ai_record() directly with unvalidated data still can't
    crash or silently accept a malformed date string. This module never
    invents a replacement date itself if the result is None - deciding
    what (if anything) to fall back to is left to the caller.

    Args:
        ai_extracted: the dict ai_manager.call_ai_with_retry() returned,
            or None.

    Returns:
        The "YYYY-MM-DD" string if present and genuinely a valid
        calendar date, otherwise None.
    """
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


def _get_metric_value(record, metric):
    """
    Read one metric's value from a historical record, which may be
    shaped either as a flat CLI-entered record (metric keys directly
    at the top level - see io_manager.prompt_new_health_record(), still
    saved via data_manager.add_health_record()) or as a full AI-pipeline
    processed record (metric keys nested under "metrics" - see
    data_manager.save_record(), which stores exactly what
    process_ai_record() below returns). Without this, reading historical
    records saved by the real AI pipeline silently found nothing, and
    trend/change detection never fired against real data.
    """
    if isinstance(record.get("metrics"), dict):
        return record["metrics"].get(metric)
    return record.get(metric)


def evaluate_health_metrics(
    current_metrics: Dict[str, Optional[float]],
    historical_records: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """
    Evaluate the current reading for each tracked metric against two
    severity tiers:

    1. URGENT - a multi-condition-free but immediate check: does the
       CURRENT reading alone cross URGENT_THRESHOLDS? A single
       dangerously high reading is worth flagging right away, without
       waiting for a pattern to emerge across visits.
    2. FLAGGED - a genuinely multi-conditional rule: the current
       reading must (a) exceed the lower TREND_FLAG_THRESHOLDS, AND
       (b) have been strictly increasing for the last three
       consecutive readings (today > previous visit > the visit before
       that). Either condition alone is not enough to flag.

    Assumes `historical_records` is sorted oldest to newest, so the
    most recent past visit is historical_records[-1].

    Args:
        current_metrics: flat dict from flatten_ai_metrics().
        historical_records: list of past health record dicts.

    Returns:
        A list of finding dicts, each with "metric", "status" ("URGENT"
        or "FLAGGED"), and "reason". Never mentions a disease name or a
        treatment - only describes the numbers and the pattern.
    """
    findings = []

    for metric in TRACKED_METRICS:
        current_val = current_metrics.get(metric)
        if current_val is None:
            continue  # nothing to evaluate for a metric that wasn't extracted

        label = METRIC_LABELS[metric]

        # --- Tier 1: immediate danger from this reading alone ---
        if current_val >= URGENT_THRESHOLDS[metric]:
            findings.append({
                "metric": label,
                "status": "URGENT",
                "reason": (
                    f"{label} reading of {current_val} is at a level that "
                    "usually warrants prompt medical attention."
                ),
            })
            continue  # already the most severe finding possible for this metric

        # --- Tier 2: multi-conditional persistent upward trend ---
        if current_val <= TREND_FLAG_THRESHOLDS[metric] or len(historical_records) < 2:
            continue

        past_1 = _get_metric_value(historical_records[-1], metric)
        past_2 = _get_metric_value(historical_records[-2], metric)

        if past_1 is not None and past_2 is not None and current_val > past_1 > past_2:
            findings.append({
                "metric": label,
                "status": "FLAGGED",
                "reason": (
                    f"{label} ({current_val}) is elevated and has been "
                    "rising for three consecutive readings."
                ),
            })

    return findings


def analyze_recent_changes(
    current_metrics: Dict[str, Optional[float]],
    historical_records: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """
    Compare the current metrics against only the single most recent
    past record, to give direct "this went up/down since last time"
    feedback. Deltas within RECENT_CHANGE_TOLERANCES are treated as
    normal fluctuation and are not reported.

    Args:
        current_metrics: flat dict from flatten_ai_metrics().
        historical_records: list of past health record dicts, assumed
            sorted oldest to newest.

    Returns:
        A list of change dicts, each with "metric", "status"
        ("CHANGED"), "assessment" ("improved"/"worsened"),
        "classification_changed" (bool), "previous_classification",
        "current_classification", and "feedback".
    """
    changes = []

    if not historical_records:
        return changes # no past data to compare against

    last_record = historical_records[-1]

    for metric in TRACKED_METRICS:
        current_val = current_metrics.get(metric)
        past_val = _get_metric_value(last_record, metric)

        # Explicit None-checks (not truthiness) so a genuine reading of
        # 0 is never mistaken for "no data".
        if current_val is None or past_val is None:
            continue

        delta = current_val - past_val
        past_class = _metric_classification(metric, past_val)
        current_class = _metric_classification(metric, current_val)
        classification_changed = past_class != current_class

        # A tiny numeric move is still notable if it crossed a
        # classification boundary (e.g. 181 -> 179 looks small, but
        # it's a genuine severe-to-normal transition) - report it even
        # though it's within the normal-fluctuation tolerance.
        if abs(delta) <= RECENT_CHANGE_TOLERANCES[metric] and not classification_changed:
            continue  # within normal day-to-day fluctuation

        label = METRIC_LABELS[metric]
        direction = "increased" if delta > 0 else "decreased"
        # All four tracked metrics use "higher is worse" thresholds
        # (see URGENT_THRESHOLDS/TREND_FLAG_THRESHOLDS above), so a
        # decrease is always the improving direction here. This labels
        # the change explicitly as "improved"/"worsened" so a later
        # summary never has to guess whether a change was good or bad -
        # it reads this classification instead of inventing one.
        assessment = "worsened" if delta > 0 else "improved" 

        if classification_changed:
            feedback = (
                f"Your {label.lower()} has changed from {past_class.lower()} "
                f"({past_val}) to {current_class.lower()} ({current_val}) "
                "since your last record."
            )
        else:
            feedback = (
                f"Your {label.lower()} has {direction} from {past_val} "
                f"to {current_val} since your last record "
                f"({assessment} - moved {'further from' if assessment == 'worsened' else 'closer to'} "
                "the typical reference range)."
            )

        changes.append({
            "metric": label,
            "status": "CHANGED",
            "assessment": assessment,
            "classification_changed": classification_changed,
            "previous_classification": past_class,
            "current_classification": current_class,
            "feedback": feedback,
        })

    return changes


# Forward-compatible safety utility: ai_manager.py's current output
# contract is purely numeric (see the module docstring) and contains no
# free-text AI explanation, so nothing in this pipeline calls this
# function today. It is kept here, tested and ready, for if/when a
# future AI-generated explanation field is added - it must be passed
# through this before ever reaching a user.
_FORBIDDEN_SINGLE_WORDS = ["diagnose", "disease", "prescribe", "treatment"]
_FORBIDDEN_PHRASES = ["stop taking", "increase dose", "decrease dose"]


# Adding Safety Guardrails
def enforce_safety_guardrails(ai_explanation: str) -> str:
    """
    Check free-text AI-generated explanation text for prohibited
    diagnostic/prescriptive language, and reject it wholesale if found.

    Args:
        ai_explanation: str - free-text explanation from an AI model.

    Returns:
        `ai_explanation` unchanged if it contains none of the forbidden
        words/phrases, or a fixed, safe replacement string if it does.
    """
    if not ai_explanation:
        return ai_explanation

    text_lower = ai_explanation.lower()

    for word in _FORBIDDEN_SINGLE_WORDS:
        if re.search(r"\b" + re.escape(word) + r"\w*\b", text_lower):
            return (
                "Safety Override: The AI generated restricted diagnostic "
                "language. Please discuss these health trends directly "
                "with your doctor."
            )

    for phrase in _FORBIDDEN_PHRASES:
        if phrase in text_lower:
            return (
                "Safety Override: The AI generated restricted diagnostic "
                "language. Please discuss these health trends directly "
                "with your doctor."
            )

    return ai_explanation


def generate_dynamic_summary(
    recent_changes: List[Dict[str, str]],
    urgent_findings: List[Dict[str, str]],
    flagged_trends: List[Dict[str, str]],
) -> str:
    """
    Build a short, plain-language summary purely from this module's own
    rule evaluations - never from raw AI-generated text. Because every
    word here comes from a fixed Python template rather than an LLM,
    "no diagnosing" is guaranteed structurally, not just by keyword
    filtering after the fact.

    Args:
        recent_changes: output of analyze_recent_changes().
        urgent_findings: findings from evaluate_health_metrics() with
            status "URGENT".
        flagged_trends: findings from evaluate_health_metrics() with
            status "FLAGGED".

    Returns:
        A summary string highlighting only significant changes and
        trends - never a diagnosis, never a treatment suggestion.
    """
    if not recent_changes and not urgent_findings and not flagged_trends:
        return "All tracked metrics are stable with no notable changes recorded."

    parts = []

    if urgent_findings:
        urgent_metrics = ", ".join(f["metric"] for f in urgent_findings)
        parts.append(
            f"Urgent: {urgent_metrics} at a level that usually warrants "
            "prompt medical attention"
        )

    if flagged_trends:
        flagged_metrics = ", ".join(f["metric"] for f in flagged_trends)
        parts.append(f"Persistent upward trend detected in: {flagged_metrics}")

    increases = [c["metric"] for c in recent_changes if "increased" in c["feedback"]]
    decreases = [c["metric"] for c in recent_changes if "decreased" in c["feedback"]]

    if increases:
        parts.append(f"Increased since last visit: {', '.join(increases)}")
    if decreases:
        parts.append(f"Decreased since last visit: {', '.join(decreases)}")

    parts.append("Please discuss these results with your doctor at your next consultation.")

    return " | ".join(parts)


def process_ai_record(
    ai_extracted: Optional[Dict[str, Any]],
    historical_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Main pipeline entry point. Takes ai_manager's raw extraction result
    (or None) plus the user's stored history, applies all business
    rules, and returns one finalized report dict ready for data_manager
    to store and for the UI to display.

    Args:
        ai_extracted: the dict ai_manager.call_ai_with_retry() returned,
            or None if the AI Manager could not produce a trustworthy
            result after retrying.
        historical_records: list of previously stored health record
            dicts (see data_manager.load_health_records()), assumed
            sorted oldest to newest.

    Returns:
        A dict with "metrics", "ai_extracted_date" (the report's own
        date as read by the AI Manager, "YYYY-MM-DD" or None - this
        module never invents a replacement for a None value itself),
        "urgent_findings", "flagged_trends", "recent_changes",
        "risk_score", "decision" (one of "REJECTED", "URGENT",
        "FLAGGED", "ACCEPTED"), "recommended_action",
        "requires_doctor_review", and "summary".
    """
    current_metrics = flatten_ai_metrics(ai_extracted)
    ai_extracted_date = _extract_report_date(ai_extracted)

    if all(value is None for value in current_metrics.values()):
        return {
            "metrics": current_metrics,
            "ai_extracted_date": ai_extracted_date,
            "urgent_findings": [],
            "flagged_trends": [],
            "recent_changes": [],
            "risk_score": 0,
            "decision": "REJECTED",
            "recommended_action": (
                "No reliable measurements could be extracted from this "
                "report. Please try uploading a clearer copy."
            ),
            "requires_doctor_review": False,
            "summary": (
                "No usable measurements were extracted from this report."
            ),
        }

    findings = evaluate_health_metrics(current_metrics, historical_records)
    urgent_findings = [f for f in findings if f["status"] == "URGENT"]
    flagged_trends = [f for f in findings if f["status"] == "FLAGGED"]
    recent_changes = analyze_recent_changes(current_metrics, historical_records)

    # A simple, transparent, rule-based score - not a black-box model
    # output - so it stays easy to explain and audit.
    risk_score = len(urgent_findings) * 2 + len(flagged_trends)

    if urgent_findings:
        decision = "URGENT"
        recommended_action = (
            "These readings fall outside typical safe ranges. Consider "
            "contacting a healthcare professional promptly rather than "
            "waiting for your next scheduled visit."
        )
    elif flagged_trends:
        decision = "FLAGGED"
        recommended_action = "Discuss these trends with your doctor at your next consultation."
    else:
        decision = "ACCEPTED"
        recommended_action = "No action needed - keep up with regular check-ups."

    summary = generate_dynamic_summary(recent_changes, urgent_findings, flagged_trends)

    return {
        "metrics": current_metrics,
        "ai_extracted_date": ai_extracted_date,
        "urgent_findings": urgent_findings,
        "flagged_trends": flagged_trends,
        "recent_changes": recent_changes,
        "risk_score": risk_score,
        "decision": decision,
        "recommended_action": recommended_action,
        "requires_doctor_review": bool(urgent_findings or flagged_trends),
        "summary": summary,
    }


# ==========================================
# DUMMY TEST SCRIPT (Local Execution Only)
# ==========================================
if __name__ == "__main__":
    import json

    # A fresh reading shaped exactly like ai_manager.call_ai_with_retry()
    # actually returns it (nested blood_pressure) - matches the
    # "severe" tier of the mock test reports used elsewhere in this
    # project, so this doubles as an integration sanity check.
    mock_ai_extracted = {
        "heart_rate": 138,
        "blood_pressure": {"systolic": 188, "diastolic": 122},
        "blood_glucose": 15.4,
        "report_date": "2026-09-22",
    }

    # Historical records use the flat key names data_manager actually
    # stores (see config.SUPPORTED_METRICS), sorted oldest to newest,
    # with a rising trend leading up to today's reading.
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

    print("--- Simulating an urgent + persistent-trend reading ---")
    result = process_ai_record(mock_ai_extracted, mock_history)
    print(json.dumps(result, indent=4))
