"""Data support package: JSON stores, repositories and file archives.

The orchestrating class, DataManager, lives in the top-level data_manager.py.
(Named data_layer, not data, because data/ holds the JSON files themselves.)
"""

from .account_repository import AccountRepository, JsonAccountRepository, SqliteAccountRepository
from .consultation_archive import ConsultationPdfArchive
from .json_store import JsonListStore, JsonObjectStore, JsonStore
from .medical_profile_store import MedicalProfileStore, default_medical_profile
from .original_report_archive import OriginalReportArchive
from .repositories import JsonRecordRepository, RecordRepository
from .sqlite_repository import SqliteRecordRepository

__all__ = [
    "JsonStore", "JsonListStore", "JsonObjectStore",
    "RecordRepository", "JsonRecordRepository", "SqliteRecordRepository",
    "AccountRepository", "JsonAccountRepository", "SqliteAccountRepository",
    "ConsultationPdfArchive", "OriginalReportArchive",
    "MedicalProfileStore", "default_medical_profile",
]
