"""
safety_guardrail.py

Forward-compatible free-text filter, extracted from logic_manager.py so
that each class lives in its own module. logic_manager.py imports the
SafetyGuardrail class from here; its public behaviour is unchanged.
"""

from __future__ import annotations

import re


class SafetyGuardrail:
    """
    Check free-text AI-generated explanation text for prohibited
    diagnostic/prescriptive language, and reject it wholesale if found.
    Nothing in the current numeric pipeline calls this (ai_manager's
    output is purely numeric), but it is kept, tested and ready for
    if/when a future AI-generated explanation field is added - the OOP
    equivalent of the old enforce_safety_guardrails().
    """

    _FORBIDDEN_SINGLE_WORDS = ["diagnose", "disease", "prescribe", "treatment"]
    _FORBIDDEN_PHRASES = ["stop taking", "increase dose", "decrease dose"]
    _OVERRIDE_MESSAGE = (
        "Safety Override: The AI generated restricted diagnostic "
        "language. Please discuss these health trends directly with "
        "your doctor."
    )

    def enforce(self, ai_explanation: str) -> str:
        if not ai_explanation:
            return ai_explanation

        text_lower = ai_explanation.lower()

        for word in self._FORBIDDEN_SINGLE_WORDS:
            if re.search(r"\b" + re.escape(word) + r"\w*\b", text_lower):
                return self._OVERRIDE_MESSAGE

        for phrase in self._FORBIDDEN_PHRASES:
            if phrase in text_lower:
                return self._OVERRIDE_MESSAGE

        return ai_explanation
