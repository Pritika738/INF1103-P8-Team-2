import math
from datetime import datetime
from typing import Any, Dict, Optional


class ExtractedFile:
    """A source file plus the validated AI extraction result for it."""

    def __init__(self, source: str,
                 mime_type: str,
                 is_medical_report: bool = False,
                 classification_reason: str = "",
                 heart_rate: Optional[float] = None,
                 blood_pressure_systolic: Optional[float] = None,
                 blood_pressure_diastolic: Optional[float] = None,
                 blood_glucose: Optional[float] = None,
                 report_date: Optional[str] = None):
        self.__source = self._require_text(source, "source")
        self.__mime_type = self._require_text(mime_type, "mime_type")
        self.__is_medical_report = is_medical_report
        self.__classification_reason = classification_reason
        self.__heart_rate = self._validate_metric(heart_rate, "heart_rate")
        self.__bp_systolic = self._validate_metric(
            blood_pressure_systolic, "blood_pressure_systolic")
        self.__bp_diastolic = self._validate_metric(
            blood_pressure_diastolic, "blood_pressure_diastolic")
        self.__blood_glucose = self._validate_metric(blood_glucose, "blood_glucose")
        self.__report_date = self._validate_date(report_date)  # "YYYY-MM-DD" or None

    @staticmethod
    def _require_text(value: str, field_name: str) -> str:
        """Return value without surrounding spaces, or raise if it is blank."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _validate_date(value: Optional[str]) -> Optional[str]:
        """Return value if it is a real 'YYYY-MM-DD' date, None if no date given."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("report_date must be a 'YYYY-MM-DD' string or None.")
        value = value.strip()
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"report_date {value!r} is not a real date.") from None
        if parsed.strftime("%Y-%m-%d") != value:
            raise ValueError(f"report_date {value!r} must use the format YYYY-MM-DD.")
        return value

    @staticmethod
    def _validate_metric(value: Optional[float], field_name: str) -> Optional[float]:
        """Return value if it is a real, non-negative number; None if not measured."""
        if value is None:
            return None
        # bool is a subclass of int in Python, but True/False is not a measurement.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field_name} must be a number or None.")
        if not math.isfinite(value):
            raise ValueError(f"{field_name} must be a finite number.")
        if value < 0:
            raise ValueError(f"{field_name} must not be negative.")
        return value
    
    # ------------------------------------------------------------------
    # Construction from AI output
    # ------------------------------------------------------------------

    @classmethod
    def from_ai_result(cls, source: str, mime_type: str, ai_result: dict) -> "ExtractedFile":
        """Build from the dict returned by AIManager.extract_report().

        The dict has already been schema-validated by ExtractionTask, so
        the keys are guaranteed to exist. blood_pressure may be None.
        """
        blood_pressure = ai_result.get("blood_pressure") or {}
        return cls(
            source=source,
            mime_type=mime_type,
            is_medical_report=ai_result["is_medical_report"],
            classification_reason=ai_result["classification_reason"],
            heart_rate=ai_result["heart_rate"],
            blood_pressure_systolic=blood_pressure.get("systolic"),
            blood_pressure_diastolic=blood_pressure.get("diastolic"),
            blood_glucose=ai_result["blood_glucose"],
            report_date=ai_result["report_date"],
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractedFile":
        """Rebuild an ExtractedFile from the dict produced by to_dict()."""
        if not isinstance(data, dict):
            raise TypeError("data must be a dict.")
        metrics = data.get("metrics") or {}
        return cls(
            source=data.get("source"),
            mime_type=data.get("mime_type"),
            is_medical_report=data.get("is_medical_report", False),
            classification_reason=data.get("classification_reason", ""),
            heart_rate=metrics.get("heart_rate"),
            blood_pressure_systolic=metrics.get("blood_pressure_systolic"),
            blood_pressure_diastolic=metrics.get("blood_pressure_diastolic"),
            blood_glucose=metrics.get("blood_glucose"),
            report_date=data.get("date"),
        )
    # ------------------------------------------------------------------
    # Read-only access
    # ------------------------------------------------------------------

    @property
    def source(self) -> str:
        return self.__source

    @property
    def mime_type(self) -> str:
        return self.__mime_type

    @property
    def is_medical_report(self) -> bool:
        return self.__is_medical_report

    @property
    def classification_reason(self) -> str:
        return self.__classification_reason

    @property
    def report_date(self) -> Optional[str]:
        return self.__report_date

    @property
    def metrics(self) -> Dict[str, Optional[float]]:
        """Flat metric values, using the keys in config.SUPPORTED_METRICS."""
        return {
            "heart_rate": self.__heart_rate,
            "blood_pressure_systolic": self.__bp_systolic,
            "blood_pressure_diastolic": self.__bp_diastolic,
            "blood_glucose": self.__blood_glucose,
        }

    # ------------------------------------------------------------------
    # Behaviour that belongs to the data itself
    # ------------------------------------------------------------------

    def has_measurements(self) -> bool:
        """True if at least one metric was extracted."""
        return any(value is not None for value in self.metrics.values())

    def to_dict(self) -> Dict[str, Any]:
        """Plain dict for saving (Data Manager) or passing to Logic Manager."""
        return {
            "source": self.__source,
            "mime_type": self.__mime_type,
            "is_medical_report": self.__is_medical_report,
            "classification_reason": self.__classification_reason,
            "date": self.__report_date,
            "metrics": self.metrics,
        }

    def __eq__(self, other: object) -> bool:
        """Two ExtractedFile objects are equal if they come from the same source file."""
        if not isinstance(other, ExtractedFile):
            return NotImplemented
        return self.__source == other.source

    def __hash__(self) -> int:
        """Hash by source, so equal files land in the same set/dict slot."""
        return hash(self.__source)
    
    def __repr__(self) -> str:
        return (f"ExtractedFile(source={self.__source!r}, date={self.__report_date!r}, "
                f"medical={self.__is_medical_report})")
