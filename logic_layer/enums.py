"""
enums.py

Small, self-describing value types (Tier, Decision), extracted from
logic_manager.py so related enums live together in one cohesive
module. logic_manager.py imports them from here; their values are
unchanged, so serialised records look identical.
"""

from __future__ import annotations

from enum import Enum


class Tier(Enum):
    """
    Severity tier for a single reading, independent of trend history.
    Replaces the old _metric_classification() bare strings ("SEVERE",
    "ELEVATED", "NORMAL") with a proper type.
    """
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    SEVERE = "SEVERE"


class Decision(Enum):
    """
    Final routing outcome for a processed record. Same five string
    values the procedural version produced, so stored/serialised records
    look identical to the old pipeline's output.
    """
    NOT_MEDICAL_REPORT = "NOT_MEDICAL_REPORT"
    REJECTED = "REJECTED"
    URGENT = "URGENT"
    FLAGGED = "FLAGGED"
    ACCEPTED = "ACCEPTED"
