from fastapi import APIRouter, HTTPException

from app.schemas.jd_match import JDMatchRequest
from app.services.jd_match_service import jd_match_service

router = APIRouter(
    prefix="/jd-match",
    tags=["Multi-Role JD Matcher"]
)


@router.post("/{document_id}")
def match_resume(
    document_id: int,
    request: JDMatchRequest
):
    """
    Compare an uploaded resume against multiple selected job roles.
    """

    result = jd_match_service.match_resume(
        document_id=document_id,
        selected_roles=request.selected_roles
    )

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("message", result.get("error"))
        )

    return result