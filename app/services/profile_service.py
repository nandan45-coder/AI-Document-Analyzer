import logging
from typing import Any, Dict

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.profile import ProfileUpdateRequest
from app.utils.file_upload_handler import (
    delete_image_file,
    save_image_file,
    validate_image_file,
)

logger = logging.getLogger("profile_module")

PROFILE_IMAGE_DIR = "uploads/profile_images"


class ProfileService:

    # =====================================================
    # Edit Profile
    # =====================================================

    def update_profile(
        self, db: Session, user: User, request: ProfileUpdateRequest
    ) -> Dict[str, Any]:

        try:
            updates: Dict[str, Any] = {}

            # Only fields that are BOTH provided AND actually different
            # from the current value count as a real change - this is what
            # lets the "submit unchanged data" case skip the DB write
            # entirely instead of doing a no-op UPDATE.

            if request.full_name is not None and request.full_name != user.full_name:
                updates["full_name"] = request.full_name

            if request.username is not None and request.username != user.username:
                existing = (
                    db.query(User)
                    .filter(User.username == request.username, User.id != user.id)
                    .first()
                )
                if existing:
                    return {"success": False, "error": "Username already exists."}
                updates["username"] = request.username

            if request.email is not None and request.email != user.email:
                existing = (
                    db.query(User)
                    .filter(User.email == request.email, User.id != user.id)
                    .first()
                )
                if existing:
                    return {"success": False, "error": "Email already exists."}
                updates["email"] = request.email

            if request.mobile is not None and request.mobile != user.mobile:
                existing = (
                    db.query(User)
                    .filter(User.mobile == request.mobile, User.id != user.id)
                    .first()
                )
                if existing:
                    return {"success": False, "error": "Mobile number already exists."}
                updates["mobile"] = request.mobile

            if not updates:
                return {"success": True, "no_changes": True, "user": user}

            for field, value in updates.items():
                setattr(user, field, value)

            db.add(user)
            db.commit()
            db.refresh(user)

            return {"success": True, "no_changes": False, "user": user}

        except Exception as e:
            db.rollback()
            logger.exception("Profile update failed for user_id=%s", user.id)
            return {"success": False, "error": str(e)}

    # =====================================================
    # Upload / Replace Profile Picture
    # =====================================================

    def upload_profile_image(
        self, db: Session, user: User, file: UploadFile
    ) -> Dict[str, Any]:

        try:
            content = file.file.read()

            is_valid, reason = validate_image_file(file, content)

            if not is_valid:
                return {"success": False, "error": reason}

            old_image_path = user.profile_image

            new_path = save_image_file(file, content, PROFILE_IMAGE_DIR)

            user.profile_image = new_path

            db.add(user)
            db.commit()
            db.refresh(user)

            # Delete the OLD file only after the new one is successfully
            # saved and committed - avoids leaving the user with no image
            # at all if something had failed partway through.
            if old_image_path:
                delete_image_file(old_image_path)

            return {"success": True, "user": user}

        except Exception as e:
            db.rollback()
            logger.exception("Profile image upload failed for user_id=%s", user.id)
            return {"success": False, "error": str(e)}

    # =====================================================
    # Remove Profile Picture
    # =====================================================

    def remove_profile_image(self, db: Session, user: User) -> Dict[str, Any]:

        try:
            if not user.profile_image:
                return {"success": False, "error": "No profile picture to remove."}

            old_path = user.profile_image
            user.profile_image = None

            db.add(user)
            db.commit()
            db.refresh(user)

            delete_image_file(old_path)

            return {"success": True, "user": user}

        except Exception as e:
            db.rollback()
            logger.exception("Profile image removal failed for user_id=%s", user.id)
            return {"success": False, "error": str(e)}


profile_service = ProfileService()