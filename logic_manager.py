"""
logic_managerClass.py

Object-oriented refactor of logic_manager.py (Phase 2).

Same responsibility as before - the "Domain Brain": take a fresh
AI-extracted reading plus the user's stored history, apply clinical
threshold rules in plain Python, and decide an outcome for the record.
It never diagnoses, prescribes, or replaces professional medical
advice - it only decides what is worth flagging for discussion with a
doctor.

What changed from the procedural version
-----------------------------------------
- The business rules that used to be inlined inside
  evaluate_health_metrics()/analyze_recent_changes() are now first-class
  `Rule` objects (UrgentThresholdRule, PersistentTrendRule,
  RecentChangeRule). The engine runs them polymorphically - it never
  branches on a rule's concrete type.
- The per-metric thresholds/labels/units that used to be module-level
  dicts are now encapsulated behind a `Measurement` hierarchy, one
  subclass per tracked metric.
- process_ai_record() is now LogicManager.process(). The single entry
  point is unchanged in contract: raw AI dict (or None) + history in,
  one finalised, JSON-serialisable report dict out.

OOP concepts demonstrated here
------------------------------
- Abstract classes / interfaces : Measurement, Rule (both ABCs).
- Inheritance                   : HeartRate/BloodPressure*/BloodGlucose
                                  subclass Measurement; the three Rule
                                  subclasses specialise Rule.
- Polymorphism                  : LogicManager.evaluate() calls
                                  rule.evaluate(...) without knowing the
                                  concrete rule; Measurement.classify().
- Encapsulation                 : thresholds held as private attrs set
                                  at construction, not mutable globals.
- Aggregation                   : LogicManager holds a list of Rule
                                  objects that exist independently of it.
- Composition                   : a processed report owns its Finding
                                  objects (they have no life outside it).
- Association                   : each Rule refers to a MetricSpec it
                                  evaluates, without owning its lifecycle.

SOLID evidence
--------------
- SRP : each Rule has exactly one reason to change (its own threshold/
        pattern); LogicManager only orchestrates, scores, and decides.
- OCP : adding a new clinical rule means writing a new Rule subclass and
        adding it to the list passed to LogicManager - zero edits to the
        engine. See LogicManager.default() for the current rule set.
- LSP : any Rule is substitutable wherever the engine expects one; any
        Measurement is substitutable wherever a reading is classified.

Input/output contract (unchanged from logic_manager.py)
-------------------------------------------------------
Fresh AI output (`ai_extracted`) is whatever
ai_manager.call_ai_with_retry() returns: either None, or a dict shaped
like {"heart_rate": num/None,
      "blood_pressure": {"systolic": num/None, "diastolic": num/None}/None,
      "blood_glucose": num/None,
      "report_date": "YYYY-MM-DD"/None,
      "is_medical_report": bool (optional),
      "classification_reason": str (optional)}.

Historical records are whatever data_manager.load_health_records()
returns: a list of dicts using the flat metric key names, assumed
sorted oldest to newest (metric keys may sit at the top level for
CLI-entered records, or under "metrics" for AI-pipeline records).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# ===========================================================================
# Enumerations - small, self-describing value types
# ===========================================================================

class Tier(Enum):
    """
    Severity tier for a single reading, independent of trend history.
    Mirrors the old _metric_classification() return values ("SEVERE",
    "ELEVATED", "NORMAL") but as a proper type instead of bare strings.
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

