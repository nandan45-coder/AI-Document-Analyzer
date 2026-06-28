from typing import List, Optional, Dict
from pydantic import BaseModel, Field


# ================================
# Start Interview
# ================================

class InterviewStartRequest(BaseModel):

    selected_role: str = Field(
        ...,
        description="Select one of the available job roles."
    )

    difficulty: str = Field(
        default="Intermediate",
        description="Beginner | Intermediate | Advanced"
    )

    total_questions: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Number of interview questions."
    )


# ================================
# Start Interview Response
# ================================

class InterviewStartResponse(BaseModel):

    success: bool

    interview_id: int

    selected_role: str

    difficulty: str

    total_questions: int

    interview_status: str


# ================================
# Current Question
# ================================

class InterviewQuestionResponse(BaseModel):

    success: bool

    interview_id: int

    question_number: int

    total_questions: int

    question: str

    category: str

    difficulty: str


# ================================
# Submit Answer
# ================================

class InterviewAnswerRequest(BaseModel):

    answer: str = Field(
        ...,
        min_length=5,
        description="Candidate answer."
    )


# ================================
# AI Evaluation
# ================================

class InterviewEvaluationResponse(BaseModel):

    success: bool

    technical_score: float

    communication_score: float

    confidence_score: float

    completeness_score: float

    overall_score: float

    feedback: str

    ideal_answer: str

    improvement_tips: List[str]


# ================================
# Final Report
# ================================

class InterviewReportResponse(BaseModel):

    success: bool

    interview_id: int

    overall_score: float

    technical_score: float

    communication_score: float

    coding_score: float

    project_score: float

    confidence_score: float

    interview_status: str

    top_strengths: List[str]

    weak_areas: List[str]

    study_plan: List[str]

    report: Dict