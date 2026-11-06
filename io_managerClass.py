"""
io_managerClass.py

Object-oriented refactor of io_manager.py (Phase 2).

Same responsibility as before - the IO Manager: collect and validate
user input, and display records, lists, results and summaries. All
user-facing input()/print() lives here; no other module calls them
directly - they return data/results and this layer shows/collects it.
This module holds NO domain logic (no business rules, no AI calls, no
persistence) - it only talks to the user.

What changed from the procedural version
-----------------------------------------
- The free functions (show_main_menu, get_menu_choice, show_message,
  prompt_new_health_record, show_health_records, get_valid_number, ...)
  are regrouped behind a small class design:
    * Console        - the one place that actually calls print()/input(),
                       so every other class depends on an abstraction,
                       not the terminal directly (testable + swappable).
    * Prompt         - abstract input collector; NumberPrompt,
                       NonEmptyPrompt, ConfirmPrompt, FreeTextPrompt
                       specialise it (inheritance + polymorphism).
    * UploadTypePolicy - the supported-MIME-type check, encapsulated.
    * IOManager (ABC)  - the presentation contract (display_records,
                         show_message, collect_*).
    * CLIIOManager     - the concrete terminal implementation; a GUI
                         IO manager (e.g. Streamlit) is just another
                         IOManager subclass later.

OOP concepts demonstrated here
------------------------------
- Abstract classes / interfaces : IOManager, Prompt (both ABCs).
- Inheritance                   : CLIIOManager subclasses IOManager;
                                  the four Prompt subclasses specialise
                                  Prompt.
- Polymorphism                  : prompt.ask() is called uniformly
                                  regardless of the concrete prompt type;
                                  a caller holding an IOManager never
                                  needs to know it is the CLI one.
- Encapsulation                 : the terminal is reached only through
                                  Console; supported MIME types live
                                  behind UploadTypePolicy.
- Composition                   : CLIIOManager owns its Console and its
                                  prompts (they share its lifecycle).
- Association                   : Prompt uses a Console it is given but
                                  does not own.

SOLID evidence
--------------
- SRP : each Prompt collects exactly one kind of input; Console only
        does raw terminal I/O; IOManager only presents/collects.
- OCP : a new input type is a new Prompt subclass, and a new frontend
        is a new IOManager subclass - neither requires editing existing
        classes.
- LSP : any Prompt is substitutable wherever ask() is expected; any
        IOManager is substitutable wherever the app presents to a user.

Backwards compatibility
-----------------------
The original module-level functions are preserved as thin wrappers at
the bottom of this file (delegating to a shared default CLIIOManager),
so existing callers like main.py keep working unchanged while new code
can use the class API.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from config import SUPPORTED_METRICS

# MIME types this application currently accepts for medical report
# uploads (see GUI_PLAN.md: "Supported Upload Formats").
SUPPORTED_UPLOAD_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg"}


# ===========================================================================
# Console - the single boundary to the real terminal (ENCAPSULATION)
# ===========================================================================

class Console:
    """
    The one place that actually touches stdin/stdout. Every other class
    depends on this abstraction instead of calling print()/input()
    directly, which keeps the terminal dependency in exactly one place
    and makes the rest of the module unit-testable (a fake Console can
    be injected in tests).
    """

    def write(self, message: str = "") -> None:
        """Display one line/message to the user."""
        print(message)

    def read(self, prompt_text: str) -> str:
        """Collect one raw line of input, stripped of surrounding space."""
        return input(prompt_text).strip()


# ===========================================================================
# Prompt hierarchy - ABSTRACT CLASS + INHERITANCE + POLYMORPHISM
# ===========================================================================

class Prompt(ABC):
    """
    Abstract single-value input collector. A Prompt keeps asking (via
    its Console) until it gets an acceptable value, then returns it.
    Subclasses implement ask(); callers invoke ask() uniformly without
    caring which concrete prompt they hold (polymorphism).

    Association: a Prompt uses a Console it is handed, but does not own
    the Console's lifecycle.
    """

    def __init__(self, console: Console):
        self._console = console

    @abstractmethod
    def ask(self, prompt_text: str) -> Any:
        """Collect and return one validated value from the user."""
        raise NotImplementedError


class FreeTextPrompt(Prompt):
    """Collect a single line of free text as-is (may be empty)."""

    def ask(self, prompt_text: str) -> str:
        return self._console.read(prompt_text)


class NumberPrompt(Prompt):
    """
    Keep prompting until a valid number (int/float) is entered, or the
    user leaves the field blank (returns None). Mirrors the old
    get_valid_number().
    """

    def ask(self, prompt_text: str) -> Optional[float]:
        while True:
            raw_value = self._console.read(prompt_text)
            if raw_value == "":
                return None
            try:
                return float(raw_value)
            except ValueError:
                self._console.write(
                    "Please enter a valid number, or leave blank to skip."
                )


class NonEmptyPrompt(Prompt):
    """
    Keep prompting until a non-empty string is entered. Mirrors the old
    get_non_empty_string().
    """

    def ask(self, prompt_text: str) -> str:
        while True:
            value = self._console.read(prompt_text)
            if value:
                return value
            self._console.write("This field cannot be empty.")


class ConfirmPrompt(Prompt):
    """
    Ask a yes/no question and return True/False. Mirrors the old
    confirm_action().
    """

    def ask(self, prompt_text: str) -> bool:
        while True:
            answer = self._console.read(f"{prompt_text} (y/n): ").lower()
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            self._console.write("Please answer 'y' or 'n'.")


# ===========================================================================
# UploadTypePolicy - supported-format rule, encapsulated
# ===========================================================================

class UploadTypePolicy:
    """
    Holds which medical-report MIME types the application accepts and
    answers whether a given type is supported. Encapsulates the set so
    callers ask a question rather than reaching into a module-level
    constant. Mirrors the old is_supported_upload_type().
    """

    def __init__(self, supported_types: Optional[set] = None):
        self._supported_types = set(
            supported_types if supported_types is not None
            else SUPPORTED_UPLOAD_MIME_TYPES
        )

    def is_supported(self, mime_type: str) -> bool:
        """True if `mime_type` is PDF/PNG/JPEG, False otherwise."""
        return mime_type in self._supported_types


# ===========================================================================
# IOManager - the presentation CONTRACT (ABSTRACT CLASS / INTERFACE)
# ===========================================================================

class IOManager(ABC):
    """
    Abstract IO Manager: the contract any frontend (terminal, GUI, ...)
    must satisfy to collect input from and present information to the
    user. Keeping this abstract is what lets the rest of the app hold an
    IOManager reference and stay agnostic about whether it is talking to
    a terminal or a browser.
    """

    @abstractmethod
    def show_message(self, message: str) -> None: ...

    @abstractmethod
    def show_health_records(self, records: List[Dict[str, Any]]) -> None: ...

    @abstractmethod
    def collect_new_health_record(self) -> Dict[str, Any]: ...


# ===========================================================================
# CLIIOManager - concrete terminal implementation (INHERITANCE + COMPOSITION)
# ===========================================================================

class CLIIOManager(IOManager):
    """
    Terminal implementation of the IO Manager. Owns a Console and the
    reusable Prompt objects (composition - they live and die with it),
    and uses an UploadTypePolicy for format checks.

    Every method here is behaviour-for-behaviour identical to the
    matching function in the procedural io_manager.py.
    """

    def __init__(self,
                 console: Optional[Console] = None,
                 upload_policy: Optional[UploadTypePolicy] = None):
        # Composition: the IO manager creates/owns these collaborators.
        self._console = console or Console()
        self._upload_policy = upload_policy or UploadTypePolicy()

        # Reusable prompts, each bound to this manager's Console.
        self._text = FreeTextPrompt(self._console)
        self._number = NumberPrompt(self._console)
        self._non_empty = NonEmptyPrompt(self._console)
        self._confirm = ConfirmPrompt(self._console)

    # --- Menu display ----------------------------------------------------

    def show_main_menu(self) -> None:
        """Print the main CLI menu options."""
        self._console.write("\n===== Health History & Consultation Prep =====")
        self._console.write("1. Add Health Record")
        self._console.write("2. View Health History")
        self._console.write("3. Analyse Health Records")
        self._console.write("4. Generate Consultation Report")
        self._console.write("5. Exit")

    def get_menu_choice(self) -> str:
        """
        Prompt for a menu choice and return it as a string. Does not
        validate the value - callers decide how to handle it.
        """
        return self._console.read("Select an option (1-5): ")

    def show_message(self, message: str) -> None:
        """Print a generic message to the user."""
        self._console.write(message)

    def show_placeholder(self, feature_name: str) -> None:
        """Print a standard 'not implemented yet' message for a feature."""
        self._console.write(f"[{feature_name}] This feature is not implemented yet.")

    # --- Input collection ------------------------------------------------

    def collect_new_health_record(self) -> Dict[str, Any]:
        """
        Prompt for the fields of a new health record and return them as
        a dictionary. Mirrors the old prompt_new_health_record().
        """
        self._console.write("\n-- Add Health Record --")
        record = {
            "date": self._text.ask("Record date (YYYY-MM-DD): "),
            "blood_pressure_systolic": self._number.ask("Systolic blood pressure (mmHg): "),
            "blood_pressure_diastolic": self._number.ask("Diastolic blood pressure (mmHg): "),
            "heart_rate": self._number.ask("Heart rate (bpm): "),
            "blood_glucose": self._number.ask("Blood glucose (mmol/L): "),
            "cholesterol": self._number.ask("Cholesterol (mmol/L): "),
            "medication_name": self._text.ask("Medication name (optional): "),
            "medication_dosage": self._text.ask("Medication dosage (optional): "),
            "allergies": self._text.ask("Allergy information (optional): "),
        }
        return record

    # --- Record display --------------------------------------------------

    def show_health_records(self, records: List[Dict[str, Any]]) -> None:
        """Print a list of health records in a simple readable format."""
        if not records:
            self._console.write("No health records found.")
            return

        self._console.write(f"\n-- Health History ({len(records)} record(s)) --")
        for index, record in enumerate(records, start=1):
            self._console.write(f"\nRecord {index}:")
            for metric in SUPPORTED_METRICS:
                if metric in record:
                    self._console.write(f"  {metric}: {record[metric]}")
            if record.get("date"):
                self._console.write(f"  date: {record['date']}")

    # --- Medical report upload handling ----------------------------------

    def is_supported_upload_type(self, mime_type: str) -> bool:
        """Delegate to the upload policy. Mirrors the old free function."""
        return self._upload_policy.is_supported(mime_type)

    # --- Reusable input prompts (polymorphic ask()) ----------------------

    def get_valid_number(self, prompt_text: str) -> Optional[float]:
        """Prompt for a number (or blank -> None). Mirrors old helper."""
        return self._number.ask(prompt_text)

    def get_non_empty_string(self, prompt_text: str) -> str:
        """Prompt until a non-empty string is entered. Mirrors old helper."""
        return self._non_empty.ask(prompt_text)

    def confirm_action(self, prompt_text: str) -> bool:
        """Ask a yes/no question. Mirrors old helper."""
        return self._confirm.ask(prompt_text)


# ===========================================================================
# Backwards-compatible module-level API
# ---------------------------------------------------------------------------
# Existing callers (e.g. main.py) still import and call the original free
# functions. These delegate to one shared default CLIIOManager so nothing
# breaks during the migration, while new code can use the class API above.
# ===========================================================================

_default_io = CLIIOManager()


def show_main_menu():
    _default_io.show_main_menu()


def get_menu_choice():
    return _default_io.get_menu_choice()


def show_message(message):
    _default_io.show_message(message)


def show_placeholder(feature_name):
    _default_io.show_placeholder(feature_name)


def prompt_new_health_record():
    return _default_io.collect_new_health_record()


def show_health_records(records):
    _default_io.show_health_records(records)


def is_supported_upload_type(mime_type):
    return _default_io.is_supported_upload_type(mime_type)


def get_valid_number(prompt_text):
    return _default_io.get_valid_number(prompt_text)


def get_non_empty_string(prompt_text):
    return _default_io.get_non_empty_string(prompt_text)


def confirm_action(prompt_text):
    return _default_io.confirm_action(prompt_text)
