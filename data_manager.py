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

import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import date as _date, datetime as _datetime

from config import (
    HEALTH_RECORDS_FILE,
    CONSULTATION_PDF_DIR,
    CONSULTATION_SUMMARIES_FILE,
    ORIGINAL_REPORTS_DIR,
    ORIGINAL_REPORTS_FILE,
    LATEST_REPORTS_LIMIT,
    MAX_RETAINED_SUMMARY_PDFS,
)


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

    Creates the parent directory if it does not already exist. Writes
    to a temporary file first and then atomically replaces the real
    file (os.replace()) rather than writing directly into it - if two
    saves happen close together (e.g. two uploads processed around the
    same time), a reader can only ever see one complete, valid file,
    never a half-written mix of both (a "torn write"). This does not
    prevent one save's data from being lost if another save started
    from an older snapshot (a "lost update") - full protection against
    that would need a real file lock, which is not implemented here.

    Returns True on success, False if the write failed.
    """
    try:
        directory = os.path.dirname(file_path) or "."
        os.makedirs(directory, exist_ok=True)
        tmp_path = f"{file_path}.tmp-{os.getpid()}"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        os.replace(tmp_path, file_path)
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
    get_records_by_date(). A unique "record_id" is stamped on the same
    way if missing, so this specific record can later be found again
    by update_record_date() - e.g. to correct a report that was saved
    with the wrong date. The caller's original dict is never mutated.

    Args:
        record: dict - the processed record to store.
        file_path: str - which records file to write to (defaults to
            the real health records file; overridable for testing).

    Returns:
        True on success, False if saving failed.
    """
    record_to_save = dict(record)
    record_to_save.setdefault("date", _date.today().isoformat())
    record_to_save.setdefault("record_id", uuid.uuid4().hex)
    return add_health_record(record_to_save, file_path)


def update_record_date(record_id, new_date, file_path=HEALTH_RECORDS_FILE):
    """
    Correct one stored record's "date" field by its record_id,
    preserving every other field on it and every other record
    untouched. Used to fix a report that was saved with the wrong date
    (e.g. a GUI date-picker that defaulted incorrectly).

    Args:
        record_id: str - the record's unique "record_id" (stamped by
            save_record(); see backfill_record_ids() for records saved
            before that existed).
        new_date: str - the corrected date, "YYYY-MM-DD".
        file_path: str - which records file to update (defaults to the
            real health records file; overridable for testing).

    Returns:
        True if a matching record was found and the save succeeded,
        False if no record has this ID, or the write failed.
    """
    records = load_health_records(file_path)

    found = False
    for record in records:
        if record.get("record_id") == record_id:
            record["date"] = new_date
            found = True
            break

    if not found:
        return False

    return save_health_records(records, file_path)


def backfill_record_ids(file_path=HEALTH_RECORDS_FILE):
    """
    Give every stored record that is missing a "record_id" a new one,
    so records saved before save_record() started stamping one can
    still be individually found and corrected by update_record_date().
    Safe to call repeatedly: a record that already has an ID is never
    touched, and if nothing is missing one, no write happens at all.

    Args:
        file_path: str - which records file to update (defaults to the
            real health records file; overridable for testing).

    Returns:
        The number of records that were given a new ID (0 if every
        record already had one, or the file is empty/missing).
    """
    records = load_health_records(file_path)

    added = 0
    for record in records:
        if not record.get("record_id"):
            record["record_id"] = uuid.uuid4().hex
            added += 1

    if added:
        save_health_records(records, file_path)

    return added


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


def get_latest_reports(records, limit=LATEST_REPORTS_LIMIT):
    """
    Select the most recent `limit` records by their own "date" field -
    the medical report's date, not when it happened to be uploaded or
    saved. Used for active trend analysis and consultation preparation
    only; Health History is unaffected and keeps showing every record
    by calling load_health_records() directly instead of this.

    Two records can legitimately share the same report date (e.g. two
    reports both dated today). save_record()/add_health_record() always
    append, so list position already reflects save order - the sort key
    includes that original position as a tiebreaker, so that among
    same-dated records, the one saved most recently is still treated as
    the most recent, instead of arbitrarily picking whichever happened
    to load first.

    Args:
        records: list of record dicts (each expected to have a "date").
        limit: int - how many of the most recent report dates to keep.

    Returns:
        Up to `limit` records, sorted oldest to newest (matching the
        order logic_manager.evaluate_health_metrics()/
        analyze_recent_changes() expect for historical_records).
        Records with no usable "date" sort as the oldest, so a missing
        date can never push out a real, dated record from this
        selection.
    """
    def sort_key(indexed_record):
        index, record = indexed_record
        return (record.get("date") or "", index)

    indexed = list(enumerate(records))
    newest_first = sorted(indexed, key=sort_key, reverse=True)
    latest_indexed = newest_first[:limit]
    oldest_first = sorted(latest_indexed, key=sort_key)
    return [record for _, record in oldest_first]


