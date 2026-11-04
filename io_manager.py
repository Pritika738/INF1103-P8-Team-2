"""
io_manager.py

The IO Manager: all terminal-facing display and input collection goes
through this class. No other module may call input()/print() directly -
they return data/results and IOManager displays/collects it.

Object relationships (see UML):
- IOManager --> UserInterface      association: IOManager uses an
                                   injected interface; the interface has
                                   no idea IOManager exists and can be
                                   reused by anything else.
- IOManager *-- RecordFormatter, InputValidator, MimeTypeValidator, Menu
                                   composition: created and owned by
                                   IOManager; they have no purpose outside it.

Business rules, AI calls and persistence are explicitly out of scope
here - see ai_manager.py, logic_manager.py and data_manager.py.
"""

from typing import Any, Optional, Sequence

from io_layer import (
    ChoiceValidator, ConsoleInterface, DateValidator, InputValidator, Menu,
    MimeTypeValidator, NonEmptyValidator, NumberValidator, TextRecordFormatter,
    UserInterface, ValidationError, YesNoValidator,
)

__all__ = ["IOManager", "UserInterface", "ConsoleInterface", "InputValidator",
           "SUPPORTED_UPLOAD_MIME_TYPES"]

# MIME types this application currently accepts for medical report
# uploads (see GUI_PLAN.md: "Supported Upload Formats").
SUPPORTED_UPLOAD_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg"}


class IOManager:
    """Collects and validates user input; displays records, lists and results."""

    def __init__(self, interface: UserInterface, formatter=None):
        self._interface = interface                                  # association
        self._formatter = formatter or TextRecordFormatter()         # composition
        self._mime_validator = MimeTypeValidator(SUPPORTED_UPLOAD_MIME_TYPES)
        self._menu = Menu.main_menu()

    # ------------------------------------------------------------------
    # Generic prompt/display
    # ------------------------------------------------------------------

    def ask(self, prompt: str, validator) -> Any:
        """Prompt with `prompt` until `validator` accepts the answer."""
        while True:
            try:
                return validator.validate(self._interface.read(prompt))
            except ValidationError as exc:
                self._interface.write(str(exc))

    def show(self, message: str = "") -> None:
        self._interface.write(message)

    def show_placeholder(self, feature_name: str) -> None:
        self._interface.write(f"[{feature_name}] This feature is not implemented yet.")

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def show_main_menu(self) -> None:
        self._interface.write(self._menu.render())

    def get_menu_choice(self) -> str:
        """Return the user's menu choice, re-prompting until it is valid."""
        return self.ask("Select an option (1-5): ", ChoiceValidator(self._menu.keys))

    # ------------------------------------------------------------------
    # Health record input / display
    # ------------------------------------------------------------------

    def prompt_new_health_record(self) -> dict:
        """Collect a new health record's fields from the user."""
        self._interface.write("\n-- Add Health Record --")
        record = {"date": self.ask("Record date (YYYY-MM-DD): ", DateValidator())}
        for metric, label, unit in (
            ("blood_pressure_systolic", "Systolic blood pressure", "mmHg"),
            ("blood_pressure_diastolic", "Diastolic blood pressure", "mmHg"),
            ("heart_rate", "Heart rate", "bpm"),
            ("blood_glucose", "Blood glucose", "mmol/L"),
            ("cholesterol", "Cholesterol", "mmol/L"),
        ):
            record[metric] = self.ask(f"{label} ({unit}): ", NumberValidator())
        record["medication_name"] = self.ask("Medication name (optional): ", NonEmptyValidator(required=False, blank_value=""))
        record["medication_dosage"] = self.ask("Medication dosage (optional): ", NonEmptyValidator(required=False, blank_value=""))
        record["allergies"] = self.ask("Allergy information (optional): ", NonEmptyValidator(required=False, blank_value=""))
        return record

    def show_health_records(self, records: Sequence[dict]) -> None:
        """Display a list of health records using the configured formatter."""
        self._interface.write(self._formatter.format(records))

    def confirm_action(self, prompt_text: str) -> bool:
        return self.ask(f"{prompt_text} (y/n): ", YesNoValidator())

    def get_non_empty_string(self, prompt_text: str) -> str:
        return self.ask(prompt_text, NonEmptyValidator())

    # ------------------------------------------------------------------
    # Medical report upload handling
    # ------------------------------------------------------------------

    def is_supported_upload_type(self, mime_type: Optional[str]) -> bool:
        """True if `mime_type` is an accepted medical report format."""
        return self._mime_validator.is_supported(mime_type or "")
