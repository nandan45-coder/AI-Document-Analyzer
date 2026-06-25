from fastapi import APIRouter
from fastapi import HTTPException

from app.schemas.jd_match import JDMatchRequest
from app.services.jd_match_service import match_resume_with_jd

router = APIRouter(
    prefix="",
    tags=["Resume vs Job Description Matching"]
)


@router.post("/jd-match/{document_id}")
def jd_match(
    document_id: int,
    request: JDMatchRequest
):

    result = match_resume_with_jd(
        document_id=document_id,
        job_description=request.job_description
    )

    if "error" in result:
        raise HTTPException(
            status_code=400,
            detail=result["error"]
        )

    return result