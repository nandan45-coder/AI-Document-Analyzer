from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
)

from sqlalchemy.sql import func

from app.database import Base


class GovernmentDocumentHistory(Base):

    __tablename__ = "government_document_history"

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

    # The govt module doesn't use the shared `documents` table - it works
    # directly from an uploaded file that's deleted after processing - so
    # there's no document_id to reference here, only a filename snapshot.
    filename = Column(
        String,
        nullable=True,
    )

    document_type = Column(
        String,
        nullable=True,
    )

    verification_status = Column(
        String,
        nullable=True,
    )

    ready_for_submission = Column(
        Boolean,
        default=False,
    )

    overall_confidence = Column(
        Float,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )