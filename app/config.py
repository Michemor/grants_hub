# app/config.py
"""
Application configuration using Pydantic Settings for validation.
"""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    Application settings with validation.

    Environment variables are automatically loaded from .env file
    and validated at application startup.
    """

    # Supabase Configuration
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_key: str = Field(..., description="Supabase API key")

    # API Keys
    serp_api: Optional[str] = Field(None, description="SerpAPI key for web scraping")
    gemini_api_key: Optional[str] = Field(None, description="Google Gemini API key")

    # Application Settings
    allowed_origins: str = Field(
        default="*", description="CORS allowed origins (comma-separated)"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Pipeline Settings
    max_deadline_days: int = Field(
        default=365, description="Maximum days ahead for grant deadlines"
    )
    relevance_threshold: int = Field(
        default=2, description="Minimum relevance score for grants"
    )
    ai_rate_limit_seconds: int = Field(
        default=5, description="Seconds between AI API calls"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()
