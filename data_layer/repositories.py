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
    """Interface: load and save the full list of health records."""

    @abstractmethod
    def load_all(self) -> List[dict]:
        """Return every stored record (empty list if none / unreadable)."""

    @abstractmethod
    def save_all(self, records: List[dict]) -> bool:
        """Replace the stored records; True on success, False if saving failed."""


class JsonRecordRepository(RecordRepository):
    """Stores records in a single JSON file."""

    def __init__(self, file_path: str = HEALTH_RECORDS_FILE):
        self.__store = JsonListStore(file_path)  # composition: owned by this repository

    def load_all(self) -> List[dict]:
        return self.__store.load()

    def save_all(self, records: List[dict]) -> bool:
        return self.__store.save(records)
