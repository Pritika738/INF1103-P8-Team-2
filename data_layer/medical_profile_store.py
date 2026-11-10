"""
data_layer/medical_profile_store.py

A user's standing medical profile: current medications & dosages, blood
group, allergies, emergency contacts and hereditary illness flags.
Unlike the health records (an append-only list of dated readings), a
profile is ONE current record per user; each save REPLACES that user's
profile rather than appending.

MedicalProfileRepository holds the shared behaviour (filling in missing
sections from the defaults, stamping "last_updated"); subclasses only say
how one user's raw profile is read and written:
- SqliteMedicalProfileStore  - the "medical_profiles" table of the app
                               database (what the running app uses);
- MedicalProfileStore        - the old JSON file keyed by username (kept
                               for the migration script and for tests).

Persistence only - all validation belongs in logic_manager, and all
user messaging in io_manager.
"""

import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import closing
from datetime import date as _date
from typing import Any, Dict, Optional

from config import DATABASE_FILE, MEDICAL_PROFILES_FILE

from .json_store import JsonObjectStore
from .sqlite_db import connect


def default_medical_profile() -> Dict[str, Any]:
    """Return a fresh, empty medical-profile dict with every expected
    section present, so callers can rely on the shape without defensive
    key-checking. A new dict is built on every call, so it is never
    shared or mutated across callers.

    Shape:
        {
            "medications":   [ {"name", "dosage_amount", "dosage_unit",
                                 "frequency"}, ... ],
            "blood_group":   str,   # e.g. "O+", "" if unknown
            "allergies":     [ {"allergen", "reaction", "severity"}, ... ],
            "emergency_contacts": [ {"name", "relationship", "phone",
                                     "email"}, ... ],
            "hereditary_illness": {
                "diabetes":       bool,
                "blood_pressure": bool,
                "heart_disease":  bool,
                "asthma":         bool,
                "other":          str,   # free text, "" if none
                "notes":          str,   # e.g. which relative, "" if none
            },
        }
    """
    return {
        "medications": [],
        "blood_group": "",
        "allergies": [],
        "emergency_contacts": [],
        "hereditary_illness": {
            "diabetes": False,
            "blood_pressure": False,
            "heart_disease": False,
            "asthma": False,
            "other": "",
            "notes": "",
        },
    }


class MedicalProfileRepository(ABC):
    """Abstract base: loads and saves one medical profile per user."""

    # ------------------------------------------------------------------
    # Raw storage (supplied by subclasses)
    # ------------------------------------------------------------------

    @abstractmethod
    def _load_stored(self, username: str) -> Optional[dict]:
        """The raw stored profile for `username`, or None if there is none."""

    @abstractmethod
    def _save_stored(self, username: str, profile: dict) -> bool:
        """Store `profile` as `username`'s profile, leaving every other user
        untouched. True on success."""

    @abstractmethod
    def load_all(self) -> Dict[str, dict]:
        """Every stored profile keyed by username ({} if none / unreadable)."""

    @abstractmethod
    def save_all(self, profiles: Dict[str, dict]) -> bool:
        """Replace every stored profile (used by the migration script)."""

    # ------------------------------------------------------------------
    # Shared behaviour
    # ------------------------------------------------------------------

    def load(self, username: str) -> Dict[str, Any]:
        """Load one user's medical profile.

        Returns the stored profile, or a fresh default_medical_profile() if
        the user has none yet (so callers always get a complete, well-shaped
        dict and never a KeyError). Any sections missing from a stored
        profile (e.g. one saved before a new section existed) are filled in
        from the default.
        """
        stored = self._load_stored(username)

        profile = default_medical_profile()
        if isinstance(stored, dict):
            # Merge known top-level sections; nested hereditary flags are
            # merged key-by-key so a newly added flag defaults correctly
            # instead of disappearing from an older stored profile.
            for key, default_value in profile.items():
                if key not in stored:
                    continue
                if key == "hereditary_illness" and isinstance(stored[key], dict):
                    merged = dict(default_value)
                    merged.update(stored[key])
                    profile[key] = merged
                else:
                    profile[key] = stored[key]
            if "last_updated" in stored:
                profile["last_updated"] = stored["last_updated"]

        return profile

    def save(self, username: str, profile: Dict[str, Any]) -> bool:
        """Save (replace) one user's medical profile, preserving every OTHER
        user's profile untouched. Stamps today's date as "last_updated" onto
        a copy of `profile`; the caller's original dict is never mutated.

        Returns True on success, False if the write failed.
        """
        profile_to_save = dict(profile)
        profile_to_save["last_updated"] = _date.today().isoformat()
        return self._save_stored(username, profile_to_save)


