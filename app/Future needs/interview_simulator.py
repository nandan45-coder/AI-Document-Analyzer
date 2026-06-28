from fastapi import APIRouter, HTTPException

from app.schemas.interview_simulator import (
    InterviewStartRequest,
    InterviewAnswerRequest
)

from app.services.interview_session_service import (
    interview_session_service
)

from app.services.interview_evaluator_service import (
    interview_evaluator_service
)

router = APIRouter(
    prefix="/interview-simulator",
    tags=["AI Interview Simulator"]
)


# ==========================================
# Start Interview
# ==========================================

@router.post("/start/{document_id}")
def start_interview(
    document_id: int,
    request: InterviewStartRequest
):

    session = interview_session_service.create_session(
        document_id=document_id,
        role=request.selected_role,
        difficulty=request.difficulty,
        total_questions=request.total_questions
    )

    if session is None:

        raise HTTPException(
            status_code=404,
            detail="Unable to create interview session."
        )

    return {

        "success": True,

        "interview_id": session.id,

        "selected_role": session.selected_role,

        "difficulty": session.difficulty,

        "total_questions": session.total_questions,

        "status": session.interview_status

    }


# ==========================================
# Get Current Question
# ==========================================

@router.get("/question/{interview_id}")
def get_question(interview_id: int):

    question = interview_session_service.get_current_question(
        interview_id
    )

    if question is None:

        raise HTTPException(
            status_code=404,
            detail="Question not found."
        )

    return {

        "success": True,

        "question": question

    }


# ==========================================
# Submit Answer
# ==========================================

@router.post("/answer/{interview_id}")
def submit_answer(
    interview_id: int,
    request: InterviewAnswerRequest
):

    result = interview_evaluator_service.evaluate_answer(
        interview_id,
        request.answer
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


# ==========================================
# Interview Report
# ==========================================

@router.get("/report/{interview_id}")
def get_report(interview_id: int):

    report = interview_evaluator_service.get_final_report(
        interview_id
    )

    if not report["success"]:

        raise HTTPException(
            status_code=404,
            detail=report.get(
                "message",
                report.get("error")
            )
        )

    return report