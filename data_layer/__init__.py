"""Data support package: JSON stores, repositories and file archives.

The orchestrating class, DataManager, lives in the top-level data_manager.py.
(Named data_layer, not data, because data/ holds the JSON files themselves.)
"""

from .account_repository import AccountRepository, JsonAccountRepository, SqliteAccountRepository
from .consultation_archive import ConsultationPdfArchive, consultation_summaries_table
from .json_store import JsonListStore, JsonObjectStore, JsonStore
from .medical_profile_store import MedicalProfileStore, default_medical_profile
from .original_report_archive import OriginalReportArchive, original_reports_table
from .sqlite_list_store import SqliteListStore
from .repositories import JsonRecordRepository, RecordRepository
from .sqlite_repository import SqliteRecordRepository
from .medical_profile_archive import (
    MedicalProfilePdfArchive,
    medical_profile_pdfs_table,
)

__all__ = [
    "JsonStore", "JsonListStore", "JsonObjectStore",
    "RecordRepository", "JsonRecordRepository", "SqliteRecordRepository",
    "AccountRepository", "JsonAccountRepository", "SqliteAccountRepository",
    "ConsultationPdfArchive", "OriginalReportArchive",
    "consultation_summaries_table", "original_reports_table", "SqliteListStore",
    "MedicalProfileStore", "default_medical_profile",
    "MedicalProfilePdfArchive", "medical_profile_pdfs_table",
]
