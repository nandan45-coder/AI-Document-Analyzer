from fastapi import APIRouter

from app.database import SessionLocal
from app.models.document import Document

from app.services.ats_service import (
    role_based_ats,
    ROLE_SKILLS
)

router = APIRouter()


@router.post("/ats/{document_id}")
def ats_analysis(
    document_id: int,
    role: str
):

    db = SessionLocal()

    document = (
        db.query(Document)
        .filter(
            Document.id == document_id
        )
        .first()
    )

    if not document:

        return {
            "error": "Document not found"
        }

    result = role_based_ats(
        document.extracted_text,
        role
    )

    return result


@router.get("/roles")
def get_roles():

    return {
        "total_roles": len(
            ROLE_SKILLS
        ),
        "roles": list(
            ROLE_SKILLS.keys()
        )
    }