"""
tests/test_data_manager.py

Tests for the Data Manager and the data_layer package. Everything runs
against pytest's temporary folders - the real data/ files are never
touched.

Run with:
    python -m pytest tests/test_data_manager.py
"""

import json
import os

import pytest

from data_layer import (
    ConsultationPdfArchive, JsonAccountRepository, JsonListStore, JsonObjectStore, JsonRecordRepository,
    JsonStore, MedicalProfileStore, OriginalReportArchive, RecordRepository,
    default_medical_profile,
)
from data_manager import DataManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def paths(tmp_path):
    return {
        "records": str(tmp_path / "records.json"),
        "summaries": str(tmp_path / "summaries.json"),
        "pdfs": str(tmp_path / "pdfs"),
        "meta": str(tmp_path / "reports.json"),
        "reports": str(tmp_path / "reports"),
        "profiles": str(tmp_path / "profiles.json"),
        "accounts": str(tmp_path / "users.json"),
        "vitals": str(tmp_path / "vitals.json"),
    }


@pytest.fixture
def make_manager(paths):
    def _make(max_retained=None):
        return DataManager(
            JsonRecordRepository(paths["records"]),
            ConsultationPdfArchive(paths["pdfs"], JsonListStore(paths["summaries"]), max_retained),
            OriginalReportArchive(paths["reports"], JsonListStore(paths["meta"])),
            MedicalProfileStore(paths["profiles"]),
            JsonAccountRepository(paths["accounts"]),
            JsonRecordRepository(paths["vitals"]),
        )
    return _make


@pytest.fixture
def dm(make_manager):
    return make_manager()


class InMemoryRepository(RecordRepository):
    """A different backend: proves DataManager only needs the interface."""

    def __init__(self):
        self.records = []

    def load_all(self):
        return [dict(r) for r in self.records]

    def save_all(self, records):
        self.records = [dict(r) for r in records]
        return True


# ---------------------------------------------------------------------------
# Design: abstract classes, interface, substitutability
# ---------------------------------------------------------------------------

class TestDesign:
    def test_abstract_store_and_interface_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            JsonStore("x.json")
        with pytest.raises(TypeError):
            RecordRepository()

    def test_stores_extend_the_abstract_store(self):
        assert issubclass(JsonListStore, JsonStore)
        assert issubclass(JsonObjectStore, JsonStore)

    def test_json_repository_implements_the_interface(self):
        assert issubclass(JsonRecordRepository, RecordRepository)

    def test_data_manager_works_with_any_repository(self, paths):
        # Liskov: swapping the backend needs no DataManager changes.
        dm = DataManager(
            InMemoryRepository(),
            ConsultationPdfArchive(paths["pdfs"], JsonListStore(paths["summaries"])),
            OriginalReportArchive(paths["reports"], JsonListStore(paths["meta"])),
            MedicalProfileStore(paths["profiles"]),
            JsonAccountRepository(paths["accounts"]),
            JsonRecordRepository(paths["vitals"]),
        )
        assert dm.save_record({"username": "ann", "date": "2026-01-01"}) is True
        assert dm.get_records_by_date("2026-01-01")[0]["username"] == "ann"

    def test_create_builds_a_data_manager_from_config(self):
        assert isinstance(DataManager.create(), DataManager)


# ---------------------------------------------------------------------------
# JSON stores: missing / corrupt files, atomic save
# ---------------------------------------------------------------------------

