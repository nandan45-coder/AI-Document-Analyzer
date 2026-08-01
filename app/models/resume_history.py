from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
)

from sqlalchemy.sql import func

from app.database import Base


class ResumeHistory(Base):

    __tablename__ = "resume_history"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False,
    )

    # Lightweight snapshot for a future "recent activity" view, so that
    # doesn't require re-running analysis or re-joining large chunk/
    # embedding tables just to show what a past entry was about.
    candidate_name = Column(
        String,
        nullable=True,
    )

    # -------------------------------------------------
    # Added for the analytics dashboard upgrade. Nullable and NOT
    # currently populated by anything - app/services/resume_analyzer.py
    # doesn't compute a numeric score today, and ATS scoring lives in a
    # separate, not-yet-linked module. These columns exist now so that
    # whenever a real scoring pipeline is wired in later, it only needs
    # to start WRITING a value here - no schema change, no dashboard
    # change, no migration required at that point.
    # -------------------------------------------------

    resume_score = Column(
        Integer,
        nullable=True,
    )

    ats_score = Column(
        Integer,
        nullable=True,
    )

    recommended_role = Column(
        String,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )