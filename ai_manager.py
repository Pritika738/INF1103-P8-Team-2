"""
ai_manager.py

Responsible for AI-related operations only (building prompts, calling
the AI API, and parsing/validating its responses).

Rules for this module:
- No business/domain rules here (that belongs in logic_manager.py).
- No print() or input() calls here - return values/errors to the caller.
- Procedural only - plain module-level functions, no custom classes.

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
import time
import ai_prompt
from datetime import datetime
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from config import (AI_MODEL_NAME, AI_FALLBACK_MODELS, AI_MAX_RETRIES, BASE_DELAY, get_api_key)


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

# Primary model first, then fallbacks in priority order (duplicates removed).
_MODEL_CHAIN = list(dict.fromkeys([AI_MODEL_NAME, *AI_FALLBACK_MODELS]))

# HTTP codes meaning "this model can't serve you right now", so trying the
# next model makes sense: not found/retired, rate limited, server errors.
# Auth (401/403) and bad-request (400) errors are deliberately excluded -
# another model would fail the same way.
_MODEL_UNAVAILABLE_CODES = {404, 429, 500, 502, 503, 504}

# The exact set of keys build_prompt() asks Gemini to return.
_REQUIRED_TOP_LEVEL_KEYS = {
    "is_medical_report", "classification_reason",
    "heart_rate", "blood_pressure", "blood_glucose", "report_date",
}
_REQUIRED_BLOOD_PRESSURE_KEYS = {"systolic", "diastolic"}

# Maps each extracted field to the key Gemini uses to confirm it during
# source verification. Single source of truth for the verification step.
_VERIFICATION_KEYS = {
    "heart_rate": "heart_rate_supported",
    "blood_pressure": "blood_pressure_supported",
    "blood_glucose": "blood_glucose_supported",
    "report_date": "report_date_supported",
}

# ---------------------------------------------------------------------------
# Talking to Gemini
# ---------------------------------------------------------------------------

def _error_json(message):
    """Return a JSON string of the form {"error": message}."""
    return json.dumps({"error": message})


def _is_model_unavailable(exc):
    """True if `exc` means the current model is unavailable (try the next one)."""
    return exc.code in _MODEL_UNAVAILABLE_CODES or exc.status == "UNAVAILABLE"


def call_ai(prompt, file_bytes=None, mime_type=None):
    """
    The single place that calls Gemini. Sends `prompt`, optionally with
    a medical report file attached, and returns the model's raw text.
    It does not parse or validate the response or apply business rules;
    that happens downstream.

    Models in _MODEL_CHAIN are tried in order. If one is unavailable
    (see _MODEL_UNAVAILABLE_CODES) the next is tried; any other error
    (bad key, rejected request, network failure) is returned
    immediately, since a different model wouldn't help.

    Args:
        prompt: str - the instructions (e.g. build_prompt()).
        file_bytes: bytes or None - the raw report file (PDF/image),
            already read into memory by the caller. None for a
            text-only request.
        mime_type: str or None - required with file_bytes, e.g.
            "application/pdf", "image/png", "image/jpeg".

    Returns:
        The model's raw response text on success. On any failure
        (missing/invalid API key, authentication failure, every model
        unavailable, network failure, or an empty response) returns a
        JSON error string instead of raising. The real API key is never
        included in the message.
    """
    api_key = get_api_key()
    if not api_key:
        return _error_json("AI API key not configured.")

    contents = [prompt]
    if file_bytes is not None:
        if not mime_type:
            return _error_json("A file was provided without a MIME type.")
        contents.append(types.Part.from_bytes(data=file_bytes, mime_type=mime_type))

    client = genai.Client(api_key=api_key)

    for model_name in _MODEL_CHAIN:
        print(f"\nPrompting {model_name}.....")
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
            )
        except genai_errors.APIError as exc:
            if exc.code in (401, 403):
                return _error_json(
                    "Authentication with the AI service failed. "
                    "Check that GEMINI_API_KEY is set correctly."
                )
            if _is_model_unavailable(exc):
                continue  # try the next model in the chain
            return _error_json("The AI service rejected the request.")
        except Exception:
            return _error_json(
                "Could not reach the AI service due to a network or unexpected error."
            )

        if not response or not getattr(response, "text", None):
            return _error_json("The AI service returned an empty response.")

        return response.text

    return _error_json(
        "The AI service is currently unavailable. Please try again later."
    )


def extract_fields(uploaded_file, prompt, schema):
    """
    Upload a file to Gemini's Files API and extract structured data
    from it directly into `schema`, retrying on a transient "model
    busy" (503) response.

    This is an alternative extraction path to build_prompt() +
    call_ai_with_retry(): it uses Gemini's native structured-output
    feature (response_schema) so Gemini itself enforces the shape. It
    is not part of the active upload pipeline (see
    io_manager.process_uploaded_report(), which uses
    call_ai_with_retry()).

    Args:
        uploaded_file: a file-like object with a `.type` attribute
            (e.g. a Streamlit UploadedFile) to send to Gemini.
        prompt: str - instructions describing what to extract.
        schema: a Pydantic model class describing the desired output.

    Returns:
        A dict parsed from Gemini's structured JSON response on
        success, or None on failure (never raises).
    """
    client = genai.Client(api_key=get_api_key())

    gemini_file = client.files.upload(
        file=uploaded_file,
        config=types.UploadFileConfig(mime_type=uploaded_file.type),
    )

    try:
        for model_name in _MODEL_CHAIN:
            for attempt in range(AI_MAX_RETRIES):
                print(f"\nExtracting with {model_name} \nAttempt: {attempt + 1}.....")
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[uploaded_file, prompt],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=schema,
                            temperature=0.1,
                        ),
                    )
                    print("Extraction Complete!")
                    return parse_response(response.text)
                except genai_errors.APIError as exc:
                    if not _is_model_unavailable(exc):
                        return None  # e.g. auth/bad request: no model will help
                    if attempt < AI_MAX_RETRIES:
                        time.sleep(BASE_DELAY)  # retry same model first
                        continue
                    break  # retries exhausted: move on to the next model
                except Exception:
                    return None
    finally:
        # Always clean up the uploaded file on Gemini's servers.
        client.files.delete(name=gemini_file.name)

    return None


# ---------------------------------------------------------------------------
# Parsing and validation
# ---------------------------------------------------------------------------

def parse_response(raw_response):
    """
    Safely convert Gemini's raw response text into a Python dictionary.

    Returns:
        A dict if `raw_response` is valid JSON representing a JSON
        object; None if it is missing, invalid JSON, or not an object.
        Never raises.
    """
    try:
        parsed = json.loads(raw_response)
    except (json.JSONDecodeError, TypeError):
        return None

    return parsed if isinstance(parsed, dict) else None


def _is_number_or_null(value):
    """
    True if `value` is an int, a float, or None.

    bool is deliberately excluded even though Python treats bools as a
    subclass of int - "True"/"False" are not valid health measurements.
    """
    if value is None:
        return True
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_valid_report_date_or_null(value):
    """
    True if `value` is None, or a string that is both shaped like
    "YYYY-MM-DD" AND a real calendar date (rejects e.g. "2026-13-40",
    which only a real parse - not just a format check - can catch).
    """
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _is_valid_blood_pressure_or_null(value):
    """True if `value` is None or {"systolic": number/null, "diastolic": number/null}."""
    if value is None:
        return True
    if not isinstance(value, dict) or set(value.keys()) != _REQUIRED_BLOOD_PRESSURE_KEYS:
        return False
    return all(_is_number_or_null(reading) for reading in value.values())


def validate_schema(parsed_response):
    """
    Check that `parsed_response` has exactly the structure build_prompt()
    asked Gemini for:

        {"is_medical_report": true or false,
         "classification_reason": non-empty string,
         "heart_rate": number or null,
         "blood_pressure": null or {"systolic": number or null,
                                     "diastolic": number or null},
         "blood_glucose": number or null,
         "report_date": "YYYY-MM-DD" string or null}

    This only checks *shape* - the right fields, nothing extra, correct
    types, and a genuinely valid calendar date. It never judges whether
    a value is medically normal, or whether Gemini's is_medical_report
    answer is actually correct; those are not structural checks.

    Returns:
        True if the structure is valid, False otherwise.
    """
    if not isinstance(parsed_response, dict):
        return False
    if set(parsed_response.keys()) != _REQUIRED_TOP_LEVEL_KEYS:
        return False

    classification_reason = parsed_response["classification_reason"]

    return (
        isinstance(parsed_response["is_medical_report"], bool)
        and isinstance(classification_reason, str)
        and bool(classification_reason.strip())
        and _is_number_or_null(parsed_response["heart_rate"])
        and _is_number_or_null(parsed_response["blood_glucose"])
        and _is_valid_report_date_or_null(parsed_response["report_date"])
        and _is_valid_blood_pressure_or_null(parsed_response["blood_pressure"])
    )


# ---------------------------------------------------------------------------
# Source verification
# ---------------------------------------------------------------------------

def _check_source_verification(file_bytes, mime_type, parsed_response):
    """
    Ask Gemini, in a SINGLE call, to re-check the original report and
    confirm whether each non-null value in `parsed_response` is
    actually backed by it. Shared by verify_source() and
    call_ai_with_retry() so neither makes its own separate call.

    Args:
        file_bytes: bytes - the same report file used for extraction.
        mime_type: str - the file's MIME type (see call_ai()).
        parsed_response: dict already confirmed by validate_schema().

    Returns:
        A dict like {"heart_rate_supported": True, ...} with one entry
        per non-null field (empty if nothing was extracted - trivially
        nothing to invent). None if the verification call failed or
        returned something unusable; callers should treat None as a
        failure.
    """
    keys_to_check = [
        verification_key
        for field, verification_key in _VERIFICATION_KEYS.items()
        if parsed_response.get(field) is not None
    ]
    if not keys_to_check:
        return {}

    raw_verification = call_ai(
        ai_prompt.build_verification_prompt(parsed_response), file_bytes, mime_type
    )
    verification = parse_response(raw_verification)
    if verification is None:
        return None

    return {key: verification.get(key) is True for key in keys_to_check}


def verify_source(file_bytes, mime_type, parsed_response):
    """
    Confirm that every non-null value in `parsed_response` is actually
    backed by the original report (presence only, never medical
    plausibility).

    Returns:
        True if every non-null value is confirmed. False if any is not
        confirmed, or if the verification call itself failed.
    """
    results = _check_source_verification(file_bytes, mime_type, parsed_response)
    return results is not None and all(results.values())


# ---------------------------------------------------------------------------
# Full extraction pipeline
# ---------------------------------------------------------------------------

def call_ai_with_retry(file_bytes, mime_type, prompt):
    """
    Call the AI up to `max_retries` times until a fully trustworthy
    response is obtained.

    Every attempt must pass three checks in order:
    1. parse_response()   - valid JSON object?
    2. validate_schema()  - exactly the expected fields and types?
    3. source verification - every non-null value backed by the report?

    A failing attempt (including a network/API failure from call_ai(),
    which fails validate_schema()) is discarded and retried - WITH TWO
    EXCEPTIONS:

    - If Gemini confidently classifies the document as NOT a medical
      report (is_medical_report is False), that result is returned
      immediately rather than retried. It is a deterministic answer to
      a classification question, not a value that could have been
      "invented" - every measurement is null by instruction, so there
      is nothing left to source-verify, and retrying would only waste
      an API call re-asking Gemini the same question.
    - If every measurement is confirmed but report_date alone could
      not be re-confirmed, the result is accepted with report_date set
      to None rather than spending more API calls retrying from
      scratch. An unconfirmed date is not evidence it was invented the
      way an unconfirmed measurement is.

    Args:
        file_bytes: bytes - the raw content of the medical report file.
        mime_type: str - the file's MIME type (see call_ai()).
        prompt: str - the extraction instructions (see build_prompt()).
        max_retries: int maximum number of attempts.

    Returns:
        A validated, source-verified dict on success, or None if every
        attempt failed.
    """
    for attempt in range(AI_MAX_RETRIES):
        raw_response = call_ai(prompt, file_bytes, mime_type)
        print(f"\nAttempt: {attempt + 1}.....")
        parsed = parse_response(raw_response)

        if not validate_schema(parsed):
            continue

        # A confident "this isn't a medical report" classification is a
        # deterministic answer, not an untrustworthy one - nothing to
        # source-verify, and retrying would just waste quota re-asking
        # the same classification question.
        if parsed["is_medical_report"] is False:
            return parsed

        # One verification call per attempt (see _check_source_verification).
        results = _check_source_verification(file_bytes, mime_type, parsed)
        if results is None:
            continue

        if all(results.values()):
            return parsed

        measurements_all_supported = all(
            supported for key, supported in results.items()
            if key != _VERIFICATION_KEYS["report_date"]
        )
        if measurements_all_supported:
            # Only the date failed verification: drop it, keep the rest.
            return {**parsed, "report_date": None}

    return None


def generate_consultation_narrative(processed_record):
    """
    Ask Gemini to phrase logic_manager's already-decided findings as
    short, plain-language consultation notes. Gemini only rewords
    existing findings - it never classifies anything itself.

    Args:
        processed_record: the dict logic_manager.process_ai_record()
            returned.
        max_retries: int maximum number of attempts.

    Returns:
        A narrative string on success, or None if no usable result was
        produced. On None, the caller must fall back to
        logic_manager's own deterministic summary.
    """
    prompt = ai_prompt.build_narrative_prompt(processed_record)

    for attempt in range(AI_MAX_RETRIES):
        parsed = parse_response(call_ai(prompt))
        print(f"\nAttempt: {attempt + 1}.....")
        if parsed is None:
            continue

        narrative = parsed.get("narrative")
        if isinstance(narrative, str) and narrative.strip():
            return narrative.strip()

    return None
