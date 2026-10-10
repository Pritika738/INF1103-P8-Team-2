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
from datetime import datetime

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from config import AI_MODEL_NAME, AI_MAX_RETRIES, BASE_DELAY, get_api_key


def build_prompt():
    """
    Build the instruction text sent to Gemini alongside an uploaded
    medical report (PDF or image).

    The prompt asks Gemini to extract heart rate, blood pressure
    (systolic/diastolic), blood glucose, and the report's own date, and
    to reply with ONLY a JSON object in an exact, fixed structure - no
    markdown, no explanation, no extra fields - so that
    parse_response() and validate_schema() can reliably check what
    comes back. It also forbids diagnosing conditions, recommending
    treatment, or inventing values that are not actually present in the
    report.

    Returns:
        A prompt string ready to be sent to the AI model together with
        the report file.
    """
    return (
        "You are a data extraction assistant. You will be given a "
        "medical report as a PDF or image.\n\n"
        "Extract the following if they are clearly visible in the "
        "report: heart rate, blood pressure (systolic and diastolic), "
        "blood glucose, and the report's own date.\n\n"
        "REPORT DATE RULES:\n"
        '- The report date is the date the measurements were taken or '
        'recorded - look for labels such as "Report Date", '
        '"Collection Date", "Test Date", or "Date of Visit".\n'
        "- Do NOT use the patient's date of birth.\n"
        "- Do NOT use a document printing/generation date if a separate "
        "report/collection/test date is also present.\n"
        "- Do NOT assume the year is 2026, or any other specific year - "
        "read the actual year printed in the report.\n"
        "- The report may show the date in any common format, e.g. "
        '"10/10/2026", "10 Oct 2026", "2026-10-10", or '
        '"10 October 2026" - convert whichever format you find into '
        '"YYYY-MM-DD" in your answer.\n'
        "- If you are not confident which date is the report date, "
        "set it to null rather than guessing.\n\n"
        "Respond with ONLY valid JSON and nothing else - no markdown "
        "formatting, no code fences (```), no explanation, and no text "
        "before or after the JSON.\n\n"
        "The JSON must contain exactly these fields, with no additional "
        "fields:\n"
        "{\n"
        '  "heart_rate": <number, or null if not visible>,\n'
        '  "blood_pressure": {"systolic": <number, or null>, '
        '"diastolic": <number, or null>},\n'
        '  "blood_glucose": <number, or null if not visible>,\n'
        '  "report_date": <"YYYY-MM-DD" string, or null if not '
        "confidently identifiable>\n"
        "}\n\n"
        'If no blood pressure reading is visible at all, set '
        '"blood_pressure" itself to null instead of guessing either '
        "value.\n\n"
        "Rules you must follow:\n"
        "- Do not diagnose any medical condition.\n"
        "- Do not prescribe or suggest any medication.\n"
        "- Do not recommend starting, stopping, or changing any "
        "medication or dosage.\n"
        "- Do not recommend any treatment plan.\n"
        "- Do not claim to replace a doctor or qualified healthcare "
        "professional.\n"
        "- Do not invent, estimate, or guess a value or date that is "
        "not clearly present in the report - use null instead.\n"
        "- Do not include any field other than heart_rate, "
        "blood_pressure, blood_glucose, and report_date."
    )


def extract_fields(uploaded_file, prompt, schema):
    """
    Upload a file to Gemini's Files API and extract structured data
    from it directly into `schema`, retrying on a transient "model
    busy" (503) response.

    This is an alternative extraction path to build_prompt() +
    call_ai_with_retry(): it uses Gemini's native structured-output
    feature (response_schema) so Gemini itself enforces the shape,
    instead of manually prompting for JSON and parsing/validating it
    by hand. It is not part of the active upload pipeline (see
    io_manager.process_uploaded_report(), which uses call_ai_with_retry()).

    Args:
        uploaded_file: a file-like object with a `.type` attribute
            (e.g. a Streamlit UploadedFile) to send to Gemini.
        prompt: str - instructions describing what to extract.
        schema: a Pydantic model class describing the desired output
            shape.

    Returns:
        A dict parsed from Gemini's structured JSON response on
        success. Returns None on failure (the model stayed busy for
        every retry, or any other API error) instead of raising - the
        caller never has to wrap this in a try/except.
    """
    client = genai.Client(api_key=get_api_key())

    gemini_file = client.files.upload(
        file=uploaded_file,
        config=types.UploadFileConfig(mime_type=uploaded_file.type),
    )

    parsed = None
    try:
        for attempt in range(1, AI_MAX_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=AI_MODEL_NAME,
                    contents=[uploaded_file, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=0.1,
                    ),
                )
                parsed = parse_response(response.text)
                break  # exits the retry loop on a successful response
            except genai_errors.APIError as exc:
                model_is_busy = exc.code == 503 or exc.status == "UNAVAILABLE"
                if model_is_busy and attempt < AI_MAX_RETRIES:
                    time.sleep(BASE_DELAY)
                    continue
                return None
            except Exception:
                return None
    finally:
        # Always clean up the uploaded file on Gemini's servers, even
        # if every attempt above failed or raised.
        client.files.delete(name=gemini_file.name)

    return parsed

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
_REQUIRED_TOP_LEVEL_KEYS = {"heart_rate", "blood_pressure", "blood_glucose", "report_date"}
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


