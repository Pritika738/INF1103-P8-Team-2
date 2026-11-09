
"""
tests/test_file.py

Unit tests for the ExtractedFile class in file.py.

Run with:
    python -m pytest tests/test_file.py
"""

import pytest

from file import ExtractedFile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ai_result():
    """A typical, already schema-validated result from AIManager.extract_report()."""
    return {
        "is_medical_report": True,
        "classification_reason": "Lab report with vitals.",
        "heart_rate": 72,
        "blood_pressure": {"systolic": 118, "diastolic": 76},
        "blood_glucose": 5.0,
        "report_date": "2026-01-01",
    }


@pytest.fixture
def report(ai_result):
    return ExtractedFile.from_ai_result("report.pdf", "application/pdf", ai_result)


# ---------------------------------------------------------------------------
# source / mime_type
# ---------------------------------------------------------------------------

def test_source_and_mime_type_are_stripped():
    f = ExtractedFile("  report.pdf ", " application/pdf ")
    assert f.source == "report.pdf"
    assert f.mime_type == "application/pdf"


@pytest.mark.parametrize("source", ["", "   ", None, 123])
def test_invalid_source_is_rejected(source):
    with pytest.raises(ValueError, match="source"):
        ExtractedFile(source, "application/pdf")


@pytest.mark.parametrize("mime_type", ["", "   ", None])
def test_invalid_mime_type_is_rejected(mime_type):
    with pytest.raises(ValueError, match="mime_type"):
        ExtractedFile("report.pdf", mime_type)


# ---------------------------------------------------------------------------
# report_date
# ---------------------------------------------------------------------------

def test_valid_date_is_kept_and_stripped():
    f = ExtractedFile("a.pdf", "application/pdf", report_date=" 2026-11-05 ")
    assert f.report_date == "2026-11-05"


def test_missing_date_is_none():
    assert ExtractedFile("a.pdf", "application/pdf").report_date is None


@pytest.mark.parametrize("bad_date", ["tomorrow", "2026-13-45", "2026-02-30", "2026-1-5", "", 20261105])
def test_invalid_date_is_rejected(bad_date):
    with pytest.raises(ValueError, match="report_date"):
        ExtractedFile("a.pdf", "application/pdf", report_date=bad_date)


# ---------------------------------------------------------------------------
# Metric values 
# ---------------------------------------------------------------------------

def test_valid_metrics_are_kept_unchanged():
    f = ExtractedFile("a.pdf", "application/pdf", heart_rate=72, blood_glucose=5.4)
    assert f.metrics == {
        "heart_rate": 72,
        "blood_pressure_systolic": None,
        "blood_pressure_diastolic": None,
        "blood_glucose": 5.4,
    }


def test_zero_is_a_valid_metric():
    f = ExtractedFile("a.pdf", "application/pdf", heart_rate=0)
    assert f.metrics["heart_rate"] == 0


@pytest.mark.parametrize("field", [
    "heart_rate", "blood_pressure_systolic", "blood_pressure_diastolic", "blood_glucose",
])
@pytest.mark.parametrize("bad_value", ["abc", True, -1, float("nan"), float("inf")])
def test_invalid_metric_is_rejected(field, bad_value):
    with pytest.raises(ValueError, match=field):
        ExtractedFile("a.pdf", "application/pdf", **{field: bad_value})


def test_has_measurements():
    assert ExtractedFile("a.pdf", "application/pdf", heart_rate=60).has_measurements()
    assert not ExtractedFile("a.pdf", "application/pdf").has_measurements()


# ---------------------------------------------------------------------------
# from_ai_result / to_dict / from_dict
# ---------------------------------------------------------------------------

def test_from_ai_result_flattens_blood_pressure(report):
    assert report.is_medical_report is True
    assert report.report_date == "2026-01-01"
    assert report.metrics["blood_pressure_systolic"] == 118
    assert report.metrics["blood_pressure_diastolic"] == 76


def test_from_ai_result_handles_null_blood_pressure(ai_result):
    ai_result["blood_pressure"] = None
    f = ExtractedFile.from_ai_result("a.pdf", "application/pdf", ai_result)
    assert f.metrics["blood_pressure_systolic"] is None
    assert f.metrics["blood_pressure_diastolic"] is None


def test_to_dict_uses_date_key_and_nested_metrics(report):
    data = report.to_dict()
    assert data["date"] == "2026-01-01"
    assert "report_date" not in data
    assert data["metrics"]["heart_rate"] == 72


def test_to_dict_from_dict_round_trip(report):
    rebuilt = ExtractedFile.from_dict(report.to_dict())
    assert rebuilt.to_dict() == report.to_dict()


def test_from_dict_uses_defaults_for_missing_keys():
    f = ExtractedFile.from_dict({"source": "b.png", "mime_type": "image/png"})
    assert f.is_medical_report is False
    assert f.classification_reason == ""
    assert f.report_date is None
    assert not f.has_measurements()


def test_from_dict_rejects_non_dict():
    with pytest.raises(TypeError):
        ExtractedFile.from_dict("oops")


def test_from_dict_still_validates():
    with pytest.raises(ValueError, match="report_date"):
        ExtractedFile.from_dict({"source": "a.pdf", "mime_type": "application/pdf",
                                 "date": "2026-99-01"})

# ---------------------------------------------------------------------------

def test_properties_are_read_only(report):
    with pytest.raises(AttributeError):
        report.source = "other.pdf"


def test_metrics_returns_a_copy(report):
    report.metrics["heart_rate"] = 999
    assert report.metrics["heart_rate"] == 72


# ---------------------------------------------------------------------------
# Equality and hashing
# ---------------------------------------------------------------------------

def test_files_with_same_source_are_equal():
    a = ExtractedFile("a.pdf", "application/pdf", heart_rate=72)
    b = ExtractedFile("a.pdf", "application/pdf")
    assert a == b
    assert hash(a) == hash(b)


def test_files_with_different_source_are_not_equal():
    assert ExtractedFile("a.pdf", "application/pdf") != ExtractedFile("c.png", "image/png")


def test_file_is_not_equal_to_other_types():
    assert ExtractedFile("a.pdf", "application/pdf") != "a.pdf"


def test_set_removes_duplicate_files():
    files = {
        ExtractedFile("a.pdf", "application/pdf"),
        ExtractedFile("a.pdf", "application/pdf"),
        ExtractedFile("c.png", "image/png"),
    }
    assert len(files) == 2
