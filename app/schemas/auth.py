import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.utils.password_handler import validate_password_strength
from app.utils.security_questions import is_valid_security_question


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

    security_question: str = Field(..., min_length=3, max_length=255)

    security_answer: str = Field(..., min_length=1, max_length=255)

    @field_validator("security_question")
    @classmethod
    def validate_security_question(cls, value: str) -> str:
        if not is_valid_security_question(value):
            raise ValueError(
                "Invalid security question. Please select one of the system-provided security questions."
            )
        return value.strip()

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
# Forgot Password (Security Question Flow)
# =====================================================

class ForgotPasswordRequest(BaseModel):
    """
    Handles password reset via Security Question:
    - Step 1 (Retrieval): Provide `username_or_email` (or `email`) to get the user's registered security question.
    - Step 2 (Reset): Provide `username_or_email`, `security_answer`, `new_password`, and `confirm_new_password` to update password.
    """

    username_or_email: Optional[str] = Field(None, description="Username or Email address")

    email: Optional[str] = Field(None, description="Email address")

    security_question: Optional[str] = Field(None, description="User's security question")

    security_answer: Optional[str] = Field(None, description="Security question answer")

    new_password: Optional[str] = Field(None, description="New password")

    confirm_new_password: Optional[str] = Field(None, description="Confirm new password")

    @model_validator(mode="after")
    def validate_request(self) -> "ForgotPasswordRequest":
        identifier = self.username_or_email or self.email
        if not identifier or not str(identifier).strip():
            raise ValueError("Username or Email is required.")

        is_reset_attempt = (
            self.security_answer is not None
            or self.new_password is not None
            or self.confirm_new_password is not None
        )

        if is_reset_attempt:
            if not self.security_answer or not str(self.security_answer).strip():
                raise ValueError("Security answer is required.")
            if not self.new_password:
                raise ValueError("New password is required.")
            if not self.confirm_new_password:
                raise ValueError("Confirm new password is required.")
            if self.new_password != self.confirm_new_password:
                raise ValueError("New Password and Confirm New Password do not match.")

            is_valid, reason = validate_password_strength(self.new_password)
            if not is_valid:
                raise ValueError(reason)

        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "username_or_email": "user123",
                "email": "user@example.com",
                "security_question": "In what city or town were you born?",
                "security_answer": "CityName",
                "new_password": "NewPassword@123",
                "confirm_new_password": "NewPassword@123"
            }
        }
    }


# =====================================================
# User Response (safe to return - never includes password_hash or security_answer)
# =====================================================

class UserResponse(BaseModel):

    id: int

    full_name: str

    username: str

    email: EmailStr

    mobile: str

    profile_image: Optional[str] = None

    security_question: Optional[str] = None

    created_at: datetime

    class Config:
        from_attributes = True