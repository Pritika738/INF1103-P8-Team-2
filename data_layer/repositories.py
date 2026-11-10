"""
data_layer/repositories.py

Where health records are kept.

RecordRepository is the contract DataManager depends on;
JsonRecordRepository is the JSON-file implementation. A different
backend (e.g. a database) only needs another subclass that provides
load_all() and save_all() - DataManager does not change (Open/Closed,
Liskov Substitution, Dependency Inversion).
"""

from abc import ABC, abstractmethod
from typing import List

from config import HEALTH_RECORDS_FILE

from .json_store import JsonListStore


class RecordRepository(ABC):
    """Contract: load and save the full list of records.

    Subclasses must provide load_all() / save_all(). The single-record
    operations below (add / list_for_user / delete) have working defaults
    built on those two, so every backend supports them; a database backend
    overrides them with direct queries instead of rewriting everything
    (Open/Closed + Liskov: callers never need to know which one they have).
    """

    @abstractmethod
    def load_all(self) -> List[dict]:
        """Return every stored record (empty list if none / unreadable)."""

    @abstractmethod
    def save_all(self, records: List[dict]) -> bool:
        """Replace the stored records; True on success, False if saving failed."""

    def add(self, record: dict) -> bool:
        """Append one record, keeping every existing one. True on success."""
        records = self.load_all()
        records.append(record)
        return self.save_all(records)

    def list_for_user(self, username: str) -> List[dict]:
        """One user's records, in the order they were saved."""
        return [r for r in self.load_all() if r.get("username") == username]

    def delete(self, username: str, record_id: str) -> bool:
        """Delete the record with this record_id, only if it belongs to
        `username`. True if one was found and the save succeeded."""
        records = self.load_all()
        kept = [
            r for r in records
            if not (r.get("record_id") == record_id and r.get("username") == username)
        ]
        if len(kept) == len(records):
            return False
        return self.save_all(kept)


class JsonRecordRepository(RecordRepository):
    """Stores records in a single JSON file."""

    def __init__(self, file_path: str = HEALTH_RECORDS_FILE):
        self.__store = JsonListStore(file_path)  # composition: owned by this repository

    def load_all(self) -> List[dict]:
        return self.__store.load()

    def save_all(self, records: List[dict]) -> bool:
        return self.__store.save(records)
