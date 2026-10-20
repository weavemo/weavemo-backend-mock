# config/settings.py

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Environment
    ENV: str = Field(default="local")

    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str

    # JWT
    SUPABASE_JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # Web Push
    VAPID_PRIVATE_KEY: str = ""
    VAPID_PUBLIC_KEY: str = ""
    VAPID_SUBJECT: str = ""

    model_config = SettingsConfigDict(
        env_file=(
            BACKEND_DIR / ".env",
            BACKEND_DIR / ".env.webpush",
        ),
        env_file_encoding="utf-8",
        extra="forbid",
    )


settings = Settings()
