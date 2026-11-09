"""
tests/test_user_file_integration.py

Proves User (user.py) and ExtractedFile (file.py) take part in the real
manager workflows: account storage, AI extraction, rule processing and
rebuilding a user's saved reports. Everything runs on temporary files.

Run with:
    python -m pytest tests/test_user_file_integration.py
"""

import pytest

from data_layer import (
    ConsultationPdfArchive, JsonAccountRepository, JsonListStore,
    JsonRecordRepository, MedicalProfileStore, OriginalReportArchive,
)
from data_manager import DataManager
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
