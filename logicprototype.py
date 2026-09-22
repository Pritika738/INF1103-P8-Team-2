"""
logic_manager.py

Responsible for business rules and domain logic only.
Acts as the "Domain Brain" - applies clinical thresholds to AI-enriched records.

Rules for this module:
- No print() or input() calls here (except in the isolated test block).
- No network/AI calls here.
- No file operations here.
- Purely evaluates dictionaries/lists to flag, route, or reject data.
"""

from typing import Dict, List, Any


# Clinical tolerance buffers used only by analyze_recent_changes().
# A day-to-day delta within these bounds is treated as normal fluctuation
# and is NOT reported as a "CHANGED" metric. This has no effect on
# evaluate_health_metrics(), which keeps using its own hard thresholds.
RECENT_CHANGE_TOLERANCES: Dict[str, float] = {
    "systolic_bp": 5,
    "diastolic_bp": 4,
    "blood_glucose": 0.5,
    "heart_rate": 5,
}


def evaluate_health_metrics(current_metrics: Dict[str, Any], historical_records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Evaluates new metrics against historical data using a multi-condition rule.
    Strictly limited to evaluating Blood Pressure, Blood Glucose, and Heart Rate.
    Checks for a persistent 3-step upward trend.
    """
    findings = []
    
    # Extract only the allowed metrics from the AI output (defaulting to 0 if missing)
    sys_bp = current_metrics.get("systolic_bp", 0)
    dia_bp = current_metrics.get("diastolic_bp", 0)
    glucose = current_metrics.get("blood_glucose", 0.0)
    heart_rate = current_metrics.get("heart_rate", 0)

    # We need at least 2 past records to check a persistent 3-step trend
    if len(historical_records) >= 2:
        # Assuming historical_records are sorted chronologically
        past_1 = historical_records[-1]
        past_2 = historical_records[-2]

        # 1a. Multi-Condition Rule for Systolic Blood Pressure
        past_1_sys = past_1.get("systolic_bp", 0)
        past_2_sys = past_2.get("systolic_bp", 0)
        
        if sys_bp > 130 and (sys_bp > past_1_sys > past_2_sys):
            findings.append({
                "metric": "Systolic Blood Pressure",
                "status": "FLAGGED",
                "reason": f"Elevated systolic reading ({sys_bp} mmHg) with a persistent upward trend."
            })

        # 1b. Multi-Condition Rule for Diastolic Blood Pressure
        past_1_dia = past_1.get("diastolic_bp", 0)
        past_2_dia = past_2.get("diastolic_bp", 0)
        
        if dia_bp > 80 and (dia_bp > past_1_dia > past_2_dia):
            findings.append({
                "metric": "Diastolic Blood Pressure",
                "status": "FLAGGED",
                "reason": f"Elevated diastolic reading ({dia_bp} mmHg) with a persistent upward trend."
            })

        # 2. Multi-Condition Rule for Blood Glucose
        past_1_gluc = past_1.get("blood_glucose", 0.0)
        past_2_gluc = past_2.get("blood_glucose", 0.0)
        
        if glucose > 7.0 and (glucose > past_1_gluc > past_2_gluc):
            findings.append({
                "metric": "Blood Glucose",
                "status": "FLAGGED",
                "reason": f"Elevated fasting glucose ({glucose} mmol/L) with a persistent upward trend."
            })

        # 3. Multi-Condition Rule for Heart Rate
        past_1_hr = past_1.get("heart_rate", 0)
        past_2_hr = past_2.get("heart_rate", 0)
        
        if heart_rate > 100 and (heart_rate > past_1_hr > past_2_hr):
            findings.append({
                "metric": "Heart Rate",
                "status": "FLAGGED",
                "reason": f"Elevated resting heart rate ({heart_rate} bpm) with a persistent upward trend."
            })
            
    return findings


def analyze_recent_changes(current_metrics: Dict[str, Any], historical_records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Compares the current metrics strictly against the most recent past record
    to generate direct feedback on what has changed.
    Restricted to Blood Pressure, Blood Glucose, and Heart Rate.

    Minor day-to-day fluctuations within RECENT_CHANGE_TOLERANCES are treated
    as stable and are not reported here.
    """
    changes = []
    
    if not historical_records:
        return changes # No past data to compare against
        
    last_record = historical_records[-1] # Get the most recent past visit
    
    # Strictly limited to your targeted metrics
    metrics_to_track = [
        "systolic_bp", 
        "diastolic_bp", 
        "blood_glucose", 
        "heart_rate"
    ]
    
    for metric in metrics_to_track:
        current_val = current_metrics.get(metric)
        past_val = last_record.get(metric)
        
        # Only compare if both records have valid, non-zero numbers
        if current_val and past_val and current_val != past_val:
            delta = current_val - past_val
            tolerance = RECENT_CHANGE_TOLERANCES.get(metric, 0)

            # Within the clinical tolerance buffer -> normal fluctuation, skip it
            if abs(delta) <= tolerance:
                continue

            direction = "increased" if current_val > past_val else "decreased"
            clean_name = metric.replace("_", " ").title()
            
            changes.append({
                "metric": clean_name,
                "status": "CHANGED",
                "feedback": f"Your {clean_name} has {direction} from {past_val} to {current_val} since your last record."
            })
            
    return changes


def enforce_safety_guardrails(ai_explanation: str) -> str:
    """
    Evaluates the AI's plain-English text for prohibited diagnostic phrasing.
    Outcome: Rejects and overrides prescriptive language to maintain safety boundaries.
    """
    forbidden_words = ["diagnose", "disease", "prescribe", "treatment", "stop taking", "increase dose"]
    text_lower = ai_explanation.lower()
    
    for word in forbidden_words:
        if word in text_lower:
            # REJECT the AI output and ROUTE to a safe, standardized prompt
            return "Safety Override: The AI generated restricted diagnostic language. Please discuss these health trends directly with your doctor."
            
    # ACCEPT if no forbidden words are found
    return ai_explanation


def generate_dynamic_summary(recent_changes: List[Dict[str, str]], persistent_trends: List[Dict[str, str]], raw_ai_summary: str) -> str:
    """
    Dynamically generates a summary string based on the Python evaluation results.
    Integrates safety guardrails and adapts to metric changes automatically.
    """
    # 1. Enforce guardrail safety check first
    safe_summary = enforce_safety_guardrails(raw_ai_summary)
    if "Safety Override" in safe_summary:
        return safe_summary

    # 2. If no metrics changed, return a default clear status
    if not recent_changes and not persistent_trends:
        return "All tracked metrics are stable with no notable changes recorded."

    # 3. Build a dynamic feedback summary based on Python evaluation
    summary_parts = []
    
    increases = [item['metric'] for item in recent_changes if 'increased' in item['feedback']]
    decreases = [item['metric'] for item in recent_changes if 'decreased' in item['feedback']]
    
    if increases:
        summary_parts.append(f"Increased: {', '.join(increases)}")
    if decreases:
        summary_parts.append(f"Decreased: {', '.join(decreases)}")
        
    if persistent_trends:
        flagged_metrics = [t['metric'] for t in persistent_trends]
        summary_parts.append(f"Persistent upward trend detected in: {', '.join(flagged_metrics)}")

    return " | ".join(summary_parts)


def process_ai_record(ai_json_output: Dict[str, Any], historical_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    The main pipeline function for the logic manager. 
    Takes the raw AI dictionary, applies all business rules, and returns a finalized 
    report dictionary ready for the data_manager to save.
    """
    # 1. Ensure we only pull the extracted metrics dictionary
    extracted_metrics = ai_json_output.get("extracted_metrics", {})
    
    # 2. Check for long-term trends (Multi-condition logic)
    persistent_trends = evaluate_health_metrics(extracted_metrics, historical_records)
    
    # 3. Check for immediate changes (Last Visit vs Today)
    recent_changes = analyze_recent_changes(extracted_metrics, historical_records)
    
    # 4. Generate a DYNAMIC summary based on actual variable evaluations
    dynamic_summary = generate_dynamic_summary(
        recent_changes, 
        persistent_trends, 
        ai_json_output.get("plain_english_summary", "")
    )
    
    # 5. Package the final validated outcome for the Data Manager
    has_flags = len(persistent_trends) > 0 or len(recent_changes) > 0
    
    final_report = {
        "metrics": {
            "systolic_bp": extracted_metrics.get("systolic_bp"),
            "diastolic_bp": extracted_metrics.get("diastolic_bp"),
            "blood_glucose": extracted_metrics.get("blood_glucose"),
            "heart_rate": extracted_metrics.get("heart_rate")
        },
        "persistent_trends": persistent_trends,
        "recent_changes": recent_changes,
        "summary": dynamic_summary,
        "requires_doctor_review": has_flags,
        "decision": "FLAGGED" if has_flags else "NORMAL"
    }
    
    return final_report


# ==========================================
# DUMMY TEST SCRIPT (Local Execution Only)
# ==========================================
if __name__ == "__main__":
    import json
    import os

    def load_ai_output(filename="mock_ai_output.json"):
        """
        Loads the AI-generated JSON output from a file safely 
        inside the test block to avoid rule violations.
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, filename)

        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        
        # Fallback dummy data if the mock file doesn't exist yet
        return {
            "extracted_metrics": {
                "systolic_bp": 128,
                "diastolic_bp": 76,
                "blood_glucose": 6.7,
                "heart_rate": 95
            },
            "plain_english_summary": "Your latest blood test shows an increase."
        }

    # 1. Historical records
    mock_history = [
        {"date": "2023-01-15", "systolic_bp": 129, "diastolic_bp": 79, "blood_glucose": 6.8, "heart_rate": 94},
        {"date": "2024-01-20", "systolic_bp": 128, "diastolic_bp": 80, "blood_glucose": 7.0, "heart_rate": 96}
    ]

    # 2. Load the current AI output from file
    mock_ai_output = load_ai_output("mock_ai_output.json")

    # 3. Run the Logic Manager pipeline
    print("--- Simulating Persistent Upward Trend Test ---")
    processed_result = process_ai_record(mock_ai_output, mock_history)
    
    print(json.dumps(processed_result, indent=4))