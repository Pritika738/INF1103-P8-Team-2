"""
tests/test_gui_user_workflow.py

Drives the real Streamlit GUI (io_gui/io_gui.py) with Streamlit's
AppTest to prove the Register, Login, PIN, Upload and Dashboard pages
work through User and ExtractedFile objects.

- The app's DataManager is swapped for one on temporary files, so the
  real data/ folder (and data/app.db) is never touched.
- The Gemini client is swapped for MockAIClient, so no AI calls are made.
- "Spies" wrap the manager methods and record each call, so the tests
  prove the GUI really goes through the User / ExtractedFile methods.

Run with:
    python -m pytest tests/test_gui_user_workflow.py
"""

import hashlib
import json
import os
import sys

import pytest
import streamlit
from streamlit.testing.v1 import AppTest

import ai_manager
import data_manager
import logic_manager
from data_layer import (
    ConsultationPdfArchive, JsonAccountRepository, JsonListStore,
    JsonRecordRepository, MedicalProfileStore, OriginalReportArchive,
)
from data_manager import DataManager
from file import ExtractedFile
from user import User

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "io_gui", "io_gui.py")
PASSWORD = "Passw0rd!23"
SALT = "00" * 16


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def dm(tmp_path, monkeypatch):
    """A DataManager on temporary files, handed to the app at start-up."""
    manager = DataManager(
        JsonRecordRepository(str(tmp_path / "records.json")),
        ConsultationPdfArchive(str(tmp_path / "pdfs"), JsonListStore(str(tmp_path / "summaries.json"))),
        OriginalReportArchive(str(tmp_path / "reports"), JsonListStore(str(tmp_path / "meta.json"))),
        MedicalProfileStore(str(tmp_path / "profiles.json")),
        JsonAccountRepository(str(tmp_path / "users.json")),
        JsonRecordRepository(str(tmp_path / "vitals.json")),
    )
    monkeypatch.setattr(data_manager.DataManager, "create", classmethod(lambda cls: manager))
    # The GUI builds its services when core.py is first imported. Forget the
    # GUI modules so this test's app imports them again and uses `manager`.
    for name in list(sys.modules):
        if name in ("core", "styles", "screens") or name.startswith("screens."):
            monkeypatch.delitem(sys.modules, name)
    return manager


@pytest.fixture
def calls(dm, monkeypatch):
    """Records (method name, arguments, result) for each spied call."""
    seen = []

    def spy_on(owner, name, bound):
        original = getattr(owner, name)

        def spy(*args, **kwargs):
            result = original(*args, **kwargs)
            seen.append((name, args[1:] if not bound else args, result))
            return result

        monkeypatch.setattr(owner, name, spy)

    for name in ("find_user", "get_account", "save_account", "load_user"):
        spy_on(dm, name, bound=True)
    spy_on(ai_manager.AIManager, "extract_file", bound=False)
    spy_on(logic_manager.LogicManager, "process_file", bound=False)
    return seen


def results(calls, name):
    return [result for called, _, result in calls if called == name]


def register_alice(dm):
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", PASSWORD.encode("utf-8"), bytes.fromhex(SALT), 200_000
    ).hex()
    dm.save_account(User("Alice"), {"salt": SALT, "password_hash": password_hash})


def start_app(**session):
    at = AppTest.from_file(APP, default_timeout=60)
    for key, value in session.items():
        at.session_state[key] = value
    at.run()
    return at


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_page_saves_a_user_object(dm, calls):
    at = start_app(page="register")
    at.text_input(key="register_username").input("Alice")
    at.text_input(key="register_password").input(PASSWORD)
    at.text_input(key="register_confirm_password").input(PASSWORD)
    click(at, "Create Account")

    assert not at.exception
    assert [args[0] for name, args, _ in calls if name == "save_account"] == [User("Alice")]
    assert dm.find_user("alice").username == "Alice"


def test_register_page_rejects_existing_username_any_case(dm, calls):
    register_alice(dm)
    calls.clear()  # only record what the GUI does from here on
    at = start_app(page="register")
    at.text_input(key="register_username").input("ALICE")
    at.text_input(key="register_password").input(PASSWORD)
    at.text_input(key="register_confirm_password").input(PASSWORD)
    click(at, "Create Account")

    assert any("already taken" in e.value for e in at.error)
    assert not results(calls, "save_account")


# ---------------------------------------------------------------------------
# Login (password and PIN)
# ---------------------------------------------------------------------------

