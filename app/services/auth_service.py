import logging
from datetime import timedelta
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.utils.jwt_handler import create_access_token
from app.utils.password_handler import hash_password, verify_password

logger = logging.getLogger("auth_module")


class AuthService:

    # =====================================================
    # Lookups
    # =====================================================

    def get_user_by_id(self, db: Session, user_id: int) -> User | None:
        return db.query(User).filter(User.id == user_id).first()

    def get_user_by_username(self, db: Session, username: str) -> User | None:
        return db.query(User).filter(User.username == username).first()

    def get_user_by_email(self, db: Session, email: str) -> User | None:
        return db.query(User).filter(User.email == email).first()

    def get_user_by_mobile(self, db: Session, mobile: str) -> User | None:
        return db.query(User).filter(User.mobile == mobile).first()

    # =====================================================
    # Registration
    # =====================================================

    def register_user(
        self, db: Session, request: UserRegisterRequest
    ) -> Dict[str, Any]:

        try:
            if self.get_user_by_username(db, request.username):
                return {"success": False, "error": "Username already exists."}

            if self.get_user_by_email(db, request.email):
                return {"success": False, "error": "Email already exists."}

            if self.get_user_by_mobile(db, request.mobile):
                return {"success": False, "error": "Mobile number already exists."}

            new_user = User(
                full_name=request.full_name,
                username=request.username,
                email=request.email,
                mobile=request.mobile,
                password_hash=hash_password(request.password),
            )

            db.add(new_user)
            db.commit()
            db.refresh(new_user)

            return {"success": True, "user": new_user}

        except Exception as e:
            db.rollback()
            logger.exception("User registration failed.")
            return {"success": False, "error": str(e)}

    # =====================================================
    # Login
    # =====================================================

    def authenticate_user(
        self, db: Session, request: UserLoginRequest
    ) -> Dict[str, Any]:
        """
        Accepts either a username or an email in `username_or_email`, per
        the "Username + Password OR Email + Password" requirement.
        """

        identifier = request.username_or_email.strip()

        user = self.get_user_by_username(db, identifier)

        if user is None and "@" in identifier:
            user = self.get_user_by_email(db, identifier)

        if user is None:
            # Deliberately identical message to the wrong-password case
            # below - never reveal whether the identifier itself exists.
            return {"success": False, "error": "Invalid credentials."}

        if not verify_password(request.password, user.password_hash):
            return {"success": False, "error": "Invalid credentials."}

        return {"success": True, "user": user}

    def login(self, db: Session, request: UserLoginRequest) -> Dict[str, Any]:

        auth_result = self.authenticate_user(db, request)

        if not auth_result["success"]:
            return auth_result

        user = auth_result["user"]

        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        return {
            "success": True,
            "access_token": access_token,
            "token_type": "bearer",
        }

    # =====================================================
    # Change Password
    # =====================================================

    def change_password(
        self, db: Session, user: User, request: ChangePasswordRequest
    ) -> Dict[str, Any]:

        try:
            if not verify_password(request.current_password, user.password_hash):
                return {"success": False, "error": "Current password is incorrect."}

            user.password_hash = hash_password(request.new_password)

            db.add(user)
            db.commit()

            return {"success": True}

        except Exception as e:
            db.rollback()
            logger.exception("Password change failed for user_id=%s", user.id)
            return {"success": False, "error": str(e)}

    # =====================================================
    # Forgot Password (Phase 1: structure only)
    #
    # No OTP/email is sent yet, per Phase 1 scope. This method exists so
    # the route layer, and any future background job or email service,
    # has a stable integration point to build on - implementing the real
    # OTP/reset-link flow later only needs to fill in the TODO below,
    # with no route or schema changes required.
    # =====================================================

    def request_password_reset(self, db: Session, email: str) -> Dict[str, Any]:

        user = self.get_user_by_email(db, email)

        # TODO (future phase): if user exists, generate a signed reset
        # token / OTP, store it (with expiry) against user.id, and send it
        # via an email service. Intentionally not implemented in Phase 1.
        if user:
            logger.info(
                "Password reset requested for existing user_id=%s "
                "(no email sent - Phase 1 placeholder only).",
                user.id,
            )

        # Always return the same generic response regardless of whether the
        # email exists - standard practice to avoid leaking which emails
        # are registered.
        return {
            "success": True,
            "message": (
                "If this email is registered, password reset instructions "
                "will be sent. (Feature not yet available - coming in a "
                "future update.)"
            ),
        }


auth_service = AuthService()