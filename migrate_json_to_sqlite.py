"""
migrate_json_to_sqlite.py

One-off migration: copy the old JSON files into the SQLite database
(config.DATABASE_FILE). Currently migrates:
    data/health_records.json -> health_records table
    data/users.json          -> users table

Each table is handled on its own and is safe to run more than once: a
table that already holds data is skipped, never overwritten. The JSON
files are never modified or deleted - a "<file>.premigration" backup copy
is made before anything is written.

Usage:  python migrate_json_to_sqlite.py
"""

import os
import shutil
import sys

from config import DATABASE_FILE, HEALTH_RECORDS_FILE, USERS_FILE
from data_layer import (
    JsonAccountRepository, JsonRecordRepository,
    SqliteAccountRepository, SqliteRecordRepository,
)


def migrate_one(label: str, json_path: str, source, target) -> bool:
    """Copy one JSON file into its table. Returns False only on a real failure."""
    if target.load_all():
        print(f"[{label}] table already has data - skipped.")
        return True

    data = source.load_all()
    if not data:
        print(f"[{label}] nothing found in {json_path} - skipped.")
        return True

    backup = json_path + ".premigration"
    if not os.path.exists(backup):
        shutil.copy2(json_path, backup)
        print(f"[{label}] backed up JSON to {backup}")

    if not target.save_all(data):
        print(f"[{label}] writing to the database FAILED - nothing migrated.")
        return False

    if target.load_all() != data:
        print(f"[{label}] verification FAILED: database contents differ from the JSON file.")
        return False

    print(f"[{label}] migrated {len(data)} entries (verified identical).")
    return True


def migrate() -> int:
    print(f"Database: {DATABASE_FILE}")
    jobs = [
        ("health_records", HEALTH_RECORDS_FILE,
         JsonRecordRepository(HEALTH_RECORDS_FILE), SqliteRecordRepository(DATABASE_FILE)),
        ("users", USERS_FILE,
         JsonAccountRepository(USERS_FILE), SqliteAccountRepository(DATABASE_FILE)),
    ]
    ok = all([migrate_one(*job) for job in jobs])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(migrate())
