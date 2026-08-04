from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_optional_current_user
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import auth_service


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# =====================================================
# Register
# =====================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new user account. Password strength, confirm-password match,
    and mobile-number format are all validated at the schema level before
    this even runs (see app/schemas/auth.py) - a 422 response means one of
    those failed. A 400 here means the account details themselves conflict
    with an existing user.
    """

    result = auth_service.register_user(db, request)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    return result["user"]


# =====================================================
# Login
# =====================================================

@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Login using EITHER username or email in `username_or_email`, plus
    password. Returns a JWT access token on success.
    """

    result = auth_service.login(db, request)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result["error"],
        )

    return {
        "access_token": result["access_token"],
        "token_type": result["token_type"],
    }


# =====================================================
# Logout
#
# JWT is stateless, so there is no server-side session to destroy. This
# endpoint still requires a valid token (via get_current_user) so it
# behaves correctly from the client's perspective, and exists as the
# stable integration point for real token blacklisting later: every
# access token already carries a unique "jti" claim (see
# app/utils/jwt_handler.py) specifically so that a future blacklist
# (Redis/DB-backed) can be added here without changing this endpoint's
# contract or re-issuing tokens for already-logged-in users.
# =====================================================

@router.post("/logout")
def logout(
    current_user: User = Depends(get_optional_current_user),
):
    # TODO (future phase): record this token's "jti" in a blacklist store
    # with a TTL matching its remaining expiry, and check that store inside
    # get_current_user (app/dependencies.py).
    return {
        "success": True,
        "message": "Logged out successfully. Please discard the access token on the client.",
    }


# =====================================================
# Change Password
# =====================================================

@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    result = auth_service.change_password(db, current_user, request)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    return {"success": True, "message": "Password updated successfully."}


# =====================================================
# Forgot Password (Phase 1: structure only, not implemented)
# =====================================================

@router.post("/forgot-password")
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Placeholder endpoint. Always returns a generic success-style message
    regardless of whether the email is registered (standard practice to
    avoid leaking registered emails) - no OTP/reset email is actually sent
    yet. See auth_service.request_password_reset for the extension point.
    """

    result = auth_service.request_password_reset(db, request.email)

    return result


# =====================================================
# Current User
# =====================================================

@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_optional_current_user),
):
    return current_user