"""
PS69 Weather Analytics - Phase 5: Configuration
Load environment variables and expose configuration
"""

import os
from functools import lru_cache
from typing import Optional

class Settings:
    """Application settings from environment variables."""
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://ps69_admin:ps69_password_dev@localhost:5432/ps69_weather"
    )
    SQLALCHEMY_ECHO: bool = os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true"
    
    # JWT / Auth
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev_secret_change_in_production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
    REFRESH_TOKEN_EXPIRATION_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRATION_DAYS", "7"))
    
    # FastAPI
    FASTAPI_ENV: str = os.getenv("FASTAPI_ENV", "development")
    FASTAPI_DEBUG: bool = os.getenv("FASTAPI_DEBUG", "true").lower() == "true"
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # CORS
    CORS_ORIGINS: list = [
        origin.strip() 
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:8000"
        ).split(",")
    ]
    
    # Phase 1-4C Pipeline paths
    PHASE1_DATA_PATH: str = os.getenv("PHASE1_DATA_PATH", "./data/raw/")
    PHASE3A_REPORTS_JSON: str = os.getenv(
        "PHASE3A_REPORTS_JSON",
        "./data/phase3/processed/all_weather_reports.json"
    )
    
    # Feature flags
    ENABLE_SOCIAL_FIXTURE_INGESTION: bool = os.getenv(
        "ENABLE_SOCIAL_FIXTURE_INGESTION", "true"
    ).lower() == "true"
    ENABLE_ALERT_DELIVERY: bool = os.getenv("ENABLE_ALERT_DELIVERY", "true").lower() == "true"
    ALERT_CONSOLE_LOG: bool = os.getenv("ALERT_CONSOLE_LOG", "true").lower() == "true"
    
    # Profiling
    ENABLE_PROFILING: bool = os.getenv("ENABLE_PROFILING", "false").lower() == "true"
    
    def __init__(self):
        """Validate settings on initialization."""
        if not self.JWT_SECRET or self.JWT_SECRET == "dev_secret_change_in_production":
            if self.FASTAPI_ENV == "production":
                raise ValueError("JWT_SECRET must be set in production")
    
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.FASTAPI_ENV.lower() == "production"
    
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.FASTAPI_ENV.lower() == "development"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_database_url() -> str:
    """Get database URL, converting SQLite-style URLs to async if needed."""
    settings = get_settings()
    url = settings.DATABASE_URL
    
    # Ensure we're using postgresql (not sqlite)
    if "sqlite" in url.lower():
        raise ValueError(
            "Phase 5 MVP requires PostgreSQL + PostGIS. "
            "SQLite is not supported. "
            f"Current DATABASE_URL: {url}"
        )
    
    return url

