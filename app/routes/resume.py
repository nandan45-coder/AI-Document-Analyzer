from fastapi import APIRouter
from fastapi import HTTPException

from app.services.resume_analyzer import (
    analyze_resume
)

router = APIRouter()


@router.post(
    "/resume-analysis/{document_id}"
)
def resume_analysis(
    document_id: int
):

    result = analyze_resume(
        document_id
    )

    if result is None:

        raise HTTPException(
            status_code=404,
            detail="No chunks found"
        )

    return result