class MedicalProfileStore(MedicalProfileRepository):
    """Stores every profile in one JSON object file keyed by username."""

    def __init__(self, profiles_file: str = MEDICAL_PROFILES_FILE):
        self.__store = JsonObjectStore(profiles_file)  # composition

    def _load_stored(self, username: str) -> Optional[dict]:
        return self.__store.load().get(username)

    def _save_stored(self, username: str, profile: dict) -> bool:
        profiles = self.__store.load()
        profiles[username] = profile
        return self.__store.save(profiles)

    def load_all(self) -> Dict[str, dict]:
        return self.__store.load()

    def save_all(self, profiles: Dict[str, dict]) -> bool:
        return self.__store.save(profiles)


# ---------------------------------------------------------------------------
# SQLite: the "medical_profiles" table
# ---------------------------------------------------------------------------
# blood_group / last_updated are plain text columns (queryable); the list
# and nested sections are JSON text. A NULL column means the key was absent,
# and any other key (or a value of an unexpected type) goes into "extra",
# so a profile always round-trips exactly.

_SCHEMA = """
CREATE TABLE IF NOT EXISTS medical_profiles (
    username           TEXT PRIMARY KEY,
    blood_group        TEXT,
    last_updated       TEXT,
    medications        TEXT,
    allergies          TEXT,
    emergency_contacts TEXT,
    hereditary_illness TEXT,
    extra              TEXT
);
"""

_TEXT_COLUMNS = ("blood_group", "last_updated")
_JSON_COLUMNS = ("medications", "allergies", "emergency_contacts", "hereditary_illness")
_COLUMNS = ("username",) + _TEXT_COLUMNS + _JSON_COLUMNS + ("extra",)

_UPSERT_SQL = (
    "INSERT INTO medical_profiles ({cols}) VALUES ({marks}) "
    "ON CONFLICT(username) DO UPDATE SET {updates}"
).format(
    cols=", ".join(_COLUMNS),
    marks=", ".join("?" for _ in _COLUMNS),
    updates=", ".join(f"{c} = excluded.{c}" for c in _COLUMNS[1:]),
)
_INSERT_SQL = "INSERT INTO medical_profiles ({}) VALUES ({})".format(
    ", ".join(_COLUMNS), ", ".join("?" for _ in _COLUMNS)
)
_SELECT_ALL_SQL = "SELECT {} FROM medical_profiles ORDER BY rowid".format(", ".join(_COLUMNS))
_SELECT_ONE_SQL = "SELECT {} FROM medical_profiles WHERE username = ?".format(", ".join(_COLUMNS))


def _profile_to_row(username: str, profile: dict) -> tuple:
    extra = {}
    values = [username]
    for col in _TEXT_COLUMNS:
        value = profile.get(col)
        if col in profile and not isinstance(value, str):
            extra[col] = value          # unexpected type: keep it exactly
            value = None
        values.append(value)
    for col in _JSON_COLUMNS:
        values.append(json.dumps(profile[col]) if col in profile else None)
    for key, value in profile.items():
        if key not in _TEXT_COLUMNS and key not in _JSON_COLUMNS:
            extra[key] = value
    values.append(json.dumps(extra) if extra else None)
    return tuple(values)


def _row_to_profile(row: tuple):
    data = dict(zip(_COLUMNS, row))
    profile = {col: data[col] for col in _TEXT_COLUMNS if data[col] is not None}
    for col in _JSON_COLUMNS:
        if data[col] is not None:
            profile[col] = json.loads(data[col])
    if data["extra"]:
        profile.update(json.loads(data["extra"]))
    return data["username"], profile


class SqliteMedicalProfileStore(MedicalProfileRepository):
    """Stores one row per user in the "medical_profiles" table."""

    def __init__(self, db_path: str = DATABASE_FILE):
        self.__db_path = db_path

    @property
    def db_path(self) -> str:
        return self.__db_path

    def _connect(self) -> sqlite3.Connection:
        return connect(self.__db_path, _SCHEMA)

    def _load_stored(self, username: str) -> Optional[dict]:
        """SELECT one user's row; None if absent or the database is unreadable."""
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(_SELECT_ONE_SQL, (username,)).fetchone()
            return _row_to_profile(row)[1] if row else None
        except (sqlite3.Error, OSError, ValueError):
            return None

    def _save_stored(self, username: str, profile: dict) -> bool:
        """INSERT or UPDATE only this user's row (an upsert)."""
        try:
            row = _profile_to_row(username, profile)
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute(_UPSERT_SQL, row)
            return True
        except (sqlite3.Error, OSError, TypeError, ValueError, AttributeError):
            return False

    def load_all(self) -> Dict[str, dict]:
        try:
            with closing(self._connect()) as conn:
                return dict(_row_to_profile(row) for row in conn.execute(_SELECT_ALL_SQL))
        except (sqlite3.Error, OSError, ValueError):
            return {}

    def save_all(self, profiles: Dict[str, dict]) -> bool:
        """Replace every profile in ONE transaction (all or nothing)."""
        try:
            rows = [_profile_to_row(u, p) for u, p in profiles.items()]
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute("DELETE FROM medical_profiles")
                    conn.executemany(_INSERT_SQL, rows)
            return True
        except (sqlite3.Error, OSError, TypeError, ValueError, AttributeError):
            return False
