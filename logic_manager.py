"""
logic_manager.py

Responsible for business rules and domain logic only.

Rules for this module:
- No print() or input() calls here.
- No network/AI calls here.
- No file operations here - this module works purely on data passed
  to it by other modules (e.g. lists/dicts of health records).

All functions below are placeholders for future business logic and
currently return simple, safe default values.
"""


def analyse_health_trends(records):
    """
    Placeholder for future long-term health trend analysis.

    Intended to compare a metric (e.g. systolic blood pressure) across
    multiple historical records and detect sustained upward/downward
    trends.

    Args:
        records: list of health record dictionaries.

    Returns:
        A list of trend findings (currently empty - not yet implemented).
    """
    # TODO: implement multi-record trend detection.
    return []


def verify_medication_dosage(medication_name, dosage):
    """
    Placeholder for future medication dosage verification logic.

    Intended to check a given dosage against known safe ranges for the
    named medication.

    Args:
        medication_name: str
        dosage: str or number representing the dosage.

    Returns:
        A dict describing the verification result (currently a stub).
    """
    # TODO: implement dosage range checks.
    return {"medication_name": medication_name, "is_verified": False, "notes": "Not implemented yet."}


def verify_allergy_information(allergies):
    """
    Placeholder for future allergy information verification logic.

    Intended to cross-check reported allergies against known allergens
    and flag potential conflicts with medications.

    Args:
        allergies: list of allergy strings.

    Returns:
        A list of verification findings (currently empty - not yet implemented).
    """
    # TODO: implement allergy cross-checking.
    return []


def select_findings_for_report(ai_findings):
    """
    Placeholder for future logic that decides which AI-generated
    findings are important enough to include in the consultation
    report.

    Args:
        ai_findings: list of findings produced by ai_manager.

    Returns:
        A list of findings selected for the report (currently returns
        all findings unfiltered, as a safe default).
    """
    # TODO: implement filtering/prioritisation rules.
    return list(ai_findings) if ai_findings else []

#test

"""
logic_manager.py

Responsible for business rules and domain logic only.
Acts as the "Domain Brain" - applies clinical thresholds to AI-enriched records.

Rules for this module:
- No print() or input() calls here.
- No network/AI calls here.
- Purely evaluates dictionaries/lists to flag, route, or reject data.
"""

def detect_persistent_trends(new_metrics, historical_records):
    """
    Evaluates new metrics against historical data using a multi-condition rule.
    Outcome: Flags a 'Notable Change' if a metric breaches clinical thresholds 
    AND shows a sustained upward trend across 3 consecutive records.
    """
    findings = []
    
    # We need at least 2 past records + 1 new record to check a 3-step trend
    if len(historical_records) >= 2:
        # Extract the last two historical systolic values (assuming chronological order)
        past_1 = historical_records[-1].get("systolic_bp", 0)
        past_2 = historical_records[-2].get("systolic_bp", 0)
        current = new_metrics.get("systolic_bp", 0)

        # MULTI-CONDITION RULE: Is BP elevated (> 130) AND persistently rising?
        if current > 130 and (current > past_1 > past_2):
            findings.append({
                "metric": "Systolic Blood Pressure",
                "status": "FLAGGED",
                "reason": f"Elevated reading ({current} mmHg) with a persistent upward trend across 3 records."
            })
            
        # You can replicate this exact logic block for Fasting Glucose or Heart Rate
        
    return findings


def enforce_safety_guardrails(ai_explanation):
    """
    Evaluates the AI's plain-English text for prohibited diagnostic phrasing.
    Outcome: Rejects and overrides prescriptive language to maintain the safety boundary.
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
    # 1. Check for trends (Multi-condition logic)
    trend_alerts = detect_persistent_trends(ai_json_output.get("extracted_metrics", {}), historical_records)
    
    # 2. Enforce guardrails on the AI's summary
    safe_summary = enforce_safety_guardrails(ai_json_output.get("plain_english_summary", ""))
    
    # 3. Package the final validated outcome
    final_report = {
        "metrics": ai_json_output.get("extracted_metrics", {}),
        "alerts": trend_alerts,
        "summary": safe_summary,
        "requires_doctor_review": len(trend_alerts) > 0
    }
    
    return final_report