"""
ai/parser.py

Turns raw model text into a Python dict. Parsing only - it does not
judge the contents (that is each AITask's validate()).
"""

import json
from typing import Optional


class ResponseParser:
    """Safely parses a raw AI response into a JSON object (dict)."""

    def parse(self, raw_response) -> Optional[dict]:
        """Return a dict, or None if the text is missing, not JSON, or not an object.

        Never raises.
        """
        try:
            parsed = json.loads(raw_response)
        except (json.JSONDecodeError, TypeError):
            return None
        return parsed if isinstance(parsed, dict) else None
