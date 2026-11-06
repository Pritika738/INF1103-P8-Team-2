"""
migrate_records_to_sqlite.py

One-off migration: copy data/health_records.json into the SQLite database.

Safe to run more than once: it refuses to touch a database that already
holds records, and it never modifies or deletes the JSON file.

Usage:  python migrate_records_to_sqlite.py
"""

import shutil
import sys

from config import HEALTH_RECORDS_DB_FILE, HEALTH_RECORDS_FILE
from data_layer import JsonRecordRepository, SqliteRecordRepository


def migrate() -> int:
    source = JsonRecordRepository(HEALTH_RECORDS_FILE)
    target = SqliteRecordRepository(HEALTH_RECORDS_DB_FILE)

    if target.load_all():
        print(f"{HEALTH_RECORDS_DB_FILE} already contains records - nothing migrated.")
        return 1

    records = source.load_all()
    if not records:
        print("No records found in the JSON file - nothing to migrate.")
        return 0

    backup = HEALTH_RECORDS_FILE + ".premigration"
    shutil.copy2(HEALTH_RECORDS_FILE, backup)
    print(f"Backed up JSON to {backup}")

    if not target.save_all(records):
        print("Writing to the database failed - nothing migrated.")
        return 1

    migrated = target.load_all()
    if migrated != records:
        print("Verification FAILED: database contents differ from the JSON file.")
        return 1

    print(f"Migrated {len(migrated)} records to {HEALTH_RECORDS_DB_FILE} (verified identical).")
    return 0


if __name__ == "__main__":
    sys.exit(migrate())