def _is_valid_report_date_or_null(value):
    """
    True if `value` is None, or a string that is both shaped like
    "YYYY-MM-DD" AND an actual, real calendar date (rejects things like
    "2026-13-40", which only a real parse - not just a format check -
    can catch).
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


def validate_schema(parsed_response):
    """
    Check that `parsed_response` has exactly the structure build_prompt()
    asked Gemini for:

        {"heart_rate": number or null,
         "blood_pressure": null or {"systolic": number or null,
                                     "diastolic": number or null},
         "blood_glucose": number or null,
         "report_date": "YYYY-MM-DD" string or null}

    This only checks *shape* - the right fields, nothing extra, correct
    types, and (for report_date) a genuinely valid calendar date. It
    never judges whether a value is medically normal, high, low, or
    dangerous; that interpretation belongs to logic_manager.py.

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

    if not _is_valid_report_date_or_null(parsed_response["report_date"]):
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
        "check whether the number or date is actually present in the "
        "document - do not judge whether a measurement is medically "
        "normal, abnormal, high, or low, and do not judge whether a "
        "date is plausible, only whether it is the one printed in the "
        "report.\n\n"
        f"Extracted values to check:\n{json.dumps(parsed_response)}\n\n"
        "Respond with ONLY valid JSON and nothing else - no markdown, no "
        "explanation - in exactly this structure:\n"
        "{\n"
        '  "heart_rate_supported": <true or false>,\n'
        '  "blood_pressure_supported": <true or false>,\n'
        '  "blood_glucose_supported": <true or false>,\n'
        '  "report_date_supported": <true or false>\n'
        "}\n\n"
        "Set a field to false if the corresponding value cannot be "
        "found in the report, or if the extracted value was null."
    )


_MEASUREMENT_SUPPORTED_FIELDS = {
    "heart_rate_supported", "blood_pressure_supported", "blood_glucose_supported",
}


def _check_source_verification(file_bytes, mime_type, parsed_response):
    """
    Ask Gemini, in a SINGLE call, to re-check the original report and
    confirm whether each non-null value in `parsed_response` is
    actually backed by it - the shared mechanics behind verify_source()
    and call_ai_with_retry()'s more selective date-dropping shortcut,
    so neither of them makes its own separate verification call.

    Args:
        file_bytes: bytes - the same medical report file used for
            extraction.
        mime_type: str - the file's MIME type (see call_ai()).
        parsed_response: dict already confirmed by validate_schema() to
            have the expected shape.

    Returns:
        A dict like {"heart_rate_supported": True, ...} with one entry
        per non-null field that was checked (empty if nothing was
        extracted - trivially nothing to invent). None if the
        verification call itself failed or returned something unusable
        - callers should treat None as a failure, the same as any
        field being False.
    """
    fields_to_check = []
    if parsed_response.get("heart_rate") is not None:
        fields_to_check.append("heart_rate_supported")
    if parsed_response.get("blood_pressure") is not None:
        fields_to_check.append("blood_pressure_supported")
    if parsed_response.get("blood_glucose") is not None:
        fields_to_check.append("blood_glucose_supported")
    if parsed_response.get("report_date") is not None:
        fields_to_check.append("report_date_supported")

    if not fields_to_check:
        # Nothing was extracted, so there is nothing that could have
        # been invented - trivially supported.
        return {}

    verification_prompt = build_verification_prompt(parsed_response)
    raw_verification = call_ai(file_bytes, mime_type, verification_prompt)
    verification = parse_response(raw_verification)

    if not isinstance(verification, dict):
        return None

    return {
        field_name: verification.get(field_name) is True
        for field_name in fields_to_check
    }


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
    results = _check_source_verification(file_bytes, mime_type, parsed_response)
    if results is None:
        return False
    return all(results.values())


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
    tries again, up to `max_retries` times total - WITH ONE EXCEPTION:
    if every extracted MEASUREMENT is confirmed but report_date alone
    could not be re-confirmed, this does not throw away an otherwise-
    trustworthy extraction and spend two more API calls retrying from
    scratch (one call was already spent confirming the measurements are
    genuine). It accepts the result with report_date set to None
    instead - a date that merely couldn't be double-checked is not
    evidence it was invented, unlike a measurement failing the same
    check, which still triggers a full retry.

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

        # One verification call per attempt, not one per field and not
        # one per fallback check - verify_source() is not called here
        # separately, since that would mean a second, duplicate API
        # call for the exact same check.
        results = _check_source_verification(file_bytes, mime_type, parsed)
        if results is None:
            continue

        if all(results.values()):
            return parsed

        measurement_results = {
            field: value for field, value in results.items()
            if field in _MEASUREMENT_SUPPORTED_FIELDS
        }
        date_was_the_only_problem = (
            results.get("report_date_supported") is False
            and all(measurement_results.values())
        )
        if date_was_the_only_problem:
            parsed_without_date = dict(parsed)
            parsed_without_date["report_date"] = None
            return parsed_without_date

    return None


