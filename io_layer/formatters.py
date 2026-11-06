"""
io_layer/formatters.py

Turns records into display text. Formatters only build strings; the
IOManager decides when and where to show them.

RecordFormatter is the abstract contract. IOManager calls format() on
whichever formatter it holds, so a new layout needs only a new subclass
(Open/Closed) and any subclass can replace another (Liskov).
"""

from abc import ABC, abstractmethod
from typing import Sequence

from config import SUPPORTED_METRICS


def _metrics_of(record: dict) -> dict:
    """Metric values from a flat CLI record or a nested AI-pipeline record."""
    nested = record.get("metrics")
    return nested if isinstance(nested, dict) else record


class RecordFormatter(ABC):
    """Abstract base: build the text for a list of health records."""

    def format(self, records: Sequence[dict]) -> str:
        if not records:
            return "No health records found."
        return self._format_records(records)

    @abstractmethod
    def _format_records(self, records: Sequence[dict]) -> str:
        """Format a non-empty list of records."""


class TextRecordFormatter(RecordFormatter):
    """Multi-line, one metric per line (the Phase 1 layout)."""

    def _format_records(self, records):
        lines = [f"\n-- Health History ({len(records)} record(s)) --"]
        for index, record in enumerate(records, start=1):
            lines.append(f"\nRecord {index}:")
            metrics = _metrics_of(record)
            for metric in SUPPORTED_METRICS:
                if metrics.get(metric) is not None:
                    lines.append(f"  {metric}: {metrics[metric]}")
            if record.get("date"):
                lines.append(f"  date: {record['date']}")
        return "\n".join(lines)


class CompactRecordFormatter(RecordFormatter):
    """One line per record - easier to scan long histories."""

    def _format_records(self, records):
        lines = []
        for record in records:
            metrics = _metrics_of(record)
            parts = [f"{m}={metrics[m]}" for m in SUPPORTED_METRICS if metrics.get(m) is not None]
            lines.append(f"{record.get('date', '????-??-??')}: " + (", ".join(parts) or "no metrics"))
        return "\n".join(lines)
