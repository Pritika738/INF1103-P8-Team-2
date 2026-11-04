"""
tests/test_io_manager.py

Tests for the IO Manager and the io_layer package. No keyboard or
terminal is needed: ScriptedInterface feeds canned answers and records
everything the IO Manager writes.

Run with:
    pytest tests/test_io_manager.py
"""

import pytest

from io_layer import (
    ChoiceValidator, CompactRecordFormatter, ConsoleInterface, DateValidator,
    InputValidator, Menu, MimeTypeValidator, NonEmptyValidator, NumberValidator,
    RecordFormatter, TextRecordFormatter, UserInterface, ValidationError, YesNoValidator,
)
from io_manager import IOManager


class ScriptedInterface(UserInterface):
    """Test double: answers come from a list, output is captured."""

    def __init__(self, answers=()):
        self._answers = list(answers)
        self.output = []
        self.prompts = []

    def read(self, prompt):
        self.prompts.append(prompt)
        if not self._answers:
            raise AssertionError("IOManager asked for more input than the test scripted.")
        return self._answers.pop(0)

    def write(self, message=""):
        self.output.append(message)

    @property
    def text(self):
        return "\n".join(self.output)


# ---------------------------------------------------------------------------
# Design: interface, abstract classes, polymorphism
# ---------------------------------------------------------------------------

class TestDesign:
    def test_interface_and_abstract_base_classes_cannot_be_instantiated(self):
        for abstract in (UserInterface, InputValidator, RecordFormatter):
            with pytest.raises(TypeError):
                abstract()

    def test_console_interface_implements_the_contract(self):
        assert issubclass(ConsoleInterface, UserInterface)

    def test_console_interface_uses_input_and_print(self, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda prompt: "hello")
        console = ConsoleInterface()
        assert console.read("?") == "hello"
        console.write("shown")
        assert capsys.readouterr().out == "shown\n"

    def test_manager_works_with_any_interface_implementation(self):
        class Shouting(UserInterface):
            def __init__(self):
                self.lines = []

            def read(self, prompt):
                return "y"

            def write(self, message=""):
                self.lines.append(message.upper())

        ui = Shouting()
        manager = IOManager(ui)
        assert manager.confirm_action("Sure?") is True
        manager.show("hi")
        assert ui.lines == ["HI"]

    def test_formatters_are_interchangeable_but_behave_differently(self):
        records = [{"date": "2026-01-01", "heart_rate": 70}]
        text = IOManager(ScriptedInterface(), TextRecordFormatter())
        compact = IOManager(ScriptedInterface(), CompactRecordFormatter())
        for manager in (text, compact):
            manager.show_health_records(records)
        assert text._interface.text != compact._interface.text


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

class TestValidators:
    def test_number_accepts_numbers_and_blank(self):
        v = NumberValidator()
        assert v.validate(" 72 ") == 72.0
        assert v.validate("5.5") == 5.5
        assert v.validate("") is None

    @pytest.mark.parametrize("raw", ["abc", "1,2", "12abc"])
    def test_number_rejects_text(self, raw):
        with pytest.raises(ValidationError):
            NumberValidator().validate(raw)

    def test_required_number_rejects_blank(self):
        with pytest.raises(ValidationError):
            NumberValidator(required=True).validate("  ")

    def test_non_empty(self):
        assert NonEmptyValidator().validate("  ann ") == "ann"
        with pytest.raises(ValidationError):
            NonEmptyValidator().validate("   ")

    def test_optional_non_empty_returns_blank_value(self):
        assert NonEmptyValidator(required=False, blank_value="").validate("") == ""

    @pytest.mark.parametrize("raw", ["2026-10-10", "2024-02-29"])
    def test_date_accepts_real_dates(self, raw):
        assert DateValidator().validate(raw) == raw

    @pytest.mark.parametrize("raw", ["10/10/2026", "2026-13-40", "2025-02-29", "today", ""])
    def test_date_rejects_bad_dates(self, raw):
        with pytest.raises(ValidationError):
            DateValidator().validate(raw)

    @pytest.mark.parametrize("raw,expected", [("y", True), ("YES", True), ("n", False), ("No", False)])
    def test_yes_no(self, raw, expected):
        assert YesNoValidator().validate(raw) is expected

    def test_yes_no_rejects_other_answers(self):
        with pytest.raises(ValidationError):
            YesNoValidator().validate("maybe")

    def test_choice_validator(self):
        v = ChoiceValidator(["1", "2"])
        assert v.validate("2") == "2"
        with pytest.raises(ValidationError):
            v.validate("9")

    def test_mime_validator(self):
        v = MimeTypeValidator({"application/pdf"})
        assert v.validate("application/pdf") == "application/pdf"
        assert v.is_supported("application/pdf") and not v.is_supported("text/plain")
        with pytest.raises(ValidationError):
            v.validate("text/plain")


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

