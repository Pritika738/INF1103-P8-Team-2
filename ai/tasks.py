"""
ai/tasks.py

One class per kind of AI request.

AITask is an abstract template: the shared flow (send prompt -> parse ->
validate) lives in run(), while each subclass supplies only its own
prompt (build_prompt) and its own schema check (validate). Adding a new
kind of AI request means adding a subclass - nothing existing changes
(Open/Closed), and AIManager treats every task through the AITask type
(polymorphism).

Validation checks *shape* only (right fields, right types). Whether a
value is medically normal is never judged here - that is Logic Manager's job.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from .client import AIClient, AIServiceError
from .parser import ResponseParser
from .prompts import PromptBuilder


class AITask(ABC):
    """Abstract base for a single AI request/response exchange."""

    def __init__(self, parser: ResponseParser):
        self._parser = parser

    @abstractmethod
    def build_prompt(self, **context) -> str:
        """Return the prompt text for this task."""

    @abstractmethod
    def validate(self, parsed: dict) -> bool:
        """Return True if `parsed` has exactly the structure this task asked for."""

    def run(self, client: AIClient, file_bytes: Optional[bytes] = None,
            mime_type: Optional[str] = None, **context) -> Optional[dict]:
        """Send the prompt, then parse and validate the reply.

        Returns the validated dict, or None if the service failed or the
        reply was malformed / had an invalid schema. Never raises.
        """
        try:
            raw = client.generate(self.build_prompt(**context), file_bytes, mime_type)
        except AIServiceError:
            return None
        parsed = self._parser.parse(raw)
        if parsed is None or not self.validate(parsed):
            return None
        return parsed


class ExtractionTask(AITask):
    """Classifies a document and extracts heart rate, BP, glucose and date."""

    FIELDS = frozenset({
        "is_medical_report", "classification_reason",
        "heart_rate", "blood_pressure", "blood_glucose", "report_date",
    })
    _BLOOD_PRESSURE_KEYS = frozenset({"systolic", "diastolic"})

    def build_prompt(self, **context) -> str:
        return PromptBuilder.extraction()

    def validate(self, parsed: dict) -> bool:
        if not isinstance(parsed, dict) or set(parsed.keys()) != self.FIELDS:
            return False
        reason = parsed["classification_reason"]
        return (
            isinstance(parsed["is_medical_report"], bool)
            and isinstance(reason, str) and bool(reason.strip())
            and self._is_number_or_null(parsed["heart_rate"])
            and self._is_number_or_null(parsed["blood_glucose"])
            and self._is_date_or_null(parsed["report_date"])
            and self._is_blood_pressure_or_null(parsed["blood_pressure"])
        )

    @staticmethod
    def _is_number_or_null(value) -> bool:
        # bool is a subclass of int in Python but is not a valid measurement.
        if value is None:
            return True
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    @staticmethod
    def _is_date_or_null(value) -> bool:
        # A real calendar parse, so "2026-13-40" is rejected, not just bad formats.
        if value is None:
            return True
        if not isinstance(value, str):
            return False
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return False
        return True

    @classmethod
    def _is_blood_pressure_or_null(cls, value) -> bool:
        if value is None:
            return True
        if not isinstance(value, dict) or set(value.keys()) != cls._BLOOD_PRESSURE_KEYS:
            return False
        return all(cls._is_number_or_null(reading) for reading in value.values())


class VerificationTask(AITask):
    """Asks the model to confirm each extracted value appears in the source file."""

    # extracted field -> key the model uses to confirm it (single source of truth)
    VERIFICATION_KEYS = {
        "heart_rate": "heart_rate_supported",
        "blood_pressure": "blood_pressure_supported",
        "blood_glucose": "blood_glucose_supported",
        "report_date": "report_date_supported",
    }

    def build_prompt(self, **context) -> str:
        return PromptBuilder.verification(context["extracted"])

    def validate(self, parsed: dict) -> bool:
        allowed = set(self.VERIFICATION_KEYS.values())
        return set(parsed.keys()) <= allowed and all(isinstance(v, bool) for v in parsed.values())


class NarrativeTask(AITask):
    """Phrases Logic Manager's already-decided findings as plain language."""

    def build_prompt(self, **context) -> str:
        return PromptBuilder.narrative(context["record"])

    def validate(self, parsed: dict) -> bool:
        narrative = parsed.get("narrative")
        return isinstance(narrative, str) and bool(narrative.strip())
