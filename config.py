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

# --- AI configuration ---------------------------------------------------

# Name of the Gemini model to use. "gemini-flash-latest" is an alias that
# Google always points at their current Flash model, so we don't have to
# update this string every time a newer Flash version is released.
AI_MODEL_NAME = "gemini-2.5-flash"

# Environment variable name that should hold the real API key.
# The actual key value must never be committed to source control.
API_KEY_ENV_VAR = ["AQ.Ab8RN6IIsCuV6bv11ePM0EicpMIdvQxZ-CzBbtPWn_TTVGY40g", "Sheng You API"]

# Maximum number of times ai_manager should retry a failed AI call.
AI_MAX_RETRIES = 3

# --- Application constants ---------------------------------------------

# Health measurements currently planned for the system.
SUPPORTED_METRICS = [
    "blood_pressure_systolic",
    "blood_pressure_diastolic",
    "heart_rate",
    "blood_glucose",
    "cholesterol",
]


def get_api_key(who):
    """
    Read the AI API key from the environment.

    Returns None if the key has not been configured. Callers are
    responsible for handling a missing key (e.g. showing a message to
    the user) - this function only reads the value.
    """
    return os.environ.get(API_KEY_ENV_VAR[who])
