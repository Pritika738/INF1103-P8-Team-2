"""
tests/test_ai_manager.py

Tests for the AI Manager and the ai/ package. No live API is used:
GeminiClient is tested with the Google SDK patched out, and AIManager is
tested with MockAIClient, which returns scripted replies.

Run with:
    python -m pytest tests/test_ai_manager.py
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors as genai_errors

from ai import (
    AIClient, AIServiceError, AITask, ExtractionTask, GeminiClient,
    MockAIClient, NarrativeTask, ResponseParser, RetryPolicy, VerificationTask,
)
from ai.prompts import PromptBuilder
from ai_manager import AIManager

PDF = "application/pdf"
INVALID = "Sure, here's the data you asked for: heart rate is 72"


# ---------------------------------------------------------------------------
# Sample AI replies
# ---------------------------------------------------------------------------

def extraction_json(heart_rate=None, blood_pressure=None, blood_glucose=None,
                    report_date=None, is_medical_report=True):
    """A valid extraction reply, as the JSON string the AI would return."""
    return json.dumps({
        "is_medical_report": is_medical_report,
        "classification_reason": "Test document.",
        "heart_rate": heart_rate,
        "blood_pressure": blood_pressure,
        "blood_glucose": blood_glucose,
        "report_date": report_date,
    })


def all_supported_json():
    """A verification reply confirming every field."""
    return json.dumps({
        "heart_rate_supported": True,
        "blood_pressure_supported": True,
        "blood_glucose_supported": True,
        "report_date_supported": True,
    })


NOT_MEDICAL = extraction_json(is_medical_report=False)


# ---------------------------------------------------------------------------
# ResponseParser
# ---------------------------------------------------------------------------

class TestResponseParser:
    def test_accepts_json_object(self):
        assert ResponseParser().parse('{"a": 1}') == {"a": 1}

    @pytest.mark.parametrize("raw", [INVALID, "[1, 2, 3]", "", None, 42])
    def test_rejects_everything_else_without_raising(self, raw):
        assert ResponseParser().parse(raw) is None


# ---------------------------------------------------------------------------
# ExtractionTask.validate (response schema)
# ---------------------------------------------------------------------------

def _valid(**overrides):
    base = json.loads(extraction_json(
        heart_rate=72, blood_glucose=5.5,
        blood_pressure={"systolic": 120, "diastolic": 80},
        report_date="2026-10-10",
    ))
    base.update(overrides)
    return base


class TestExtractionValidation:
    task = ExtractionTask(ResponseParser())

    def test_accepts_full_response(self):
        assert self.task.validate(_valid())

    def test_accepts_all_null_measurements(self):
        assert self.task.validate(_valid(
            heart_rate=None, blood_glucose=None, blood_pressure=None, report_date=None))

    def test_accepts_partial_blood_pressure(self):
        assert self.task.validate(_valid(blood_pressure={"systolic": 120, "diastolic": None}))

    def test_accepts_non_medical_classification(self):
        assert self.task.validate(json.loads(NOT_MEDICAL))

    @pytest.mark.parametrize("overrides", [
        {"heart_rate": "72"},                                   # string, not a number
        {"heart_rate": True},                                   # bool is not a measurement
        {"blood_glucose": [5.5]},
        {"blood_pressure": {"systolic": 120}},                  # missing key
        {"blood_pressure": {"systolic": "x", "diastolic": 80}},
        {"blood_pressure": 120},
        {"report_date": "05/01/2026"},                          # wrong format
        {"report_date": "2026-13-40"},                          # not a real date
        {"report_date": 20261010},
        {"is_medical_report": "yes"},
        {"classification_reason": "   "},
        {"classification_reason": 5},
    ])
    def test_rejects_invalid_values(self, overrides):
        assert not self.task.validate(_valid(**overrides))

    def test_rejects_extra_field(self):
        assert not self.task.validate({**_valid(), "diagnosis": "possible hypertension"})

    def test_rejects_missing_field(self):
        incomplete = _valid()
        del incomplete["heart_rate"]
        assert not self.task.validate(incomplete)

    def test_rejects_non_dict(self):
        assert not self.task.validate(None)
        assert not self.task.validate(["not", "a", "dict"])


class TestOtherTaskValidation:
    def test_verification_accepts_booleans_for_known_keys(self):
        task = VerificationTask(ResponseParser())
        assert task.validate({"heart_rate_supported": True, "report_date_supported": False})

    def test_verification_rejects_unknown_keys_and_non_booleans(self):
        task = VerificationTask(ResponseParser())
        assert not task.validate({"unknown_supported": True})
        assert not task.validate({"heart_rate_supported": "yes"})

    def test_narrative_requires_non_empty_string(self):
        task = NarrativeTask(ResponseParser())
        assert task.validate({"narrative": "Some notes."})
        assert not task.validate({"narrative": "  "})
        assert not task.validate({"narrative": 5})
        assert not task.validate({})


# ---------------------------------------------------------------------------
# OOP structure: interface, abstract class, inheritance, polymorphism
# ---------------------------------------------------------------------------

class TestDesign:
    def test_interface_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            AIClient()

    def test_abstract_task_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            AITask(ResponseParser())

    def test_concrete_clients_implement_the_interface(self):
        assert issubclass(GeminiClient, AIClient)
        assert issubclass(MockAIClient, AIClient)

    def test_concrete_tasks_extend_the_abstract_task(self):
        for cls in (ExtractionTask, VerificationTask, NarrativeTask):
            assert issubclass(cls, AITask)

    def test_manager_works_with_any_client_implementation(self):
        # Liskov: a brand-new AIClient is substitutable with no manager changes.
        class OneShot(AIClient):
            def generate(self, prompt, file_bytes=None, mime_type=None):
                return NOT_MEDICAL

        result = AIManager(OneShot()).extract_report(b"x", PDF)
        assert result["is_medical_report"] is False

    def test_each_task_builds_a_different_prompt(self):
        parser = ResponseParser()
        prompts = {
            ExtractionTask(parser).build_prompt(),
            VerificationTask(parser).build_prompt(extracted={"heart_rate": 1}),
            NarrativeTask(parser).build_prompt(record={"decision": "NORMAL"}),
        }
        assert len(prompts) == 3

    def test_prompts_request_json(self):
        assert "JSON" in PromptBuilder.extraction()
        assert "JSON" in PromptBuilder.verification({"heart_rate": 72})
        assert "JSON" in PromptBuilder.narrative({"decision": "NORMAL"})

    def test_verification_prompt_includes_extracted_values(self):
        assert "72" in PromptBuilder.verification({"heart_rate": 72})


# ---------------------------------------------------------------------------
# AITask.run (shared template flow)
# ---------------------------------------------------------------------------

class TestAITaskRun:
    task = ExtractionTask(ResponseParser())

    def test_returns_validated_dict(self):
        client = MockAIClient([extraction_json(heart_rate=72)])
        assert self.task.run(client, b"x", PDF)["heart_rate"] == 72

    def test_returns_none_on_service_error(self):
        assert self.task.run(MockAIClient([AIServiceError("down")]), b"x", PDF) is None

    def test_returns_none_on_malformed_json(self):
        assert self.task.run(MockAIClient([INVALID]), b"x", PDF) is None

    def test_returns_none_on_invalid_schema(self):
        assert self.task.run(MockAIClient([json.dumps({"heart_rate": 72})]), b"x", PDF) is None

    def test_passes_file_and_mime_type_to_client(self):
        client = MockAIClient([extraction_json()])
        self.task.run(client, b"report-bytes", PDF)
        assert client.calls[0]["file_bytes"] == b"report-bytes"
        assert client.calls[0]["mime_type"] == PDF


# ---------------------------------------------------------------------------
# AIManager.verify_source
# ---------------------------------------------------------------------------

class TestVerifySource:
    PARSED = {"heart_rate": 72, "blood_pressure": {"systolic": 120, "diastolic": 80},
              "blood_glucose": None, "report_date": "2026-10-10"}
    NOTHING = {"heart_rate": None, "blood_pressure": None, "blood_glucose": None,
               "report_date": None}

    def test_accepts_confirmed_values(self):
        reply = json.dumps({"heart_rate_supported": True, "blood_pressure_supported": True,
                            "report_date_supported": True})
        assert AIManager(MockAIClient([reply])).verify_source(b"x", PDF, self.PARSED) is True

    def test_rejects_unconfirmed_measurement(self):
        parsed = {**self.NOTHING, "blood_glucose": 5.5}
        reply = json.dumps({"blood_glucose_supported": False})
        assert AIManager(MockAIClient([reply])).verify_source(b"x", PDF, parsed) is False

    def test_rejects_invented_date(self):
        parsed = {**self.NOTHING, "report_date": "2026-03-14"}
        reply = json.dumps({"report_date_supported": False})
        assert AIManager(MockAIClient([reply])).verify_source(b"x", PDF, parsed) is False

    def test_makes_no_api_call_when_nothing_was_extracted(self):
        client = MockAIClient([])
        assert AIManager(client).verify_source(b"x", PDF, self.NOTHING) is True
        assert client.calls == []

    def test_malformed_reply_counts_as_unsupported(self):
        parsed = {**self.NOTHING, "heart_rate": 72}
        assert AIManager(MockAIClient(["not json"])).verify_source(b"x", PDF, parsed) is False

    def test_service_failure_counts_as_unsupported(self):
        parsed = {**self.NOTHING, "heart_rate": 72}
        client = MockAIClient([AIServiceError("down")])
        assert AIManager(client).verify_source(b"x", PDF, parsed) is False

    def test_missing_confirmation_key_counts_as_unsupported(self):
        # AI confirms heart rate but says nothing about the date.
        parsed = {**self.NOTHING, "heart_rate": 72, "report_date": "2026-10-10"}
        reply = json.dumps({"heart_rate_supported": True})
        assert AIManager(MockAIClient([reply])).verify_source(b"x", PDF, parsed) is False


# ---------------------------------------------------------------------------
# AIManager.extract_report (retry + verification pipeline)
# ---------------------------------------------------------------------------

class TestExtractReport:
    def test_valid_all_null_response_needs_one_call(self):
        client = MockAIClient([extraction_json()])
        result = AIManager(client, max_retries=3).extract_report(b"x", PDF)
        assert result == json.loads(extraction_json())
        assert len(client.calls) == 1  # nothing extracted, so no verification call

    def test_recovers_after_malformed_reply(self):
        client = MockAIClient([INVALID, extraction_json()])
        assert AIManager(client, max_retries=5).extract_report(b"x", PDF) is not None
        assert len(client.calls) == 2

    def test_schema_invalid_reply_is_retried(self):
        bad = json.dumps({**json.loads(extraction_json()), "extra": 1})
        client = MockAIClient([bad, extraction_json()])
        assert AIManager(client, max_retries=3).extract_report(b"x", PDF) is not None

    def test_stops_at_retry_limit(self):
        client = MockAIClient([INVALID] * 10)
        assert AIManager(client, max_retries=3).extract_report(b"x", PDF) is None
        assert len(client.calls) == 3

    def test_service_errors_do_not_crash_and_are_retried(self):
        client = MockAIClient([AIServiceError("down"), AIServiceError("down")])
        assert AIManager(client, max_retries=2).extract_report(b"x", PDF) is None
        assert len(client.calls) == 2

    def test_recovers_after_service_error(self):
        client = MockAIClient([AIServiceError("timeout"), extraction_json()])
        assert AIManager(client, max_retries=2).extract_report(b"x", PDF) is not None

    def test_invented_value_exhausts_retries(self):
        ext = extraction_json(blood_glucose=5.5)
        ver = json.dumps({"blood_glucose_supported": False})
        client = MockAIClient([ext, ver] * 3)
        assert AIManager(client, max_retries=3).extract_report(b"x", PDF) is None
        assert len(client.calls) == 6  # 3 attempts x (extract + verify)

    def test_not_a_medical_report_returns_immediately(self):
        client = MockAIClient([NOT_MEDICAL])
        result = AIManager(client, max_retries=3).extract_report(b"x", PDF)
        assert result["is_medical_report"] is False
        assert len(client.calls) == 1  # no verification, no retries

    def test_verified_measurements_are_accepted(self):
        client = MockAIClient([extraction_json(heart_rate=72), all_supported_json()])
        result = AIManager(client).extract_report(b"x", PDF)
        assert result["heart_rate"] == 72

    def test_blood_pressure_is_returned_nested(self):
        bp = {"systolic": 120, "diastolic": 80}
        client = MockAIClient([extraction_json(blood_pressure=bp), all_supported_json()])
        assert AIManager(client).extract_report(b"x", PDF)["blood_pressure"] == bp

    def test_only_date_unverified_keeps_measurements_and_drops_date(self):
        ext = extraction_json(heart_rate=72, report_date="2026-10-10")
        ver = json.dumps({"heart_rate_supported": True, "report_date_supported": False})
        result = AIManager(MockAIClient([ext, ver])).extract_report(b"x", PDF)
        assert result["heart_rate"] == 72
        assert result["report_date"] is None

    def test_unverified_verification_reply_triggers_retry(self):
        client = MockAIClient([
            extraction_json(heart_rate=72), INVALID,                     # attempt 1: bad verify
            extraction_json(heart_rate=72), all_supported_json(),        # attempt 2: ok
        ])
        assert AIManager(client, max_retries=2).extract_report(b"x", PDF) is not None

    def test_file_is_sent_to_extraction_and_verification(self):
        client = MockAIClient([extraction_json(heart_rate=72), all_supported_json()])
        AIManager(client).extract_report(b"report", PDF)
        assert all(c["file_bytes"] == b"report" and c["mime_type"] == PDF for c in client.calls)

    def test_repeated_runs_stay_stable(self):
        for _ in range(25):
            client = MockAIClient([INVALID, extraction_json()])
            assert AIManager(client, max_retries=3).extract_report(b"x", PDF) is not None


# ---------------------------------------------------------------------------
# AIManager.generate_narrative
# ---------------------------------------------------------------------------

class TestNarrative:
    def test_returns_stripped_narrative(self):
        ai = AIManager(MockAIClient([json.dumps({"narrative": "  Hello.  "})]))
        assert ai.generate_narrative({"decision": "NORMAL"}) == "Hello."

    def test_returns_none_when_every_attempt_is_unusable(self):
        ai = AIManager(MockAIClient([INVALID, json.dumps({"narrative": ""})]), max_retries=2)
        assert ai.generate_narrative({}) is None

    def test_returns_none_on_service_error(self):
        ai = AIManager(MockAIClient([AIServiceError("down")]), max_retries=1)
        assert ai.generate_narrative({}) is None

    def test_recovers_after_bad_attempt(self):
        ai = AIManager(MockAIClient([INVALID, json.dumps({"narrative": "ok"})]), max_retries=2)
        assert ai.generate_narrative({}) == "ok"

    def test_text_only_request_sends_no_file(self):
        client = MockAIClient([json.dumps({"narrative": "ok"})])
        AIManager(client).generate_narrative({})
        assert client.calls[0]["file_bytes"] is None

    def test_record_is_included_in_the_prompt(self):
        client = MockAIClient([json.dumps({"narrative": "ok"})])
        AIManager(client).generate_narrative({"decision": "FLAGGED"})
        assert "FLAGGED" in client.calls[0]["prompt"]


# ---------------------------------------------------------------------------
# RetryPolicy
# ---------------------------------------------------------------------------

class TestRetryPolicy:
    def test_yields_max_attempts(self):
        assert list(RetryPolicy(3).attempts()) == [1, 2, 3]

    def test_exponential_backoff_between_attempts_only(self):
        waits = []
        list(RetryPolicy(4, base_delay=2, sleeper=waits.append).attempts())
        assert waits == [2, 4, 8]  # nothing before attempt 1

    def test_no_wait_by_default(self):
        waits = []
        list(RetryPolicy(3, sleeper=waits.append).attempts())
        assert waits == []

    def test_at_least_one_attempt(self):
        assert list(RetryPolicy(0).attempts()) == [1]

    def test_manager_passes_its_retry_settings_to_the_policy(self):
        with patch("ai_manager.RetryPolicy", wraps=RetryPolicy) as policy:
            AIManager(MockAIClient(), max_retries=3, retry_delay=1.5)
        policy.assert_called_once_with(3, 1.5)


# ---------------------------------------------------------------------------
# GeminiClient error handling (SDK patched - no network)
# ---------------------------------------------------------------------------

def _gemini(key="fake-key"):
    return GeminiClient(models=["model-1", "model-2"], key_provider=lambda: key)


def _patched_sdk(**configure):
    """Patch genai.Client; `configure` sets up generate_content (side_effect/return_value)."""
    fake = MagicMock()
    fake.models.generate_content.configure_mock(**configure)
    return patch("ai.client.genai.Client", return_value=fake), fake


class TestGeminiClient:
    def test_missing_key_raises_service_error(self):
        with pytest.raises(AIServiceError):
            _gemini(key=None).generate("prompt")

    def test_file_without_mime_type_raises(self):
        with pytest.raises(AIServiceError):
            _gemini().generate("prompt", b"bytes", None)

    def test_auth_failure_does_not_leak_the_key(self):
        error = genai_errors.ClientError(
            401, {"error": {"message": "bad key", "status": "UNAUTHENTICATED"}})
        sdk, _ = _patched_sdk(side_effect=error)
        with sdk, pytest.raises(AIServiceError) as exc:
            _gemini(key="super-secret-key").generate("prompt", b"b", PDF)
        assert "super-secret-key" not in str(exc.value)

    def test_auth_failure_does_not_try_other_models(self):
        error = genai_errors.ClientError(
            403, {"error": {"message": "forbidden", "status": "PERMISSION_DENIED"}})
        sdk, fake = _patched_sdk(side_effect=error)
        with sdk, pytest.raises(AIServiceError):
            _gemini().generate("prompt", b"b", PDF)
        assert fake.models.generate_content.call_count == 1

    def test_bad_request_does_not_try_other_models(self):
        error = genai_errors.ClientError(
            400, {"error": {"message": "bad request", "status": "INVALID_ARGUMENT"}})
        sdk, fake = _patched_sdk(side_effect=error)
        with sdk, pytest.raises(AIServiceError):
            _gemini().generate("prompt", b"b", PDF)
        assert fake.models.generate_content.call_count == 1

    def test_falls_back_to_next_model_when_unavailable(self):
        busy = genai_errors.ServerError(
            503, {"error": {"message": "busy", "status": "UNAVAILABLE"}})
        sdk, fake = _patched_sdk(side_effect=[busy, MagicMock(text='{"a": 1}')])
        with sdk:
            assert _gemini().generate("prompt", b"b", PDF) == '{"a": 1}'
        models_tried = [c.kwargs["model"] for c in fake.models.generate_content.call_args_list]
        assert models_tried == ["model-1", "model-2"]

    def test_all_models_unavailable_raises(self):
        busy = genai_errors.ServerError(
            503, {"error": {"message": "busy", "status": "UNAVAILABLE"}})
        sdk, fake = _patched_sdk(side_effect=busy)
        with sdk, pytest.raises(AIServiceError):
            _gemini().generate("prompt", b"b", PDF)
        assert fake.models.generate_content.call_count == 2

    def test_network_timeout_raises_service_error(self):
        sdk, _ = _patched_sdk(side_effect=TimeoutError("timed out"))
        with sdk, pytest.raises(AIServiceError):
            _gemini().generate("prompt", b"b", PDF)

    def test_empty_response_raises(self):
        sdk, _ = _patched_sdk(return_value=MagicMock(text=""))
        with sdk, pytest.raises(AIServiceError):
            _gemini().generate("prompt", b"b", PDF)

    def test_text_only_prompt_works(self):
        sdk, _ = _patched_sdk(return_value=MagicMock(text='{"narrative": "ok"}'))
        with sdk:
            assert json.loads(_gemini().generate("text only")) == {"narrative": "ok"}

    def test_key_is_read_at_call_time(self):
        keys = iter(["first", "second"])
        client = GeminiClient(models=["m"], key_provider=lambda: next(keys))
        sdk, fake = _patched_sdk(return_value=MagicMock(text="{}"))
        with sdk as constructor:
            client.generate("p")
            client.generate("p")
        used = [c.kwargs["api_key"] for c in constructor.call_args_list]
        assert used == ["first", "second"]

    def test_duplicate_models_are_removed(self):
        busy = genai_errors.ServerError(
            503, {"error": {"message": "busy", "status": "UNAVAILABLE"}})
        client = GeminiClient(models=["m", "m"], key_provider=lambda: "k")
        sdk, fake = _patched_sdk(side_effect=busy)
        with sdk, pytest.raises(AIServiceError):
            client.generate("prompt")
        assert fake.models.generate_content.call_count == 1


class TestMockAIClient:
    def test_returns_scripted_replies_in_order_and_records_calls(self):
        client = MockAIClient(["a", "b"])
        assert client.generate("p1") == "a"
        assert client.generate("p2", b"x", PDF) == "b"
        assert [c["prompt"] for c in client.calls] == ["p1", "p2"]

    def test_raises_scripted_exceptions(self):
        client = MockAIClient([AIServiceError("x")])
        with pytest.raises(AIServiceError):
            client.generate("p")

    def test_raises_when_script_is_exhausted(self):
        with pytest.raises(AIServiceError):
            MockAIClient([]).generate("p")
