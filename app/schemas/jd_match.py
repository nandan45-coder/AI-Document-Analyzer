from typing import List, Optional

from pydantic import BaseModel, Field

class JDMatchRequest(BaseModel):
    """
    Request body for Multi-Role JD Matcher
    """

    selected_roles: List[str] = Field(
        ...,
        min_items=1,
        description="Select one or more job roles."
    )

class RoleMatchResult(BaseModel):
    """
    Result for a single selected role
    """

    role: str
    match_score: float

    matched_skills: List[str]
    missing_skills: List[str]

    why_match: Optional[str] = None

    improvements: List[str] = []

    learning_roadmap: List[str] = []

    interview_readiness: Optional[str] = None

    career_level: Optional[str] = None

    salary_range: Optional[str] = None

    description: Optional[str] = None

    tools: List[str] = []

class JDMatchResponse(BaseModel):
    """
    Final API Response
    """

    success: bool

    roles_selected: int

    results: List[RoleMatchResult]