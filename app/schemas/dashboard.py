from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# =====================================================
# Welcome Section
# =====================================================

class DashboardUserInfo(BaseModel):

    full_name: str

    username: str

    # Always populated - either the user's real profile picture URL or a
    # default avatar path, never null. See DEFAULT_AVATAR_PATH in
    # dashboard_service.py.
    profile_image: str


# =====================================================
# Statistics Cards (unchanged from the basic dashboard)
# =====================================================

class DashboardStatistics(BaseModel):

    resume_documents: int = 0

    government_documents: int = 0

    reports: int = 0

    total_ai_analysis: int = 0


# =====================================================
# Resume Statistics (NEW)
#
# average/highest score fields are Optional and default to None, not 0 -
# "no data yet" and "a real score of 0" are different things, and
# collapsing them to 0 would be misleading once real scoring exists.
# =====================================================

class ResumeStatistics(BaseModel):

    total: int = 0

    average_resume_score: Optional[float] = None

    highest_resume_score: Optional[float] = None

    average_ats_score: Optional[float] = None

    highest_ats_score: Optional[float] = None

    most_recommended_role: Optional[str] = None

    reports: int = 0


# =====================================================
# Government Statistics (NEW)
# =====================================================

class GovernmentStatistics(BaseModel):

    total: int = 0

    verified: int = 0

    needs_review: int = 0

    failed: int = 0

    average_confidence: Optional[float] = None

    reports: int = 0


# =====================================================
# Recent History Widgets (NEW)
# =====================================================

class RecentResumeHistoryItem(BaseModel):

    id: int

    file_name: Optional[str] = None

    processed_at: datetime

    resume_score: Optional[int] = None

    ats_score: Optional[int] = None

    recommended_role: Optional[str] = None


class RecentGovernmentHistoryItem(BaseModel):

    id: int

    document_type: Optional[str] = None

    verification: Optional[str] = None

    confidence: Optional[float] = None

    processed_at: datetime


# =====================================================
# Recent Activity Timeline (NEW)
# =====================================================

class ActivityItem(BaseModel):

    type: str  # "resume" | "government"

    title: str

    # Human-friendly bucket label ("Today", "Yesterday", "Earlier") -
    # exact timestamp is also included below for anything that needs it.
    time: str

    timestamp: datetime


# =====================================================
# Weekly / Monthly Summary (NEW)
# =====================================================

class PeriodSummary(BaseModel):

    resume_analysis: int = 0

    government_analysis: int = 0

    reports: int = 0

    total_ai_jobs: int = 0


# =====================================================
# Quick Access Shortcuts (unchanged)
# =====================================================

class QuickAccessItem(BaseModel):

    module_name: str

    description: str

    path: str


# =====================================================
# Full Dashboard Response
#
# Every field from the original basic dashboard (user, statistics,
# quick_access) is UNCHANGED - only new fields were added around them.
# Any existing frontend reading only the old fields keeps working exactly
# as before.
# =====================================================

class DashboardResponse(BaseModel):

    user: DashboardUserInfo

    statistics: DashboardStatistics

    resume_statistics: ResumeStatistics

    government_statistics: GovernmentStatistics

    recent_resume_history: List[RecentResumeHistoryItem]

    recent_government_history: List[RecentGovernmentHistoryItem]

    recent_activity: List[ActivityItem]

    weekly_summary: PeriodSummary

    monthly_summary: PeriodSummary

    quick_access: List[QuickAccessItem]