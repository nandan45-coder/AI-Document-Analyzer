"""
Shared helpers for the Government Document Intelligence module.

This module intentionally contains NO business logic specific to any single
service. It only removes duplicated glue code (Gemini JSON-fence stripping,
overall confidence aggregation) so govt_classifier_service.py and
govt_report_service.py stay focused on their own responsibilities.
"""

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("govt_document_intelligence")

# Single source of truth for PDF rasterization resolution. Previously
# govt_ocr_service.py and govt_verification_service.py each rendered the
# same PDF at DIFFERENT zoom levels (OCR used 3x, verification used the
# default 1x/72 DPI). That mismatch meant verification was working off a
# much blurrier, lower-resolution image than OCR, directly hurting template
# matching precision and the document_quality resolution/blur scores.
# Both services now import this one constant.
PDF_RENDER_ZOOM = 3.0


# =====================================================
# Lenient URL Matching Helper
# =====================================================

def normalize_ocr_spacing(text: str) -> str:
    """
    OCR frequently inserts stray spaces around punctuation in URLs/domains
    (e.g. "https :// example . gov . in" instead of "https://example.gov.in").
    This collapses spacing immediately around ':', '/', and '.' so a
    verification-URL regex has a fair chance of matching even on
    imperfect OCR text. Only touches punctuation spacing - does not alter
    words themselves, so it's safe to run before any other text matching.
    """

    if not text:
        return text

    return re.sub(r"\s*([:/.])\s*", r"\1", text)


# =====================================================
# Gemini JSON Response Parsing
# =====================================================

def parse_json_response(raw_text: str) -> Dict[str, Any]:
    """
    Strip Markdown code fences (```json / ```) that Gemini frequently wraps
    JSON responses in, then parse the result.

    Raises:
        ValueError: if the cleaned text is not valid JSON.
    """

    if raw_text is None:
        raise ValueError("Empty response from Gemini.")

    text = raw_text.strip()

    if text.startswith("```json"):
        text = text[len("```json"):].strip()

    if text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[: -len("```")].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Gemini JSON response: %s", exc)
        logger.debug("Raw Gemini output was: %s", raw_text)
        raise ValueError(f"Gemini did not return valid JSON: {exc}") from exc


# =====================================================
# Overall Confidence Aggregation
# =====================================================

# Relative importance of each pipeline stage in the final confidence score.
# Kept centralized so tuning it doesn't require touching multiple services.
DEFAULT_CONFIDENCE_WEIGHTS: Dict[str, float] = {
    "ocr": 0.20,
    "classification": 0.20,
    "extraction": 0.20,
    "validation": 0.20,
    "verification": 0.20,
}


def _normalize_to_percent(value: Optional[float]) -> float:
    """
    Accepts a confidence expressed either as 0-1 or 0-100 and normalizes it
    to a 0-100 scale. Missing/invalid values are treated as 0.
    """

    if value is None:
        return 0.0

    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0

    if 0.0 <= value <= 1.0:
        return value * 100.0

    return max(0.0, min(value, 100.0))


def compute_overall_confidence(
    ocr_confidence: Optional[float] = None,
    classification_confidence: Optional[float] = None,
    extraction_confidence: Optional[float] = None,
    validation_confidence: Optional[float] = None,
    verification_confidence: Optional[float] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Combines per-stage confidence scores into a single overall confidence
    score (0-100), using a weighted average. Any stage that did not report a
    confidence is scored as 0 for that stage, and its weight is redistributed
    proportionally across the remaining stages so a single missing signal
    doesn't unfairly zero out the whole score.

    Returns a dict with the individual normalized scores plus the overall
    weighted result, so it can be dropped straight into the JSON response.
    """

    weights = weights or DEFAULT_CONFIDENCE_WEIGHTS

    scores = {
        "ocr": _normalize_to_percent(ocr_confidence),
        "classification": _normalize_to_percent(classification_confidence),
        "extraction": _normalize_to_percent(extraction_confidence),
        "validation": _normalize_to_percent(validation_confidence),
        "verification": _normalize_to_percent(verification_confidence),
    }

    present_keys = [
        key for key, value in {
            "ocr": ocr_confidence,
            "classification": classification_confidence,
            "extraction": extraction_confidence,
            "validation": validation_confidence,
            "verification": verification_confidence,
        }.items()
        if value is not None
    ]

    if not present_keys:
        return {
            "stage_scores": scores,
            "overall_confidence": 0.0,
            "overall_confidence_label": "Unknown",
        }

    total_weight = sum(weights[key] for key in present_keys)

    overall = sum(
        scores[key] * (weights[key] / total_weight)
        for key in present_keys
    )

    overall = round(overall, 2)

    if overall >= 85:
        label = "High"
    elif overall >= 60:
        label = "Medium"
    else:
        label = "Low"

    return {
        "stage_scores": {key: round(val, 2) for key, val in scores.items()},
        "overall_confidence": overall,
        "overall_confidence_label": label,
    }