"""Data support package: JSON stores, repositories and file archives.

The orchestrating class, DataManager, lives in the top-level data_manager.py.
(Named data_layer, not data, because data/ holds the JSON files themselves.)
"""

from .consultation_archive import ConsultationPdfArchive
from .json_store import JsonListStore, JsonObjectStore, JsonStore
from .medical_profile_store import MedicalProfileStore, default_medical_profile
from .original_report_archive import OriginalReportArchive
from .repositories import JsonRecordRepository, RecordRepository

__all__ = [
    "JsonStore", "JsonListStore", "JsonObjectStore",
    "RecordRepository", "JsonRecordRepository",
    "ConsultationPdfArchive", "OriginalReportArchive",
    "MedicalProfileStore", "default_medical_profile",
]
