import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

from app.config import settings


class TokenExpiredError(Exception):
    """Raised when a JWT has expired. Kept distinct from TokenInvalidError
    so the auth dependency can return a precise, meaningful error message
    ("Token expired" vs "Invalid token") as required."""
    pass


class TokenInvalidError(Exception):
    """Raised for any malformed/tampered/wrong-signature token."""
    pass


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Creates a signed JWT access token.

    `data` should contain at minimum {"sub": <user_id as str>}. A unique
    "jti" (JWT ID) claim is always embedded, even though token blacklisting
    isn't implemented yet - this is a deliberate forward-compatibility
    choice: adding real blacklist support later (Redis/DB-backed) only
    needs to start checking this existing claim, with no token-schema
    change and no re-issuing of tokens for already-logged-in users.
    """

    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    })

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT access token.

    Raises:
        TokenExpiredError: if the token's expiry has passed.
        TokenInvalidError: for any other decoding/validation failure
            (bad signature, malformed token, wrong algorithm, etc.).
    """

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token has expired.")

    except jwt.InvalidTokenError:
        raise TokenInvalidError("Token is invalid.")