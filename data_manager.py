"""
data_manager.py

Responsible for JSON file persistence only.

Rules for this module:
- No print() or input() calls here.
- No AI calls, no business rules - just reading/writing the records file.
- Callers (io_manager / main) are responsible for reporting errors to the user.

save_record()/get_records_by_date() are the lecturer-facing entry points
for the AI+Logic Manager pipeline: save_record() stores whatever
logic_manager.process_ai_record() returns (the "Processed Record" in
the project's architecture diagram), stamping today's date onto it if
it doesn't already have one - that is bookkeeping about when a record
was persisted, not a medical judgment, so it stays in scope here.
load_health_records()/save_health_records()/add_health_record() are
unchanged and still used directly by main.py's CLI flow.
"""

import json
import os
import shutil
from datetime import date as _date

from config import HEALTH_RECORDS_FILE


def _backup_corrupted_file(file_path):
    """
    Preserve an unreadable/unexpected records file by copying it to
    "<file_path>.bak" before any caller gets a chance to overwrite it
    with fresh data. Best-effort only - a failure here (e.g. disk full)
    is not itself allowed to crash the caller, so it is swallowed.
    """
    try:
        shutil.copy2(file_path, file_path + ".bak")
    except OSError:
        pass


def load_health_records(file_path=HEALTH_RECORDS_FILE):
    """
    Load health records from the JSON file.

    Returns a list of record dictionaries. If the file does not exist,
    an empty list is returned. If the file contains invalid/corrupted
    JSON, or valid JSON that isn't a list, the corrupted file is backed
    up to "<file_path>.bak" (so a later save can't silently destroy it)
    and an empty list is returned instead of raising an exception.
    """
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        _backup_corrupted_file(file_path)
        return []
    except OSError:
        return []

    if not isinstance(data, list):
        _backup_corrupted_file(file_path)
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


def save_record(record, file_path=HEALTH_RECORDS_FILE):
    """
    Save one already-processed health record - e.g. the dict returned
    by logic_manager.process_ai_record() - preserving all previously
    stored records (never overwrites history with just this one).

    If `record` has no "date" key, today's date is stamped onto a copy
    of it before saving, so every stored record can be found again by
    get_records_by_date(). The caller's original dict is never mutated.

    Args:
        record: dict - the processed record to store.
        file_path: str - which records file to write to (defaults to
            the real health records file; overridable for testing).

    Returns:
        True on success, False if saving failed.
    """
    record_to_save = dict(record)
    record_to_save.setdefault("date", _date.today().isoformat())
    return add_health_record(record_to_save, file_path)


def get_records_by_date(target_date, file_path=HEALTH_RECORDS_FILE):
    """
    Find all stored records whose "date" field matches `target_date`.

    Args:
        target_date: str - the date to match exactly, e.g. "2026-09-25".
        file_path: str - which records file to search (defaults to the
            real health records file; overridable for testing).

    Returns:
        A list of matching record dicts (empty if none match). Never
        raises - relies on load_health_records()'s own safe handling of
        a missing or corrupted file.
    """
    records = load_health_records(file_path)
    return [record for record in records if record.get("date") == target_date]
