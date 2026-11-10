"""
tests/test_user_file_integration.py

Proves User (user.py) and ExtractedFile (file.py) take part in the real
manager workflows: account storage, AI extraction, rule processing and
rebuilding a user's saved reports. Everything runs on temporary files.

Run with:
    python -m pytest tests/test_user_file_integration.py
"""

import json

import pytest

from ai_manager import AIManager, MockAIClient
from data_layer import (
    ConsultationPdfArchive, JsonAccountRepository, JsonListStore,
    JsonRecordRepository, MedicalProfileStore, OriginalReportArchive,
)
from data_manager import DataManager
from file import ExtractedFile
from logic_manager import LogicManager
from user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def dm(tmp_path):
    return DataManager(
        JsonRecordRepository(str(tmp_path / "records.json")),
        ConsultationPdfArchive(str(tmp_path / "pdfs"), JsonListStore(str(tmp_path / "summaries.json"))),
        OriginalReportArchive(str(tmp_path / "reports"), JsonListStore(str(tmp_path / "meta.json"))),
        MedicalProfileStore(str(tmp_path / "profiles.json")),
        JsonAccountRepository(str(tmp_path / "users.json")),
        JsonRecordRepository(str(tmp_path / "vitals.json")),
    )


# ---------------------------------------------------------------------------
# DataManager <-> User (registration, login, user management)
# ---------------------------------------------------------------------------

def test_save_account_and_find_user(dm):
    assert dm.save_account(User("Alice"), {"salt": "s", "password_hash": "h"})
    found = dm.find_user("ALICE")
    assert isinstance(found, User)
    assert found.username == "Alice"
    assert dm.load_accounts() == {"alice": {"salt": "s", "password_hash": "h", "username": "Alice"}}


def test_find_user_unknown_or_blank_returns_none(dm):
    assert dm.find_user("nobody") is None
    assert dm.find_user("   ") is None


def test_get_account_returns_a_copy(dm):
    dm.save_account(User("bob"), {"salt": "s", "password_hash": "h"})
    account = dm.get_account(User("Bob"))
    account["password_hash"] = "changed"
    assert dm.get_account(User("bob"))["password_hash"] == "h"


def test_save_account_leaves_other_accounts_untouched(dm):
    dm.save_account(User("alice"), {"salt": "a", "password_hash": "1"})
    dm.save_account(User("bob"), {"salt": "b", "password_hash": "2"})
    account = dm.get_account(User("alice"))
    account["pin_hash"] = "p"
    dm.save_account(User("alice"), account)
    assert dm.get_account(User("bob")) == {"salt": "b", "password_hash": "2", "username": "bob"}
    assert dm.get_account(User("alice"))["pin_hash"] == "p"


def test_save_account_username_always_comes_from_the_user(dm):
    dm.save_account(User("Alice"), {"salt": "s", "password_hash": "h", "username": "eve"})
    assert dm.get_account(User("alice"))["username"] == "Alice"


def test_account_methods_reject_non_users(dm):
    with pytest.raises(TypeError):
        dm.get_account("alice")
    with pytest.raises(TypeError):
        dm.save_account("alice", {})


# ---------------------------------------------------------------------------
# AIManager -> ExtractedFile
# ---------------------------------------------------------------------------

def extraction_json(heart_rate=72, blood_glucose=5.0, report_date="2026-01-01",
                    is_medical_report=True):
    """The JSON string the AI returns for one report."""
    return json.dumps({
        "is_medical_report": is_medical_report,
        "classification_reason": "Lab report.",
        "heart_rate": heart_rate,
        "blood_pressure": {"systolic": 118, "diastolic": 76},
        "blood_glucose": blood_glucose,
        "report_date": report_date,
    })


ALL_SUPPORTED = json.dumps({
    "heart_rate_supported": True,
    "blood_pressure_supported": True,
    "blood_glucose_supported": True,
    "report_date_supported": True,
})


def ai_with(*replies):
    """An AIManager whose mock client returns these replies in order."""
    return AIManager(MockAIClient(list(replies)))


def test_extract_file_returns_validated_extracted_file():
    f = ai_with(extraction_json(), ALL_SUPPORTED).extract_file(b"pdf", "application/pdf", "lab.pdf")
    assert isinstance(f, ExtractedFile)
    assert f.source == "lab.pdf"
    assert f.mime_type == "application/pdf"
    assert f.report_date == "2026-01-01"
    assert f.metrics["blood_pressure_systolic"] == 118


def test_extract_file_keeps_non_medical_classification():
    f = ai_with(extraction_json(is_medical_report=False)).extract_file(b"img", "image/png", "cat.png")
    assert isinstance(f, ExtractedFile)
    assert f.is_medical_report is False


def test_extract_file_rejects_invalid_ai_values():
    # The AI schema allows any number; ExtractedFile refuses a negative reading.
    ai = ai_with(extraction_json(heart_rate=-5), ALL_SUPPORTED)
    assert ai.extract_file(b"pdf", "application/pdf", "lab.pdf") is None


