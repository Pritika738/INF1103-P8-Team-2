"""
io_layer/validators.py

Input validation, one small class per kind of input.

InputValidator is an abstract template: validate() handles the blank
case and strips whitespace, and each subclass only supplies _convert()
for its own kind of value. Adding a new input type means adding a
subclass; IOManager.ask() works with any of them (Open/Closed,
polymorphism).

Validators never read or print anything - they either return a clean
value or raise ValidationError with a user-friendly message.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Iterable


class ValidationError(ValueError):
    """Raised when user input is not acceptable. The message is user-facing."""


class InputValidator(ABC):
    """Abstract base for all input validators."""

    def __init__(self, required: bool = True, blank_value: Any = None):
        self._required = required
        self._blank_value = blank_value  # returned for blank input when not required

    def validate(self, raw: str) -> Any:
        """Return the cleaned value for `raw`, or raise ValidationError."""
        text = (raw or "").strip()
        if text == "":
            if self._required:
                raise ValidationError(self._empty_message())
            return self._blank_value
        return self._convert(text)

    @abstractmethod
    def _convert(self, text: str) -> Any:
        """Convert a non-blank, stripped string or raise ValidationError."""

    def _empty_message(self) -> str:
        return "This field cannot be empty."


class NonEmptyValidator(InputValidator):
    """Any non-blank text."""

    def _convert(self, text):
        return text


class NumberValidator(InputValidator):
    """An int/float. Blank is allowed (returns None) unless required=True."""

    def __init__(self, required: bool = False):
        super().__init__(required=required, blank_value=None)

    def _convert(self, text):
        try:
            return float(text)
        except ValueError:
            raise ValidationError("Please enter a valid number, or leave blank to skip.") from None

    def _empty_message(self):
        return "Please enter a valid number."


class DateValidator(InputValidator):
    """A real calendar date written as YYYY-MM-DD."""

    def _convert(self, text):
        try:
            datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            raise ValidationError("Please enter a valid date as YYYY-MM-DD.") from None
        return text

    def _empty_message(self):
        return "Please enter a date as YYYY-MM-DD."


class YesNoValidator(InputValidator):
    """y/yes -> True, n/no -> False."""

    def _convert(self, text):
        answer = text.lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        raise ValidationError("Please answer 'y' or 'n'.")

    def _empty_message(self):
        return "Please answer 'y' or 'n'."


class ChoiceValidator(InputValidator):
    """One of a fixed set of keys, e.g. menu options."""

    def __init__(self, valid_choices: Iterable[str]):
        super().__init__(required=True)
        self._valid_choices = tuple(valid_choices)

    def _convert(self, text):
        if text not in self._valid_choices:
            raise ValidationError(f"Please choose one of: {', '.join(self._valid_choices)}.")
        return text

    def _empty_message(self):
        return f"Please choose one of: {', '.join(self._valid_choices)}."


class MimeTypeValidator(InputValidator):
    """A file MIME type the application accepts for medical report uploads."""

    def __init__(self, supported_types: Iterable[str]):
        super().__init__(required=True)
        self._supported_types = frozenset(supported_types)

    def _convert(self, text):
        if text not in self._supported_types:
            raise ValidationError(
                f"Unsupported file type '{text}'. Supported: "
                f"{', '.join(sorted(self._supported_types))}."
            )
        return text

    def is_supported(self, mime_type: str) -> bool:
        """Yes/no check for callers that don't want an exception."""
        return mime_type in self._supported_types
