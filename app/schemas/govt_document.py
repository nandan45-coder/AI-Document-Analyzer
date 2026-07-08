from typing import Dict, List, Any, Optional

from pydantic import BaseModel


# ============================================
# Upload Response
# ============================================

class GovtDocumentResponse(BaseModel):

    success: bool

    document_type: str

    classification_confidence: float

    verification: Dict[str, Any]

    field_validation: Dict[str, Any]

    extracted_fields: Dict[str, Any]

    expected_fields: List[str]

    ai_report: Dict[str, Any]

    # NEW - additive only. Existing consumers that don't read this field
    # are unaffected; nothing above was removed or renamed.
    overall_confidence: Optional[Dict[str, Any]] = None


# ============================================
# Error Response
# ============================================

class GovtErrorResponse(BaseModel):

    success: bool

    error: str