"""
tests/test_logic_manager.py

Focused unit tests for the Logic Manager domain layer: metric
classification thresholds, the individual business rules (including the
multi-condition PersistentTrendRule the brief requires preserved), the
scoring/routing done by LogicManager, and the standing-profile and
manual-vitals validators.

These run without a live AI API - every input is a hardcoded dict or
value - so they are safe for CI and Docker.

Run with:
    python -m pytest tests/test_logic_manager.py
"""

from logic_layer import (
    HeartRate, SystolicBloodPressure, DiastolicBloodPressure, BloodGlucose,
    Tier,
    UrgentThresholdRule, PersistentTrendRule, RecentChangeRule,
    MedicalProfileValidator, ManualVitalsValidator,
)
from logic_manager import LogicManager


# ---------------------------------------------------------------------------
# MetricSpec.classify() - threshold boundaries
# classify(): value >= urgent_at -> SEVERE; value > flag_above -> ELEVATED;
# otherwise NORMAL. None in -> None out.
# ---------------------------------------------------------------------------

def test_classify_none_returns_none():
    assert HeartRate().classify(None) is None


def test_heart_rate_severe_at_urgent_threshold():
    # urgent_at = 130, inclusive
    assert HeartRate().classify(130) is Tier.SEVERE
    assert HeartRate().classify(131) is Tier.SEVERE


def test_heart_rate_elevated_just_below_urgent():
    assert HeartRate().classify(129) is Tier.ELEVATED


def test_heart_rate_flag_boundary_is_exclusive():
    # flag_above = 100, strictly greater -> ELEVATED; exactly 100 -> NORMAL
    assert HeartRate().classify(101) is Tier.ELEVATED
    assert HeartRate().classify(100) is Tier.NORMAL
    assert HeartRate().classify(90) is Tier.NORMAL


def test_systolic_boundaries():
    spec = SystolicBloodPressure()  # urgent_at=180, flag_above=130
    assert spec.classify(180) is Tier.SEVERE
    assert spec.classify(131) is Tier.ELEVATED
    assert spec.classify(130) is Tier.NORMAL


def test_diastolic_boundaries():
    spec = DiastolicBloodPressure()  # urgent_at=120, flag_above=80
    assert spec.classify(120) is Tier.SEVERE
    assert spec.classify(81) is Tier.ELEVATED
    assert spec.classify(80) is Tier.NORMAL


def test_blood_glucose_boundaries():
    spec = BloodGlucose()  # urgent_at=13.9, flag_above=7.0
    assert spec.classify(13.9) is Tier.SEVERE
    assert spec.classify(7.1) is Tier.ELEVATED
    assert spec.classify(7.0) is Tier.NORMAL


def test_is_urgent_matches_severe_threshold():
    spec = HeartRate()
    assert spec.is_urgent(130) is True
    assert spec.is_urgent(129) is False
    assert spec.is_urgent(None) is False


# ---------------------------------------------------------------------------
# UrgentThresholdRule - fires on a single reading at/above urgent_at,
# regardless of history.
# ---------------------------------------------------------------------------

def test_urgent_rule_fires_at_threshold():
    rule = UrgentThresholdRule(HeartRate())  # urgent_at = 130
    finding = rule.evaluate(130, [])
    assert finding is not None
    assert finding.status == "URGENT"


def test_urgent_rule_silent_below_threshold():
    rule = UrgentThresholdRule(HeartRate())
    assert rule.evaluate(129, []) is None


def test_urgent_rule_ignores_history():
    # A single urgent reading fires even with no prior visits.
    rule = UrgentThresholdRule(BloodGlucose())  # urgent_at = 13.9
    assert rule.evaluate(14.0, []) is not None


def test_urgent_rule_none_value_is_silent():
    rule = UrgentThresholdRule(HeartRate())
    assert rule.evaluate(None, [120, 125]) is None


