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
        "CRITICAL SAFETY & QUALITY RULES:\n"
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

# 1.1 Schema for summary
class TrendMetric(BaseModel):
    metric: str = Field(description="The health metric being tracked (e.g., Blood Pressure, Heart Rate)")
    direction: str = Field(description="The trend trajectory over time: 'Improving', 'Worsening', or 'Stable'")
    observation: str = Field(description="A brief description of what the numbers show over the dates.")

# 1.2 Schema for summary
class TrendAnalysis(BaseModel):
    overall_health_trajectory: str = Field(description="A 3-4 sentence high-level overview of how the patient is progressing across all reports.")
    key_areas_of_concern: List[str] = Field(description="Bullet points of specific metrics or symptoms that need immediate medical review.")
    tracked_trends: List[TrendMetric] = Field(description="A list breakdown of each individual vital sign's trend trajectory.")

# 2.1 Schema for data extraction
class VitalsReading(BaseModel):
    date: str = Field(description="The date of the report or reading formatted as YYYY-MM-DD")
    blood_pressure: Optional[str] = Field(None, description="The blood pressure reading, e.g., '140/80'")
    heart_rate: Optional[int] = Field(None, description="The pulse/heart rate value as an integer bpm")
    blood_glucose: Optional[str] = Field(None, description="The blood glucose value if present, otherwise null")

# 2.2 Schema for data extraction
class PatientAlert(BaseModel):
    topic: str = Field(description="The category of the alert (e.g., Medication, Vitals, Follow-up)")
    criticality: str = Field(description="Severity indicator: 'High', 'Medium', or 'Low'")
    message: str = Field(description="Clear, actionable advice on what the patient needs to watch out for or do")

# 2.3 Schema for data extraction
class ComprehensiveMedicalAnalysis(BaseModel):
    # For your database
    database_vitals: VitalsReading = Field(description="Cleaned numeric and structured health metrics for DB storage")
    
    # For your user interface
    patient_summary: str = Field(description="A friendly, clear 2-3 sentence overview of the medical report written directly to the patient.")
    action_items: List[PatientAlert] = Field(description="Important flags, medications to continue, or next steps the user must remember.")


def process_vitals_extraction(file_bytes: bytes, mime_type: str) -> ComprehensiveMedicalAnalysis:
    print("extracting... ")
    
    prompt_text = PROMPT_TEMPLATES.get("extract", "Extract data fields cleanly.")

    # Call AI Manager
    raw_json = ai_manager.call_ai_structured(
        file_bytes=file_bytes,
        mime_type=mime_type,
        prompt=prompt_text,     # Prompt from PROMPT_TEMPLATE for easy edit
        schema=ComprehensiveMedicalAnalysis     # Injected dynamic typing reference
    )

    print("extraction complete!")
    # Return the validated Python object
    return ComprehensiveMedicalAnalysis.model_validate_json(raw_json)

def process_summary_report() -> TrendAnalysis:
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

    # Return the validated Python object
    return TrendAnalysis.model_validate_json(raw_json)

def save_analysis_by_report_date(analysis_data: ComprehensiveMedicalAnalysis) -> str:
    """
    Saves the validated Pydantic model payload as a clean JSON file,
    naming it after the extracted report date.
    """
    # Ensure the destination folder exists safely
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Extract the date from the json file
    # If the date field is empty or missing, fallback cleanly to avoid a crash
    report_date = None
    if analysis_data.database_vitals:
        report_date = getattr(analysis_data.database_vitals, "date", None)
        
    if not report_date:
        from datetime import datetime
        report_date = f"unknown_date_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
    # Remove characters that are illegal in file names and replace to '_'
    safe_filename = str(report_date).replace("/", "-").replace(" ", "_")
    file_path = os.path.join(DATA_DIR, f"report_{safe_filename}.json")
    
    # Save the json file as 'report_{date}.json'
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(analysis_data.model_dump(), f, indent=2, ensure_ascii=False)
        
    return file_path

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
