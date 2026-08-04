from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.auth_service import auth_service
from app.utils.jwt_handler import (
    TokenExpiredError,
    TokenInvalidError,
    decode_access_token,
)

# HTTPBearer (rather than OAuth2PasswordBearer) gives Swagger's "Authorize"
# button a single "paste your token" field - OAuth2PasswordBearer instead
# renders a username/password form that submits as
# application/x-www-form-urlencoded, which doesn't match our JSON-based
# /auth/login and would never actually work from that dialog. This change
# only affects how the token is read out of the Authorization header for
# docs/testing convenience - get_current_user's behavior is unchanged.
#
# auto_error=False (not True) is required to support the AUTH_ENABLED
# bypass below - when auth is disabled, requests may have no
# Authorization header at all, and that must not raise before this
# function's body even runs.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Reusable authentication dependency. Every protected route in every
    module goes through this ONE function - which is exactly why
    AUTH_ENABLED (app/config.py) can disable authentication everywhere at
    once from a single place, with zero changes needed in profile.py,
    dashboard.py, resume.py, govt_document.py, or any future module.
    """

    # -------------------------------------------------
    # TEMPORARY BYPASS - see AUTH_ENABLED in app/config.py.
    # Every request, regardless of what (if any) token it sends, is
    # treated as the same shared placeholder user. No real
    # authentication or access control happens in this branch.
    # -------------------------------------------------
    if not settings.AUTH_ENABLED:
        return auth_service.get_or_create_placeholder_user(db)

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)

    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except TokenInvalidError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_service.get_user_by_id(db, int(user_id))

    if user is None:
        # Token is structurally valid but the user no longer exists
        # (e.g. deleted account) - treat as unauthorized, don't leak detail.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """
    Like get_current_user, but with two differences:

    1. NEVER raises 401 - falls back to a shared placeholder user instead
       of blocking the request when no valid token is present.

    2. Does NOT show authorization input box in Swagger/OpenAPI docs.

    - Valid "Bearer <token>" header present -> returns the REAL
      authenticated user.
    - No header / malformed header / invalid / expired token -> silently
      falls back to the shared placeholder user.
    """

    authorization = request.headers.get("Authorization") or request.headers.get("authorization")

    if authorization:
        scheme, _, token = authorization.partition(" ")

        if scheme.lower() == "bearer" and token:
            try:
                payload = decode_access_token(token)
                user_id = payload.get("sub")

                if user_id is not None:
                    user = auth_service.get_user_by_id(db, int(user_id))
                    if user is not None:
                        return user

            except (TokenExpiredError, TokenInvalidError):
                pass  # fall through to placeholder below

    return auth_service.get_or_create_placeholder_user(db)