# ---------------------------------------------------------------------------
# PersistentTrendRule - the MULTI-CONDITION rule the brief requires
# preserved. Fires FLAGGED only when BOTH hold:
#   (a) flag_above < current < urgent_at, AND
#   (b) current > previous > the-one-before (strictly rising x3).
# ---------------------------------------------------------------------------

def test_persistent_trend_fires_on_three_strictly_rising():
    rule = PersistentTrendRule(SystolicBloodPressure())  # flag=130, urgent=180
    finding = rule.evaluate(150, [135, 142])  # 142 < 150, 135 < 142 -> rising
    assert finding is not None
    assert finding.status == "FLAGGED"


def test_persistent_trend_silent_when_not_strictly_rising():
    rule = PersistentTrendRule(SystolicBloodPressure())
    # current(150) > past_1(142) but past_1(142) is NOT > past_2(145)
    assert rule.evaluate(150, [145, 142]) is None


def test_persistent_trend_silent_when_current_not_elevated():
    rule = PersistentTrendRule(SystolicBloodPressure())
    # current 128 is below flag_above(130): condition (a) fails
    assert rule.evaluate(128, [120, 124]) is None


def test_persistent_trend_defers_to_urgent():
    rule = PersistentTrendRule(SystolicBloodPressure())
    # current 185 is urgent -> handled by UrgentThresholdRule, not here
    assert rule.evaluate(185, [150, 170]) is None


def test_persistent_trend_needs_two_history_points():
    rule = PersistentTrendRule(SystolicBloodPressure())
    assert rule.evaluate(150, [142]) is None  # only one prior reading


# ---------------------------------------------------------------------------
# RecentChangeRule - compares the current reading to the single most
# recent past reading. Silent when the change is within tolerance AND no
# classification boundary was crossed; otherwise reports a CHANGED finding.
# ---------------------------------------------------------------------------

def test_recent_change_silent_within_tolerance():
    rule = RecentChangeRule(HeartRate())  # tolerance = 5
    # delta of 3 bpm, both readings NORMAL -> ignored as fluctuation
    assert rule.evaluate(88, [85]) is None


def test_recent_change_fires_when_delta_exceeds_tolerance():
    rule = RecentChangeRule(HeartRate())  # tolerance = 5
    finding = rule.evaluate(95, [85])  # delta 10 > 5
    assert finding is not None
    assert finding.status == "CHANGED"


def test_recent_change_fires_on_classification_change_even_if_small():
    # Small numeric delta but crosses the ELEVATED/SEVERE boundary (130).
    rule = RecentChangeRule(HeartRate())  # tolerance = 5
    finding = rule.evaluate(131, [129])  # delta 2 (within tol) but class changed
    assert finding is not None
    assert finding.status == "CHANGED"
    d = finding.to_dict()
    assert d["classification_changed"] is True


def test_recent_change_silent_without_history():
    rule = RecentChangeRule(HeartRate())
    assert rule.evaluate(120, []) is None


def test_recent_change_improvement_is_labelled():
    rule = RecentChangeRule(HeartRate())
    # a decrease for a 'higher is worse' metric is an improvement
    finding = rule.evaluate(85, [120])  # delta -35
    assert finding is not None
    assert finding.to_dict()["assessment"] == "improved"


# ---------------------------------------------------------------------------
# LogicManager.process() - scoring and routing of a whole AI record.
# risk_score = (#urgent * 2) + (#flagged). Decision follows: any urgent
# -> URGENT; else any flagged -> FLAGGED; else ACCEPTED. Special cases:
# not-a-medical-report and no-extractable-metrics.
# ---------------------------------------------------------------------------

def _engine():
    return LogicManager.default()


def test_process_routes_not_medical_report():
    result = _engine().process({"is_medical_report": False}, [])
    assert result["decision"] == "NOT_MEDICAL_REPORT"
    assert result["requires_doctor_review"] is False


