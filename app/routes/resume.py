from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_optional_current_user
from app.models.resume_history import ResumeHistory
from app.models.user import User

from app.services.resume_analyzer_service import (
    analyze_resume
)

router = APIRouter()


@router.post(
    "/resume-analysis/{document_id}"
)
def resume_analysis(
    document_id: int,
    # Permanently open regardless of AUTH_ENABLED - this is core product
    # functionality. If a valid token IS sent, the real user gets credit
    # in history; otherwise it's attributed to the shared placeholder
    # user. See get_optional_current_user in app/dependencies.py.
    current_user: User = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):

    result = analyze_resume(
        document_id
    )

    if result is None:

        raise HTTPException(
            status_code=404,
            detail="No chunks found"
        )

    # Record this analysis in the authenticated user's history - this is
    # what powers the Dashboard's "Total Resume Documents" statistic.
    # Only recorded on a genuine successful parse (analyze_resume returns
    # an {"error": ...} dict, not None, when Gemini's JSON parsing fails -
    # that case is still returned to the caller as before, just not
    # counted as a successful history entry).
    if isinstance(result, dict) and "error" not in result:

        history_entry = ResumeHistory(
            user_id=current_user.id,
            document_id=document_id,
            candidate_name=result.get("candidate_name") or None,
        )

        db.add(history_entry)
        db.commit()

    return result