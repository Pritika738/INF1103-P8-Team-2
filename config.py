"""
config.py

Central place for configuration constants used across the application.
No secrets (e.g. API keys) should be hardcoded here - those are loaded
from environment variables (see .env / load_env_variables in this file).
"""

import os
from pydantic import BaseModel, Field
from typing import List, Optional
from dotenv import load_dotenv

# Load variables from a local .env file (if present) into the environment.
load_dotenv()

# --- File paths -------------------------------------------------------

# Location of the local JSON "database" that stores health records.
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
HEALTH_RECORDS_FILE = os.path.join(DATA_DIR, "health_records.json")

# --- AI configuration ---------------------------------------------------

# Name of the Gemini model to use. "gemini-2.5-flash" was retired for new
# requests (Google's API now returns 404 for it). Verified working and
# correctly extracting values from a test report as of 2026-09-22:
# gemini-3.6-flash. "gemini-3.1-flash-image" (tried previously) is an
# image-generation model, not a fit for text extraction, and its own
# free-tier quota is currently exhausted anyway.
# Name of the Gemini model to use. "gemini-flash-latest" is an alias that
# Google always points at their current Flash model, so we don't have to
# update this string every time a newer Flash version is released.
AI_MODEL_NAME = "gemini-3.6-flash"

# The actual key value must never be committed to source control.
API_KEY_ENV_VAR = "GEMINI_API_KEY"

# Maximum number of times ai_manager should retry a failed AI call.
AI_MAX_RETRIES = 3
# Base wait time in between each retry 
BASE_DELAY = 5

# --- Application constants ---------------------------------------------

# Health measurements currently planned for the system.
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



def get_api_key():
    """
    Read the AI API key from the environment.

    Returns None if the key has not been configured. Callers are
    responsible for handling a missing key (e.g. showing a message to
    the user) - this function only reads the value.
    """
    return os.environ.get(API_KEY_ENV_VAR)