def test_extract_file_returns_none_when_ai_fails():
    assert AIManager(MockAIClient([])).extract_file(b"pdf", "application/pdf", "lab.pdf") is None


# ---------------------------------------------------------------------------
# LogicManager <- ExtractedFile
# ---------------------------------------------------------------------------

HISTORY = [
    {"metrics": {"heart_rate": 70, "blood_glucose": 5.0}, "date": "2025-12-01"},
    {"metrics": {"heart_rate": 80}, "date": "2025-12-15"},
]


@pytest.mark.parametrize("heart_rate", [None, 60, 130, 200])
@pytest.mark.parametrize("blood_glucose", [None, 5.0, 15.0])
@pytest.mark.parametrize("history", [[], HISTORY])
def test_process_file_matches_process(heart_rate, blood_glucose, history):
    ai_result = json.loads(extraction_json(heart_rate=heart_rate, blood_glucose=blood_glucose))
    extracted = ExtractedFile.from_ai_result("lab.pdf", "application/pdf", ai_result)
    logic = LogicManager.default()
    assert logic.process_file(extracted, history) == logic.process(ai_result, history)


def test_process_file_not_medical_report():
    selfie = ExtractedFile("selfie.jpg", "image/jpeg", False, "A photo of a cat.")
    result = LogicManager.default().process_file(selfie, [])
    assert result["decision"] == "NOT_MEDICAL_REPORT"
    assert result["summary"] == "A photo of a cat."


def test_process_file_without_measurements_is_rejected():
    letter = ExtractedFile("letter.pdf", "application/pdf", True, "Referral letter.",
                           report_date="2026-01-01")
    result = LogicManager.default().process_file(letter, [])
    assert result["decision"] == "REJECTED"
    assert result["ai_extracted_date"] == "2026-01-01"


def test_process_file_rejects_non_files():
    with pytest.raises(TypeError):
        LogicManager.default().process_file({"heart_rate": 72}, [])


# ---------------------------------------------------------------------------
# End-to-end: register -> upload -> rebuild the User with their files
# ---------------------------------------------------------------------------

def upload(dm, user, ai, file_bytes, filename):
    """The same manager calls show_upload() makes, without Streamlit."""
    extracted = ai.extract_file(file_bytes, "application/pdf", filename)
    processed = LogicManager.default().process_file(extracted, dm.load_health_records())
    record = dict(processed, username=user.username, date=extracted.report_date)
    original = dm.save_original_report(file_bytes, filename, "application/pdf",
                                       record["date"], user.username)
    record["report_id"] = original["report_id"]
    assert dm.save_record(record)


def test_full_workflow_user_owns_extracted_files(dm):
    dm.save_account(User("Alice"), {"salt": "s", "password_hash": "h"})
    alice = dm.find_user("alice")

    upload(dm, alice, ai_with(extraction_json(report_date="2026-03-01"), ALL_SUPPORTED), b"march", "mar.pdf")
    upload(dm, alice, ai_with(extraction_json(report_date="2026-01-15"), ALL_SUPPORTED), b"january", "jan.pdf")

    loaded = dm.load_user("alice")
    assert loaded == alice
    assert loaded.file_count == 2
    assert all(isinstance(f, ExtractedFile) for f in loaded.files)
    assert [f.report_date for f in loaded.files_by_date()] == ["2026-01-15", "2026-03-01"]
    assert len(loaded.medical_files()) == 2


def test_load_user_ignores_other_users_and_duplicate_uploads(dm):
    dm.save_account(User("alice"), {"salt": "s", "password_hash": "h"})
    dm.save_account(User("bob"), {"salt": "s", "password_hash": "h"})
    alice, bob = dm.find_user("alice"), dm.find_user("bob")

    upload(dm, alice, ai_with(extraction_json(), ALL_SUPPORTED), b"same", "a.pdf")
    upload(dm, alice, ai_with(extraction_json(), ALL_SUPPORTED), b"same", "a-again.pdf")
    upload(dm, bob, ai_with(extraction_json(), ALL_SUPPORTED), b"bob", "b.pdf")

    assert len(dm.load_health_records()) == 3
    assert dm.load_user("alice").file_count == 1   # identical bytes -> one archived file
    assert dm.load_user("bob").file_count == 1


def test_load_user_skips_records_that_fail_validation(dm):
    dm.save_account(User("alice"), {"salt": "s", "password_hash": "h"})
    dm.save_record({"username": "alice", "date": "not-a-date", "metrics": {"heart_rate": 70}})
    dm.save_record({"username": "alice", "date": "2026-01-01", "metrics": {"heart_rate": -1}})
    dm.save_record({"username": "alice", "date": "2026-01-01", "metrics": {"heart_rate": 70}})
    assert dm.load_user("alice").file_count == 1


def test_load_user_unknown_returns_none(dm):
    assert dm.load_user("ghost") is None
