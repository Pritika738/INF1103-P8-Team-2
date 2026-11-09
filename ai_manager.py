"""
ai_manager.py

The AI Manager: orchestrates every AI request. Every uploaded record is
processed here (extract -> parse -> validate -> source-verify -> retry).

Responsibilities kept OUT of this module:
- Business rules (normal/high/low, trends)  -> logic_manager.py
- User-facing input/output (print/input)    -> io_manager.py
- Persistence                               -> data_manager.py
- Talking to a specific AI vendor           -> ai_layer/client.py

Object relationships (see UML):
- AIManager o-- AIClient     aggregation: the client is injected, can be
                             shared, and outlives the manager.
- AIManager *-- ResponseParser, RetryPolicy, ExtractionTask,
  VerificationTask, NarrativeTask
                             composition: created and owned by the manager.
- AITask  --> AIClient       association: a task uses a client during run().
"""

from typing import Optional

from ai_layer import (
    AIClient, AIServiceError, GeminiClient, MockAIClient,
    ResponseParser, RetryPolicy,
    ExtractionTask, VerificationTask, NarrativeTask,
)
from config import AI_MAX_RETRIES

__all__ = ["AIManager", "AIClient", "AIServiceError", "GeminiClient", "MockAIClient"]


class AIManager:
    """Coordinates AI tasks and enforces retry + source-verification rules."""

    def __init__(self, client: AIClient, max_retries: int = AI_MAX_RETRIES,
                 retry_delay: float = 0.0):
        """
        Args:
            client: any AIClient (GeminiClient in production, MockAIClient in tests).
            max_retries: maximum number of attempts per request.
            retry_delay: base seconds to wait between attempts (grows 2x each
                retry). Pass config.BASE_DELAY for real-world backoff; the
                default of 0 retries immediately.
        """
        self._client = client                              # aggregation
        self._parser = ResponseParser()                    # composition
        self._retry = RetryPolicy(max_retries, retry_delay)
        self._extraction = ExtractionTask(self._parser)
        self._verification = VerificationTask(self._parser)
        self._narrative = NarrativeTask(self._parser)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_report(self, file_bytes: bytes, mime_type: str) -> Optional[dict]:
        """Extract measurements from a report file, fully validated and verified.

        Each attempt must pass: parse -> schema validation -> source
        verification. A failing attempt is retried, with two exceptions:

        - A confident "not a medical report" classification is returned
          at once (it is a deterministic answer; every measurement is
          null so there is nothing to verify).
        - If every measurement is confirmed but only report_date could
          not be, the result is accepted with report_date set to None.

        Returns:
            A validated dict, or None if every attempt failed.
        """
        for _ in self._retry.attempts():
            parsed = self._extraction.run(self._client, file_bytes, mime_type)
            if parsed is None:
                continue

            if parsed["is_medical_report"] is False:
                return parsed

            results = self._check_source_verification(file_bytes, mime_type, parsed)
            if results is None:
                continue
            if all(results.values()):
                return parsed

            date_key = VerificationTask.VERIFICATION_KEYS["report_date"]
            if all(ok for key, ok in results.items() if key != date_key):
                return {**parsed, "report_date": None}

        return None

    def verify_source(self, file_bytes: bytes, mime_type: str, parsed: dict) -> bool:
        """True only if every non-null value in `parsed` is confirmed by the report."""
        results = self._check_source_verification(file_bytes, mime_type, parsed)
        return results is not None and all(results.values())

    def generate_narrative(self, processed_record: dict) -> Optional[str]:
        """Phrase Logic Manager's decided findings as plain-language notes.

        Returns the narrative, or None so the caller can fall back to
        Logic Manager's own deterministic summary.
        """
        for _ in self._retry.attempts():
            parsed = self._narrative.run(self._client, record=processed_record)
            if parsed is not None:
                return parsed["narrative"].strip()
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_source_verification(
        self,
        file_bytes,
        mime_type,
        parsed
    ) -> Optional[dict]:
        """Verify only measurements that were actually extracted."""

        keys_to_check = []

        for field, key in VerificationTask.VERIFICATION_KEYS.items():

            value = parsed.get(field)

            if field == "blood_pressure":

                # Do not verify blood pressure if both readings are missing.
                if (
                    isinstance(value, dict)
                    and (
                        value.get("systolic") is not None
                        or value.get("diastolic") is not None
                    )
                ):
                    keys_to_check.append(key)

            elif value is not None:

                keys_to_check.append(key)

        if not keys_to_check:
            return {}

        reply = self._verification.run(
            self._client,
            file_bytes,
            mime_type,
            extracted=parsed
        )

        if reply is None:
            return None

        return {
            key: reply.get(key) is True
            for key in keys_to_check
        }
