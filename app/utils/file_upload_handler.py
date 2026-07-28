import logging
import os
import uuid
from typing import Tuple

from fastapi import UploadFile

logger = logging.getLogger("profile_module")


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def validate_image_file(file: UploadFile, content: bytes) -> Tuple[bool, str]:
    """
    Validates an uploaded image against extension, content-type, and size
    rules. Returns (is_valid, reason) - reason is empty when is_valid.
    """

    if len(content) == 0:
        return False, "Uploaded file is empty."

    extension = os.path.splitext(file.filename or "")[1].lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return False, (
            f"Unsupported file type '{extension or 'unknown'}'. "
            f"Allowed formats: JPG, JPEG, PNG, WEBP."
        )

    if file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        return False, f"Unsupported content type '{file.content_type}'."

    if len(content) > MAX_IMAGE_SIZE_BYTES:
        return False, (
            f"Image exceeds the maximum allowed size of "
            f"{MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB."
        )

    return True, ""


def save_image_file(file: UploadFile, content: bytes, directory: str) -> str:
    """
    Saves image bytes under `directory` with a UUID-generated filename
    (preserving the original extension), creating the directory if it
    doesn't exist yet. Returns the relative path using forward slashes
    ONLY (never os.path.join) so the stored value is safe to reuse
    directly as a URL path on any OS, including Windows.
    """

    os.makedirs(directory, exist_ok=True)

    extension = os.path.splitext(file.filename or "")[1].lower()
    unique_name = f"{uuid.uuid4().hex}{extension}"

    relative_path = f"{directory}/{unique_name}"

    with open(relative_path, "wb") as f:
        f.write(content)

    return relative_path


def delete_image_file(relative_path: str) -> None:
    """
    Deletes a previously-saved image file if it exists. Never raises -
    a missing/already-deleted file is not an error worth failing the
    calling operation over (e.g. replacing a profile picture should
    still succeed even if the old file was somehow already gone).
    """

    if not relative_path:
        return

    try:
        if os.path.exists(relative_path):
            os.remove(relative_path)
    except OSError:
        logger.warning("Could not delete image file: %s", relative_path)