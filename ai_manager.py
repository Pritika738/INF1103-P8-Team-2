"""
ai_manager.py

Responsible for AI-related operations only (building prompts, calling
the AI API, and parsing/validating its responses).

Rules for this module:
- No business/domain rules here (that belongs in logic_manager.py).
- No print() or input() calls here - return values/errors to the caller.

call_ai_api() below now makes a real call to the Gemini API. Prompt
content (build_prompt) and response handling (parse/validate) are still
simple placeholders - they will be expanded once PDF/image ingestion and
real trend-analysis prompts are implemented.
"""

#pip install google-genai pydantic

import json
import os
from typing import List, Optional
from google.genai import types
from pydantic import BaseModel, Field
from google import genai

from config import AI_MODEL_NAME, AI_MAX_RETRIES, get_api_key


def build_prompt(record):
    """
    Placeholder for future prompt construction logic.

    Intended to turn a health record (or raw report text) into a
    well-formed prompt string for the AI model.

    Args:
        record: dict containing health record data.

    Returns:
        A prompt string (currently a simple placeholder).
    """
    # TODO: build a real prompt template once AI analysis is implemented.
    return f"[PLACEHOLDER PROMPT] Analyse this health record: {record}"


def call_ai_api(prompt):
    """
    Send `prompt` to the configured Gemini model (AI_MODEL_NAME) using
    the API key from config.get_api_key(), and return the raw response
    text.

    Args:
        prompt: str prompt to send to the AI.

    Returns:
        The model's response text on success. On failure (missing key,
        network error, API error) returns a JSON string describing the
        error instead of raising an exception, so callers never have to
        wrap this in a try/except.
    """
    api_key = get_api_key()
    if not api_key:
        return json.dumps({"error": "AI API key not configured."})

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=AI_MODEL_NAME,
            contents=prompt,
        )
        return response.text
    except Exception as exc:
        return json.dumps({"error": f"AI API call failed: {exc}"})


def parse_ai_response(raw_response):
    """
    Placeholder for future JSON response parsing.

    Args:
        raw_response: str raw text returned by the AI API.

    Returns:
        A parsed dict, or None if the response could not be parsed as JSON.
    """
    try:
        return json.loads(raw_response)
    except (json.JSONDecodeError, TypeError):
        return None


def validate_ai_response(parsed_response, expected_keys=None):
    """
    Placeholder for future validation of an AI response's structure.

    Args:
        parsed_response: dict returned by parse_ai_response.
        expected_keys: optional list of keys that must be present.

    Returns:
        True if the response looks structurally valid, False otherwise.
    """
    if not isinstance(parsed_response, dict):
        return False

    if expected_keys:
        return all(key in parsed_response for key in expected_keys)

    return True


def call_ai_with_retry(prompt, max_retries=AI_MAX_RETRIES):
    """
    Placeholder for future retry/error-handling logic around AI calls.

    Intended to call the AI API up to `max_retries` times, parsing and
    validating each response, until a valid response is obtained.

    Args:
        prompt: str prompt to send to the AI.
        max_retries: int maximum number of attempts.

    Returns:
        A parsed response dict, or None if all attempts failed.
    """
    for _ in range(max_retries):
        raw_response = call_ai_api(prompt)
        parsed = parse_ai_response(raw_response)
        if validate_ai_response(parsed):
            return parsed

    return None

def Prompt(prompt:str):
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )

    print(response.text)


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


def ExtractFields(fileName):

    client = genai.Client(api_key=get_api_key[0])

    print("Processing document...")

    medical_file = client.files.upload(file=fileName) 

    print("Analyzing report and generating patient dashboard data...")
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            medical_file, 
            "Analyze this medical document. Extract the data fields, compile a patient-friendly summary, and flag all key actionable areas."
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ComprehensiveMedicalAnalysis,
            temperature=0.1,
        ),
    )

    # 5. Output the clean JSON results
    print("\n--- Extracted Data ---")
    print(response.text)
    
    # Optional: Clean up the file from Google's servers after processing
    client.files.delete(name=medical_file.name)


#main for testing
if __name__ == "__main__":

    ExtractFields()