from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Centralized application configuration, loaded from environment
    variables (and a local .env file if present via python-dotenv, which
    is already a project dependency).

    This is a NEW file - the project had no config.py before. Only the
    Authentication module currently reads from it; other modules are
    untouched and keep working exactly as they did.
    """

    # -------------------------------------------------
    # JWT Authentication
    # -------------------------------------------------

    JWT_SECRET_KEY: str = "CHANGE_THIS_SECRET_KEY_IN_PRODUCTION_ENV_FILE"

    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # -------------------------------------------------
    # Temporary Auth Bypass Switch
    #
    # Defaults to True (auth fully enforced, current behavior unchanged).
    # Set AUTH_ENABLED=false in .env to temporarily disable authentication
    # across EVERY protected route in EVERY module in one place (see
    # app/dependencies.py) - no route files need to change either way.
    #
    # WARNING: when False, every request (with or without a token) is
    # treated as the same shared placeholder user. There is NO real
    # access control in this mode - local/solo dev use only, never on
    # anything publicly reachable. Revert to true (or remove the line
    # from .env) to restore normal authentication.
    # -------------------------------------------------

    AUTH_ENABLED: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()