"""
tests/test_user.py

Unit tests for the User class in user.py.

Run with:
    python -m pytest tests/test_user.py
"""

import pytest

from file import ExtractedFile
from user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user():
    return User("Alice")


def make_file(source, report_date=None, medical=True, heart_rate=72):
    """Build a small ExtractedFile for tests."""
    return ExtractedFile(source, "application/pdf", medical, "test file",
                         heart_rate=heart_rate, report_date=report_date)


# ---------------------------------------------------------------------------
# Construction and identity
# ---------------------------------------------------------------------------

def test_username_is_stripped_and_case_is_kept():
    u = User("  Alice ")
    assert u.username == "Alice"
    assert u.key == "alice"

@pytest.mark.parametrize("bad_username", ["", "   ", None])
def test_empty_username_is_rejected(bad_username):
    with pytest.raises(ValueError, match="username"):
        User(bad_username)


def test_username_is_read_only(user):
    with pytest.raises(AttributeError):
        user.username = "Bob"


def test_user_has_no_email(user):
    assert not hasattr(user, "email")


def test_new_user_has_no_files(user):
    assert user.files == []
    assert user.file_count == 0


# ---------------------------------------------------------------------------
# Equality and hashing
# ---------------------------------------------------------------------------

def test_usernames_are_case_insensitive():
    assert User("Alice") == User("alice")
    assert hash(User("Alice")) == hash(User("ALICE"))


def test_different_users_are_not_equal():
    assert User("alice") != User("bob")


def test_user_is_not_equal_to_other_types():
    assert User("alice") != "alice"


def test_set_removes_duplicate_users():
    assert len({User("Alice"), User("alice"), User("bob")}) == 2


# ---------------------------------------------------------------------------
# add_file / remove_file / file_count
# ---------------------------------------------------------------------------

def test_add_file(user):
    user.add_file(make_file("a.pdf"))
    user.add_file(make_file("b.pdf"))
    assert user.file_count == 2
    assert [f.source for f in user.files] == ["a.pdf", "b.pdf"]


def test_add_file_rejects_non_files(user):
    with pytest.raises(TypeError):
        user.add_file("a.pdf")


def test_add_file_rejects_duplicates(user):
    user.add_file(make_file("a.pdf"))
    with pytest.raises(ValueError, match="already been added"):
        user.add_file(make_file("a.pdf"))
    assert user.file_count == 1


def test_remove_file_returns_the_removed_file(user):
    user.add_file(make_file("a.pdf"))
    user.add_file(make_file("b.pdf"))
    removed = user.remove_file("a.pdf")
    assert removed.source == "a.pdf"
    assert [f.source for f in user.files] == ["b.pdf"]


def test_remove_missing_file_raises(user):
    with pytest.raises(ValueError, match="missing.pdf"):
        user.remove_file("missing.pdf")


def test_removed_file_can_be_added_again(user):
    user.add_file(make_file("a.pdf"))
    user.remove_file("a.pdf")
    user.add_file(make_file("a.pdf"))
    assert user.file_count == 1


def test_file_count_is_read_only(user):
    with pytest.raises(AttributeError):
        user.file_count = 5


def test_to_dict_contains_username_only(user):
    assert user.to_dict() == {"username": "Alice"}


def test_files_returns_a_copy(user):
    user.add_file(make_file("a.pdf"))
    user.files.append(make_file("sneaky.pdf"))
    user.files.clear()
    assert user.file_count == 1


def test_files_by_date_sorts_oldest_first_and_skips_undated(user):
    user.add_file(make_file("mar.pdf", "2026-03-01"))
    user.add_file(make_file("undated.pdf"))
    user.add_file(make_file("jan.pdf", "2026-01-15"))
    assert [f.source for f in user.files_by_date()] == ["jan.pdf", "mar.pdf"]


def test_medical_files_keeps_only_reports_with_readings(user):
    user.add_file(make_file("lab.pdf"))
    user.add_file(make_file("selfie.jpg", medical=False))
    user.add_file(make_file("letter.pdf", heart_rate=None))
    assert [f.source for f in user.medical_files()] == ["lab.pdf"]


def test_to_dict_from_dict_round_trip(user):
    assert User.from_dict(user.to_dict()) == user


def test_from_dict_ignores_old_email_key():
    u = User.from_dict({"username": "bob", "email": "bob@example.com"})
    assert u.to_dict() == {"username": "bob"}


def test_from_dict_without_username_is_rejected():
    with pytest.raises(ValueError):
        User.from_dict({})
