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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()