class TestJsonStores:
    def test_missing_file_reads_as_empty(self, tmp_path):
        assert JsonListStore(str(tmp_path / "no.json")).load() == []
        assert JsonObjectStore(str(tmp_path / "no.json")).load() == {}

    def test_empty_values_are_not_shared_between_calls(self, tmp_path):
        store = JsonListStore(str(tmp_path / "no.json"))
        first = store.load()
        first.append("x")
        assert store.load() == []

    def test_round_trip(self, tmp_path):
        store = JsonListStore(str(tmp_path / "a.json"))
        assert store.save([{"a": 1}]) is True
        assert store.load() == [{"a": 1}]

    def test_corrupt_json_is_backed_up_and_reads_as_empty(self, tmp_path):
        path = tmp_path / "a.json"
        path.write_text("{not json", encoding="utf-8")
        assert JsonListStore(str(path)).load() == []
        assert (tmp_path / "a.json.bak").read_text(encoding="utf-8") == "{not json"

    def test_wrong_top_level_type_is_backed_up(self, tmp_path):
        path = tmp_path / "a.json"
        path.write_text('{"a": 1}', encoding="utf-8")
        assert JsonListStore(str(path)).load() == []
        assert (tmp_path / "a.json.bak").exists()

        other = tmp_path / "b.json"
        other.write_text("[1, 2]", encoding="utf-8")
        assert JsonObjectStore(str(other)).load() == {}
        assert (tmp_path / "b.json.bak").exists()

    def test_save_creates_missing_parent_directories(self, tmp_path):
        path = tmp_path / "deep" / "er" / "a.json"
        assert JsonListStore(str(path)).save([1]) is True
        assert path.exists()

    def test_save_failure_returns_false_instead_of_raising(self, tmp_path):
        blocker = tmp_path / "blocker"
        blocker.write_text("i am a file", encoding="utf-8")
        assert JsonListStore(str(blocker / "a.json")).save([1]) is False

    def test_save_leaves_no_temporary_file_behind(self, tmp_path):
        JsonListStore(str(tmp_path / "a.json")).save([1])
        assert [p.name for p in tmp_path.iterdir()] == ["a.json"]

    def test_file_path_is_exposed_read_only(self, tmp_path):
        store = JsonListStore(str(tmp_path / "a.json"))
        assert store.file_path.endswith("a.json")
        with pytest.raises(AttributeError):
            store.file_path = "other"


# ---------------------------------------------------------------------------
# Health records
# ---------------------------------------------------------------------------

class TestHealthRecords:
    def test_load_when_missing(self, dm):
        assert dm.load_health_records() == []

    def test_load_when_corrupt_returns_empty_and_keeps_a_backup(self, dm, paths):
        with open(paths["records"], "w", encoding="utf-8") as f:
            f.write("garbage")
        assert dm.load_health_records() == []
        assert os.path.exists(paths["records"] + ".bak")

    def test_save_record_stamps_date_and_id_without_mutating_input(self, dm):
        original = {"username": "ann", "heart_rate": 70}
        assert dm.save_record(original) is True
        assert original == {"username": "ann", "heart_rate": 70}
        stored = dm.load_health_records()[0]
        assert stored["date"] and stored["record_id"]

    def test_save_record_keeps_existing_date_and_id(self, dm):
        dm.save_record({"date": "2026-01-01", "record_id": "mine"})
        stored = dm.load_health_records()[0]
        assert stored["date"] == "2026-01-01" and stored["record_id"] == "mine"

    def test_save_record_preserves_history(self, dm):
        dm.save_record({"n": 1})
        dm.save_record({"n": 2})
        assert [r["n"] for r in dm.load_health_records()] == [1, 2]

    def test_add_and_save_health_records(self, dm):
        assert dm.add_health_record({"a": 1}) is True
        assert dm.save_health_records([{"b": 2}]) is True
        assert dm.load_health_records() == [{"b": 2}]

    def test_get_records_by_date(self, dm):
        dm.save_record({"date": "2026-01-01", "n": 1})
        dm.save_record({"date": "2026-01-02", "n": 2})
        dm.save_record({"date": "2026-01-01", "n": 3})
        assert [r["n"] for r in dm.get_records_by_date("2026-01-01")] == [1, 3]
        assert dm.get_records_by_date("1999-01-01") == []

    def test_update_record_date(self, dm):
        dm.save_record({"record_id": "a", "date": "2026-01-01", "keep": "me"})
        dm.save_record({"record_id": "b", "date": "2026-01-02"})
        assert dm.update_record_date("a", "2026-05-05") is True
        records = {r["record_id"]: r for r in dm.load_health_records()}
        assert records["a"]["date"] == "2026-05-05" and records["a"]["keep"] == "me"
        assert records["b"]["date"] == "2026-01-02"

    def test_update_record_date_unknown_id(self, dm):
        dm.save_record({"record_id": "a"})
        assert dm.update_record_date("nope", "2026-05-05") is False

    def test_backfill_record_ids(self, dm, paths):
        dm.save_health_records([{"n": 1}, {"n": 2, "record_id": "keep"}, {"n": 3}])
        assert dm.backfill_record_ids() == 2
        ids = [r["record_id"] for r in dm.load_health_records()]
        assert ids[1] == "keep" and all(ids) and len(set(ids)) == 3

    def test_backfill_is_idempotent_and_skips_the_write_when_nothing_to_do(self, dm, paths):
        dm.save_record({"n": 1})
        before = os.path.getmtime(paths["records"])
        assert dm.backfill_record_ids() == 0
        assert os.path.getmtime(paths["records"]) == before

    def test_backfill_on_missing_file(self, dm):
        assert dm.backfill_record_ids() == 0


