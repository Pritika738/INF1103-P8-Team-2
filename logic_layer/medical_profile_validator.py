"""
medical_profile_validator.py

Standing reference-data validation, extracted from logic_manager.py so
that each class lives in its own module. logic_manager.py imports the
MedicalProfileValidator class from here; its public behaviour is
unchanged.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


class MedicalProfileValidator:
    """
    Validate and normalise a raw medical-profile dict (medications,
    blood group, allergies, emergency contacts, hereditary illness).

    A separate class from the vital-sign engine because this is
    user-entered reference data, not a measurement - it gets no
    thresholds, trend analysis or scoring, only validation. Mirrors the
    old validate_medical_profile() exactly, including its (cleaned,
    errors) return and its never-mutate-the-input guarantee.
    """

    VALID_BLOOD_GROUPS = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    VALID_ALLERGY_SEVERITIES = ["mild", "moderate", "severe"]
    VALID_DOSAGE_UNITS = [
        "", "mg", "mcg", "g", "ml", "L", "IU", "%",
        "units", "tablet(s)", "drop(s)", "puff(s)", "patch(es)",
    ]
    # Mandatory leading "+" and country code, then digits/spaces/dashes only.
    _PHONE_RE = re.compile(r"^\+[1-9][0-9 \-]{5,18}$")

    def validate(self, profile: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        errors: List[str] = []
        cleaned: Dict[str, Any] = {
            "medications": [],
            "blood_group": "",
            "allergies": [],
            "emergency_contacts": [],
            "hereditary_illness": {
                "diabetes": False, "blood_pressure": False,
                "heart_disease": False, "asthma": False,
                "other": "", "notes": "",
            },
        }

        # --- Blood group: must be one of the known groups (blank = unknown) ---
        blood_group = str(profile.get("blood_group", "")).strip().upper()
        if blood_group in self.VALID_BLOOD_GROUPS:
            cleaned["blood_group"] = blood_group
        else:
            errors.append(f"'{blood_group}' is not a recognised blood group.")



        # --- Medications: name required if row isn't fully blank; dosage, ---
        # --- if given, must be a non-negative number. ---
        for index, med in enumerate(profile.get("medications", []), start=1):
            name = str(med.get("name", "")).strip()
            amount_raw = str(med.get("dosage_amount", "")).strip()
            if not name and not amount_raw:
                continue  # fully blank row - skip silently
            if not name:
                errors.append(f"Medication {index}: a name is required.")
                continue
            amount = None
            if amount_raw:
                try:
                    amount = float(amount_raw)
                except ValueError:
                    errors.append(f"Medication '{name}': dosage must be a number.")
                    continue
                if amount < 0:
                    errors.append(f"Medication '{name}': dosage cannot be negative.")
                    continue
            unit = str(med.get("dosage_unit", "")).strip()
            if unit and unit not in self.VALID_DOSAGE_UNITS:
                errors.append(f"Medication '{name}': '{unit}' is not a recognised dosage unit.")
                unit = ""
            cleaned["medications"].append({
                "name": name,
                "dosage_amount": amount,
                "dosage_unit": unit,
                "frequency": str(med.get("frequency", "")).strip(),
            })

            # --- Allergies: allergen required; severity, if given, must be known ---
        for index, allergy in enumerate(profile.get("allergies", []), start=1):
            allergen = str(allergy.get("allergen", "")).strip()
            if not allergen:
                continue
            severity = str(allergy.get("severity", "")).strip().lower()
            if severity and severity not in self.VALID_ALLERGY_SEVERITIES:
                errors.append(
                    f"Allergy '{allergen}': severity must be mild, moderate or severe."
                )
                severity = ""
            cleaned["allergies"].append({
                "allergen": allergen,
                "reaction": str(allergy.get("reaction", "")).strip(),
                "severity": severity,
            })

        # --- Emergency contacts: name and a plausible phone number required ---
        for index, contact in enumerate(profile.get("emergency_contacts", []), start=1):
            name = str(contact.get("name", "")).strip()
            phone = str(contact.get("phone", "")).strip()
            if not name and not phone:
                continue
            if not name:
                errors.append(f"Emergency contact {index}: a name is required.")
                continue
            if not phone:
                errors.append(f"Emergency contact '{name}': a phone number is required.")
                continue
            if not self._PHONE_RE.fullmatch(phone):
                errors.append(
                    f"Emergency contact '{name}': phone number must include the "
                    "country code, e.g. +65 1234 5678."
                )
                continue
            cleaned["emergency_contacts"].append({
                "name": name,
                "relationship": str(contact.get("relationship", "")).strip(),
                "phone": phone,
                "email": str(contact.get("email", "")).strip(),
            })

        # --- Hereditary illness: force the four flags to booleans, strip text ---
        hereditary = profile.get("hereditary_illness", {}) or {}
        for flag in ("diabetes", "blood_pressure", "heart_disease", "asthma"):
            cleaned["hereditary_illness"][flag] = bool(hereditary.get(flag, False))
        cleaned["hereditary_illness"]["other"] = str(hereditary.get("other", "")).strip()
        cleaned["hereditary_illness"]["notes"] = str(hereditary.get("notes", "")).strip()

        return cleaned, errors
