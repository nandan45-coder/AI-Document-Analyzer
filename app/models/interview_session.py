from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text
)

from sqlalchemy.sql import func

from app.database import Base


class InterviewSession(Base):

    __tablename__ = "interview_sessions"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False
    )

    selected_role = Column(
        String,
        nullable=False
    )

    difficulty = Column(
        String,
        nullable=False
    )

    total_questions = Column(
        Integer,
        nullable=False
    )

    current_question = Column(
        Integer,
        default=1
    )

    # -------------------------
    # Scores
    # -------------------------

    overall_score = Column(
        Float,
        default=0
    )

    technical_score = Column(
        Float,
        default=0
    )

    communication_score = Column(
        Float,
        default=0
    )

    coding_score = Column(
        Float,
        default=0
    )

    project_score = Column(
        Float,
        default=0
    )

    confidence_score = Column(
        Float,
        default=0
    )

    completeness_score = Column(
        Float,
        default=0
    )

    # -------------------------
    # Interview Status
    # -------------------------

    interview_status = Column(
        String,
        default="NOT_STARTED"
    )

    # -------------------------
    # Store Generated Questions
    # -------------------------

    questions_json = Column(
        Text,
        nullable=True
    )

    # -------------------------
    # Store Candidate Answers
    # -------------------------

    answers_json = Column(
        Text,
        nullable=True
    )

    # -------------------------
    # Store AI Feedback
    # -------------------------

    feedback_json = Column(
        Text,
        nullable=True
    )

    # -------------------------
    # Final Report
    # -------------------------

    interview_report = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )