"""
data_layer/sqlite_repository.py

SQLite implementation of RecordRepository: health records live in a
database file instead of health_records.json.

It honours the same contract as JsonRecordRepository (load_all() /
save_all()), so DataManager does not change. Rows keep insertion order
(an AUTOINCREMENT id), which DataManager.get_latest_reports() relies on
as a tiebreaker for records that share a report date.

Storage layout: the scalar fields are real columns; the nested lists/dicts
(metrics, urgent_findings, flagged_trends, recent_changes) are JSON text
columns; any other key a record happens to carry is kept in "extra", so a
record round-trips without losing data.

No print()/input(), no AI calls, no business rules.
"""

import json
import sqlite3
from contextlib import closing
from typing import List

from config import DATABASE_FILE

from .repositories import RecordRepository
from .sqlite_db import connect

_SCHEMA = """
CREATE TABLE IF NOT EXISTS health_records (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id              TEXT UNIQUE,
    username               TEXT,
    date                   TEXT,
    ai_extracted_date      TEXT,
    report_id              TEXT,
    risk_score             NUMERIC,
    decision               TEXT,
    recommended_action     TEXT,
    requires_doctor_review INTEGER,
    summary                TEXT,
    metrics                TEXT,
    urgent_findings        TEXT,
    flagged_trends         TEXT,
    recent_changes         TEXT,
    extra                  TEXT
);
CREATE INDEX IF NOT EXISTS idx_health_records_username ON health_records (username);
CREATE INDEX IF NOT EXISTS idx_health_records_date ON health_records (date);
"""

_SCALAR_COLUMNS = (
    "record_id", "username", "date", "ai_extracted_date", "report_id",
    "risk_score", "decision", "recommended_action", "requires_doctor_review",
    "summary",
)
_JSON_COLUMNS = ("metrics", "urgent_findings", "flagged_trends", "recent_changes")
_KNOWN_KEYS = set(_SCALAR_COLUMNS) | set(_JSON_COLUMNS)
_ALL_COLUMNS = _SCALAR_COLUMNS + _JSON_COLUMNS + ("extra",)

_INSERT_SQL = "INSERT INTO health_records ({}) VALUES ({})".format(
    ", ".join(_ALL_COLUMNS), ", ".join("?" for _ in _ALL_COLUMNS)
)
_SELECT_SQL = "SELECT {} FROM health_records ORDER BY id".format(", ".join(_ALL_COLUMNS))


def _record_to_row(record: dict) -> tuple:
    values = []
    for col in _SCALAR_COLUMNS:
        value = record.get(col)
        if col == "requires_doctor_review" and value is not None:
            value = int(bool(value))
        values.append(value)
    for col in _JSON_COLUMNS:
        values.append(json.dumps(record[col]) if col in record else None)
    extra = {k: v for k, v in record.items() if k not in _KNOWN_KEYS}
    values.append(json.dumps(extra) if extra else None)
    return tuple(values)


def _row_to_record(row: tuple) -> dict:
    data = dict(zip(_ALL_COLUMNS, row))
    record = {}
    for col in _SCALAR_COLUMNS:
        if data[col] is not None:
            record[col] = data[col]
    if "requires_doctor_review" in record:
        record["requires_doctor_review"] = bool(record["requires_doctor_review"])
    for col in _JSON_COLUMNS:
        if data[col] is not None:
            record[col] = json.loads(data[col])
    if data["extra"]:
        record.update(json.loads(data["extra"]))
    return record


class SqliteRecordRepository(RecordRepository):
    """Stores health records in a SQLite database file."""

    def __init__(self, db_path: str = DATABASE_FILE):
        self.__db_path = db_path

    @property
    def db_path(self) -> str:
        return self.__db_path

    def _connect(self) -> sqlite3.Connection:
        return connect(self.__db_path, _SCHEMA)

    def load_all(self) -> List[dict]:
        """Every stored record in the order it was saved; [] if none or unreadable."""
        try:
            with closing(self._connect()) as conn:
                return [_row_to_record(row) for row in conn.execute(_SELECT_SQL)]
        except (sqlite3.Error, OSError, ValueError):
            return []

    def save_all(self, records: List[dict]) -> bool:
        """Replace all stored records in ONE transaction: either every record
        is written or, on any failure, the previous contents are kept."""
        try:
            rows = [_record_to_row(r) for r in records]
            with closing(self._connect()) as conn:
                with conn:  # commits on success, rolls back on error
                    conn.execute("DELETE FROM health_records")
                    conn.executemany(_INSERT_SQL, rows)
            return True
        except (sqlite3.Error, OSError, TypeError, ValueError):
            return False
