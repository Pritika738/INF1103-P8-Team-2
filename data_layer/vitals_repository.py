"""
data_layer/vitals_repository.py

SQLite implementation of RecordRepository for self-logged vitals: the
"vitals" table of config.DATABASE_FILE, replacing data/manual_vitals.json.

Same contract as JsonRecordRepository (load_all() / save_all()), so
DataManager's save_manual_vital / list_manual_vitals / delete_manual_vital
work unchanged. Rows keep insertion order (AUTOINCREMENT id), which
list_manual_vitals() relies on as a tiebreaker for entries measured at
the same moment.

Storage layout:
- each tracked metric is its own NUMERIC column (a blank reading is NULL),
  so the table can be queried directly, e.g. "heart_rate > 100";
- the finding lists are JSON text columns;
- any other key an entry carries is kept in "extra", so nothing is lost.

On load, "metrics" always holds all four metric keys (None when blank) -
the same shape ManualVitalsValidator produces for every entry.

No print()/input(), no AI calls, no business rules.
"""

import json
import sqlite3
from contextlib import closing
from typing import List

from config import DATABASE_FILE

from .repositories import RecordRepository
from .sqlite_db import connect

_METRIC_COLUMNS = (
    "blood_pressure_systolic", "blood_pressure_diastolic", "heart_rate", "blood_glucose",
)
_SCALAR_COLUMNS = (
    "record_id", "username", "date", "time", "logged_at", "source", "note",
    "decision", "recommended_action", "requires_doctor_review", "summary",
)
_JSON_COLUMNS = ("urgent_findings", "flagged_trends", "recent_changes")
_ALL_COLUMNS = _SCALAR_COLUMNS + _METRIC_COLUMNS + _JSON_COLUMNS + ("extra",)
_KNOWN_KEYS = set(_SCALAR_COLUMNS) | set(_JSON_COLUMNS) | {"metrics"}
# Metric keys outside _METRIC_COLUMNS are kept in "extra" under this key.
_EXTRA_METRICS_KEY = "__extra_metrics"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vitals (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id                TEXT UNIQUE,
    username                 TEXT,
    date                     TEXT,
    time                     TEXT,
    logged_at                TEXT,
    source                   TEXT,
    note                     TEXT,
    decision                 TEXT,
    recommended_action       TEXT,
    requires_doctor_review   INTEGER,
    summary                  TEXT,
    blood_pressure_systolic  NUMERIC,
    blood_pressure_diastolic NUMERIC,
    heart_rate               NUMERIC,
    blood_glucose            NUMERIC,
    urgent_findings          TEXT,
    flagged_trends           TEXT,
    recent_changes           TEXT,
    extra                    TEXT
);
CREATE INDEX IF NOT EXISTS idx_vitals_username_date ON vitals (username, date, time);
"""

_INSERT_SQL = "INSERT INTO vitals ({}) VALUES ({})".format(
    ", ".join(_ALL_COLUMNS), ", ".join("?" for _ in _ALL_COLUMNS)
)
_SELECT_SQL = "SELECT {} FROM vitals ORDER BY id".format(", ".join(_ALL_COLUMNS))


def _entry_to_row(entry: dict) -> tuple:
    values = []
    for col in _SCALAR_COLUMNS:
        value = entry.get(col)
        if col == "requires_doctor_review" and value is not None:
            value = int(bool(value))
        values.append(value)

    metrics = entry.get("metrics") or {}
    values.extend(metrics.get(col) for col in _METRIC_COLUMNS)

    for col in _JSON_COLUMNS:
        values.append(json.dumps(entry[col]) if col in entry else None)

    extra = {k: v for k, v in entry.items() if k not in _KNOWN_KEYS}
    other_metrics = {k: v for k, v in metrics.items() if k not in _METRIC_COLUMNS}
    if other_metrics:
        extra[_EXTRA_METRICS_KEY] = other_metrics
    values.append(json.dumps(extra) if extra else None)
    return tuple(values)


def _row_to_entry(row: tuple) -> dict:
    data = dict(zip(_ALL_COLUMNS, row))
    entry = {col: data[col] for col in _SCALAR_COLUMNS if data[col] is not None}
    if "requires_doctor_review" in entry:
        entry["requires_doctor_review"] = bool(entry["requires_doctor_review"])

    metrics = {col: data[col] for col in _METRIC_COLUMNS}

    for col in _JSON_COLUMNS:
        if data[col] is not None:
            entry[col] = json.loads(data[col])

    if data["extra"]:
        extra = json.loads(data["extra"])
        metrics.update(extra.pop(_EXTRA_METRICS_KEY, {}))
        entry.update(extra)

    entry["metrics"] = metrics
    return entry


class SqliteVitalsRepository(RecordRepository):
    """Stores self-logged vitals in the "vitals" table of the SQLite database."""

    def __init__(self, db_path: str = DATABASE_FILE):
        self.__db_path = db_path

    @property
    def db_path(self) -> str:
        return self.__db_path

    def _connect(self) -> sqlite3.Connection:
        return connect(self.__db_path, _SCHEMA)

    def load_all(self) -> List[dict]:
        """Every stored entry in the order it was saved; [] if none or unreadable."""
        try:
            with closing(self._connect()) as conn:
                return [_row_to_entry(row) for row in conn.execute(_SELECT_SQL)]
        except (sqlite3.Error, OSError, ValueError):
            return []

    def save_all(self, entries: List[dict]) -> bool:
        """Replace all stored entries in ONE transaction: either every entry
        is written or, on any failure, the previous contents are kept."""
        try:
            rows = [_entry_to_row(e) for e in entries]
            with closing(self._connect()) as conn:
                with conn:  # commits on success, rolls back on error
                    conn.execute("DELETE FROM vitals")
                    conn.executemany(_INSERT_SQL, rows)
            return True
        except (sqlite3.Error, OSError, TypeError, ValueError, AttributeError):
            return False
