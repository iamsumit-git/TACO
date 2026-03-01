"""
app/config.py — Environment variable settings using pydantic-settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:tacopassword@localhost:5432/taco"

    # LLM Provider keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Routing
    slice_window: int = 10
    default_cheap_model: str = "gpt-4o-mini"
    default_smart_model: str = "gpt-4o"

    # App metadata
    app_version: str = "0.1.0"


# Singleton settings instance
settings = Settings()
