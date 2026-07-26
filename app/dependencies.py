from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

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
bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Reusable authentication dependency. Every future protected route in
    every future module should only need:

        current_user: User = Depends(get_current_user)

    without re-implementing any JWT logic.
    """

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