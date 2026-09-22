import json
import os


def evaluate_health_metrics(current_metrics, historical_records):
    """
    Evaluates new metrics against historical data using a multi-condition rule.
    Strictly limited to evaluating Blood Pressure, Blood Glucose, and Heart Rate.
    """
    findings = []

    # Extract only the 3 allowed metrics from the AI output (defaulting to 0 if missing)
    sys_bp = current_metrics.get("systolic_bp", 0)
    dia_bp = current_metrics.get("diastolic_bp", 0)
    glucose = current_metrics.get("blood_glucose", 0.0)
    heart_rate = current_metrics.get("heart_rate", 0)

    # We need at least 2 past records to check a persistent 3-step trend
    if len(historical_records) >= 2:
        # Assuming historical_records are sorted chronologically
        past_1 = historical_records[-1]
        past_2 = historical_records[-2]

        # 1. Multi-Condition Rule for Blood Pressure
        past_1_sys = past_1.get("systolic_bp", 0)
        past_2_sys = past_2.get("systolic_bp", 0)

        if sys_bp > 130 and (sys_bp > past_1_sys > past_2_sys):
            findings.append({
                "metric": "Blood Pressure",
                "status": "FLAGGED",
                "reason": f"Elevated systolic reading ({sys_bp} mmHg) with a persistent upward trend."
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


def enforce_safety_guardrails(ai_explanation):
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


def process_ai_record(ai_json_output, historical_records):
    """
    The main pipeline function for the logic manager.
    Takes the raw AI dictionary, applies all business rules, and returns a finalized
    report dictionary ready for the data_manager to save.
    """
    # 1. Ensure we only pull the extracted metrics dictionary
    extracted_metrics = ai_json_output.get("extracted_metrics", {})

    # 2. Check for trends (Multi-condition logic)
    trend_alerts = evaluate_health_metrics(extracted_metrics, historical_records)

    # 3. Enforce guardrails on the AI's summary
    safe_summary = enforce_safety_guardrails(ai_json_output.get("plain_english_summary", ""))

    # 4. Package the final validated outcome for the Data Manager
    final_report = {
        "metrics": {
            "systolic_bp": extracted_metrics.get("systolic_bp"),
            "diastolic_bp": extracted_metrics.get("diastolic_bp"),
            "blood_glucose": extracted_metrics.get("blood_glucose"),
            "heart_rate": extracted_metrics.get("heart_rate")
        },
        "alerts": trend_alerts,
        "summary": safe_summary,
        "requires_doctor_review": len(trend_alerts) > 0,
        "decision": "FLAGGED" if len(trend_alerts) > 0 else "NORMAL"
    }

    return final_report


def load_ai_output(filename="mock_ai_output.json"):
    """
    Loads the AI-generated JSON output from a file located in the same
    directory as this script.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, filename)

    with open(file_path, "r") as f:
        return json.load(f)


# ==========================================
# DUMMY TEST SCRIPT (Local Execution Only)
# ==========================================
if __name__ == "__main__":
    # Mock historical records loaded by Data Manager
    mock_history = [
        {"date": "2023-01-15", "systolic_bp": 118, "diastolic_bp": 75, "blood_glucose": 5.4, "heart_rate": 72},
        {"date": "2024-01-20", "systolic_bp": 125, "diastolic_bp": 78, "blood_glucose": 6.1, "heart_rate": 78}
    ]

    # Fetch the AI-generated output from the sample JSON file in this directory
    mock_ai_output = load_ai_output("mock_ai_output.json")

    # Run the Logic Manager pipeline
    print("--- Simulating Logic Manager Pipeline ---")
    processed_result = process_ai_record(mock_ai_output, mock_history)

    print(json.dumps(processed_result, indent=4))
