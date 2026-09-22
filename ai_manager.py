"""
ai_manager.py

Responsible for AI-related operations only (building prompts, calling
the AI API, and parsing/validating its responses).

Rules for this module:
- No business/domain rules here (that belongs in logic_manager.py).
- No print() or input() calls here - return values/errors to the caller.

build_prompt() builds the extraction instructions, and call_ai() sends
those instructions plus an already-read medical report (PDF/image bytes)
to Gemini and returns its raw text response.

parse_response() and validate_schema() turn that raw text into a
trustworthy Python dictionary with a known shape, and verify_source()
double-checks that each extracted value is actually backed by the
report rather than invented. call_ai_with_retry() ties all of this
together: it retries structurally invalid or unsupported responses up
to a fixed limit and returns a controlled failure (None) if Gemini
never produces a trustworthy result. No business rules (e.g. whether a
value is medically normal, high, or low) are applied here - that
belongs to logic_manager.py.
"""

#pip install google-genai pydantic

import json
import os
from typing import List, Optional
from google.genai import types
from pydantic import BaseModel, Field
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from config import AI_MODEL_NAME, AI_MAX_RETRIES, get_api_key


def build_prompt():
    """
    Build the instruction text sent to Gemini alongside an uploaded
    medical report (PDF or image).

    The prompt asks Gemini to extract heart rate, blood pressure
    (systolic/diastolic), and blood glucose, and to reply with ONLY a
    JSON object in an exact, fixed structure - no markdown, no
    explanation, no extra fields - so that parse_response() and
    validate_schema() can reliably check what comes back. It also
    forbids diagnosing conditions, recommending treatment, or inventing
    values that are not actually present in the report.

    Returns:
        A prompt string ready to be sent to the AI model together with
        the report file.
    """
    return (
        "You are a data extraction assistant. You will be given a "
        "medical report as a PDF or image.\n\n"
        "Extract the following health metrics if they are clearly "
        "visible in the report: heart rate, blood pressure (systolic "
        "and diastolic), and blood glucose.\n\n"
        "Respond with ONLY valid JSON and nothing else - no markdown "
        "formatting, no code fences (```), no explanation, and no text "
        "before or after the JSON.\n\n"
        "The JSON must contain exactly these fields, with no additional "
        "fields:\n"
        "{\n"
        '  "heart_rate": <number, or null if not visible>,\n'
        '  "blood_pressure": {"systolic": <number, or null>, '
        '"diastolic": <number, or null>},\n'
        '  "blood_glucose": <number, or null if not visible>\n'
        "}\n\n"
        'If no blood pressure reading is visible at all, set '
        '"blood_pressure" itself to null instead of guessing either '
        "value.\n\n"
        "Rules you must follow:\n"
        "- Do not diagnose any medical condition.\n"
        "- Do not recommend or suggest any treatment, medication, or "
        "dosage.\n"
        "- Do not invent, estimate, or guess a value that is not clearly "
        "present in the report - use null instead.\n"
        "- Do not include any field other than heart_rate, "
        "blood_pressure, and blood_glucose."
    )


def call_ai(file_bytes, mime_type, prompt):
    """
    Send a prepared medical report (PDF or image, already read into
    memory by the caller) together with the extraction prompt to the
    configured Gemini model, and return its raw text response.

    This function only talks to the AI - it does not parse the response
    as JSON, validate its structure, or apply any business rules. That
    happens later, downstream of this function.

    Args:
        file_bytes: bytes - the raw content of the medical report file.
        mime_type: str - the file's MIME type, e.g. "application/pdf",
            "image/png", or "image/jpeg".
        prompt: str - the extraction instructions (see build_prompt()).

    Returns:
        The model's raw response text on success. On any failure
        (missing/invalid API key, authentication failure, network/API
        failure, or an empty response) this returns a JSON string
        describing the problem instead of raising an exception. The
        real API key is never included in that error message.
    """
    api_key = get_api_key()
    if not api_key:
        return json.dumps({"error": "AI API key not configured."})

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=AI_MODEL_NAME,
            contents=[
                prompt,
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
            ],
        )
    except genai_errors.ClientError as exc:
        if exc.code in (401, 403):
            return json.dumps({
                "error": "Authentication with the AI service failed. "
                         "Check that GEMINI_API_KEY is set correctly."
            })
        return json.dumps({"error": "The AI service rejected the request."})
    except genai_errors.APIError:
        return json.dumps({
            "error": "The AI service is currently unavailable. Please try again later."
        })
    except Exception:
        return json.dumps({
            "error": "Could not reach the AI service due to a network or unexpected error."
        })

    if not response or not getattr(response, "text", None):
        return json.dumps({"error": "The AI service returned an empty response."})

    return response.text


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


