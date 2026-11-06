"""
data_layer/medical_profile_store.py

A user's standing medical profile: current medications & dosages, blood
group, allergies, emergency contacts and hereditary illness flags.
Unlike health_records.json (an append-only list of dated readings), a
profile is ONE current record per user, stored as a JSON OBJECT keyed
by username; each save REPLACES that user's profile rather than
appending.

Persistence only - all validation belongs in logic_manager, and all
user messaging in io_manager.
"""

from datetime import date as _date
from typing import Any, Dict

from config import MEDICAL_PROFILES_FILE

from .json_store import JsonObjectStore


def default_medical_profile() -> Dict[str, Any]:
    """Return a fresh, empty medical-profile dict with every expected
    section present, so callers can rely on the shape without defensive
    key-checking. A new dict is built on every call, so it is never
    shared or mutated across callers.

    Shape:
        {
            "medications":   [ {"name", "dosage_amount", "dosage_unit",
                                 "frequency"}, ... ],
            "blood_group":   str,   # e.g. "O+", "" if unknown
            "allergies":     [ {"allergen", "reaction", "severity"}, ... ],
            "emergency_contacts": [ {"name", "relationship", "phone",
                                     "email"}, ... ],
            "hereditary_illness": {
                "diabetes":       bool,
                "blood_pressure": bool,
                "heart_disease":  bool,
                "asthma":         bool,
                "other":          str,   # free text, "" if none
                "notes":          str,   # e.g. which relative, "" if none
            },
        }
    """
    return {
        "medications": [],
        "blood_group": "",
        "allergies": [],
        "emergency_contacts": [],
        "hereditary_illness": {
            "diabetes": False,
            "blood_pressure": False,
            "heart_disease": False,
            "asthma": False,
            "other": "",
            "notes": "",
        },
    }


class MedicalProfileStore:
    """Loads and saves one medical profile per user."""

    def __init__(self, profiles_file: str = MEDICAL_PROFILES_FILE):
        self.__store = JsonObjectStore(profiles_file)  # composition

    def load(self, username: str) -> Dict[str, Any]:
        """Load one user's medical profile.

        Returns the stored profile, or a fresh default_medical_profile() if
        the user has none yet (so callers always get a complete, well-shaped
        dict and never a KeyError). Any sections missing from a stored
        profile (e.g. one saved before a new section existed) are filled in
        from the default.
        """
        stored = self.__store.load().get(username)

        profile = default_medical_profile()
        if isinstance(stored, dict):
            # Merge known top-level sections; nested hereditary flags are
            # merged key-by-key so a newly added flag defaults correctly
            # instead of disappearing from an older stored profile.
            for key, default_value in profile.items():
                if key not in stored:
                    continue
                if key == "hereditary_illness" and isinstance(stored[key], dict):
                    merged = dict(default_value)
                    merged.update(stored[key])
                    profile[key] = merged
                else:
                    profile[key] = stored[key]
            if "last_updated" in stored:
                profile["last_updated"] = stored["last_updated"]

        return profile

    def save(self, username: str, profile: Dict[str, Any]) -> bool:
        """Save (replace) one user's medical profile, preserving every OTHER
        user's profile untouched. Stamps today's date as "last_updated" onto
        a copy of `profile`; the caller's original dict is never mutated.

        Returns True on success, False if the write failed.
        """
        profiles = self.__store.load()

        profile_to_save = dict(profile)
        profile_to_save["last_updated"] = _date.today().isoformat()

        profiles[username] = profile_to_save
        return self.__store.save(profiles)
