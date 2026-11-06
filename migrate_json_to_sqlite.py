"""
migrate_json_to_sqlite.py

One-off migration: copy the old JSON files into the SQLite database
(config.DATABASE_FILE). Currently migrates:
    data/health_records.json         -> health_records table
    data/users.json                  -> users table
    data/consultation_summaries.json -> consultation_summaries table
    data/original_reports.json       -> original_reports table

Only metadata moves; the PDF / image files themselves stay where they are
in data/consultation_pdfs/ and data/original_reports/.

Each table is handled on its own and is safe to run more than once: a
table that already holds data is skipped, never overwritten. The JSON
files are never modified or deleted - a "<file>.premigration" backup copy
is made before anything is written.

Usage:  python migrate_json_to_sqlite.py
"""

import os
import shutil
import sys

from config import (
    CONSULTATION_SUMMARIES_FILE, DATABASE_FILE, HEALTH_RECORDS_FILE,
    ORIGINAL_REPORTS_FILE, USERS_FILE,
)
from data_layer import (
    JsonAccountRepository, JsonListStore, JsonRecordRepository,
    SqliteAccountRepository, SqliteRecordRepository,
    consultation_summaries_table, original_reports_table,
)


def migrate_one(label, json_path, load_source, load_target, save_target) -> bool:
    """Copy one JSON file into its table. Returns False only on a real failure."""
    if load_target():
        print(f"[{label}] table already has data - skipped.")
        return True

    data = load_source()
    if not data:
        print(f"[{label}] nothing found in {json_path} - skipped.")
        return True

    backup = json_path + ".premigration"
    if not os.path.exists(backup):
        shutil.copy2(json_path, backup)
        print(f"[{label}] backed up JSON to {backup}")

    if not save_target(data):
        print(f"[{label}] writing to the database FAILED - nothing migrated.")
        return False

    if load_target() != data:
        print(f"[{label}] verification FAILED: database contents differ from the JSON file.")
        return False

    print(f"[{label}] migrated {len(data)} entries (verified identical).")
    return True


def migrate() -> int:
    print(f"Database: {DATABASE_FILE}")

    records_src, records_db = JsonRecordRepository(HEALTH_RECORDS_FILE), SqliteRecordRepository(DATABASE_FILE)
    users_src, users_db = JsonAccountRepository(USERS_FILE), SqliteAccountRepository(DATABASE_FILE)
    summaries_src, summaries_db = JsonListStore(CONSULTATION_SUMMARIES_FILE), consultation_summaries_table(DATABASE_FILE)
    reports_src, reports_db = JsonListStore(ORIGINAL_REPORTS_FILE), original_reports_table(DATABASE_FILE)

    jobs = [
        ("health_records", HEALTH_RECORDS_FILE, records_src.load_all, records_db.load_all, records_db.save_all),
        ("users", USERS_FILE, users_src.load_all, users_db.load_all, users_db.save_all),
        ("consultation_summaries", CONSULTATION_SUMMARIES_FILE, summaries_src.load, summaries_db.load, summaries_db.save),
        ("original_reports", ORIGINAL_REPORTS_FILE, reports_src.load, reports_db.load, reports_db.save),
    ]
    ok = all([migrate_one(*job) for job in jobs])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(migrate())
