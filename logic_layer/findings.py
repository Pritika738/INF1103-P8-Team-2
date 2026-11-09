"""
findings.py

The Finding value object, extracted from logic_manager.py so it lives
in its own module. One rule's conclusion about one metric;
JSON-serialisable via to_dict() so stored records are unchanged.
"""

from __future__ import annotations

from typing import Any, Dict


class Finding:
    """
    One rule's conclusion about one metric. Replaces the loose
    {"metric", "status", "reason", ...} dicts the old functions built.
    JSON-serialisable via to_dict() so stored records match the
    procedural pipeline's output shape exactly.
    """

    def __init__(self, metric: str, status: str, **extra: Any):
        self._metric = metric
        self._status = status
        self._extra = extra

    @property
    def status(self) -> str:
        return self._status

    @property
    def metric(self) -> str:
        return self._metric

    def to_dict(self) -> Dict[str, Any]:
        return {"metric": self._metric, "status": self._status, **self._extra}