def test_login_page_signs_in_the_stored_user(dm, calls):
    register_alice(dm)
    at = start_app()
    at.text_input(key="login_username").input("ALICE")
    at.text_input(key="login_password").input(PASSWORD)
    click(at, "Log In")

    assert not at.exception
    assert User("Alice") in results(calls, "find_user")
    # The session name comes from the User object, not from what was typed.
    assert at.session_state["username"] == "Alice"
    assert at.session_state["page"] == "dashboard"


def test_login_page_rejects_wrong_password(dm):
    register_alice(dm)
    at = start_app()
    at.text_input(key="login_username").input("alice")
    at.text_input(key="login_password").input("wrong")
    click(at, "Log In")

    assert "username" not in at.session_state
    assert any("Incorrect username or password" in e.value for e in at.error)


def test_pin_set_then_pin_login_use_the_user(dm, calls):
    register_alice(dm)
    calls.clear()
    at = start_app(username="Alice", page="settings")
    at.text_input(key="settings_new_pin").input("1234")
    at.text_input(key="settings_confirm_pin").input("1234")
    click(at, "Set PIN")
    assert [args[0] for name, args, _ in calls if name == "save_account"] == [User("Alice")]
    assert "pin_hash" in dm.get_account(User("alice"))

    at = start_app(page="pin_login")
    at.text_input(key="pin_login_username").input("alice")
    at.text_input(key="pin_login_pin").input("1234")
    click(at, "Log In with PIN")
    assert at.session_state["username"] == "Alice"


# ---------------------------------------------------------------------------
# Upload (ExtractedFile through the AI and Logic Managers)
# ---------------------------------------------------------------------------

class FakeUpload:
    """Stands in for Streamlit's UploadedFile."""

    def __init__(self, name, mime_type, data):
        self.name, self.type, self.size, self._data = name, mime_type, len(data), data

    def getvalue(self):
        return self._data


def use_mock_ai(monkeypatch, heart_rate):
    reply = json.dumps({
        "is_medical_report": True, "classification_reason": "Lab report.",
        "heart_rate": heart_rate, "blood_pressure": {"systolic": 118, "diastolic": 76},
        "blood_glucose": 5.0, "report_date": "2026-01-01",
    })
    verified = json.dumps({"heart_rate_supported": True, "blood_pressure_supported": True,
                           "blood_glucose_supported": True, "report_date_supported": True})
    monkeypatch.setattr(ai_manager, "GeminiClient",
                        lambda *a, **k: ai_manager.MockAIClient([reply, verified] * 3))
    monkeypatch.setattr(streamlit, "file_uploader",
                        lambda *a, **k: [FakeUpload("lab.pdf", "application/pdf", b"%PDF-1.4 test")])


def test_upload_page_processes_an_extracted_file(dm, calls, monkeypatch):
    use_mock_ai(monkeypatch, heart_rate=72)
    at = start_app(username="Alice", page="upload")
    click(at, "Analyze with AI")

    assert not at.exception
    assert any("saved" in s.value for s in at.success)
    extracted = results(calls, "extract_file")
    assert len(extracted) == 1 and isinstance(extracted[0], ExtractedFile)
    processed_with = [args[0] for name, args, _ in calls if name == "process_file"]
    assert processed_with == extracted
    assert [r["username"] for r in dm.load_health_records()] == ["Alice"]


def test_upload_page_rejects_impossible_readings(dm, calls, monkeypatch):
    use_mock_ai(monkeypatch, heart_rate=-5)
    at = start_app(username="Alice", page="upload")
    click(at, "Analyze with AI")

    assert results(calls, "extract_file") == [None]
    assert any("could not complete" in e.value for e in at.error)
    assert dm.load_health_records() == []


# ---------------------------------------------------------------------------
# Dashboard (User aggregating ExtractedFiles)
# ---------------------------------------------------------------------------

def test_dashboard_counts_reports_through_user_files(dm, calls):
    register_alice(dm)
    for file_bytes, day in ((b"%PDF-1 jan", "2026-01-15"),
                            (b"%PDF-1 jan", "2026-01-15"),   # same file uploaded twice
                            (b"%PDF-2 mar", "2026-03-01")):
        original = dm.save_original_report(file_bytes, "r.pdf", "application/pdf", day, "Alice")
        dm.save_record({"username": "Alice", "date": day, "report_id": original["report_id"],
                        "metrics": {"heart_rate": 72}, "decision": "ACCEPTED", "summary": "ok",
                        "requires_doctor_review": False})

    at = start_app(username="Alice", page="dashboard")

    assert not at.exception
    loaded = results(calls, "load_user")
    assert loaded and loaded[-1].file_count == 2
    assert all(isinstance(f, ExtractedFile) for f in loaded[-1].files)
    tile = next(m.value for m in at.markdown if "Reports on file" in m.value)
    assert ">2</div>" in tile.replace(" ", "")
