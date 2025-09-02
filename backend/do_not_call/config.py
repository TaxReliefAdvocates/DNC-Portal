from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Do Not Call List Manager"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "sqlite:///./do_not_call.db"
    
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Do Not Call List Manager API"
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]
    
    # Security
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # CRM API Keys
    TRACKDRIVE_API_KEY: Optional[str] = None
    TRACKDRIVE_BASE_URL: str = "https://api.trackdrive.com"
    
    EVERYSOURCE_API_KEY: Optional[str] = None
    EVERYSOURCE_BASE_URL: str = "https://api.everysource.com"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Redis (for caching and rate limiting)
    REDIS_URL: str = "redis://localhost:6379"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None
    
    # File Upload
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES: List[str] = [".txt", ".csv", ".xlsx"]
    
    # Processing
    BATCH_SIZE: int = 100
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 5  # seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create settings instance
settings = Settings()

# Update allowed origins from environment if provided
if os.getenv("ALLOWED_ORIGINS"):
    settings.ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
