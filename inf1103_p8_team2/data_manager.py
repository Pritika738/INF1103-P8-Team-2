"""
data_manager.py

Responsible for JSON file persistence only.

Rules for this module:
- No print() or input() calls here.
- No AI calls, no business rules - just reading/writing the records file.
- Callers (io_manager / main) are responsible for reporting errors to the user.
"""

import json
import os

from config import HEALTH_RECORDS_FILE


def load_health_records(file_path=HEALTH_RECORDS_FILE):
    """
    Load health records from the JSON file.

    Returns a list of record dictionaries. If the file does not exist,
    an empty list is returned. If the file contains invalid/corrupted
    JSON, an empty list is returned instead of raising an exception.
    """
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(data, list):
        return []

    return data


def save_health_records(records, file_path=HEALTH_RECORDS_FILE):
    """
    Save the given list of health record dictionaries to the JSON file.

    Creates the parent directory if it does not already exist.
    Returns True on success, False if the write failed.
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        return True
    except OSError:
        return False


def add_health_record(record, file_path=HEALTH_RECORDS_FILE):
    """
    Append a single health record dictionary to the stored records
    and persist the updated list.

    Returns True on success, False if saving failed.
    """
    records = load_health_records(file_path)
    records.append(record)
    return save_health_records(records, file_path)
