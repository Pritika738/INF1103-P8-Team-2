"""
ai_manager.py

Responsible for AI-related operations only (building prompts, calling
the AI API, and parsing/validating its responses).

Rules for this module:
- No business/domain rules here (that belongs in logic_manager.py).
- No print() or input() calls here - return values/errors to the caller.

All functions below are placeholders. No real API integration has been
implemented yet.
"""

import json

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
    Placeholder for the future call to the AI API.

    Intended to send `prompt` to the configured AI model (AI_MODEL_NAME)
    using the API key from config.get_api_key(), and return the raw
    response text.

    Args:
        prompt: str prompt to send to the AI.

    Returns:
        A raw response string. Currently returns a placeholder response
        and does not perform any real network call.
    """
    # TODO: implement the real API call (e.g. via requests/SDK).
    api_key = get_api_key()
    if not api_key:
        return json.dumps({"error": "AI API key not configured."})

    return json.dumps({"status": "not_implemented", "model": AI_MODEL_NAME})


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