# --- Consultation-summary PDF persistence ---------------------------------
# These never touch health_records.json - generated summary PDFs and
# their metadata are tracked completely separately, so pruning old
# summaries (see max_retained below) can never delete a medical record.

def _safe_filename_component(value):
    """
    Turn an arbitrary string (a date, a username, a timestamp) into
    something safe to use inside a filename - letters, numbers, dashes
    and underscores only, everything else replaced with "_".
    """
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(value)) or "unknown"


def save_consultation_pdf(
    pdf_bytes,
    report_date,
    username,
    pdf_dir=CONSULTATION_PDF_DIR,
    summaries_file=CONSULTATION_SUMMARIES_FILE,
    max_retained=MAX_RETAINED_SUMMARY_PDFS,
):
    """
    Save a generated consultation-summary PDF to disk and record its
    metadata, so it can be listed and re-downloaded later from the
    Consultation page's Summary History. Only ever touches generated
    summary PDFs and their own metadata file - never health_records.json.

    Args:
        pdf_bytes: bytes - the generated PDF file's contents.
        report_date: str or None - the medical report date this summary
            covers (used in the filename/metadata; not necessarily today).
        username: str - whose summary this is.
        pdf_dir: str - directory PDFs are written to (overridable for
            testing).
        summaries_file: str - metadata JSON file (overridable for
            testing).
        max_retained: int or None - how many summaries to keep per user
            before the oldest generated one is deleted; None keeps all.

    Returns:
        The new metadata dict ({"username", "report_date",
        "generated_at", "filename"}) on success, or None if saving
        failed.
    """
    try:
        os.makedirs(pdf_dir, exist_ok=True)
    except OSError:
        return None

    # Microsecond precision (not just seconds) - several summaries can
    # genuinely be generated within the same second, and this value is
    # used both in the filename and to order/prune old ones, so it
    # must be unique per save.
    generated_at = _datetime.now().isoformat(timespec="microseconds")
    filename = (
        f"consultation_{_safe_filename_component(username)}_"
        f"{_safe_filename_component(report_date)}_"
        f"{_safe_filename_component(generated_at.replace(':', '-'))}.pdf"
    )
    pdf_path = os.path.join(pdf_dir, filename)

    try:
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
    except OSError:
        return None

    entry = {
        "username": username,
        "report_date": report_date,
        "generated_at": generated_at,
        "filename": filename,
    }

    summaries = load_health_records(summaries_file)
    summaries.append(entry)

    if max_retained is not None:
        other_entries = [s for s in summaries if s.get("username") != username]
        user_entries = sorted(
            (s for s in summaries if s.get("username") == username),
            key=lambda s: s.get("generated_at") or "",
        )
        if len(user_entries) > max_retained:
            for old in user_entries[:-max_retained]:
                try:
                    os.remove(os.path.join(pdf_dir, old["filename"]))
                except OSError:
                    pass
            user_entries = user_entries[-max_retained:]
        summaries = other_entries + user_entries

    if not save_health_records(summaries, summaries_file):
        return None

    return entry


def list_consultation_pdfs(username, summaries_file=CONSULTATION_SUMMARIES_FILE):
    """
    List previously generated consultation-summary PDFs for one user,
    sorted by the medical report date they cover (newest first) - not
    by when the summary itself was generated. Two summaries can share a
    report date (e.g. regenerated after a correction); generated_at is
    used as a tiebreaker so the most recently generated one of a tied
    pair is listed first.

    Args:
        username: str - whose summaries to list.
        summaries_file: str - metadata JSON file (overridable for
            testing).

    Returns:
        A list of metadata dicts (empty if none exist).
    """
    summaries = load_health_records(summaries_file)
    user_entries = [s for s in summaries if s.get("username") == username]
    return sorted(
        user_entries,
        key=lambda s: (s.get("report_date") or "", s.get("generated_at") or ""),
        reverse=True,
    )


def get_consultation_pdf_bytes(filename, pdf_dir=CONSULTATION_PDF_DIR):
    """
    Read back a previously saved consultation-summary PDF's raw bytes
    for download.

    Args:
        filename: str - the filename recorded in a
            list_consultation_pdfs() entry.
        pdf_dir: str - directory PDFs are stored in (overridable for
            testing).

    Returns:
        The PDF's bytes, or None if the file is missing or unreadable.
    """
    # os.path.basename() strips any directory components so a stray
    # "../" in a filename can never escape pdf_dir.
    pdf_path = os.path.join(pdf_dir, os.path.basename(filename))
    try:
        with open(pdf_path, "rb") as f:
            return f.read()
    except OSError:
        return None


