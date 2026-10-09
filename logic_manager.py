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
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from ai_manager import ai_manager
from config import DATA_DIR
import os, json

# Prompt templates for to prompt AI
PROMPT_TEMPLATES: Dict[str, str] = {    
    "extract": (
        "You are a compassionate clinical communication assistant. Your task is to process "
        "this medical document to extract data, synthesize findings, and flag key follow-ups.\n\n"
        "INSTRUCTIONS:\n"
        "- Extract all visible numerical health metrics and vital signs.\n"
        "- Write a patient-friendly summary explaining the document's contents in clear, comforting language.\n"
        "- Flag critical, actionable areas or specific follow-up appointments the patient needs to remember.\n\n"
        
        # 🔧 CRITICAL FIX: Directing the model to omit structural wrappers
        "JSON STRUCTURING RULE:\n"
        "- Do NOT wrap properties with text labels like 'VitalsReading(...)' or 'PatientAlert(...)'.\n"
        "- Output all fields strictly as standard, raw JSON objects, values, and lists.\n\n"
        
        "CRITICAL SAFETY & QUALITY RULES:\n"
        "- Do not include and personal details of the paitient in the summary"
        "- Do not provide a novel clinical diagnosis. Only summarize what the document states.\n"
        "- Do not suggest or prescribe medications, treatments, or alternative therapies.\n"
        "- Stick strictly to the text provided. Do not guess or infer missing clinical data."
        
    ),
    
    "summary": (
        "You are an advanced clinical analytics specialist. You will be provided with a "
        "chronological list of multiple historical health records belonging to the same patient.\n\n"
        "HISTORICAL PATIENT DATA:\n"
        "{json_data}\n\n" # Required*** DO NOT REMOVE
        "INSTRUCTIONS:\n"
        "- Analyze these reports sequentially from the oldest file date to the newest.\n"
        "- Identify clear metric trajectories, systemic trends, and escalating shifts.\n"
        "- Explicitly pull out any deteriorating vital paths into your critical focus areas.\n\n"
        "CRITICAL RULES:\n"
        "- Focus strictly on comparing the provided historical data points. Do not guess records.\n"
        "- Map your synthesis fields precisely to match the properties required by the schema."
    )
}

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
# NOT reported as a "CHANGED" metric by analyze_recent_changes(). This
# has no effect on evaluate_health_metrics(), which uses the thresholds
# above instead.
RECENT_CHANGE_TOLERANCES = {
    "blood_pressure_systolic": 5,
    "blood_pressure_diastolic": 4,
    "blood_glucose": 0.5,
    "heart_rate": 5,
}


# 1.1 Schema for summary
class TrendMetric(BaseModel):
    metric: str = Field(description="The health metric being tracked (e.g., Blood Pressure, Heart Rate)")
    direction: str = Field(description="The trend trajectory over time: 'Improving', 'Worsening', or 'Stable'")
    observation: str = Field(description="A brief description of what the numbers show over the dates.")

# 1.2 Schema for summary
class TrendAnalysis(BaseModel):
    date: str = Field(description="Today's date formatted as YYYY-MM-DD")
    overall_health_trajectory: str = Field(description="A 3-4 sentence high-level overview of how the patient is progressing across all reports.")
    key_areas_of_concern: List[str] = Field(description="Bullet points of specific metrics or symptoms that need immediate medical review.")
    tracked_trends: List[TrendMetric] = Field(description="A list breakdown of each individual vital sign's trend trajectory.")


# 2.2 Schema for data extraction
class MedicalAnalysis(BaseModel):
    # Saving vitals in report
    date: str = Field(description="The date of the report or reading formatted as YYYY-MM-DD")
    blood_pressure: Optional[str] = Field(None, description="The blood pressure reading, e.g., '140/80'")
    heart_rate: Optional[int] = Field(None, description="The pulse/heart rate value as an integer bpm")
    blood_glucose: Optional[str] = Field(None, description="The blood glucose value if present, otherwise null")

    # Generate a summary
    patient_summary: str = Field(description="A friendly, clear 2-3 sentence overview of the medical report written directly to the patient.")


