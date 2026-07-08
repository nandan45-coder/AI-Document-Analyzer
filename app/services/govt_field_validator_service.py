import logging
import re
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger("govt_document_intelligence")


# Maharashtra's 36 revenue districts, used for lightweight validation of the
# "District" field. Kept here (rather than a new data file) since it is only
# consumed by this validator.
MAHARASHTRA_DISTRICTS = {
    "ahmednagar", "akola", "amravati", "aurangabad", "chhatrapati sambhajinagar",
    "beed", "bhandara", "buldhana", "chandrapur", "dhule", "gadchiroli",
    "gondia", "hingoli", "jalgaon", "jalna", "kolhapur", "latur", "mumbai city",
    "mumbai suburban", "nagpur", "nanded", "nandurbar", "nashik", "osmanabad",
    "dharashiv", "palghar", "parbhani", "pune", "raigad", "ratnagiri", "sangli",
    "satara", "sindhudurg", "solapur", "thane", "wardha", "washim", "yavatmal",
}

# Common BROAD category/classification values seen on Maharashtra government
# certificates. Note this deliberately does NOT try to enumerate every
# individual caste/sub-caste name (e.g. "Gabit", "Mahar", "Koli") - Maharashtra
# has hundreds of these under SC/ST/OBC/VJNT/NT/SBC umbrellas, and hardcoding
# them would be both incomplete and a maintenance burden. Caste-specific names
# that don't match this broad list are handled separately below as
# "requires manual verification" rather than flatly "invalid", since they are
# very often correct, just not enumerable.
VALID_CATEGORIES = {
    "open", "general", "obc", "sc", "st", "sbc", "vjnt", "vj", "nt-1", "nt-2",
    "nt-3", "ews", "sebc", "scheduled caste", "scheduled tribe",
    "other backward class", "special backward class", "vimukta jati",
    "de-notified tribes", "de-notified tribe", "nomadic tribe",
    "nomadic tribes",
}

# Certificates frequently state a validity OUTCOME rather than an expiry
# date (e.g. a Caste Validity Certificate certifying a claim "is found to be
# VALID", as opposed to a license with an actual expiry date). Previously
# any non-date value in a "Validity" field was rejected as an invalid date,
# which is a false positive for this common, legitimate case.
VALIDITY_ACCEPTABLE_KEYWORDS = {
    "valid", "invalid", "lifetime", "life time", "permanent",
    "n/a", "na", "not applicable",
}

# Fields that should be treated as dates even though their key doesn't
# literally contain the word "date".
DATE_LIKE_FIELDS = {
    "dob", "date of birth", "issue date", "validity", "registration date",
    "marriage date", "date of death",
}


