from fastapi import APIRouter, HTTPException

from app.services.score_dashboard_service import (
    resume_score_dashboard_service
)

router = APIRouter(
    prefix="/resume-dashboard",
    tags=["Resume Score Dashboard"]
)


@router.get("/{document_id}")
def generate_dashboard(document_id: int):

    result = resume_score_dashboard_service.generate_dashboard(
        document_id
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