from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ourtdev API"
    app_env: str = "development"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ourtdev"

    secret_key: str = "change-me-to-a-long-random-secret"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    # Clé Fernet (url-safe base64 32 bytes). En prod: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    mfa_encryption_key: str = "dev-only-replace-with-fernet-key-32b!!"

    default_language: str = "fr"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    frontend_url: str = "http://localhost:3000"

    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/api/v1/auth/oauth/github/callback"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/oauth/google/callback"

    media_root: str = "./storage"
    media_base_url: str = "http://localhost:8000/media"


@lru_cache
def get_settings() -> Settings:
    return Settings()