def test_process_rejects_when_no_metrics_extracted():
    ai = {"heart_rate": None,
          "blood_pressure": {"systolic": None, "diastolic": None},
          "blood_glucose": None}
    result = _engine().process(ai, [])
    assert result["decision"] == "REJECTED"


def test_process_routes_urgent_and_scores():
    ai = {"heart_rate": 138,
          "blood_pressure": {"systolic": 188, "diastolic": 122},
          "blood_glucose": 15.4,
          "report_date": "2026-09-22"}
    result = _engine().process(ai, [])
    assert result["decision"] == "URGENT"
    assert len(result["urgent_findings"]) == 4
    # four urgent findings, no flagged -> score = 4*2 + 0
    assert result["risk_score"] == 8
    assert result["requires_doctor_review"] is True


def test_process_accepts_normal_reading():
    ai = {"heart_rate": 72,
          "blood_pressure": {"systolic": 118, "diastolic": 76},
          "blood_glucose": 5.2,
          "report_date": "2026-09-22"}
    result = _engine().process(ai, [])
    assert result["decision"] == "ACCEPTED"
    assert result["risk_score"] == 0
    assert result["requires_doctor_review"] is False


def test_process_preserves_extracted_date():
    ai = {"heart_rate": 72, "report_date": "2026-09-22"}
    result = _engine().process(ai, [])
    assert result["ai_extracted_date"] == "2026-09-22"


# ---------------------------------------------------------------------------
# MedicalProfileValidator - validates standing reference data. Returns
# (cleaned, errors) and never mutates its input.
# ---------------------------------------------------------------------------

def test_profile_rejects_unknown_blood_group():
    cleaned, errors = MedicalProfileValidator().validate({"blood_group": "XX"})
    assert any("blood group" in e for e in errors)


def test_profile_accepts_known_blood_group():
    cleaned, errors = MedicalProfileValidator().validate({"blood_group": "O+"})
    assert cleaned["blood_group"] == "O+"
    assert errors == []


def test_profile_medication_requires_name():
    _, errors = MedicalProfileValidator().validate(
        {"blood_group": "", "medications": [{"name": "", "dosage_amount": "5"}]})
    assert any("name is required" in e for e in errors)


def test_profile_does_not_mutate_input():
    original = {"blood_group": "O+", "medications": []}
    MedicalProfileValidator().validate(original)
    assert original == {"blood_group": "O+", "medications": []}


# ---------------------------------------------------------------------------
# ManualVitalsValidator - plausibility checks on a self-logged entry.
# ---------------------------------------------------------------------------

def test_manual_vitals_rejects_future_date():
    _, errors = ManualVitalsValidator().validate(
        {"date": "2099-01-01", "metrics": {"heart_rate": 80}},
        today="2026-01-01")
    assert any("future" in e for e in errors)


def test_manual_vitals_flags_implausible_value():
    _, errors = ManualVitalsValidator().validate(
        {"date": "2026-01-01", "metrics": {"heart_rate": 999}},
        today="2026-01-01")
    assert any("heart rate" in e.lower() for e in errors)


def test_manual_vitals_requires_bp_as_pair():
    _, errors = ManualVitalsValidator().validate(
        {"date": "2026-01-01",
         "metrics": {"blood_pressure_systolic": 120}},
        today="2026-01-01")
    assert any("both systolic and diastolic" in e for e in errors)


def test_manual_vitals_requires_at_least_one_measurement():
    _, errors = ManualVitalsValidator().validate(
        {"date": "2026-01-01", "metrics": {}}, today="2026-01-01")
    assert any("at least one measurement" in e for e in errors)


def test_manual_vitals_accepts_valid_entry():
    cleaned, errors = ManualVitalsValidator().validate(
        {"date": "2026-01-01", "metrics": {"heart_rate": 72}},
        today="2026-01-01")
    assert errors == []
    assert cleaned["metrics"]["heart_rate"] == 72