def parse_response(raw_response):
    """
    Safely convert Gemini's raw response text into a Python dictionary.

    Args:
        raw_response: str - the raw text returned by call_ai().

    Returns:
        A dict if `raw_response` is valid JSON representing a JSON
        object. Returns None if the text is missing, not valid JSON, or
        valid JSON that isn't an object (e.g. a list or a bare number).
        Never raises an exception itself.
    """
    try:
        parsed = json.loads(raw_response)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(parsed, dict):
        return None

    return parsed


# The exact set of keys build_prompt() asks Gemini to return.
_REQUIRED_TOP_LEVEL_KEYS = {"heart_rate", "blood_pressure", "blood_glucose"}
_REQUIRED_BLOOD_PRESSURE_KEYS = {"systolic", "diastolic"}


def _is_number_or_null(value):
    """
    True if `value` is an int, a float, or None.

    bool is deliberately excluded even though Python treats bools as a
    subclass of int - "True"/"False" are not valid health measurements.
    """
    if value is None:
        return True
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_schema(parsed_response):
    """
    Check that `parsed_response` has exactly the structure build_prompt()
    asked Gemini for:

        {"heart_rate": number or null,
         "blood_pressure": null or {"systolic": number or null,
                                     "diastolic": number or null},
         "blood_glucose": number or null}

    This only checks *shape* - the right fields, nothing extra, correct
    types. It never judges whether a value is medically normal, high,
    low, or dangerous; that interpretation belongs to logic_manager.py.

    Args:
        parsed_response: the value returned by parse_response().

    Returns:
        True if the structure is valid, False otherwise (missing,
        additional, or malformed fields).
    """
    if not isinstance(parsed_response, dict):
        return False

    if set(parsed_response.keys()) != _REQUIRED_TOP_LEVEL_KEYS:
        return False

    if not _is_number_or_null(parsed_response["heart_rate"]):
        return False

    if not _is_number_or_null(parsed_response["blood_glucose"]):
        return False

    blood_pressure = parsed_response["blood_pressure"]
    if blood_pressure is not None:
        if not isinstance(blood_pressure, dict):
            return False

        if set(blood_pressure.keys()) != _REQUIRED_BLOOD_PRESSURE_KEYS:
            return False

        if not _is_number_or_null(blood_pressure["systolic"]):
            return False

        if not _is_number_or_null(blood_pressure["diastolic"]):
            return False

    return True


def build_verification_prompt(parsed_response):
    """
    Build a prompt asking Gemini to re-check the (same) medical report
    and confirm whether each non-null extracted value is explicitly
    present in it - a source/grounding check, not a medical judgment.

    Args:
        parsed_response: dict already confirmed by validate_schema() to
            have the expected shape.

    Returns:
        A prompt string ready to be sent to the AI model together with
        the same report file used for extraction.
    """
    return (
        "You will be given a medical report again, along with a set of "
        "values that were previously extracted from it.\n\n"
        "For EACH extracted value below that is not null, check whether "
        "that exact value is explicitly written in the report. Only "
        "check whether the number is actually present in the document - "
        "do not judge whether it is medically normal, abnormal, high, "
        "low, or dangerous.\n\n"
        f"Extracted values to check:\n{json.dumps(parsed_response)}\n\n"
        "Respond with ONLY valid JSON and nothing else - no markdown, no "
        "explanation - in exactly this structure:\n"
        "{\n"
        '  "heart_rate_supported": <true or false>,\n'
        '  "blood_pressure_supported": <true or false>,\n'
        '  "blood_glucose_supported": <true or false>\n'
        "}\n\n"
        "Set a field to false if the corresponding value cannot be "
        "found in the report, or if the extracted value was null."
    )


