from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
)

from app.database import Base


class User(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    full_name = Column(
        String,
        nullable=False,
    )

    username = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    email = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    mobile = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash = Column(
        String,
        nullable=False,
    )

    profile_image = Column(
        String,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.now,
    )

    # NOTE for future modules: reference this table via
    # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # - `id` is indexed and unique (primary key), so it's FK-ready as-is.