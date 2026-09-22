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

def evaluate_health_metrics(current_metrics, historical_records):
    """
    Evaluates new metrics against historical data using a multi-condition rule.
    Strictly limited to evaluating Blood Pressure, Blood Glucose, and Heart Rate.
    Checks for a persistent 3-step upward trend.
    """
    findings = []
    
    # Extract only the allowed metrics from the AI output (defaulting to 0 if missing)
    sys_bp = current_metrics.get("systolic_bp", 0)
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


def analyze_recent_changes(current_metrics, historical_records):
    """
    Compares the current metrics strictly against the most recent past record
    to generate direct feedback on what has changed.
    Restricted to Blood Pressure, Blood Glucose, and Heart Rate.
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
            direction = "increased" if current_val > past_val else "decreased"
            clean_name = metric.replace("_", " ").title()
            
            changes.append({
                "metric": clean_name,
                "status": "CHANGED",
                "feedback": f"Your {clean_name} has {direction} from {past_val} to {current_val} since your last record."
            })
            
    return changes


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
    
    # 2. Check for long-term trends (Multi-condition logic)
    persistent_trends = evaluate_health_metrics(extracted_metrics, historical_records)
    
    # 3. Check for immediate changes (Last Visit vs Today)
    recent_changes = analyze_recent_changes(extracted_metrics, historical_records)
    
    # 4. Enforce guardrails on the AI's summary
    safe_summary = enforce_safety_guardrails(ai_json_output.get("plain_english_summary", ""))
    
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
        "summary": safe_summary,
        "requires_doctor_review": has_flags,
        "decision": "FLAGGED" if has_flags else "NORMAL"
    }
    
    return final_report


# ==========================================
# DUMMY TEST SCRIPT (Local Execution Only)
# ==========================================
if __name__ == "__main__":
    # Mock historical records loaded by Data Manager
    mock_history = [
        {"date": "2023-01-15", "systolic_bp": 118, "diastolic_bp": 75, "blood_glucose": 5.4, "heart_rate": 72},
        {"date": "2024-01-20", "systolic_bp": 125, "diastolic_bp": 78, "blood_glucose": 6.1, "heart_rate": 78}
    ]

    # Mock output generated by AI Manager after scanning a PDF
    mock_ai_output = {
        "extracted_metrics": {
            "systolic_bp": 135,
            "diastolic_bp": 82,
            "blood_glucose": 7.5,
            "heart_rate": 85,
            "unrelated_metric": 45  # The logic manager will ignore this
        },
        "plain_english_summary": "Your latest blood test shows an increase. I diagnose you with hypertension."
    }

    # Run the Logic Manager pipeline
    print("--- Simulating Logic Manager Pipeline ---")
    processed_result = process_ai_record(mock_ai_output, mock_history)
    
    import json
    print(json.dumps(processed_result, indent=4))