class TestFormatters:
    RECORDS = [
        {"date": "2026-01-01", "heart_rate": 70, "blood_glucose": 5.5},
        {"date": "2026-02-01", "metrics": {"heart_rate": 80, "blood_glucose": None}},
    ]

    @pytest.mark.parametrize("formatter", [TextRecordFormatter(), CompactRecordFormatter()])
    def test_empty_list_message(self, formatter):
        assert formatter.format([]) == "No health records found."

    def test_text_formatter_handles_flat_and_nested_records(self):
        out = TextRecordFormatter().format(self.RECORDS)
        assert "2 record(s)" in out and "heart_rate: 70" in out and "heart_rate: 80" in out
        assert "blood_glucose: None" not in out

    def test_compact_formatter_is_one_line_per_record(self):
        out = CompactRecordFormatter().format(self.RECORDS)
        assert len(out.splitlines()) == 2
        assert "2026-01-01: heart_rate=70, blood_glucose=5.5" in out

    def test_compact_formatter_handles_missing_metrics(self):
        assert "no metrics" in CompactRecordFormatter().format([{"date": "2026-01-01"}])


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

class TestMenu:
    def test_main_menu_lists_all_options(self):
        menu = Menu.main_menu()
        assert menu.keys == ["1", "2", "3", "4", "5"]
        assert "5. Exit" in menu.render()


# ---------------------------------------------------------------------------
# IOManager behaviour
# ---------------------------------------------------------------------------

class TestIOManager:
    def test_ask_reprompts_until_valid_and_explains_why(self):
        ui = ScriptedInterface(["abc", "", "42"])
        assert IOManager(ui).ask("Number: ", NumberValidator(required=True)) == 42.0
        assert len(ui.prompts) == 3
        assert len(ui.output) == 2  # one error message per bad answer

    def test_menu_choice_rejects_invalid_then_accepts(self):
        ui = ScriptedInterface(["9", "abc", "3"])
        assert IOManager(ui).get_menu_choice() == "3"

    def test_show_main_menu(self):
        ui = ScriptedInterface()
        IOManager(ui).show_main_menu()
        assert "Add Health Record" in ui.text

    def test_confirm_action(self):
        assert IOManager(ScriptedInterface(["what", "y"])).confirm_action("Delete?") is True
        assert IOManager(ScriptedInterface(["n"])).confirm_action("Delete?") is False

    def test_get_non_empty_string_retries_blank(self):
        ui = ScriptedInterface(["  ", "ann"])
        assert IOManager(ui).get_non_empty_string("Name: ") == "ann"

    def test_prompt_new_health_record_collects_and_validates(self):
        ui = ScriptedInterface([
            "10/10/2026",   # rejected: wrong date format
            "2026-10-10",
            "120", "80", "72", "5.5", "",       # cholesterol skipped
            "", "", "",                          # optional text fields skipped
        ])
        record = IOManager(ui).prompt_new_health_record()
        assert record["date"] == "2026-10-10"
        assert record["blood_pressure_systolic"] == 120.0
        assert record["cholesterol"] is None
        assert record["medication_name"] == ""

    def test_prompt_new_health_record_reprompts_bad_number(self):
        ui = ScriptedInterface(["2026-10-10", "abc", "120", "80", "72", "5.5", "5", "", "", ""])
        record = IOManager(ui).prompt_new_health_record()
        assert record["blood_pressure_systolic"] == 120.0
        assert any("valid number" in line for line in ui.output)

    def test_show_health_records_uses_the_formatter(self):
        ui = ScriptedInterface()
        IOManager(ui).show_health_records([{"date": "2026-01-01", "heart_rate": 70}])
        assert "heart_rate: 70" in ui.text

    def test_show_health_records_empty(self):
        ui = ScriptedInterface()
        IOManager(ui).show_health_records([])
        assert "No health records found." in ui.text

    @pytest.mark.parametrize("mime,expected", [
        ("application/pdf", True), ("image/png", True), ("image/jpeg", True),
        ("text/plain", False), ("", False), (None, False),
    ])
    def test_is_supported_upload_type(self, mime, expected):
        assert IOManager(ScriptedInterface()).is_supported_upload_type(mime) is expected

    def test_show_placeholder(self):
        ui = ScriptedInterface()
        IOManager(ui).show_placeholder("Trends")
        assert "[Trends]" in ui.text