class TestLatestReports:
    RECORDS = [{"date": d, "n": i} for i, d in enumerate(
        ["2026-03-01", None, "2026-03-01", "2026-01-01", "2026-04-01", "", "2026-03-01", "2026-02-01"])]

    def test_returns_newest_n_oldest_first(self):
        latest = DataManager.get_latest_reports(self.RECORDS, limit=3)
        assert [r["date"] for r in latest] == ["2026-03-01", "2026-03-01", "2026-04-01"]

    def test_same_date_tiebreak_prefers_most_recently_saved(self):
        latest = DataManager.get_latest_reports(self.RECORDS, limit=2)
        assert [r["n"] for r in latest] == [6, 4]  # latest-saved 03-01 record, then 04-01

    def test_missing_dates_never_push_out_dated_records(self):
        latest = DataManager.get_latest_reports(self.RECORDS, limit=6)
        assert all(r["date"] for r in latest)

    def test_default_limit_comes_from_config(self):
        from config import LATEST_REPORTS_LIMIT
        records = [{"date": f"2026-01-{day:02d}"} for day in range(1, 11)]
        assert len(DataManager.get_latest_reports(records)) == LATEST_REPORTS_LIMIT

    def test_empty_and_does_not_mutate_input(self):
        assert DataManager.get_latest_reports([]) == []
        snapshot = list(self.RECORDS)
        DataManager.get_latest_reports(self.RECORDS, limit=2)
        assert self.RECORDS == snapshot


# ---------------------------------------------------------------------------
# Consultation-summary PDFs
# ---------------------------------------------------------------------------

