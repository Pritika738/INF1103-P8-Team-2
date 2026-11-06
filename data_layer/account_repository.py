"""
data_layer/account_repository.py

Where login accounts are kept.

The shape matches the old data/users.json exactly: a dict keyed by the
lowercased username, each value holding username, email, salt,
password_hash and (optionally) pin_salt / pin_hash. Only hashes are ever
stored - never a plain-text password or PIN.

AccountRepository is the contract DataManager depends on.
SqliteAccountRepository is the live backend (the "users" table in
config.DATABASE_FILE); JsonAccountRepository reads/writes the old JSON
file and is kept for the migration script and for tests.

No print()/input(), no AI calls, no business rules (duplicate checks and
password hashing stay with the caller).
"""

import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import closing
from typing import Dict

from config import DATABASE_FILE, USERS_FILE

from .json_store import JsonObjectStore
from .sqlite_db import connect


class AccountRepository(ABC):
    """Interface: load and save every account, keyed by lowercased username."""

    @abstractmethod
    def load_all(self) -> Dict[str, dict]:
        """Return every account ({} if none / unreadable)."""

    @abstractmethod
    def save_all(self, accounts: Dict[str, dict]) -> bool:
        """Replace the stored accounts; True on success, False if saving failed."""


class JsonAccountRepository(AccountRepository):
    """Stores accounts in a single JSON object file (the old users.json)."""

    def __init__(self, file_path: str = USERS_FILE):
        self.__store = JsonObjectStore(file_path)  # composition: owned by this repository

    def load_all(self) -> Dict[str, dict]:
        return self.__store.load()

    def save_all(self, accounts: Dict[str, dict]) -> bool:
        return self.__store.save(accounts)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username_key  TEXT NOT NULL UNIQUE,
    username      TEXT,
    email         TEXT,
    salt          TEXT,
    password_hash TEXT,
    pin_salt      TEXT,
    pin_hash      TEXT,
    extra         TEXT
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
"""

_FIELDS = ("username", "email", "salt", "password_hash", "pin_salt", "pin_hash")
_COLUMNS = ("username_key",) + _FIELDS + ("extra",)

_INSERT_SQL = "INSERT INTO users ({}) VALUES ({})".format(
    ", ".join(_COLUMNS), ", ".join("?" for _ in _COLUMNS)
)
_SELECT_SQL = "SELECT {} FROM users ORDER BY id".format(", ".join(_COLUMNS))


def _account_to_row(username_key: str, account: dict) -> tuple:
    extra = {k: v for k, v in account.items() if k not in _FIELDS}
    return (
        (username_key,)
        + tuple(account.get(f) for f in _FIELDS)
        + (json.dumps(extra) if extra else None,)
    )


def _row_to_account(row: tuple):
    data = dict(zip(_COLUMNS, row))
    # Absent fields (e.g. no PIN set) are left out, not returned as None,
    # so the dict looks exactly like it did in users.json.
    account = {f: data[f] for f in _FIELDS if data[f] is not None}
    if data["extra"]:
        account.update(json.loads(data["extra"]))
    return data["username_key"], account


class SqliteAccountRepository(AccountRepository):
    """Stores accounts in the "users" table of the SQLite database."""

    def __init__(self, db_path: str = DATABASE_FILE):
        self.__db_path = db_path

    @property
    def db_path(self) -> str:
        return self.__db_path

    def load_all(self) -> Dict[str, dict]:
        """Every account, in the order they were created; {} if none or unreadable."""
        try:
            with closing(connect(self.__db_path, _SCHEMA)) as conn:
                return dict(_row_to_account(row) for row in conn.execute(_SELECT_SQL))
        except (sqlite3.Error, OSError, ValueError):
            return {}

    def save_all(self, accounts: Dict[str, dict]) -> bool:
        """Replace all accounts in ONE transaction: either every account is
        written or, on any failure, the previous contents are kept."""
        try:
            rows = [_account_to_row(key, acc) for key, acc in accounts.items()]
            with closing(connect(self.__db_path, _SCHEMA)) as conn:
                with conn:  # commits on success, rolls back on error
                    conn.execute("DELETE FROM users")
                    conn.executemany(_INSERT_SQL, rows)
            return True
        except (sqlite3.Error, OSError, TypeError, ValueError, AttributeError):
            return False
