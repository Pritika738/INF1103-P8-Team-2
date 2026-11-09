"""
data_manager.py

The Data Manager: saves, loads and queries everything the application
persists (health records, consultation-summary PDFs, original report
files, medical profiles). Missing or corrupt files are handled
gracefully - a missing file reads as empty, a corrupt one is backed up
to "<file>.bak" before an empty value is returned.

Rules for this module:
- No print() or input() calls here.
- No AI calls, no business rules - just persistence and querying.
- Callers (io_manager / the GUI) are responsible for reporting errors
  to the user.

Object relationships (see UML):
- DataManager o-- RecordRepository, ConsultationPdfArchive,
  OriginalReportArchive, MedicalProfileStore
                       aggregation: they are injected, can be built and
                       used on their own (and are in the tests), and do
                       not depend on DataManager.
- JsonRecordRepository *-- JsonListStore, and each archive/profile store
  *-- its own JsonStore
                       composition: the store is created and owned by the
                       class that uses it.
- JsonStore <|-- JsonListStore, JsonObjectStore       inheritance
- RecordRepository <|.. JsonRecordRepository          interface
  (another backend, e.g. a database, only needs another subclass)

save_record()/get_records_by_date() are the entry points for the
AI + Logic Manager pipeline: save_record() stores whatever
logic_manager.process_ai_record() returns (the "Processed Record" in the
architecture diagram), stamping today's date onto it if it doesn't
already have one - that is bookkeeping about when a record was
persisted, not a medical judgment, so it stays in scope here.
"""

import uuid
from datetime import date as _date
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import LATEST_REPORTS_LIMIT, MANUAL_VITALS_FILE

from data_layer import (
    AccountRepository,
    ConsultationPdfArchive,
    JsonRecordRepository,
    MedicalProfilePdfArchive,
    MedicalProfileStore,
    OriginalReportArchive,
    RecordRepository,
    SqliteAccountRepository,
    SqliteRecordRepository,
    default_medical_profile,
)

from user import User

__all__ = [
    "DataManager", "RecordRepository", "JsonRecordRepository", "SqliteRecordRepository",
    "ConsultationPdfArchive", "OriginalReportArchive", "MedicalProfileStore",
    "AccountRepository", "SqliteAccountRepository",
]


