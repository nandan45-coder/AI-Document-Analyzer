import logging
from typing import Any, Dict, List, Optional

from app.data.govt_document_types import (
    GOVT_DOCUMENT_TYPES,
    CONFIDENCE_THRESHOLDS,
)

from app.services.gemini_service import model
from app.utils.govt_common import parse_json_response

logger = logging.getLogger("govt_document_intelligence")


class GovtClassifierService:

    # =====================================================
    # Document Classification
    # =====================================================

    def classify_document(self, ocr_text: str) -> Dict[str, Any]:

        try:
            supported_documents = list(GOVT_DOCUMENT_TYPES.keys())

            # ---------------------------------------------
            # Step 1: cheap local keyword prefilter.
            # Not authoritative - purely a hint passed to Gemini and a
            # sanity signal we can fall back on if Gemini's response is
            # malformed or names an unsupported type.
            # ---------------------------------------------

            keyword_candidates = self.keyword_prefilter(ocr_text)

            classification = self.classify_with_gemini(
                ocr_text, supported_documents, keyword_candidates
            )

            document_type = classification.get("document_type")

            if document_type not in GOVT_DOCUMENT_TYPES:
                logger.warning(
                    "Gemini returned unsupported document_type '%s'. "
                    "Falling back to keyword prefilter result.",
                    document_type,
                )

                if keyword_candidates:
                    document_type = keyword_candidates[0][0]
                else:
                    return {
                        "success": False,
                        "error": (
                            f"Unable to classify document. Gemini suggested "
                            f"'{classification.get('document_type')}', which is "
                            f"not a supported document type."
                        ),
                    }

            confidence = float(classification.get("confidence", 0) or 0)

            below_threshold = confidence < CONFIDENCE_THRESHOLDS.get(
                "document_classification", 0.80
            ) * (100 if confidence > 1 else 1)

            expected_fields = GOVT_DOCUMENT_TYPES[document_type]["fields"]

            # ---------------------------------------------
            # Step 2: field extraction tailored to the *actual* expected
            # fields for this document type, instead of one fixed template
            # for every certificate.
            # ---------------------------------------------

            extraction = self.extract_fields(ocr_text, document_type, expected_fields)

            return {
                "success": True,
                "document_type": document_type,
                "confidence": confidence,
                "classification_below_threshold": below_threshold,
                "keyword_candidates": [c[0] for c in keyword_candidates],
                "expected_fields": expected_fields,
                "extracted_fields": extraction.get("fields", {}),
                "extraction_confidence": extraction.get("confidence", 0),
            }

        except Exception as e:
            logger.exception("Document classification failed.")
            return {
                "success": False,
                "error": str(e),
            }

    # =====================================================
    # Local Keyword / Alias Prefilter
    # =====================================================

    def keyword_prefilter(self, ocr_text: str) -> List[tuple]:
        """
        Scores each supported document type by how many of its aliases
        appear in the OCR text. Returns a list of (document_type, score)
        sorted descending, for use as a fallback/hint signal only.
        """

        text_lower = (ocr_text or "").lower()
        scored = []

        for doc_type, meta in GOVT_DOCUMENT_TYPES.items():
            score = sum(
                1 for alias in meta.get("aliases", [])
                if alias.lower() in text_lower
            )
            if score > 0:
                scored.append((doc_type, score))

        scored.sort(key=lambda item: item[1], reverse=True)

        return scored

    # =====================================================
    # Gemini Classification Call
    # =====================================================

    def classify_with_gemini(
        self,
        ocr_text: str,
        supported_documents: List[str],
        keyword_candidates: List[tuple],
    ) -> Dict[str, Any]:

        hint = (
            f"Local keyword analysis suggests this is most likely one of: "
            f"{[c[0] for c in keyword_candidates[:3]]}"
            if keyword_candidates
            else "Local keyword analysis found no strong match."
        )

        prompt = f"""
You are an expert Maharashtra Government Document Classifier.

Below is OCR extracted text from a document.

====================

{ocr_text}

====================

Supported Documents

{supported_documents}

{hint}

Your Tasks

1 Detect the document type from the supported list only.
2 Return a confidence score from 0 to 100.
3 Return only JSON, nothing else.

Required Format

{{
    "document_type":"",
    "confidence":0
}}
"""

        response = model.generate_content(prompt)

        return parse_json_response(response.text)

    # =====================================================
    # Gemini Field Extraction Call (tailored per document type)
    # =====================================================

    def extract_fields(
        self,
        ocr_text: str,
        document_type: str,
        expected_fields: List[str],
    ) -> Dict[str, Any]:

        fields_template = {field: "" for field in expected_fields}

        prompt = f"""
You are an expert at extracting structured fields from Maharashtra
Government certificates.

Document Type: {document_type}

OCR Extracted Text

====================

{ocr_text}

====================

Extract ONLY the following fields. If a field is genuinely not present in
the text, return an empty string for it - do not guess or hallucinate a
value. Also return an overall extraction confidence from 0 to 100 based on
how clearly these fields were present and unambiguous in the OCR text.

Return ONLY JSON in this exact format:

{{
    "fields": {fields_template},
    "confidence": 0
}}
"""

        response = model.generate_content(prompt)

        return parse_json_response(response.text)


govt_classifier_service = GovtClassifierService()