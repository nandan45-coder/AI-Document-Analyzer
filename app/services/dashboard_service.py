import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.govt_document_history import GovernmentDocumentHistory
from app.models.resume_history import ResumeHistory
from app.models.user import User
from app.schemas.dashboard import (
    ActivityItem,
    DashboardResponse,
    DashboardStatistics,
    DashboardUserInfo,
    GovernmentStatistics,
    PeriodSummary,
    QuickAccessItem,
    RecentGovernmentHistoryItem,
    RecentResumeHistoryItem,
    ResumeStatistics,
)

logger = logging.getLogger("dashboard_module")


# Placeholder path for users with no profile picture. This does NOT point
# to a real file yet - either drop an actual image at this relative path
# under your existing /uploads static mount (Phase 2), or have the
# frontend treat this exact string as a signal to render its own local
# default-avatar asset instead. Either way, the dashboard always returns
# a non-null profile_image so the frontend never has to special-case null.
DEFAULT_AVATAR_PATH = "/uploads/default_avatar.png"


# Static quick-access metadata for the 6 existing AI modules. Paths below
# match each module's ACTUAL route as currently registered in main.py -
# not placeholders. Add a new entry here (and nowhere else) when a new AI
# module is added later.
QUICK_ACCESS_MODULES = [
    {
        "module_name": "Resume Intelligence",
        "description": "Analyze and extract insights from a resume.",
        "path": "/resume-analysis/{document_id}",
    },
    {
        "module_name": "ATS Analyzer",
        "description": "Check resume compatibility against ATS systems.",
        "path": "/ats/{document_id}",
    },
    {
        "module_name": "JD Matcher",
        "description": "Match a resume against a job description.",
        "path": "/jd-match/{document_id}",
    },
    {
        "module_name": "Career Recommendation",
        "description": "Get personalized career path recommendations.",
        "path": "/career/{document_id}",
    },
    {
        "module_name": "Interview Preparation",
        "description": "Generate interview questions and preparation material.",
        "path": "/interview/{document_id}",
    },
    {
        "module_name": "Government Document Intelligence",
        "description": "Analyze and verify Maharashtra government documents.",
        "path": "/govt/analyze",
    },
]

# Maps the free-text verification_status values actually produced by
# govt_verification_service.py into the 3 dashboard buckets requested.
# Kept as one explicit mapping (not scattered if/elif checks) so adding a
# new possible status later is a one-line change here only.
GOVT_STATUS_BUCKET_MAP = {
    "Verified": "verified",
    "Verification Pending": "needs_review",
    "Unknown": "failed",
}

RECENT_HISTORY_LIMIT = 5
RECENT_ACTIVITY_LIMIT = 10


