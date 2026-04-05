"""Configuration management for Gold Dashboard."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    db_path: Path = Path(__file__).parent / "alerts.db"

    # Intervals (seconds)
    news_refresh_interval: int = 300  # 5 minutes
    price_sync_interval: int = 300  # 5 minutes
    briefing_interval: int = 3600  # 1 hour

    # API
    frontend_path: Path = Path(__file__).parent.parent / "frontend"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
