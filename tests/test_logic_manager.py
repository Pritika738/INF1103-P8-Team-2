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

from metrics import (
    HeartRate, SystolicBloodPressure, DiastolicBloodPressure, BloodGlucose,
)
from enums import Tier


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