class TestConsultationPdfs:
    def test_save_writes_file_and_metadata(self, dm, paths):
        entry = dm.save_consultation_pdf(b"%PDF-data", "2026-01-01", "ann", "rec1")
        assert entry["username"] == "ann" and entry["source_record_id"] == "rec1"
        assert os.path.exists(os.path.join(paths["pdfs"], entry["filename"]))
        assert dm.get_consultation_pdf_bytes(entry["filename"]) == b"%PDF-data"

    def test_unsafe_username_and_date_are_sanitised_in_the_filename(self, dm):
        entry = dm.save_consultation_pdf(b"x", "2026/01/01", "../ann smith", "rec1")
        assert "/" not in entry["filename"] and ".." not in entry["filename"]
        assert " " not in entry["filename"]

    def test_pdf_path_is_relative(self, dm):
        entry = dm.save_consultation_pdf(b"x", "2026-01-01", "ann")
        assert not os.path.isabs(entry["pdf_path"])

    def test_list_is_per_user_newest_first(self, dm):
        first = dm.save_consultation_pdf(b"1", "2026-01-01", "ann")
        second = dm.save_consultation_pdf(b"2", "2026-01-02", "ann")
        dm.save_consultation_pdf(b"3", "2026-01-03", "bob")
        listed = dm.list_consultation_pdfs("ann")
        assert [e["filename"] for e in listed] == [second["filename"], first["filename"]]
        assert dm.list_consultation_pdfs("zed") == []

    def test_find_by_source(self, dm):
        saved = dm.save_consultation_pdf(b"x", "2026-01-01", "ann", "rec1")
        assert dm.find_consultation_pdf_by_source("ann", "rec1") == saved
        assert dm.find_consultation_pdf_by_source("bob", "rec1") is None
        assert dm.find_consultation_pdf_by_source("ann", "other") is None

    def test_find_by_source_with_no_id_always_returns_none(self, dm):
        dm.save_consultation_pdf(b"x", "2026-01-01", "ann", None)
        assert dm.find_consultation_pdf_by_source("ann", None) is None
        assert dm.find_consultation_pdf_by_source("ann", "") is None

    def test_read_bytes_missing_file(self, dm):
        assert dm.get_consultation_pdf_bytes("nope.pdf") is None

    def test_read_bytes_cannot_escape_the_pdf_folder(self, dm, tmp_path):
        (tmp_path / "secret.pdf").write_bytes(b"secret")
        assert dm.get_consultation_pdf_bytes("../secret.pdf") is None

    def test_retention_limit_deletes_only_the_oldest_pdfs_of_that_user(self, make_manager, paths):
        dm = make_manager(max_retained=2)
        entries = [dm.save_consultation_pdf(b"%d" % i, "2026-01-01", "ann") for i in range(4)]
        other = dm.save_consultation_pdf(b"bob", "2026-01-01", "bob")

        kept = {e["filename"] for e in dm.list_consultation_pdfs("ann")}
        assert kept == {entries[2]["filename"], entries[3]["filename"]}
        assert not os.path.exists(os.path.join(paths["pdfs"], entries[0]["filename"]))
        assert os.path.exists(os.path.join(paths["pdfs"], other["filename"]))
        assert len(dm.list_consultation_pdfs("bob")) == 1

    def test_no_retention_limit_keeps_everything(self, dm):
        for i in range(5):
            dm.save_consultation_pdf(b"x", "2026-01-01", "ann")
        assert len(dm.list_consultation_pdfs("ann")) == 5

    def test_never_touches_health_records(self, dm, paths):
        dm.save_consultation_pdf(b"x", "2026-01-01", "ann")
        assert not os.path.exists(paths["records"])

    def test_save_fails_cleanly_when_the_folder_cannot_be_created(self, tmp_path, paths):
        blocker = tmp_path / "blocker"
        blocker.write_text("file", encoding="utf-8")
        archive = ConsultationPdfArchive(str(blocker / "pdfs"), JsonListStore(paths["summaries"]))
        assert archive.save(b"x", "2026-01-01", "ann") is None

    def test_corrupt_metadata_file_does_not_crash_listing(self, dm, paths):
        os.makedirs(os.path.dirname(paths["summaries"]), exist_ok=True)
        with open(paths["summaries"], "w", encoding="utf-8") as f:
            f.write("{broken")
        assert dm.list_consultation_pdfs("ann") == []


# ---------------------------------------------------------------------------
# Original report files
# ---------------------------------------------------------------------------

