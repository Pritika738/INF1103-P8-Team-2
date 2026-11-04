"""
data_layer/json_store.py

Low-level JSON file storage shared by every repository and archive.

JsonStore is an abstract template: load() and save() hold the shared,
careful file handling (missing file, corrupt file backup, atomic write),
while each subclass only says what an "empty" value is and what shape
valid data must have. Adding a new kind of store means adding a
subclass; nothing existing changes (Open/Closed).

No print()/input(), no AI calls, no business rules.
"""

import json
import os
import shutil
from abc import ABC, abstractmethod
from typing import Any


class JsonStore(ABC):
    """Abstract base for one JSON file on disk."""

    def __init__(self, file_path: str):
        self.__file_path = file_path

    @property
    def file_path(self) -> str:
        return self.__file_path

    # ------------------------------------------------------------------
    # Shape (supplied by subclasses)
    # ------------------------------------------------------------------

    @abstractmethod
    def _empty(self) -> Any:
        """A fresh empty value of the right type (used when nothing can be loaded)."""

    @abstractmethod
    def _is_valid_shape(self, data: Any) -> bool:
        """True if `data` is the type this store expects."""

    # ------------------------------------------------------------------
    # Shared behaviour
    # ------------------------------------------------------------------

    def load(self) -> Any:
        """Load the file's contents.

        A missing file gives an empty value. Invalid JSON, or valid JSON of
        the wrong type, is first backed up to "<file>.bak" (so a later save
        can't silently destroy it) and an empty value is returned instead of
        raising an exception.
        """
        if not os.path.exists(self.__file_path):
            return self._empty()

        try:
            with open(self.__file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            self._backup_corrupted_file()
            return self._empty()
        except OSError:
            return self._empty()

        if not self._is_valid_shape(data):
            self._backup_corrupted_file()
            return self._empty()

        return data

    def save(self, data: Any) -> bool:
        """Write `data` to the file; return True on success, False if the write failed.

        Creates the parent directory if needed. Writes to a temporary file and
        then atomically replaces the real file (os.replace()), so a reader can
        only ever see one complete, valid file, never a half-written one (a
        "torn write"). This does not prevent a "lost update" if two saves start
        from the same older snapshot - that would need a real file lock.
        """
        try:
            directory = os.path.dirname(self.__file_path) or "."
            os.makedirs(directory, exist_ok=True)
            tmp_path = f"{self.__file_path}.tmp-{os.getpid()}"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.__file_path)
            return True
        except OSError:
            return False

    def _backup_corrupted_file(self) -> None:
        """Copy an unreadable file to "<file>.bak". Best-effort: a failure here
        (e.g. disk full) must not crash the caller, so it is swallowed."""
        try:
            shutil.copy2(self.__file_path, self.__file_path + ".bak")
        except OSError:
            pass


class JsonListStore(JsonStore):
    """A JSON file whose top level is a list (health records, metadata lists)."""

    def _empty(self) -> list:
        return []

    def _is_valid_shape(self, data) -> bool:
        return isinstance(data, list)


class JsonObjectStore(JsonStore):
    """A JSON file whose top level is an object (e.g. {username: profile})."""

    def _empty(self) -> dict:
        return {}

    def _is_valid_shape(self, data) -> bool:
        return isinstance(data, dict)
