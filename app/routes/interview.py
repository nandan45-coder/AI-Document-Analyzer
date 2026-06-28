from fastapi import APIRouter, HTTPException

from app.schemas.interview import InterviewRequest
from app.services.interview_service import interview_service


router = APIRouter(
    prefix="/interview",
    tags=["AI Interview Preparation"]
)


@router.post("/{document_id}")
def generate_interview(
    document_id: int,
    request: InterviewRequest
):
    """
    Generate personalized AI Interview Preparation Guide.
    """

    result = interview_service.generate_interview_guide(
        document_id=document_id,
        selected_role=request.selected_role,
        difficulty=request.difficulty,
        total_questions=request.total_questions
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