class TestOriginalReports:
    def save(self, dm, data=b"AAA", name="a.pdf", mime="application/pdf",
             date="2026-02-01", user="ann"):
        return dm.save_original_report(data, name, mime, date, user)

    def test_save_keeps_the_exact_bytes(self, dm):
        entry = self.save(dm, b"\x00\x01binary")
        assert dm.get_original_report_bytes(entry["stored_filename"]) == b"\x00\x01binary"
        assert entry["filename"] == "a.pdf" and entry["stored_filename"] != "a.pdf"

    def test_identical_upload_by_same_user_is_stored_once(self, dm, paths):
        first = self.save(dm)
        second = self.save(dm, name="renamed.pdf")
        assert first == second
        assert len(os.listdir(paths["reports"])) == 1

    def test_same_bytes_from_another_user_are_stored_separately(self, dm):
        assert self.save(dm, user="ann")["report_id"] != self.save(dm, user="bob")["report_id"]

    def test_same_filename_different_content_never_collides(self, dm):
        a, b = self.save(dm, b"AAA"), self.save(dm, b"BBB")
        assert a["stored_filename"] != b["stored_filename"]

    @pytest.mark.parametrize("name,mime,expected", [
        ("noext", "application/pdf", ".pdf"),
        ("noext", "image/png", ".png"),
        ("noext", "image/jpeg", ".jpg"),
        ("noext", "text/plain", ""),
        ("scan.jpeg", "image/png", ".jpeg"),   # the filename's own extension wins
    ])
    def test_extension(self, dm, name, mime, expected):
        entry = self.save(dm, name=name, mime=mime)
        assert entry["stored_filename"].endswith(expected)
        if expected == "":
            assert "." not in entry["stored_filename"]

    def test_list_is_per_user_newest_report_date_first_and_handles_missing_dates(self, dm):
        old = self.save(dm, b"1", date="2026-01-01")
        new = self.save(dm, b"2", date="2026-03-01")
        undated = self.save(dm, b"3", date=None)
        self.save(dm, b"4", user="bob")
        ids = [e["report_id"] for e in dm.list_original_reports("ann")]
        assert ids == [new["report_id"], old["report_id"], undated["report_id"]]
        assert dm.list_original_reports("zed") == []

    def test_find_by_id(self, dm):
        entry = self.save(dm)
        assert dm.get_original_report_by_id(entry["report_id"]) == entry
        assert dm.get_original_report_by_id("nope") is None

    def test_read_bytes_missing_and_path_traversal(self, dm, tmp_path):
        (tmp_path / "secret.txt").write_bytes(b"secret")
        assert dm.get_original_report_bytes("nope.pdf") is None
        assert dm.get_original_report_bytes("../secret.txt") is None

    def test_save_fails_cleanly_when_the_folder_cannot_be_created(self, tmp_path, paths):
        blocker = tmp_path / "blocker"
        blocker.write_text("file", encoding="utf-8")
        archive = OriginalReportArchive(str(blocker / "reports"), JsonListStore(paths["meta"]))
        assert archive.save(b"x", "a.pdf", "application/pdf", None, "ann") is None

    def test_upload_date_is_recorded(self, dm):
        from datetime import date
        assert self.save(dm)["upload_date"] == date.today().isoformat()


# ---------------------------------------------------------------------------
# Medical profiles
# ---------------------------------------------------------------------------

