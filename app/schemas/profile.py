import re
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

# Reusing the exact same mobile validation logic from Phase 1 rather than
# duplicating it - if the mobile format rule ever changes, it only needs
# to change in one place (app/schemas/auth.py).
from app.schemas.auth import MOBILE_PATTERN, _normalize_mobile

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


# =====================================================
# View Profile
#
# Deliberately does NOT include `id` (per spec: "Never return ...
# Internal IDs") even though Phase 1's UserResponse does - this is a
# narrower, profile-specific view, not the auth module's user object.
# =====================================================

class ProfileResponse(BaseModel):

    full_name: str

    username: str

    email: EmailStr

    mobile: str

    profile_image: Optional[str] = None

    @field_validator("profile_image")
    @classmethod
    def build_image_url(cls, value: Optional[str]) -> Optional[str]:
        """
        Stored DB paths are plain relative paths (e.g.
        "uploads/profile_images/xxxx.jpg"). This adds the leading slash
        needed to actually use it as a URL path against the /uploads
        static mount, without ever storing that leading slash in the DB.
        """

        if value and not value.startswith("/"):
            return f"/{value}"
        return value

    class Config:
        from_attributes = True


# =====================================================
# Edit Profile
#
# All fields are optional (partial update) - a field left as null/omitted
# means "leave this unchanged". Only fields that are both provided AND
# different from the current value are actually validated for uniqueness
# and written to the database (see profile_service.py).
# =====================================================

class ProfileUpdateRequest(BaseModel):

    full_name: Optional[str] = Field(None, min_length=2, max_length=100)

    username: Optional[str] = Field(None, min_length=3, max_length=30)

    email: Optional[EmailStr] = None

    mobile: Optional[str] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        if not USERNAME_PATTERN.match(value):
            raise ValueError(
                "Username can only contain letters, numbers, and underscores."
            )

        return value

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        normalized = _normalize_mobile(value)

        if not MOBILE_PATTERN.match(normalized):
            raise ValueError(
                "Mobile number must be a valid 10-digit Indian mobile number."
            )

        return normalized


class ProfileUpdateResponse(BaseModel):

    success: bool

    message: str

    profile: Optional[ProfileResponse] = None


# =====================================================
# Profile Picture
# =====================================================

class ProfileImageResponse(BaseModel):

    success: bool

    message: str

    profile_image: Optional[str] = None