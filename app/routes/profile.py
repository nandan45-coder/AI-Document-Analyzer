from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.profile import (
    ProfileImageResponse,
    ProfileUpdateRequest,
    ProfileUpdateResponse,
)
from app.services.profile_service import profile_service


router = APIRouter(
    prefix="/profile",
    tags=["User Profile"],
)


# =====================================================
# Edit Profile
#
# No GET /profile endpoint here - Phase 1's GET /auth/me already returns
# the same information (it's populated directly at registration), so a
# separate profile-retrieval endpoint would just be a duplicate.
# =====================================================

@router.put(
    "",
    response_model=ProfileUpdateResponse,
)
def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = profile_service.update_profile(db, current_user, request)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    if result.get("no_changes"):
        return {
            "success": True,
            "message": "No changes detected.",
            "profile": result["user"],
        }

    return {
        "success": True,
        "message": "Profile updated successfully.",
        "profile": result["user"],
    }


# =====================================================
# Upload / Replace Profile Picture
# =====================================================

@router.post(
    "/upload-image",
    response_model=ProfileImageResponse,
)
def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = profile_service.upload_profile_image(db, current_user, file)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    profile_image = result["user"].profile_image
    url = f"/{profile_image}" if profile_image and not profile_image.startswith("/") else profile_image

    return {
        "success": True,
        "message": "Profile picture uploaded successfully.",
        "profile_image": url,
    }


# =====================================================
# Remove Profile Picture
# =====================================================

@router.delete(
    "/remove-image",
    response_model=ProfileImageResponse,
)
def remove_image(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = profile_service.remove_profile_image(db, current_user)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    return {
        "success": True,
        "message": "Profile picture removed successfully.",
        "profile_image": None,
    }