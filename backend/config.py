"""Configuration management for Gold Dashboard."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    db_path: Path = Path(__file__).parent / "alerts.db"

    # Intervals (seconds)
    news_refresh_interval: int = 300  # 5 minutes

    # API
    frontend_path: Path = Path(__file__).parent.parent / "frontend"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_cors_origins(self) -> list[str]:
        """Get CORS origins from env var (comma-separated) or fallback to defaults."""
        raw = os.getenv("CORS_ORIGINS", "")
        if raw:
            return [o.strip() for o in raw.split(",") if o.strip()]
        # Fallback: allow frontend dev/prod if env var not set
        return ["http://localhost:3000", "http://localhost:8000"]


settings = Settings()
