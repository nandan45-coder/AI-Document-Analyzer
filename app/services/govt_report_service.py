import json
import logging

from app.services.govt_ocr_service import govt_ocr_service
from app.services.govt_classifier_service import govt_classifier_service
from app.services.govt_verification_service import govt_verification_service
from app.services.govt_field_validator_service import govt_field_validator_service
from app.services.gemini_service import model
from app.utils.govt_common import parse_json_response, compute_overall_confidence

logger = logging.getLogger("govt_document_intelligence")


class GovtReportService:

    # =====================================================
    # Generate Complete Government Document Report
    # =====================================================

    def generate_report(self, file_path: str):

        try:
            # ----------------------------------------
            # OCR
            # ----------------------------------------

            ocr_result = govt_ocr_service.extract_text(file_path)

            if not ocr_result["success"]:
                return ocr_result

            # ----------------------------------------
            # Classification + Field Extraction
            # ----------------------------------------

            classifier_result = govt_classifier_service.classify_document(
                ocr_result["clean_text"]
            )

            if not classifier_result["success"]:
                return classifier_result

            # ----------------------------------------
            # Verification (now also receives OCR text for
            # text-based indicators like digital signatures / URLs)
            # ----------------------------------------

            verification_result = govt_verification_service.verify_document(
                file_path, ocr_text=ocr_result["clean_text"]
            )

            if not verification_result["success"]:
                return verification_result

            # ----------------------------------------
            # Field Validation
            # ----------------------------------------

            validation_result = govt_field_validator_service.validate_fields(
                extracted_fields=classifier_result["extracted_fields"],
                expected_fields=classifier_result["expected_fields"],
            )

            if not validation_result["valid"]:
                logger.info(
                    "Document failed field validation: missing=%s invalid=%s",
                    validation_result["missing_fields"],
                    validation_result["invalid_fields"],
                )

            # ----------------------------------------
            # Deterministic Overall Confidence
            # ----------------------------------------

            confidence_summary = compute_overall_confidence(
                ocr_confidence=ocr_result.get("ocr_confidence"),
                classification_confidence=classifier_result.get("confidence"),
                extraction_confidence=classifier_result.get("extraction_confidence"),
                validation_confidence=validation_result.get("completion_percentage"),
                verification_confidence=verification_result.get("confidence"),
            )

            # ----------------------------------------
            # AI Report
            # ----------------------------------------

            prompt = self.build_prompt(
                ocr_result,
                classifier_result,
                verification_result,
                validation_result,
                confidence_summary,
            )

            response = model.generate_content(prompt)

            ai_report = parse_json_response(response.text)

            return {
                "success": True,
                "document_type": classifier_result["document_type"],
                "classification_confidence": classifier_result["confidence"],
                "verification": verification_result,
                "field_validation": validation_result,
                "extracted_fields": classifier_result["extracted_fields"],
                "expected_fields": classifier_result["expected_fields"],
                "overall_confidence": confidence_summary,
                "ai_report": ai_report,
            }

        except Exception as e:
            logger.exception("Report generation failed for %s", file_path)
            return {
                "success": False,
                "error": str(e),
            }

    # =====================================================
    # Build Gemini Prompt
    # =====================================================

    def build_prompt(
        self,
        ocr_result,
        classifier_result,
        verification_result,
        validation_result,
        confidence_summary,
    ):

        prompt = f"""
You are an expert Maharashtra Government Document Verification Officer.

Analyze the following document details and generate a professional verification report.

====================================================
Document Type
====================================================

{classifier_result["document_type"]}

====================================================
OCR Quality
====================================================

Engine used: {ocr_result.get("ocr_engine")}
OCR Confidence: {ocr_result.get("ocr_confidence")}

====================================================
Classification Confidence
====================================================

{classifier_result["confidence"]}

====================================================
Extracted Information
====================================================

{json.dumps(classifier_result["extracted_fields"], indent=4)}

====================================================
Expected Fields
====================================================

{json.dumps(classifier_result["expected_fields"], indent=4)}

====================================================
Field Validation Result
====================================================

{json.dumps(validation_result, indent=4)}

====================================================
Verification Result
====================================================

{json.dumps(verification_result, indent=4)}

====================================================
Computed Overall Confidence
====================================================

{json.dumps(confidence_summary, indent=4)}

====================================================

Generate a professional verification report.

Include:

1. Overall Summary
2. Verification Explanation
3. Missing Information
4. Invalid or Suspicious Fields (including likely OCR mistakes)
5. Document Quality
6. Ready For Submission
7. Recommendations
8. Warnings (if any)
9. Overall Confidence Explanation (use the computed overall confidence provided above, do not invent a different number)

Return ONLY JSON.

Required Format

{{
    "summary":"",
    "verification_explanation":"",
    "missing_information":[],
    "invalid_or_suspicious_fields":[],
    "document_quality":"",
    "ready_for_submission":true,
    "recommendations":[],
    "warnings":[],
    "overall_confidence_explanation":""
}}
"""

        return prompt


govt_report_service = GovtReportService()