from fastapi import APIRouter

from app.services.summary_service import (
    summarize_document
)

router = APIRouter()


@router.post(
    "/summary/{document_id}"
)
def create_summary(
    document_id: int
):

    summary = summarize_document(
        document_id
    )

    if summary is None:
        return {
            "error":
            "No chunks found"
        }

    return {
        "document_id": document_id,
        "summary": summary
    }