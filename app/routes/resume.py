from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.document import Document
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
    current_user: User = Depends(get_current_user),
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
            # Not populated by analyze_resume() today - these stay None
            # until a real scoring pipeline is wired in. Reading them
            # defensively here means that whenever that day comes, this
            # line needs zero changes - the values just stop being None.
            resume_score=result.get("resume_score"),
            ats_score=result.get("ats_score"),
            recommended_role=result.get("recommended_role"),
        )

        db.add(history_entry)
        db.commit()

    return result