def build_narrative_prompt(processed_record):
    """
    Build a prompt asking Gemini to turn logic_manager's own,
    already-decided findings into short, plain-language consultation
    notes - phrasing only. Gemini is given the finished classifications
    (decision, urgent_findings, flagged_trends, recent_changes, each
    recent change already labelled "improved" or "worsened") and is
    explicitly told never to invent its own thresholds or severity -
    only to describe, in plain words, what Logic Manager already
    decided.

    Args:
        processed_record: the dict logic_manager.process_ai_record()
            returned.

    Returns:
        A prompt string ready to send to Gemini (text only, no file).
    """
    return (
        "You are writing short, factual notes to help a patient "
        "prepare for a doctor's appointment. You will be given "
        "already-finalised health findings as JSON - every "
        "classification (urgent, flagged, improved, worsened, stable) "
        "has ALREADY been decided by a separate rule-based system. "
        "Your only job is to phrase these existing findings in clear, "
        "plain language for a patient to read.\n\n"
        "STRICT RULES:\n"
        "- Do not diagnose any medical condition.\n"
        "- Do not prescribe or suggest any medication.\n"
        "- Do not recommend starting, stopping, or changing any "
        "medication or dosage.\n"
        "- Do not recommend any treatment plan.\n"
        "- Do not claim to replace a doctor or qualified healthcare "
        "professional.\n"
        "- Do not invent your own severity, thresholds, or "
        "classifications - only describe the findings exactly as given.\n"
        '- If a finding\'s "assessment" is "improved", say so clearly - '
        'never describe an improvement as "no significant change".\n'
        "- If a measurement is normal/stable, explain it in relation to "
        "the patient's previous reading(s) if given, rather than only "
        'saying "normal" or "everything is fine".\n'
        "- Do not state or imply that a normal reading proves the "
        "patient is healthy overall.\n"
        "- End with a brief reminder to discuss these findings with a "
        "qualified healthcare professional.\n\n"
        "Findings (already classified - do not reclassify):\n"
        f"{json.dumps(processed_record)}\n\n"
        "Respond with ONLY valid JSON and nothing else - no markdown, "
        "no code fences, no explanation outside the JSON - in exactly "
        "this structure:\n"
        "{\n"
        '  "narrative": "<3-6 sentences of plain-language notes>"\n'
        "}"
    )


def generate_consultation_narrative(processed_record, max_retries=AI_MAX_RETRIES):
    """
    Ask Gemini to phrase logic_manager's already-decided findings as
    short, plain-language consultation notes. Gemini only rewords
    existing findings here - it never classifies anything itself.

    Args:
        processed_record: the dict logic_manager.process_ai_record()
            returned.
        max_retries: int maximum number of attempts.

    Returns:
        A plain-language narrative string on success, or None if
        Gemini could not produce a usable result after retrying. On
        None, the caller must fall back to logic_manager's own
        deterministic summary rather than fabricate a successful AI
        result.
    """
    prompt = build_narrative_prompt(processed_record)

    for _ in range(max_retries):
        raw_response = call_ai_api(prompt)
        parsed = parse_response(raw_response)

        if not isinstance(parsed, dict):
            continue

        narrative = parsed.get("narrative")
        if isinstance(narrative, str) and narrative.strip():
            return narrative.strip()

    return None