from fastapi import APIRouter, HTTPException

from app.services.resume_improver_service import (
    resume_improver_service
)

router = APIRouter(
    prefix="/resume-improver",
    tags=["AI Resume Improvement"]
)


@router.get("/{document_id}")
def improve_resume(document_id: int):
    """
    Improve an uploaded resume using AI.
    """

    result = resume_improver_service.improve_resume(
        document_id=document_id
    )

    if not result["success"]:

        raise HTTPException(
            status_code=400,
            detail=result.get(
                "message",
                result.get("error")
            )
        )

    return result