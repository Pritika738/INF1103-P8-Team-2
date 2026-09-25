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

from pydantic import BaseModel, Field
from typing import List, Optional
from typing import Dict, Optional
from ai_manager import AIManager

PROMPT_TEMPLATES: Dict[str, str] = {
    "vital": (
        "You are a data extraction assistant. You will be given a medical report as a PDF or image.\n\n"
        "Extract the following health metrics if they are clearly visible in the report: heart rate, blood pressure (systolic and diastolic), and blood glucose.\n\n"
        "Respond with ONLY valid JSON and nothing else - no markdown formatting, no code fences (```), no explanation, and no text before or after the JSON.\n\n"
        "The JSON must contain exactly these fields, with no additional fields:\n"
        'If no blood pressure reading is visible at all, set "blood_pressure" itself to null instead of guessing either value.\n\n'
        "Rules you must follow:\n"
        "- Do not diagnose any medical condition.\n"
        "- Do not recommend or suggest any treatment, medication, or dosage.\n"
        "- Do not invent, estimate, or guess a value that is not clearly present in the report - use null instead.\n"
        "- Do not include any field other than heart_rate, blood_pressure, and blood_glucose."
    ),
    
    "extract": (
        "You are a compassionate clinical communication assistant. Your task is to process "
        "this medical document to extract data, synthesize findings, and flag key follow-ups.\n\n"
        "INSTRUCTIONS:\n"
        "- Extract all visible numerical health metrics and vital signs.\n"
        "- Write a patient-friendly summary explaining the document's contents in clear, comforting language.\n"
        "- Flag critical, actionable areas or specific follow-up appointments the patient needs to remember.\n\n"
        "CRITICAL SAFETY & QUALITY RULES:\n"
        "- Do not provide a novel clinical diagnosis. Only summarize what the document states.\n"
        "- Do not suggest or prescribe medications, treatments, or alternative therapies.\n"
        "- Stick strictly to the text provided. Do not guess or infer missing clinical data."
        
    ),
    
    "summary": (
        "You are a document processing assistant.\n\n"
        "Extract general administrative information from the medical report.\n\n"
        "Respond with ONLY valid JSON strictly matching this structure:\n"
        "{\n"
        '  "provider_name": <string or null>,\n'
        '  "report_date": <string YYYY-MM-DD or null>,\n'
        '  "document_type": <string or null>\n'
        "}\n\n"
        "Rules:\n"
        "- Do not invent details; use null if not visible."
    )
}

# 1. Database Mapping Schema
class VitalsReading(BaseModel):
    date: str = Field(description="The date of the report or reading formatted as YYYY-MM-DD")
    blood_pressure: Optional[str] = Field(None, description="The blood pressure reading, e.g., '140/80'")
    heart_rate: Optional[int] = Field(None, description="The pulse/heart rate value as an integer bpm")
    blood_glucose: Optional[str] = Field(None, description="The blood glucose value if present, otherwise null")

# 2. Key Action Item / Alert Schema
class PatientAlert(BaseModel):
    topic: str = Field(description="The category of the alert (e.g., Medication, Vitals, Follow-up)")
    criticality: str = Field(description="Severity indicator: 'High', 'Medium', or 'Low'")
    message: str = Field(description="Clear, actionable advice on what the patient needs to watch out for or do")

# 3. Complete API Payload Structure
class ComprehensiveMedicalAnalysis(BaseModel):
    # For your database
    database_vitals: VitalsReading = Field(description="Cleaned numeric and structured health metrics for DB storage")
    
    # For your user interface
    patient_summary: str = Field(description="A friendly, clear 2-3 sentence overview of the medical report written directly to the patient.")
    action_items: List[PatientAlert] = Field(description="Important flags, medications to continue, or next steps the user must remember.")


def process_medical_report(uploadedFile):
    prompt = PROMPT_TEMPLATES["extract"]

    # Calls AI Manager dynamically with its own domain schemas
    raw_ai_response = AIManager.ExtractFields(
        payload=uploadedFile,
        prompt_text=prompt,
        schema=ComprehensiveMedicalAnalysis # Domain schema lives here
    )
    
    # Save to database, trigger alerts if blood pressure is too high, etc.
    #database.save(raw_ai_response.database_vitals) 
    
    return raw_ai_response

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