class TestMedicalProfiles:
    def test_default_profile_has_every_section(self):
        profile = default_medical_profile()
        assert set(profile) == {"medications", "blood_group", "allergies",
                                "emergency_contacts", "hereditary_illness"}

    def test_default_profile_is_never_shared(self):
        first = default_medical_profile()
        first["medications"].append("x")
        first["hereditary_illness"]["asthma"] = True
        assert default_medical_profile() == DataManager.get_default_medical_profile()
        assert default_medical_profile()["medications"] == []
        assert default_medical_profile()["hereditary_illness"]["asthma"] is False

    def test_load_unknown_user_gives_the_default(self, dm):
        assert dm.load_medical_profile("ann") == default_medical_profile()

    def test_save_and_load_round_trip(self, dm):
        profile = default_medical_profile()
        profile["blood_group"] = "O+"
        assert dm.save_medical_profile("ann", profile) is True
        loaded = dm.load_medical_profile("ann")
        assert loaded["blood_group"] == "O+" and loaded["last_updated"]

    def test_save_does_not_mutate_the_callers_dict(self, dm):
        profile = {"blood_group": "A-"}
        dm.save_medical_profile("ann", profile)
        assert profile == {"blood_group": "A-"}

    def test_save_replaces_one_user_without_touching_others(self, dm):
        dm.save_medical_profile("ann", {"blood_group": "O+"})
        dm.save_medical_profile("bob", {"blood_group": "A-"})
        dm.save_medical_profile("ann", {"blood_group": "B+"})
        assert dm.load_medical_profile("ann")["blood_group"] == "B+"
        assert dm.load_medical_profile("bob")["blood_group"] == "A-"

    def test_older_profile_is_filled_in_from_the_defaults(self, dm):
        dm.save_medical_profile("ann", {"blood_group": "O+",
                                        "hereditary_illness": {"diabetes": True}})
        loaded = dm.load_medical_profile("ann")
        assert loaded["hereditary_illness"]["diabetes"] is True
        assert loaded["hereditary_illness"]["asthma"] is False  # newly defaulted flag
        assert loaded["allergies"] == []

    def test_corrupt_profiles_file_is_backed_up(self, dm, paths):
        with open(paths["profiles"], "w", encoding="utf-8") as f:
            f.write("[1, 2]")  # valid JSON but not an object
        assert dm.load_medical_profile("ann") == default_medical_profile()
        assert os.path.exists(paths["profiles"] + ".bak")

    def test_saved_file_is_an_object_keyed_by_username(self, dm, paths):
        dm.save_medical_profile("ann", {"blood_group": "O+"})
        with open(paths["profiles"], encoding="utf-8") as f:
            assert list(json.load(f)) == ["ann"]


# ---------------------------------------------------------
# Phase 2: New feature tests
# ---------------------------------------------------------

def test_manual_vitals_save_and_retrieve(dm, tmp_path):
    from data_layer import JsonRecordRepository

    dm._manual_vitals = JsonRecordRepository(
        str(tmp_path / "manual_vitals.json")
    )

    entry = {
        "username": "alice",
        "date": "2026-11-09",
        "time": "10:30",
        "metrics": {"heart_rate": 72}
    }

    saved = dm.save_manual_vital(entry)

    assert saved is not None
    assert saved["record_id"]
    assert len(dm.list_manual_vitals("alice")) == 1
    assert dm.list_manual_vitals("alice")[0]["metrics"]["heart_rate"] == 72
    assert dm.list_manual_vitals("bob") == []


def test_manual_vitals_logic_processing():
    from logic_manager import LogicManager

    manager = LogicManager.default()

    result = manager.process_manual_reading(
        {"heart_rate": 72},
        []
    )

    assert isinstance(result, dict)
    assert result["decision"] == "ACCEPTED"


def test_medical_profile_pdf_save_and_retrieve(dm, tmp_path):
    from data_layer import MedicalProfilePdfArchive, JsonListStore

    dm._medical_profile_pdfs = MedicalProfilePdfArchive(
        str(tmp_path / "profile_pdfs"),
        JsonListStore(str(tmp_path / "profile_pdf_metadata.json"))
    )

    pdf_bytes = b"%PDF-1.4\nTest PDF content"

    saved = dm.save_medical_profile_pdf(pdf_bytes, "alice")

    assert saved is not None
    assert saved["filename"].endswith(".pdf")

    history = dm.list_medical_profile_pdfs("alice")
    assert len(history) == 1
    assert dm.list_medical_profile_pdfs("bob") == []

    retrieved = dm.get_medical_profile_pdf_bytes(
        saved["filename"]
    )
    assert retrieved == pdf_bytes
