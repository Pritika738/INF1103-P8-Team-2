"""
ai_layer/parser.py

Turns raw model text into a Python dict. Parsing only - it does not
judge the contents (that is each AITask's validate()).
"""

import json
from typing import Optional


class ResponseParser:
    """Safely parses a raw AI response into a JSON object (dict)."""

    def parse(self, raw_response) -> Optional[dict]:
        """Return a dict, or None if the text is missing, not JSON, or not an object.

        A reply wrapped in a Markdown code fence (```json ... ```) is
        accepted too - models often add one even when told not to.
        Never raises.
        """
        if not isinstance(raw_response, str):
            return None
        text = self._strip_code_fence(raw_response.strip())
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        """Remove one surrounding ``` fence (with or without a language tag)."""
        if text.startswith("```") and text.endswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                return text[first_newline + 1:-3].strip()
        return text
