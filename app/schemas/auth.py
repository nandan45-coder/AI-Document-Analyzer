import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.utils.password_handler import validate_password_strength


MOBILE_PATTERN = re.compile(r"^[6-9]\d{9}$")


def _normalize_mobile(mobile: str) -> str:
    """
    Strips a leading '+91' / '91' country-code prefix and surrounding
    whitespace, so both "9876543210" and "+91 9876543210" are accepted
    and stored consistently as a plain 10-digit number.
    """

    cleaned = mobile.strip().replace(" ", "").replace("-", "")

    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]

    return cleaned


# =====================================================
# Registration
# =====================================================

class UserRegisterRequest(BaseModel):

    full_name: str = Field(..., min_length=2, max_length=100)

    username: str = Field(..., min_length=3, max_length=30)

    email: EmailStr

    mobile: str

    password: str

    confirm_password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not re.match(r"^[A-Za-z0-9_]+$", value):
            raise ValueError(
                "Username can only contain letters, numbers, and underscores."
            )
        return value

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, value: str) -> str:
        normalized = _normalize_mobile(value)

        if not MOBILE_PATTERN.match(normalized):
            raise ValueError(
                "Mobile number must be a valid 10-digit Indian mobile number."
            )

        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        is_valid, reason = validate_password_strength(value)

        if not is_valid:
            raise ValueError(reason)

        return value

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "UserRegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Password and Confirm Password do not match.")
        return self


# =====================================================
# Login
# =====================================================

class UserLoginRequest(BaseModel):

    # Accepts EITHER a username or an email address in this single field,
    # matching the "Username + Password OR Email + Password" requirement
    # without needing two separate login endpoints.
    username_or_email: str = Field(..., min_length=3)

    password: str = Field(..., min_length=1)


# =====================================================
# Token Response
# =====================================================

class TokenResponse(BaseModel):

    access_token: str

    token_type: str = "bearer"


# =====================================================
# Change Password
# =====================================================

class ChangePasswordRequest(BaseModel):

    current_password: str

    new_password: str

    confirm_new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        is_valid, reason = validate_password_strength(value)

        if not is_valid:
            raise ValueError(reason)

        return value

    @model_validator(mode="after")
    def validate_new_passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_new_password:
            raise ValueError("New Password and Confirm New Password do not match.")
        return self


# =====================================================
# Forgot Password (structure only - not implemented yet)
# =====================================================

class ForgotPasswordRequest(BaseModel):
    """
    Structure only, per Phase 1 scope. No OTP/email is sent yet - this
    exists so the /auth/forgot-password endpoint and service method have
    a stable request contract that a future phase can implement behind
    without any breaking change here.
    """

    email: EmailStr


# =====================================================
# User Response (safe to return - never includes password_hash)
# =====================================================

class UserResponse(BaseModel):

    id: int

    full_name: str

    username: str

    email: EmailStr

    mobile: str

    profile_image: Optional[str] = None

    created_at: datetime

    class Config:
        from_attributes = True