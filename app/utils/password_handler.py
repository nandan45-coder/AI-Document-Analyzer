import re
from typing import Tuple

import bcrypt


# =====================================================
# Password Hashing
#
# Uses bcrypt directly rather than Passlib. Passlib's bcrypt backend has
# known compatibility issues with bcrypt>=4.1 (it depends on a removed
# `bcrypt.__about__` attribute), and this project already has
# bcrypt==5.0.0 installed - using it directly avoids that entirely instead
# of adding a second dependency with a known conflict.
# =====================================================

def hash_password(plain_password: str) -> str:
    """
    Hashes a plain-text password for storage. Never store plain_password
    anywhere - only the returned hash.
    """

    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)

    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Verifies a plain-text password against a stored bcrypt hash.
    Returns False (never raises) on any malformed-hash edge case, so a
    corrupted/legacy hash fails safe instead of crashing the login flow.
    """

    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


# =====================================================
# Password Strength Validation
#
# Kept as a standalone, importable function (rather than only inline in a
# Pydantic validator) so both app/schemas/auth.py (registration/change
# password) and any future caller can reuse the exact same rule set
# without duplicating it.
# =====================================================

MIN_PASSWORD_LENGTH = 8


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Returns (is_valid, reason). reason is empty when is_valid is True.

    Minimum security requirements enforced:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """

    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."

    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."

    if not re.search(r"[!@#$%^&*()\-_=+\[\]{};:'\",.<>/?\\|`~]", password):
        return False, "Password must contain at least one special character."

    return True, ""