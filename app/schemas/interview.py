from typing import List, Dict, Optional

from pydantic import BaseModel, Field


class InterviewRequest(BaseModel):
    """
    Request body for Interview Preparation Module
    """

    selected_role: str = Field(
        ...,
        description="Select one role from the available 30 roles."
    )

    difficulty: str = Field(
        default="Intermediate",
        description="Beginner | Intermediate | Advanced"
    )

    total_questions: int = Field(
        default=30,
        ge=10,
        le=100,
        description="Number of interview questions."
    )


class InterviewQuestion(BaseModel):

    question: str

    expected_answer: str

    tip: str

    difficulty: str

    topics: List[str]


class InterviewCategories(BaseModel):

    hr_questions: List[InterviewQuestion]

    resume_questions: List[InterviewQuestion]

    technical_questions: List[InterviewQuestion]

    project_questions: List[InterviewQuestion]

    coding_questions: List[InterviewQuestion]

    scenario_questions: List[InterviewQuestion]


class InterviewGuide(BaseModel):

    target_role: str

    difficulty: str

    overall_readiness: int

    estimated_preparation_days: int

    top_strengths: List[str]

    weak_areas: List[str]

    missing_skills: List[str]

    study_plan: List[str]

    categories: InterviewCategories


class InterviewResponse(BaseModel):

    success: bool

    document_id: int

    selected_role: str

    difficulty: str

    interview_guide: Dict