def verify_source(file_bytes, mime_type, parsed_response):
    """
    Ask Gemini to re-check the original report and confirm that every
    non-null value in `parsed_response` is actually backed by it.

    This exists to catch responses that are structurally valid (correct
    JSON, correct types) but where Gemini invented a value that is not
    actually present in the source document. It only checks presence in
    the source, never medical plausibility.

    Args:
        file_bytes: bytes - the same medical report file used for
            extraction.
        mime_type: str - the file's MIME type (see call_ai()).
        parsed_response: dict already confirmed by validate_schema() to
            have the expected shape.

    Returns:
        True if every non-null value is confirmed as present in the
        report. False if any value is not confirmed, or if the
        verification call itself failed or returned something
        unusable - callers should treat False the same as any other
        validation failure.
    """
    fields_to_check = []
    if parsed_response.get("heart_rate") is not None:
        fields_to_check.append("heart_rate_supported")
    if parsed_response.get("blood_pressure") is not None:
        fields_to_check.append("blood_pressure_supported")
    if parsed_response.get("blood_glucose") is not None:
        fields_to_check.append("blood_glucose_supported")

    if not fields_to_check:
        # Nothing was extracted, so there is nothing that could have
        # been invented - trivially supported.
        return True

    verification_prompt = build_verification_prompt(parsed_response)
    raw_verification = call_ai(file_bytes, mime_type, verification_prompt)
    verification = parse_response(raw_verification)

    if not isinstance(verification, dict):
        return False

    return all(verification.get(field_name) is True for field_name in fields_to_check)


def call_ai_with_retry(file_bytes, mime_type, prompt, max_retries=AI_MAX_RETRIES):
    """
    Call the AI up to `max_retries` times, parsing, schema-validating,
    and source-verifying each response, until a fully trustworthy one
    is obtained.

    Every attempt must pass three checks in order:
    1. parse_response() - is it valid JSON representing an object?
    2. validate_schema() - does it have exactly the expected fields
       and types?
    3. verify_source() - is every non-null value actually backed by
       the report, rather than invented?

    An attempt that fails any of these three checks (including a
    network/API failure from call_ai(), which comes back as an error
    JSON object that fails validate_schema()) is discarded and the loop
    tries again, up to `max_retries` times total.

    Args:
        file_bytes: bytes - the raw content of the medical report file.
        mime_type: str - the file's MIME type (see call_ai()).
        prompt: str - the extraction instructions (see build_prompt()).
        max_retries: int maximum number of attempts.

    Returns:
        A validated, source-verified response dict on success, or None
        if every attempt failed - a controlled failure the caller can
        check for (e.g. `if result is None: ...`) instead of the
        program crashing or an untrustworthy value being used.
    """
    for _ in range(max_retries):
        raw_response = call_ai(file_bytes, mime_type, prompt)
        parsed = parse_response(raw_response)

        if not validate_schema(parsed):
            continue

        if not verify_source(file_bytes, mime_type, parsed):
            continue

        return parsed

    return None


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


def ExtractFields(uploadedFile):
    print("Processing document...")

    client = genai.Client(api_key=get_api_key())


    gemini_file = client.files.upload(
        file=uploadedFile,
        config=types.UploadFileConfig(mime_type=uploadedFile.type)
    )

    print("Analyzing report and generating patient dashboard data...")
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            gemini_file, 
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
    extracted_json = json.loads(response.text)
    
    # Clean up uploaded file from Gemini storage
    client.files.delete(name=gemini_file.name)
    
    return extracted_json

#main for testing
if __name__ == "__main__":

    ExtractFields()