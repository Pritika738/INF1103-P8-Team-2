"""
config.py

Central place for configuration constants used across the application.
No secrets (e.g. API keys) should be hardcoded here - those are loaded
from environment variables (see .env / load_env_variables in this file).
"""

import os
from dotenv import load_dotenv

# Load variables from a local .env file (if present) into the environment.
load_dotenv()

# --- File paths -------------------------------------------------------

# Location of the local JSON "database" that stores health records.
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
HEALTH_RECORDS_FILE = os.path.join(DATA_DIR, "health_records.json")
# The single SQLite database the app stores its data in. Each kind of data
# has its own table (health_records, users, ...). The JSON files in this
# folder are kept only as the source for migrate_json_to_sqlite.py.
DATABASE_FILE = os.path.join(DATA_DIR, "app.db")

# Registered login accounts (salted password/PIN hashes) - migration source
# only; accounts are now stored in the "users" table of DATABASE_FILE.
USERS_FILE = os.path.join(DATA_DIR, "users.json")

# Generated consultation-summary PDFs (separate from uploaded medical
# reports). Their metadata now lives in the "consultation_summaries" table
# of DATABASE_FILE; the JSON file is kept only as the migration source.
CONSULTATION_PDF_DIR = os.path.join(DATA_DIR, "consultation_pdfs")
CONSULTATION_SUMMARIES_FILE = os.path.join(DATA_DIR, "consultation_summaries.json")

# Original uploaded medical report files (the actual PDF/image the user
# uploaded, kept verbatim) - completely separate from both the health
# records (extracted values) and the consultation-summary PDFs above (AI
# Manager's own output). Their metadata now lives in the "original_reports"
# table of DATABASE_FILE; the JSON file is kept only as the migration source.
ORIGINAL_REPORTS_DIR = os.path.join(DATA_DIR, "original_reports")
ORIGINAL_REPORTS_FILE = os.path.join(DATA_DIR, "original_reports.json")
MEDICAL_PROFILES_FILE = os.path.join(DATA_DIR, "medical_profiles.json")

# Vitals the user measured themselves at home (e.g. a daily blood
# pressure reading) and typed in by hand. Kept in their OWN file, apart
# from health_records.json, so self-logged readings never mix with the
# history, trends or consultation summary built from medical reports.
MANUAL_VITALS_FILE = os.path.join(DATA_DIR, "manual_vitals.json")

# How many report dates are used for active trend analysis and
# consultation preparation - older reports stay visible in full in
# Health History, just excluded from these two calculations.
LATEST_REPORTS_LIMIT = 5

# How many generated consultation-summary PDFs are kept per user before
# the oldest is deleted. None means keep all of them - this project does
# not currently have an agreed reason to cap summary history, unlike
# LATEST_REPORTS_LIMIT above (which is specifically required). This
# never deletes medical records either way, only generated summary PDFs.
MAX_RETAINED_SUMMARY_PDFS = None

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
AI_MODEL_NAME = "gemini-3-flash-preview"
AI_FALLBACK_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.1-pro-preview"]
# The actual key value must never be committed to source control.
API_KEY_ENV_VAR = "GEMINI_API_KEY"

# Maximum number of times ai_manager should retry a failed AI call.
AI_MAX_RETRIES = 2
# Base wait time in between each retry 
BASE_DELAY = 5

# --- Application constants ---------------------------------------------

# Health measurements currently planned for the system.
SUPPORTED_METRICS = [
    "blood_pressure_systolic",
    "blood_pressure_diastolic",
    "heart_rate",
    "blood_glucose",
    "cholesterol",
]


def get_api_key():
    """
    Read the AI API key from the environment.

    Returns None if the key has not been configured. Callers are
    responsible for handling a missing key (e.g. showing a message to
    the user) - this function only reads the value.
    """
    return os.environ.get(API_KEY_ENV_VAR)