class DataManager:
    """Single entry point to every kind of stored data."""

    def __init__(self, records: RecordRepository,
                 consultation_pdfs: ConsultationPdfArchive,
                 original_reports: OriginalReportArchive,
                 medical_profiles: MedicalProfileStore,
                 accounts: AccountRepository,
                 manual_vitals: Optional[RecordRepository] = None,
                 medical_profile_pdfs: Optional[MedicalProfilePdfArchive] = None):
        self._records = records                      # aggregation: all injected
        self._consultation_pdfs = consultation_pdfs
        self._original_reports = original_reports
        self._medical_profiles = medical_profiles
        self._accounts = accounts
        # Self-logged vitals use the SAME repository class as report
        # records, just pointed at a different file - so they are stored
        # completely apart from health_records.json. Optional so callers
        # (and tests) that don't use self-logged vitals can leave it out.
        self._manual_vitals = (
            manual_vitals if manual_vitals is not None
            else JsonRecordRepository(MANUAL_VITALS_FILE)
        )
        self._medical_profile_pdfs = (
            medical_profile_pdfs
            if medical_profile_pdfs is not None
            else MedicalProfilePdfArchive()
        )

    @classmethod
    def create(cls) -> "DataManager":
        """Build a DataManager that uses the real files configured in config.py."""
        return cls(
            SqliteRecordRepository(),
            ConsultationPdfArchive(),
            OriginalReportArchive(),
            MedicalProfileStore(),
            SqliteAccountRepository(),
            JsonRecordRepository(MANUAL_VITALS_FILE),
            MedicalProfilePdfArchive(),
        )

        # ------------------------------------------------------------------
    # Self-logged vitals (entered by hand, not from a medical report)
    # ------------------------------------------------------------------

    def save_manual_vital(self, entry: dict) -> Optional[dict]:
        """Save one self-logged vitals entry, preserving every earlier one.

        A unique "record_id" and a "logged_at" timestamp are stamped onto
        a copy (the caller's dict is never mutated). Returns the saved
        entry, or None if the write failed.
        """
        entry_to_save = dict(entry)
        entry_to_save.setdefault("record_id", uuid.uuid4().hex)
        entry_to_save.setdefault("logged_at", datetime.now().isoformat(timespec="seconds"))

        entries = self._manual_vitals.load_all()
        entries.append(entry_to_save)
        return entry_to_save if self._manual_vitals.save_all(entries) else None

    def list_manual_vitals(self, username: str) -> List[dict]:
        """One user's self-logged vitals, sorted oldest to newest by the
        date (and time, if given) they were MEASURED - not when typed in.
        Entries measured at the same moment keep their save order."""
        mine = [
            (index, e) for index, e in enumerate(self._manual_vitals.load_all())
            if e.get("username") == username
        ]
        mine.sort(key=lambda pair: (pair[1].get("date") or "",
                                    pair[1].get("time") or "", pair[0]))
        return [e for _, e in mine]

    def delete_manual_vital(self, username: str, record_id: str) -> bool:
        """Delete one self-logged entry by its record_id. Only the owner's
        own entry can be deleted. Returns True if one was found and the
        save succeeded, False otherwise."""
        entries = self._manual_vitals.load_all()
        kept = [
            e for e in entries
            if not (e.get("record_id") == record_id and e.get("username") == username)
        ]
        if len(kept) == len(entries):
            return False
        return self._manual_vitals.save_all(kept)

    # ------------------------------------------------------------------
    # Login accounts
    # ------------------------------------------------------------------

    def load_accounts(self) -> Dict[str, dict]:
        """Every registered account, keyed by lowercased username ({} if none)."""
        return self._accounts.load_all()

    def save_accounts(self, accounts: Dict[str, dict]) -> bool:
        """Replace the stored accounts. Returns True on success, False if the write failed."""
        return self._accounts.save_all(accounts)

    def find_user(self, username: str) -> Optional[User]:
        """The registered User with this username (any letter case), or None."""
        try:
            key = User(username).key
        except ValueError:  # a blank username can never match an account
            return None
        account = self._accounts.load_all().get(key)
        return User.from_dict(account) if account else None

    def get_account(self, user: User) -> Optional[dict]:
        """A copy of this user's stored account (password/PIN hashes), or None."""
        if not isinstance(user, User):
            raise TypeError("get_account expects a User object.")
        account = self._accounts.load_all().get(user.key)
        return dict(account) if account else None

    def save_account(self, user: User, account: dict) -> bool:
        """Insert or replace ONE user's account, leaving every other account
        untouched. The stored username always comes from the User object."""
        if not isinstance(user, User):
            raise TypeError("save_account expects a User object.")
        accounts = self._accounts.load_all()
        accounts[user.key] = {**account, **user.to_dict()}
        return self._accounts.save_all(accounts)

    # ------------------------------------------------------------------
    # Health records
    # ------------------------------------------------------------------

    def load_health_records(self) -> List[dict]:
        """Load all health records. Missing file -> []; corrupt file -> backed
        up to "<file>.bak" and [] returned, never an exception."""
        return self._records.load_all()

    def save_health_records(self, records: List[dict]) -> bool:
        """Replace the stored records. Returns True on success, False if the write failed."""
        return self._records.save_all(records)

    def add_health_record(self, record: dict) -> bool:
        """Append one record and persist. Returns True on success, False if saving failed."""
        records = self._records.load_all()
        records.append(record)
        return self._records.save_all(records)

    def save_record(self, record: dict) -> bool:
        """Save one already-processed health record, preserving all previously
        stored records (never overwrites history with just this one).

        If `record` has no "date" key, today's date is stamped onto a copy
        before saving. A unique "record_id" is stamped on the same way if
        missing, so this specific record can later be found again by
        update_record_date(). The caller's original dict is never mutated.
        """
        record_to_save = dict(record)
        record_to_save.setdefault("date", _date.today().isoformat())
        record_to_save.setdefault("record_id", uuid.uuid4().hex)
        return self.add_health_record(record_to_save)

    def update_record_date(self, record_id: str, new_date: str) -> bool:
        """Correct one stored record's "date" by its record_id, leaving every
        other field and record untouched.

        Returns True if a matching record was found and the save succeeded,
        False if no record has this ID, or the write failed.
        """
        records = self._records.load_all()

        for record in records:
            if record.get("record_id") == record_id:
                record["date"] = new_date
                return self._records.save_all(records)

        return False

    def backfill_record_ids(self) -> int:
        """Give every stored record missing a "record_id" a new one. Safe to
        call repeatedly: records that already have an ID are never touched,
        and if nothing is missing one, no write happens at all.

        Returns the number of records that were given a new ID.
        """
        records = self._records.load_all()

        added = 0
        for record in records:
            if not record.get("record_id"):
                record["record_id"] = uuid.uuid4().hex
                added += 1

        if added:
            self._records.save_all(records)

        return added

    def get_records_by_date(self, target_date: str) -> List[dict]:
        """Find all stored records whose "date" field matches `target_date` exactly."""
        return [r for r in self._records.load_all() if r.get("date") == target_date]

    @staticmethod
    def get_latest_reports(records: List[dict], limit: int = LATEST_REPORTS_LIMIT) -> List[dict]:
        """Select the most recent `limit` records by their own "date" field -
        the medical report's date, not when it was uploaded or saved.

        Two records can share the same report date. Records are always
        appended, so list position reflects save order; that original
        position is used as a tiebreaker so that among same-dated records the
        most recently saved is treated as the most recent.

        Returns up to `limit` records sorted oldest to newest. Records with no
        usable "date" sort as the oldest, so a missing date can never push out
        a real, dated record.
        """
        def sort_key(indexed_record):
            index, record = indexed_record
            return (record.get("date") or "", index)

        indexed = list(enumerate(records))
        newest_first = sorted(indexed, key=sort_key, reverse=True)
        latest_indexed = newest_first[:limit]
        oldest_first = sorted(latest_indexed, key=sort_key)
        return [record for _, record in oldest_first]

    # ------------------------------------------------------------------
    # Consultation-summary PDFs
    # ------------------------------------------------------------------

    def save_consultation_pdf(self, pdf_bytes: bytes, report_date, username: str,
                              source_record_id=None) -> Optional[dict]:
        """Save a generated consultation PDF and its metadata. Returns the
        metadata dict, or None if saving failed."""
        return self._consultation_pdfs.save(pdf_bytes, report_date, username, source_record_id)

    def find_consultation_pdf_by_source(self, username: str, source_record_id) -> Optional[dict]:
        """The already-saved summary for this user and source record, or None."""
        return self._consultation_pdfs.find_by_source(username, source_record_id)

    def list_consultation_pdfs(self, username: str) -> List[dict]:
        """A user's saved summaries, newest generated first."""
        return self._consultation_pdfs.list_for_user(username)

    def get_consultation_pdf_bytes(self, filename: str) -> Optional[bytes]:
        """Raw bytes of a saved summary PDF, or None if missing/unreadable."""
        return self._consultation_pdfs.read_pdf_bytes(filename)

    # ------------------------------------------------------------------
    # Original medical report files
    # ------------------------------------------------------------------

    def save_original_report(self, file_bytes: bytes, original_filename: str, mime_type: str,
                             report_date, username: str) -> Optional[dict]:
        """Save an uploaded file exactly as uploaded (reusing an identical
        earlier upload by the same user). Returns the metadata dict, or None
        if saving failed."""
        return self._original_reports.save(
            file_bytes, original_filename, mime_type, report_date, username
        )

    def list_original_reports(self, username: str) -> List[dict]:
        """A user's original reports, newest report date first."""
        return self._original_reports.list_for_user(username)

    def get_original_report_bytes(self, stored_filename: str) -> Optional[bytes]:
        """Raw bytes of a saved original report, or None if missing/unreadable."""
        return self._original_reports.read_bytes(stored_filename)

    def get_original_report_by_id(self, report_id: str) -> Optional[dict]:
        """Metadata for one original report by its report_id, or None."""
        return self._original_reports.find_by_id(report_id)

    # ------------------------------------------------------------------
    # Medical profiles
    # ------------------------------------------------------------------

    @staticmethod
    def get_default_medical_profile() -> Dict[str, Any]:
        """A fresh, empty medical profile with every expected section present."""
        return default_medical_profile()

    def load_medical_profile(self, username: str) -> Dict[str, Any]:
        """One user's medical profile, or a complete default one if none exists."""
        return self._medical_profiles.load(username)

    def save_medical_profile(self, username: str, profile: Dict[str, Any]) -> bool:
        """Replace one user's medical profile. Returns True on success."""
        return self._medical_profiles.save(username, profile)

    def save_medical_profile_pdf(
    self,
    pdf_bytes: bytes,
    username: str
    ) -> Optional[dict]:

        return self._medical_profile_pdfs.save(
            pdf_bytes,
            username
        )


    def list_medical_profile_pdfs(
        self,
        username: str
    ) -> List[dict]:

        return self._medical_profile_pdfs.list_for_user(
            username
        )


    def get_medical_profile_pdf_bytes(
        self,
        filename: str
    ) -> Optional[bytes]:

        return self._medical_profile_pdfs.read_pdf_bytes(
            filename
        )
