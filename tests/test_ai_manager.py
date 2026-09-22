"""
tests/test_ai_manager.py

Unit and reliability tests for ai_manager.py (P1's build_prompt()/call_ai(),
and P2's parse_response()/validate_schema()/verify_source()/
call_ai_with_retry()).

These tests never make a real network call to Gemini. Every call to
config.get_api_key() and the google-genai client is replaced with a fake
(mocked) version, so the tests run instantly, for free, and produce the
same result every time regardless of whether a real GEMINI_API_KEY is
configured on the machine running them.

Run with:
    pytest tests/test_ai_manager.py
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors as genai_errors

# ai_manager.py lives in the project root, one directory above this file.
# Insert that directory into sys.path so "import ai_manager" works no
# matter which directory pytest/unittest is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai_manager


# ---------------------------------------------------------------------------
# Shared test data / helpers
# ---------------------------------------------------------------------------

VALID_RESPONSE_ALL_NULL = json.dumps({
    "heart_rate": None,
    "blood_pressure": None,
    "blood_glucose": None,
})

INVALID_RESPONSE = "Sure, here's the data you asked for: heart rate is 72"


def _make_fake_gemini_response(text):
    """Build a fake Gemini response object with just a `.text` attribute."""
    fake_response = MagicMock()
    fake_response.text = text
    return fake_response


# ---------------------------------------------------------------------------
# Unit tests: parse_response()
# ---------------------------------------------------------------------------

def test_parse_response_accepts_valid_json_object():
    raw = (
        '{"heart_rate": 72, "blood_pressure": '
        '{"systolic": 120, "diastolic": 80}, "blood_glucose": null}'
    )
    assert ai_manager.parse_response(raw) == {
        "heart_rate": 72,
        "blood_pressure": {"systolic": 120, "diastolic": 80},
        "blood_glucose": None,
    }


def test_parse_response_rejects_malformed_json_without_crashing():
    assert ai_manager.parse_response(INVALID_RESPONSE) is None


def test_parse_response_rejects_json_that_is_not_an_object():
    # "[1, 2, 3]" is valid JSON, but it's a list, not the object we need.
    assert ai_manager.parse_response("[1, 2, 3]") is None


def test_parse_response_rejects_non_string_input():
    assert ai_manager.parse_response(None) is None


# ---------------------------------------------------------------------------
# Unit tests: validate_schema()
# ---------------------------------------------------------------------------

def test_validate_schema_accepts_fully_valid_response():
    response = {
        "heart_rate": 72,
        "blood_pressure": {"systolic": 120, "diastolic": 80},
        "blood_glucose": 5.5,
    }
    assert ai_manager.validate_schema(response) is True


def test_validate_schema_accepts_null_for_genuinely_missing_measurement():
    # The key IS present here - a null VALUE means "the report really
    # doesn't contain this measurement", which is valid by design.
    response = {
        "heart_rate": 72,
        "blood_pressure": {"systolic": 120, "diastolic": 80},
        "blood_glucose": None,
    }
    assert ai_manager.validate_schema(response) is True


def test_validate_schema_rejects_completely_missing_key():
    # blood_glucose is missing entirely here - different from being
    # present with a null value (see test above).
    response = {
        "heart_rate": 72,
        "blood_pressure": {"systolic": 120, "diastolic": 80},
    }
    assert ai_manager.validate_schema(response) is False


def test_validate_schema_rejects_unexpected_extra_key():
    response = {
        "heart_rate": 72,
        "blood_pressure": {"systolic": 120, "diastolic": 80},
        "blood_glucose": None,
        "diagnosis": "possible hypertension",
    }
    assert ai_manager.validate_schema(response) is False


def test_validate_schema_rejects_wrong_type_for_heart_rate():
    response = {
        "heart_rate": ["72"],
        "blood_pressure": {"systolic": 120, "diastolic": 80},
        "blood_glucose": None,
    }
    assert ai_manager.validate_schema(response) is False


def test_validate_schema_accepts_null_blood_pressure():
    response = {"heart_rate": 72, "blood_pressure": None, "blood_glucose": 5.5}
    assert ai_manager.validate_schema(response) is True


def test_validate_schema_rejects_blood_pressure_missing_diastolic():
    response = {
        "heart_rate": 72,
        "blood_pressure": {"systolic": 120},
        "blood_glucose": None,
    }
    assert ai_manager.validate_schema(response) is False


def test_validate_schema_rejects_boolean_disguised_as_number():
    # bool is a subclass of int in Python - True/False must not be
    # mistaken for a valid numeric measurement.
    response = {"heart_rate": True, "blood_pressure": None, "blood_glucose": None}
    assert ai_manager.validate_schema(response) is False


def test_validate_schema_rejects_non_dict_input():
    assert ai_manager.validate_schema(None) is False
    assert ai_manager.validate_schema(["not", "a", "dict"]) is False


# ---------------------------------------------------------------------------
# Unit tests: verify_source()
# ---------------------------------------------------------------------------

def test_verify_source_accepts_value_confirmed_by_report():
    parsed = {
        "heart_rate": 72,
        "blood_pressure": {"systolic": 120, "diastolic": 80},
        "blood_glucose": None,
    }
    with patch("ai_manager.call_ai") as mock_call_ai:
        mock_call_ai.return_value = json.dumps({
            "heart_rate_supported": True,
            "blood_pressure_supported": True,
        })
        assert ai_manager.verify_source(b"fake-bytes", "application/pdf", parsed) is True


def test_verify_source_rejects_value_not_confirmed_by_report():
    # Simulates the report containing no glucose result, but Gemini
    # extracting one anyway (an "invented" value).
    parsed = {"heart_rate": None, "blood_pressure": None, "blood_glucose": 5.5}
    with patch("ai_manager.call_ai") as mock_call_ai:
        mock_call_ai.return_value = json.dumps({"blood_glucose_supported": False})
        assert ai_manager.verify_source(b"fake-bytes", "application/pdf", parsed) is False


def test_verify_source_skips_the_extra_api_call_when_nothing_was_extracted():
    all_null = {"heart_rate": None, "blood_pressure": None, "blood_glucose": None}
    with patch("ai_manager.call_ai") as mock_call_ai:
        assert ai_manager.verify_source(b"fake-bytes", "application/pdf", all_null) is True
        mock_call_ai.assert_not_called()


def test_verify_source_treats_malformed_verification_reply_as_unsupported():
    parsed = {"heart_rate": 72, "blood_pressure": None, "blood_glucose": None}
    with patch("ai_manager.call_ai") as mock_call_ai:
        mock_call_ai.return_value = "not valid json at all"
        assert ai_manager.verify_source(b"fake-bytes", "application/pdf", parsed) is False


# ---------------------------------------------------------------------------
# Reliability tests: call_ai() error handling / API & network failures
# ---------------------------------------------------------------------------

def test_call_ai_handles_missing_api_key_without_crashing():
    with patch("ai_manager.get_api_key", return_value=None):
        result = ai_manager.call_ai(b"bytes", "application/pdf", "prompt")
    assert "error" in json.loads(result)


def test_call_ai_handles_authentication_failure_without_leaking_the_key():
    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = genai_errors.ClientError(
        401, {"error": {"message": "invalid api key", "status": "UNAUTHENTICATED"}}
    )
    with patch("ai_manager.get_api_key", return_value="super-secret-key"), \
            patch("ai_manager.genai.Client", return_value=fake_client):
        result = ai_manager.call_ai(b"bytes", "application/pdf", "prompt")

    assert "error" in json.loads(result)
    assert "super-secret-key" not in result


def test_call_ai_handles_server_error_without_crashing():
    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = genai_errors.ServerError(
        503, {"error": {"message": "overloaded", "status": "UNAVAILABLE"}}
    )
    with patch("ai_manager.get_api_key", return_value="fake-key"), \
            patch("ai_manager.genai.Client", return_value=fake_client):
        result = ai_manager.call_ai(b"bytes", "application/pdf", "prompt")

    assert "error" in json.loads(result)


def test_call_ai_handles_network_timeout_without_crashing():
    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = TimeoutError("connection timed out")
    with patch("ai_manager.get_api_key", return_value="fake-key"), \
            patch("ai_manager.genai.Client", return_value=fake_client):
        result = ai_manager.call_ai(b"bytes", "application/pdf", "prompt")

    assert "error" in json.loads(result)


def test_call_ai_handles_empty_response_without_crashing():
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = _make_fake_gemini_response("")
    with patch("ai_manager.get_api_key", return_value="fake-key"), \
            patch("ai_manager.genai.Client", return_value=fake_client):
        result = ai_manager.call_ai(b"bytes", "application/pdf", "prompt")

    assert "error" in json.loads(result)


# ---------------------------------------------------------------------------
# Reliability tests: call_ai_with_retry()
# ---------------------------------------------------------------------------

def test_invalid_response_causes_another_attempt():
    with patch("ai_manager.call_ai") as mock_call_ai:
        mock_call_ai.side_effect = [INVALID_RESPONSE, VALID_RESPONSE_ALL_NULL]
        result = ai_manager.call_ai_with_retry(
            b"bytes", "application/pdf", "prompt", max_retries=3
        )

    assert result == {"heart_rate": None, "blood_pressure": None, "blood_glucose": None}
    assert mock_call_ai.call_count == 2


def test_retry_recovers_after_one_bad_attempt():
    with patch("ai_manager.call_ai") as mock_call_ai:
        mock_call_ai.side_effect = [INVALID_RESPONSE, VALID_RESPONSE_ALL_NULL]
        result = ai_manager.call_ai_with_retry(
            b"bytes", "application/pdf", "prompt", max_retries=5
        )

    assert result is not None
    assert mock_call_ai.call_count == 2  # stopped as soon as it succeeded


def test_retry_stops_at_the_configured_limit():
    with patch("ai_manager.call_ai") as mock_call_ai:
        mock_call_ai.side_effect = [INVALID_RESPONSE] * 10  # far more than max_retries
        result = ai_manager.call_ai_with_retry(
            b"bytes", "application/pdf", "prompt", max_retries=3
        )

    assert result is None
    assert mock_call_ai.call_count == 3  # never exceeds max_retries


def test_immediately_valid_response_needs_only_one_attempt():
    with patch("ai_manager.call_ai") as mock_call_ai:
        mock_call_ai.return_value = VALID_RESPONSE_ALL_NULL
        result = ai_manager.call_ai_with_retry(
            b"bytes", "application/pdf", "prompt", max_retries=3
        )

    assert result is not None
    assert mock_call_ai.call_count == 1


def test_invented_value_fails_source_verification_and_exhausts_retries():
    # Gemini keeps extracting a blood_glucose value that verify_source
    # can never confirm is actually written in the report. Each attempt
    # makes two calls to call_ai(): one to extract, one to verify.
    extraction_response = json.dumps({
        "heart_rate": None,
        "blood_pressure": None,
        "blood_glucose": 5.5,
    })
    verification_response = json.dumps({"blood_glucose_supported": False})

    with patch("ai_manager.call_ai") as mock_call_ai:
        mock_call_ai.side_effect = [extraction_response, verification_response] * 3
        result = ai_manager.call_ai_with_retry(
            b"bytes", "application/pdf", "prompt", max_retries=3
        )

    assert result is None
    assert mock_call_ai.call_count == 6  # 3 attempts x (extract + verify)


# ---------------------------------------------------------------------------
# Reliability test: stability under repeated calls
# ---------------------------------------------------------------------------

def test_repeated_calls_do_not_crash_or_corrupt_shared_state():
    """
    Calls call_ai_with_retry() many times in a row with a mix of
    malformed, schema-invalid, and valid mocked responses, and checks
    that: (1) nothing ever raises an exception, (2) the result is
    always the expected value, and (3) the module-level constants every
    call relies on for validation are never accidentally mutated.
    """
    original_top_level_keys = set(ai_manager._REQUIRED_TOP_LEVEL_KEYS)
    original_bp_keys = set(ai_manager._REQUIRED_BLOOD_PRESSURE_KEYS)

    responses = [
        "not valid json",
        json.dumps({
            "heart_rate": 72,
            "blood_pressure": None,
            "blood_glucose": None,
            "extra_field": "should be rejected",
        }),
        VALID_RESPONSE_ALL_NULL,
    ]

    for i in range(50):
        with patch("ai_manager.call_ai") as mock_call_ai:
            mock_call_ai.side_effect = list(responses)
            try:
                result = ai_manager.call_ai_with_retry(
                    b"bytes", "application/pdf", "prompt", max_retries=3
                )
            except Exception as exc:  # pragma: no cover - this must never happen
                pytest.fail(f"call_ai_with_retry raised on iteration {i}: {exc}")

        assert result == {"heart_rate": None, "blood_pressure": None, "blood_glucose": None}

    assert ai_manager._REQUIRED_TOP_LEVEL_KEYS == original_top_level_keys
    assert ai_manager._REQUIRED_BLOOD_PRESSURE_KEYS == original_bp_keys


# ---------------------------------------------------------------------------
# Reliability test: logging (documented as not yet implemented)
# ---------------------------------------------------------------------------

def test_logging_not_yet_implemented():
    """
    ai_manager.py does not import or call Python's `logging` module
    anywhere - AI/API failures are currently reported only by returning
    a JSON error string to the caller (see call_ai()), never logged.

    This is recorded as a skipped test rather than silently left out,
    so it shows up in the test run as a visible reminder. Once logging
    is added to ai_manager.py, replace this with a real test using
    pytest's `caplog` fixture to assert a log record was emitted on
    failure.
    """
    pytest.skip("No logging implemented in ai_manager.py yet - nothing to verify.")


# ---------------------------------------------------------------------------
# Reliability test: idempotency (documented decision, not forced)
# ---------------------------------------------------------------------------

def test_idempotency_not_applicable():
    """
    ai_manager.py performs no state-changing operations of its own: no
    file writes, no database updates, and no in-memory state that
    persists between calls (data_manager.py owns persistence, and
    that's out of scope for this module). Every function here is a
    request/response step - call it once or ten times and nothing on
    disk or in memory changes as a side effect of ai_manager.py's own
    code.

    Idempotency is about what happens when a state-changing operation
    is repeated (e.g. "does submitting a payment twice charge twice?").
    Since there is no such operation here, a forced idempotency test
    would not be testing anything real, so it is intentionally skipped
    rather than fabricated.

    Note: Gemini itself is a generative model, so calling call_ai()
    twice with the same prompt is not guaranteed to return
    byte-identical text - but that is a property of the external AI
    service, not of ai_manager.py's own code, and is exactly why
    validate_schema() and verify_source() exist: to make the *outcome*
    trustworthy even though the raw text may vary between calls.
    """
    pytest.skip(
        "ai_manager.py has no state-changing operation to test for "
        "idempotency - see this test's docstring for the reasoning."
    )
