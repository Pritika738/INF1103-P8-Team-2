"""
io_manager.py

All user-facing input() and print() operations live in this module.
Other modules should never call input()/print() directly - they should
return data/results, and io_manager displays/collects it.
"""

from config import SUPPORTED_METRICS


# --- Menu display --------------------------------------------------------

def show_main_menu():
    """Print the main CLI menu options."""
    print("\n===== Health History & Consultation Prep =====")
    print("1. Add Health Record")
    print("2. View Health History")
    print("3. Analyse Health Records")
    print("4. Generate Consultation Report")
    print("5. Exit")


def get_menu_choice():
    """
    Prompt the user for a menu choice and return it as a string.
    Does not validate the value - callers decide how to handle it.
    """
    return input("Select an option (1-5): ").strip()


def show_message(message):
    """Print a generic message to the user."""
    print(message)


def show_placeholder(feature_name):
    """Print a standard 'not implemented yet' message for a feature."""
    print(f"[{feature_name}] This feature is not implemented yet.")


# --- Input collection ------------------------------------------------------

def prompt_new_health_record():
    """
    Prompt the user for the fields of a new health record and return
    them as a dictionary. Uses the basic validation helpers below.

    Returns:
        dict with the collected health record fields.
    """
    print("\n-- Add Health Record --")
    record = {
        "date": input("Record date (YYYY-MM-DD): ").strip(),
        "blood_pressure_systolic": get_valid_number("Systolic blood pressure (mmHg): "),
        "blood_pressure_diastolic": get_valid_number("Diastolic blood pressure (mmHg): "),
        "heart_rate": get_valid_number("Heart rate (bpm): "),
        "blood_glucose": get_valid_number("Blood glucose (mmol/L): "),
        "cholesterol": get_valid_number("Cholesterol (mmol/L): "),
        "medication_name": input("Medication name (optional): ").strip(),
        "medication_dosage": input("Medication dosage (optional): ").strip(),
        "allergies": input("Allergy information (optional): ").strip(),
    }
    return record


def show_health_records(records):
    """Print a list of health records in a simple readable format."""
    if not records:
        print("No health records found.")
        return

    print(f"\n-- Health History ({len(records)} record(s)) --")
    for index, record in enumerate(records, start=1):
        print(f"\nRecord {index}:")
        for metric in SUPPORTED_METRICS:
            if metric in record:
                print(f"  {metric}: {record[metric]}")
        if record.get("date"):
            print(f"  date: {record['date']}")


# --- Reusable input-validation helpers -------------------------------------

def get_valid_number(prompt_text):
    """
    Repeatedly prompt the user until a valid number (int or float) is
    entered, or the user leaves the field blank (returns None).
    """
    while True:
        raw_value = input(prompt_text).strip()
        if raw_value == "":
            return None
        try:
            return float(raw_value)
        except ValueError:
            print("Please enter a valid number, or leave blank to skip.")


def get_non_empty_string(prompt_text):
    """Repeatedly prompt the user until a non-empty string is entered."""
    while True:
        value = input(prompt_text).strip()
        if value:
            return value
        print("This field cannot be empty.")


def confirm_action(prompt_text):
    """Ask the user a yes/no question and return True/False."""
    while True:
        answer = input(f"{prompt_text} (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer 'y' or 'n'.")
