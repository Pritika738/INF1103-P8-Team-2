"""IO support package: user-interface channel, validators, formatters, menu.

The orchestrating class, IOManager, lives in the top-level io_manager.py.
(Named io_layer, not io, to avoid clashing with Python's standard `io` module.)
"""

from .formatters import CompactRecordFormatter, RecordFormatter, TextRecordFormatter
from .interface import ConsoleInterface, UserInterface
from .menu import Menu, MenuOption
from .validators import (
    ChoiceValidator, DateValidator, InputValidator, MimeTypeValidator,
    NonEmptyValidator, NumberValidator, ValidationError, YesNoValidator,
)

__all__ = [
    "UserInterface", "ConsoleInterface",
    "InputValidator", "ValidationError", "NonEmptyValidator", "NumberValidator",
    "DateValidator", "YesNoValidator", "ChoiceValidator", "MimeTypeValidator",
    "RecordFormatter", "TextRecordFormatter", "CompactRecordFormatter",
    "Menu", "MenuOption",
]