class GovtFieldValidatorService:

    # ============================================
    # Validate Extracted Fields
    # ============================================

    def validate_fields(
        self,
        extracted_fields: Dict[str, Any],
        expected_fields: List[str],
    ) -> Dict[str, Any]:

        report = {
            "valid": True,
            "completion_percentage": 0,
            "missing_fields": [],
            "empty_fields": [],
            "invalid_fields": [],
            "validated_fields": {},
            "field_confidence": {},
        }

        completed = 0
        total = len(expected_fields) or 1

        for field in expected_fields:

            value = extracted_fields.get(field)

            if value is None:
                report["missing_fields"].append(field)
                self._set_field_confidence(report, field, 0.0)
                continue

            value = str(value).strip()

            if value == "":
                report["empty_fields"].append(field)
                self._set_field_confidence(report, field, 0.0)
                continue

            report["validated_fields"][field] = value
            self._set_field_confidence(report, field, 0.85)
            completed += 1

        report["completion_percentage"] = round((completed / total) * 100, 2)

        self.validate_dates(report)
        self.validate_certificate_number(report)
        self.validate_district(report)
        self.validate_taluka(report)
        self.validate_pin(report)
        self.validate_category(report)

        if report["missing_fields"] or report["invalid_fields"]:
            report["valid"] = False

        return report

    # ============================================
    # Confidence helper
    # ============================================

    def _set_field_confidence(
        self, report: Dict[str, Any], field: str, confidence: float
    ) -> None:
        report["field_confidence"][field] = round(confidence, 2)

    def _mark_invalid(
        self, report: Dict[str, Any], field: str, reason: str, confidence: float = 0.1
    ) -> None:
        report["invalid_fields"].append({"field": field, "reason": reason})
        self._set_field_confidence(report, field, confidence)

    # ============================================
    # Date Validation (broadened key matching)
    # ============================================

    def validate_dates(self, report: Dict[str, Any]) -> None:

        for key, value in list(report["validated_fields"].items()):

            key_lower = key.lower()

            is_date_field = (
                "date" in key_lower or key_lower in DATE_LIKE_FIELDS
            )

            if not is_date_field:
                continue

            # "Validity" is a special case - it can legitimately hold an
            # outcome word ("VALID", "LIFETIME", "PERMANENT") instead of an
            # actual date. Only apply that leniency to fields literally
            # named "validity" - other date fields (Issue Date, DOB, etc.)
            # should never contain free-text words, so they still go
            # through strict date parsing below.
            if key_lower == "validity" and value.strip().lower() in VALIDITY_ACCEPTABLE_KEYWORDS:
                self._set_field_confidence(report, key, 0.8)
                continue

            valid = False

            formats = ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"]

            for fmt in formats:
                try:
                    dt = datetime.strptime(value, fmt)

                    if dt > datetime.now():
                        self._mark_invalid(report, key, "Future Date", confidence=0.2)

                    valid = True
                    break
                except ValueError:
                    continue

            if not valid:
                self._mark_invalid(report, key, "Invalid Date Format", confidence=0.15)

    # ============================================
    # Certificate Number Validation (stricter)
    # ============================================

    def validate_certificate_number(self, report: Dict[str, Any]) -> None:

        for key, value in report["validated_fields"].items():

            if "certificate" not in key.lower() and "vc number" not in key.lower():
                continue

            if len(value) < 6:
                self._mark_invalid(report, key, "Too Short", confidence=0.2)
                continue

            # Maharashtra certificate/VC numbers are alphanumeric, typically
            # with digits, hyphens, or slashes - reject values that are pure
            # words (a strong signal of an OCR misread of a nearby label).
            if not re.match(r"^[A-Za-z0-9][A-Za-z0-9\-/]*$", value):
                self._mark_invalid(report, key, "Invalid Format", confidence=0.2)
                continue

            if not re.search(r"\d", value):
                self._mark_invalid(
                    report, key, "No Digits Found - Likely OCR Error", confidence=0.3
                )
                continue

            self._set_field_confidence(report, key, 0.9)

    # ============================================
    # District Validation
    # ============================================

    def validate_district(self, report: Dict[str, Any]) -> None:

        for key, value in report["validated_fields"].items():

            if key.lower() != "district":
                continue

            normalized = value.strip().lower()

            if normalized in MAHARASHTRA_DISTRICTS:
                self._set_field_confidence(report, key, 0.95)
            else:
                self._mark_invalid(
                    report, key, "Unrecognized Maharashtra District", confidence=0.3
                )

    # ============================================
    # Taluka Validation
    # ============================================

    def validate_taluka(self, report: Dict[str, Any]) -> None:
        """
        Maharashtra has 350+ talukas, so we don't maintain a full static
        list here. Instead we apply a structural sanity check: a taluka
        name should be alphabetic (allowing spaces/hyphens) and reasonably
        sized - this catches common OCR corruption (stray digits/symbols)
        without needing an exhaustive gazetteer.
        """

        for key, value in report["validated_fields"].items():

            if key.lower() != "taluka":
                continue

            if re.match(r"^[A-Za-z\s\-]{3,40}$", value):
                self._set_field_confidence(report, key, 0.75)
            else:
                self._mark_invalid(
                    report, key, "Unusual Taluka Value - Possible OCR Error",
                    confidence=0.3,
                )

    # ============================================
    # PIN Code Validation
    # ============================================

    def validate_pin(self, report: Dict[str, Any]) -> None:

        for key, value in report["validated_fields"].items():

            if "pin" not in key.lower():
                continue

            if re.match(r"^[1-9][0-9]{5}$", value.strip()):
                self._set_field_confidence(report, key, 0.95)
            else:
                self._mark_invalid(report, key, "Invalid PIN Code", confidence=0.2)

    # ============================================
    # Category Validation
    # ============================================

    def validate_category(self, report: Dict[str, Any]) -> None:

        for key, value in report["validated_fields"].items():

            if key.lower() != "category":
                continue

            normalized = value.strip().lower()

            if normalized in VALID_CATEGORIES:
                self._set_field_confidence(report, key, 0.9)

            elif re.match(r"^[A-Za-z\s\-\.\(\)]{2,60}$", value):
                # Not one of the broad classification groups, but structurally
                # looks like a plausible caste/sub-caste name (letters only,
                # reasonable length) rather than OCR garbage. Flagged for
                # manual review rather than marked as flatly invalid, since
                # this is very likely a correct value we just can't enumerate.
                self._mark_invalid(
                    report, key,
                    "Category Not In Standard Broad List - Likely a Specific "
                    "Caste/Sub-Caste Name, Requires Manual Verification",
                    confidence=0.55,
                )

            else:
                self._mark_invalid(
                    report, key,
                    "Unrecognized Category Value - Contains Unexpected "
                    "Characters, Possible OCR Error",
                    confidence=0.2,
                )


govt_field_validator_service = GovtFieldValidatorService()