# --- Original medical report file persistence ------------------------------
# The actual uploaded PDF/image, kept byte-for-byte as uploaded - distinct
# from both health_records.json (the AI Manager's extracted numbers) and
# the consultation-summary PDFs above (the AI Manager's own generated
# output). Every original report is kept forever regardless of
# config.LATEST_REPORTS_LIMIT - that limit only affects trend/consultation
# calculations, never what stays visible in Health History.

def _guess_extension(mime_type):
    """Fallback file extension when the original filename has none."""
    return {
        "application/pdf": ".pdf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
    }.get(mime_type, "")


def save_original_report(
    file_bytes,
    original_filename,
    mime_type,
    report_date,
    username,
    reports_dir=ORIGINAL_REPORTS_DIR,
    metadata_file=ORIGINAL_REPORTS_FILE,
):
    """
    Save an uploaded medical report's original file exactly as
    uploaded - no re-encoding, no format conversion - and record its
    metadata so it can be found again and linked to its processed
    health record.

    If the exact same bytes have already been saved for this user
    (checked by a content hash, not by filename), the existing entry
    is reused instead of storing a second physical copy - this is the
    "prevent duplicate storage" requirement. Each stored file is named
    using a unique ID, never the original filename alone, so two
    different files that happen to share a name never collide.

    Args:
        file_bytes: bytes - the uploaded file's raw, unmodified content.
        original_filename: str - the filename the user uploaded (kept
            in metadata for display; never used as the stored filename).
        mime_type: str - e.g. "application/pdf", "image/png".
        report_date: str or None - the medical report's own date.
        username: str - whose report this is.
        reports_dir: str - directory files are written to (overridable
            for testing).
        metadata_file: str - metadata JSON file (overridable for
            testing).

    Returns:
        The metadata dict ({"report_id", "username", "report_date",
        "upload_date", "filename", "stored_filename", "mime_type",
        "content_hash"}) on success, or None if saving failed.
    """
    content_hash = hashlib.sha256(file_bytes).hexdigest()

    existing = load_health_records(metadata_file)
    for entry in existing:
        if entry.get("username") == username and entry.get("content_hash") == content_hash:
            return entry  # identical file already stored for this user - reuse it

    try:
        os.makedirs(reports_dir, exist_ok=True)
    except OSError:
        return None

    report_id = uuid.uuid4().hex
    extension = os.path.splitext(original_filename)[1] or _guess_extension(mime_type)
    stored_filename = f"{report_id}{extension}"
    file_path = os.path.join(reports_dir, stored_filename)

    try:
        with open(file_path, "wb") as f:
            f.write(file_bytes)
    except OSError:
        return None

    entry = {
        "report_id": report_id,
        "username": username,
        "report_date": report_date,
        "upload_date": _date.today().isoformat(),
        "filename": original_filename,
        "stored_filename": stored_filename,
        "mime_type": mime_type,
        "content_hash": content_hash,
    }

    existing.append(entry)
    if not save_health_records(existing, metadata_file):
        return None

    return entry


def list_original_reports(username, metadata_file=ORIGINAL_REPORTS_FILE):
    """
    List all original uploaded medical report files for one user,
    sorted by report date, newest first. Never limited to the latest
    five - Health History always shows every uploaded report.

    Args:
        username: str - whose reports to list.
        metadata_file: str - metadata JSON file (overridable for
            testing).

    Returns:
        A list of metadata dicts (empty if none exist).
    """
    entries = load_health_records(metadata_file)
    user_entries = [e for e in entries if e.get("username") == username]
    return sorted(user_entries, key=lambda e: e.get("report_date") or "", reverse=True)


def get_original_report_bytes(stored_filename, reports_dir=ORIGINAL_REPORTS_DIR):
    """
    Read back a previously saved original medical report file's raw
    bytes for download, exactly as it was uploaded.

    Args:
        stored_filename: str - the "stored_filename" from a
            list_original_reports() entry.
        reports_dir: str - directory files are stored in (overridable
            for testing).

    Returns:
        The file's bytes, or None if missing or unreadable.
    """
    file_path = os.path.join(reports_dir, os.path.basename(stored_filename))
    try:
        with open(file_path, "rb") as f:
            return f.read()
    except OSError:
        return None


def get_original_report_by_id(report_id, metadata_file=ORIGINAL_REPORTS_FILE):
    """
    Find one original report's metadata by its report_id - used to
    link a processed health record (which stores this same report_id)
    back to its source file.

    Args:
        report_id: str - the unique ID assigned when the file was saved.
        metadata_file: str - metadata JSON file (overridable for
            testing).

    Returns:
        The matching metadata dict, or None if no entry has this ID.
    """
    entries = load_health_records(metadata_file)
    for entry in entries:
        if entry.get("report_id") == report_id:
            return entry
    return None