def process_vitals_extraction(file_bytes: bytes, mime_type: str):
    print("extracting... ")
    
    prompt_text = PROMPT_TEMPLATES.get("extract", "Extract data fields cleanly.")

    # Call AI Manager
    raw_json = ai_manager.call_ai_structured(
        file_bytes=file_bytes,
        mime_type=mime_type,
        prompt=prompt_text,     # Prompt from PROMPT_TEMPLATE for easy edit
        schema=MedicalAnalysis     # Injected dynamic typing reference
    )

    # Return the response
    return raw_json

def process_summary_report():
    all_reports = []

    # Read all saved JSON report files in DATA_DIR
    if os.path.exists(DATA_DIR):
        for filename in sorted(os.listdir(DATA_DIR)):
            if filename.startswith("report_") and filename.endswith(".json"):
                file_path = os.path.join(DATA_DIR, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    all_reports.append(json.load(f))

    # If no report is detected
    if not all_reports:
        raise ValueError("No historical reports found in the data directory to analyze.")

    # Create prompt
    base_template = PROMPT_TEMPLATES["summary"]
    if not base_template:
        raise ValueError("The 'summary' prompt template is missing from global configurations.")
        
    final_prompt = base_template.format(json_data=json.dumps(all_reports, indent=2)) #json_data in prompt

    # Call AI Manager
    raw_json = ai_manager.call_ai_structured_no_file(
        prompt=final_prompt,
        schema=TrendAnalysis
    )

    # Return AI response
    return raw_json

def save_analysis_by_report_date(analysis_data , reporttype:str) -> str:
    """
    Saves the validated Pydantic model payload as a clean JSON file,
    naming it after the extracted report date.
    """
    print("Saving...")

    # Ensure the destination folder exists safely
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Extract the date from the json file
    data_dict = json.loads(analysis_data)
    report_date = data_dict["date"]
    
    # Remove characters that are illegal in file names and replace to '_'
    safe_filename = report_date.replace("/", "-").replace(" ", "_")
    file_path = os.path.join(DATA_DIR, f"{reporttype}_{safe_filename}.json")
    
    # Save the json file as 'report_{date}.json'
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, indent=2, ensure_ascii=False)
        
    return file_path



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

        past_1 = historical_records[-1].get(metric)
        past_2 = historical_records[-2].get(metric)

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
        ("CHANGED"), and "feedback".
    """
    changes = []

    if not historical_records:
        return changes  # no past data to compare against

    last_record = historical_records[-1]

    for metric in TRACKED_METRICS:
        current_val = current_metrics.get(metric)
        past_val = last_record.get(metric)

        # Explicit None-checks (not truthiness) so a genuine reading of
        # 0 is never mistaken for "no data".
        if current_val is None or past_val is None:
            continue

        delta = current_val - past_val
        if abs(delta) <= RECENT_CHANGE_TOLERANCES[metric]:
            continue  # within normal day-to-day fluctuation

        label = METRIC_LABELS[metric]
        direction = "increased" if delta > 0 else "decreased"

        changes.append({
            "metric": label,
            "status": "CHANGED",
            "feedback": (
                f"Your {label.lower()} has {direction} from {past_val} "
                f"to {current_val} since your last record."
            ),
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
        A dict with "metrics", "urgent_findings", "flagged_trends",
        "recent_changes", "risk_score", "decision" (one of "REJECTED",
        "URGENT", "FLAGGED", "ACCEPTED"), "recommended_action",
        "requires_doctor_review", and "summary".
    """
    current_metrics = flatten_ai_metrics(ai_extracted)

    if all(value is None for value in current_metrics.values()):
        return {
            "metrics": current_metrics,
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
        "urgent_findings": urgent_findings,
        "flagged_trends": flagged_trends,
        "recent_changes": recent_changes,
        "risk_score": risk_score,
        "decision": decision,
        "recommended_action": recommended_action,
        "requires_doctor_review": bool(urgent_findings or flagged_trends),
        "summary": summary,
    }



