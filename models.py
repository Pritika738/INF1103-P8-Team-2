"""
models.py

Shared domain classes used by all four managers. They hold data and
small pieces of behaviour that belong to the data itself; they never do
I/O, call the AI, or persist anything.

Encapsulation convention (Python has no real access modifiers):
- ``name``      public, part of the class contract
- ``_name``     protected, for the class and its subclasses only
- ``__name``    private, name-mangled, for this class only
Where a value must not be changed from outside, the attribute is private
and exposed through a read-only ``@property``.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MetricSpec:
    """
    Immutable description of one tracked health metric and the business
    thresholds that apply to it. Every metric used here is "higher is
    worse", so a decrease is always the improving direction.

    Attributes:
        key: flat storage key, e.g. "blood_glucose".
        label: human-readable name shown to users.
        unit: display unit, e.g. "mmol/L".
        urgent_threshold: a single reading at/above this is URGENT.
        trend_threshold: a reading above this, with a persistent rise, is FLAGGED.
        change_tolerance: day-to-day delta inside this is normal noise.
    """

    key: str
    label: str
    unit: str
    urgent_threshold: float
    trend_threshold: float
    change_tolerance: float

    def classify(self, value: Optional[float]) -> Optional[str]:
        """Return "SEVERE", "ELEVATED", "NORMAL", or None when value is None."""
        if value is None:
            return None
        if value >= self.urgent_threshold:
            return "SEVERE"
        if value > self.trend_threshold:
            return "ELEVATED"
        return "NORMAL"


# Business-rule cutoffs used only to decide what is worth discussing with
# a doctor. Commonly cited reference points for a student project; they
# are not a medical guideline and are never used to name a condition.
DEFAULT_METRIC_SPECS: List[MetricSpec] = [
    MetricSpec("blood_pressure_systolic", "Systolic Blood Pressure", "mmHg", 180, 130, 5),
    MetricSpec("blood_pressure_diastolic", "Diastolic Blood Pressure", "mmHg", 120, 80, 4),
    MetricSpec("blood_glucose", "Blood Glucose", "mmol/L", 13.9, 7.0, 0.5),
    MetricSpec("heart_rate", "Heart Rate", "bpm", 130, 100, 5),
]


# ---------------------------------------------------------------------------
# Findings and processed records
# ---------------------------------------------------------------------------

class Finding:
    """One rule outcome for one metric (status "URGENT" or "FLAGGED")."""

    def __init__(self, metric: str, status: str, reason: str):
        self.__metric = metric
        self.__status = status
        self.__reason = reason

    @property
    def metric(self) -> str:
        return self.__metric

    @property
    def status(self) -> str:
        return self.__status

    @property
    def reason(self) -> str:
        return self.__reason

    def to_dict(self) -> Dict[str, str]:
        return {"metric": self.__metric, "status": self.__status, "reason": self.__reason}


class ProcessedRecord:
    """
    The finalized outcome of running one AI-enriched reading through the
    Logic Manager. State is private and exposed read-only; the only way
    to get a storable/JSON shape is ``to_dict()``.
    """

    def __init__(
        self,
        metrics: Dict[str, Optional[float]],
        ai_extracted_date: Optional[str],
        decision: str,
        recommended_action: str,
        summary: str,
        urgent_findings: Optional[List[Finding]] = None,
        flagged_trends: Optional[List[Finding]] = None,
        recent_changes: Optional[List[Dict[str, Any]]] = None,
    ):
        self.__metrics = dict(metrics)
        self.__ai_extracted_date = ai_extracted_date
        self.__decision = decision
        self.__recommended_action = recommended_action
        self.__summary = summary
        self.__urgent = list(urgent_findings or [])
        self.__flagged = list(flagged_trends or [])
        self.__recent_changes = list(recent_changes or [])

    @property
    def decision(self) -> str:
        return self.__decision

    @property
    def metrics(self) -> Dict[str, Optional[float]]:
        return dict(self.__metrics)

    @property
    def urgent_findings(self) -> List[Finding]:
        return list(self.__urgent)

    @property
    def flagged_trends(self) -> List[Finding]:
        return list(self.__flagged)

    @property
    def risk_score(self) -> int:
        """Transparent rule-based score: urgent counts double a flagged trend."""
        return len(self.__urgent) * 2 + len(self.__flagged)

    @property
    def requires_doctor_review(self) -> bool:
        return bool(self.__urgent or self.__flagged)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics": dict(self.__metrics),
            "ai_extracted_date": self.__ai_extracted_date,
            "urgent_findings": [f.to_dict() for f in self.__urgent],
            "flagged_trends": [f.to_dict() for f in self.__flagged],
            "recent_changes": list(self.__recent_changes),
            "risk_score": self.risk_score,
            "decision": self.__decision,
            "recommended_action": self.__recommended_action,
            "requires_doctor_review": self.requires_doctor_review,
            "summary": self.__summary,
        }


# ---------------------------------------------------------------------------
# Uploaded report file
# ---------------------------------------------------------------------------

class UploadedReport:
    """
    A medical report file (PDF/image) handed to the system. It is passed
    between the IO, AI and Data managers so each works on the same object.
    """

    SUPPORTED_MIME_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg"})

    def __init__(self, data: bytes, mime_type: str, filename: str = "report"):
        self.__data = bytes(data)
        self.__mime_type = mime_type
        self.__filename = filename

    @property
    def data(self) -> bytes:
        return self.__data

    @property
    def mime_type(self) -> str:
        return self.__mime_type

    @property
    def filename(self) -> str:
        return self.__filename

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.__data).hexdigest()

    def is_supported(self) -> bool:
        return self.__mime_type in self.SUPPORTED_MIME_TYPES


# ---------------------------------------------------------------------------
# Record query (used by the repository and the summary report feature)
# ---------------------------------------------------------------------------

class RecordQuery:
    """
    Declarative filter over stored records. Every criterion is optional;
    a record must satisfy all criteria that are set. Dates are
    "YYYY-MM-DD" strings, which compare correctly as text.
    """

    def __init__(
        self,
        username: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        decision: Optional[str] = None,
        min_risk_score: Optional[int] = None,
    ):
        self.username = username
        self.date_from = date_from
        self.date_to = date_to
        self.decision = decision.upper() if decision else None
        self.min_risk_score = min_risk_score

    def matches(self, record: Dict[str, Any]) -> bool:
        if self.username is not None and record.get("username") != self.username:
            return False
        record_date = record.get("date") or ""
        if self.date_from is not None and record_date < self.date_from:
            return False
        if self.date_to is not None and record_date > self.date_to:
            return False
        if self.decision is not None and record.get("decision") != self.decision:
            return False
        if self.min_risk_score is not None and (record.get("risk_score") or 0) < self.min_risk_score:
            return False
        return True


def is_valid_iso_date(value: Any) -> bool:
    """True if value is a real calendar date written as YYYY-MM-DD."""
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True