class DashboardService:

    # =====================================================
    # Main Entry Point
    # =====================================================

    def get_dashboard(self, db: Session, user: User) -> DashboardResponse:

        return DashboardResponse(
            user=self._build_user_info(user),
            statistics=self._build_statistics(db, user),
            resume_statistics=self._build_resume_statistics(db, user),
            government_statistics=self._build_government_statistics(db, user),
            recent_resume_history=self._build_recent_resume_history(db, user),
            recent_government_history=self._build_recent_government_history(db, user),
            recent_activity=self._build_recent_activity(db, user),
            weekly_summary=self._build_period_summary(db, user, days=7),
            monthly_summary=self._build_period_summary(db, user, days=30),
            quick_access=self._build_quick_access(),
        )

    # =====================================================
    # Welcome Section
    # =====================================================

    def _build_user_info(self, user: User) -> DashboardUserInfo:

        profile_image = user.profile_image

        if profile_image and not profile_image.startswith("/"):
            profile_image = f"/{profile_image}"

        if not profile_image:
            profile_image = DEFAULT_AVATAR_PATH

        return DashboardUserInfo(
            full_name=user.full_name,
            username=user.username,
            profile_image=profile_image,
        )

    # =====================================================
    # Statistics (unchanged behavior from the basic dashboard)
    # =====================================================

    def _build_statistics(self, db: Session, user: User) -> DashboardStatistics:

        resume_documents = self._count_resume_documents(db, user)
        government_documents = self._count_government_documents(db, user)
        reports = resume_documents + government_documents
        total_ai_analysis = resume_documents + government_documents

        return DashboardStatistics(
            resume_documents=resume_documents,
            government_documents=government_documents,
            reports=reports,
            total_ai_analysis=total_ai_analysis,
        )

    def _count_resume_documents(self, db: Session, user: User) -> int:
        return (
            db.query(func.count(ResumeHistory.id))
            .filter(ResumeHistory.user_id == user.id)
            .scalar()
            or 0
        )

    def _count_government_documents(self, db: Session, user: User) -> int:
        return (
            db.query(func.count(GovernmentDocumentHistory.id))
            .filter(GovernmentDocumentHistory.user_id == user.id)
            .scalar()
            or 0
        )

    # =====================================================
    # Resume Statistics (NEW)
    #
    # Single aggregate query (COUNT/AVG/MAX in one round trip) - not one
    # query per number. average_/highest_ fields stay None (not 0) when
    # there is no scored data yet, since resume_score/ats_score are not
    # populated by anything today - see resume_history.py.
    # =====================================================

    def _build_resume_statistics(self, db: Session, user: User) -> ResumeStatistics:

        row = (
            db.query(
                func.count(ResumeHistory.id),
                func.avg(ResumeHistory.resume_score),
                func.max(ResumeHistory.resume_score),
                func.avg(ResumeHistory.ats_score),
                func.max(ResumeHistory.ats_score),
            )
            .filter(ResumeHistory.user_id == user.id)
            .one()
        )

        total, avg_resume, max_resume, avg_ats, max_ats = row

        most_recommended_role = self._get_most_recommended_role(db, user)

        return ResumeStatistics(
            total=total or 0,
            average_resume_score=round(avg_resume, 2) if avg_resume is not None else None,
            highest_resume_score=max_resume,
            average_ats_score=round(avg_ats, 2) if avg_ats is not None else None,
            highest_ats_score=max_ats,
            most_recommended_role=most_recommended_role,
            reports=total or 0,
        )

    def _get_most_recommended_role(self, db: Session, user: User) -> Optional[str]:

        result = (
            db.query(
                ResumeHistory.recommended_role,
                func.count(ResumeHistory.id).label("role_count"),
            )
            .filter(
                ResumeHistory.user_id == user.id,
                ResumeHistory.recommended_role.isnot(None),
            )
            .group_by(ResumeHistory.recommended_role)
            .order_by(func.count(ResumeHistory.id).desc())
            .first()
        )

        return result[0] if result else None

    # =====================================================
    # Government Statistics (NEW)
    #
    # Two queries total: one aggregate for count/avg confidence, one
    # GROUP BY for the verified/needs_review/failed buckets - not one
    # query per bucket.
    # =====================================================

    def _build_government_statistics(self, db: Session, user: User) -> GovernmentStatistics:

        total, avg_confidence = (
            db.query(
                func.count(GovernmentDocumentHistory.id),
                func.avg(GovernmentDocumentHistory.overall_confidence),
            )
            .filter(GovernmentDocumentHistory.user_id == user.id)
            .one()
        )

        status_counts = (
            db.query(
                GovernmentDocumentHistory.verification_status,
                func.count(GovernmentDocumentHistory.id),
            )
            .filter(GovernmentDocumentHistory.user_id == user.id)
            .group_by(GovernmentDocumentHistory.verification_status)
            .all()
        )

        verified = needs_review = failed = 0

        for status_value, count in status_counts:
            bucket = GOVT_STATUS_BUCKET_MAP.get(status_value, "failed")

            if bucket == "verified":
                verified += count
            elif bucket == "needs_review":
                needs_review += count
            else:
                failed += count

        return GovernmentStatistics(
            total=total or 0,
            verified=verified,
            needs_review=needs_review,
            failed=failed,
            average_confidence=(
                round(avg_confidence, 2) if avg_confidence is not None else None
            ),
            reports=total or 0,
        )

    # =====================================================
    # Recent History Widgets (NEW)
    # =====================================================

    def _build_recent_resume_history(
        self, db: Session, user: User
    ) -> List[RecentResumeHistoryItem]:

        # Single JOIN to pull the filename from Document, rather than N+1
        # separate lookups per history row.
        rows = (
            db.query(ResumeHistory, Document.filename)
            .join(Document, Document.id == ResumeHistory.document_id)
            .filter(ResumeHistory.user_id == user.id)
            .order_by(ResumeHistory.created_at.desc())
            .limit(RECENT_HISTORY_LIMIT)
            .all()
        )

        return [
            RecentResumeHistoryItem(
                id=history.id,
                file_name=filename,
                processed_at=history.created_at,
                resume_score=history.resume_score,
                ats_score=history.ats_score,
                recommended_role=history.recommended_role,
            )
            for history, filename in rows
        ]

    def _build_recent_government_history(
        self, db: Session, user: User
    ) -> List[RecentGovernmentHistoryItem]:

        rows = (
            db.query(GovernmentDocumentHistory)
            .filter(GovernmentDocumentHistory.user_id == user.id)
            .order_by(GovernmentDocumentHistory.created_at.desc())
            .limit(RECENT_HISTORY_LIMIT)
            .all()
        )

        return [
            RecentGovernmentHistoryItem(
                id=row.id,
                document_type=row.document_type,
                verification=row.verification_status,
                confidence=row.overall_confidence,
                processed_at=row.created_at,
            )
            for row in rows
        ]

    # =====================================================
    # Recent Activity Timeline (NEW)
    #
    # Pulls a bounded number of recent rows from EACH table (not the
    # entire table), merges in Python, sorts once, and trims to the
    # final limit - avoids scanning full history tables just to show a
    # handful of recent items.
    # =====================================================

    def _build_recent_activity(self, db: Session, user: User) -> List[ActivityItem]:

        resume_rows = (
            db.query(ResumeHistory)
            .filter(ResumeHistory.user_id == user.id)
            .order_by(ResumeHistory.created_at.desc())
            .limit(RECENT_ACTIVITY_LIMIT)
            .all()
        )

        govt_rows = (
            db.query(GovernmentDocumentHistory)
            .filter(GovernmentDocumentHistory.user_id == user.id)
            .order_by(GovernmentDocumentHistory.created_at.desc())
            .limit(RECENT_ACTIVITY_LIMIT)
            .all()
        )

        activities: List[ActivityItem] = []

        for row in resume_rows:
            activities.append(
                ActivityItem(
                    type="resume",
                    title="Resume Analysis Completed",
                    time=self._humanize_time_bucket(row.created_at),
                    timestamp=row.created_at,
                )
            )

        for row in govt_rows:
            activities.append(
                ActivityItem(
                    type="government",
                    title=f"Government Document {row.verification_status or 'Processed'}",
                    time=self._humanize_time_bucket(row.created_at),
                    timestamp=row.created_at,
                )
            )

        activities.sort(key=lambda item: item.timestamp, reverse=True)

        return activities[:RECENT_ACTIVITY_LIMIT]

    def _humanize_time_bucket(self, timestamp: datetime) -> str:

        if timestamp is None:
            return "Earlier"

        now = datetime.now(timezone.utc)

        ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)

        delta_days = (now.date() - ts.date()).days

        if delta_days <= 0:
            return "Today"
        if delta_days == 1:
            return "Yesterday"

        return "Earlier"

    # =====================================================
    # Weekly / Monthly Summary (NEW)
    #
    # 2 COUNT queries per period (resume + government) - not a query per
    # individual number shown in the response.
    # =====================================================

    def _build_period_summary(self, db: Session, user: User, days: int) -> PeriodSummary:

        since = datetime.now(timezone.utc) - timedelta(days=days)

        resume_count = (
            db.query(func.count(ResumeHistory.id))
            .filter(
                ResumeHistory.user_id == user.id,
                ResumeHistory.created_at >= since,
            )
            .scalar()
            or 0
        )

        government_count = (
            db.query(func.count(GovernmentDocumentHistory.id))
            .filter(
                GovernmentDocumentHistory.user_id == user.id,
                GovernmentDocumentHistory.created_at >= since,
            )
            .scalar()
            or 0
        )

        reports = resume_count + government_count
        total_ai_jobs = resume_count + government_count

        return PeriodSummary(
            resume_analysis=resume_count,
            government_analysis=government_count,
            reports=reports,
            total_ai_jobs=total_ai_jobs,
        )

    # =====================================================
    # Quick Access
    # =====================================================

    def _build_quick_access(self) -> List[QuickAccessItem]:
        return [QuickAccessItem(**item) for item in QUICK_ACCESS_MODULES]


dashboard_service = DashboardService()