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
    
    # CRM API Keys - Updated for new systems
    LOGICS_API_KEY: Optional[str] = None
    LOGICS_BASE_URL: str = "https://api.logics.com"
    
    GENESYS_API_KEY: Optional[str] = None
    GENESYS_BASE_URL: str = "https://api.genesys.com"
    
    RINGCENTRAL_API_KEY: Optional[str] = None
    RINGCENTRAL_BASE_URL: str = "https://platform.ringcentral.com"
    RINGCENTRAL_ACCESS_TOKEN: Optional[str] = None
    RINGCENTRAL_JWT_TOKEN: Optional[str] = None
    RINGCENTRAL_ACCOUNT_ID: str = "~"  # use ~ for current
    RINGCENTRAL_EXTENSION_ID: str = "~"  # use ~ for current
    # OAuth app credentials
    RINGCENTRAL_CLIENT_ID: Optional[str] = None
    RINGCENTRAL_CLIENT_SECRET: Optional[str] = None
    RINGCENTRAL_REDIRECT_URI: Optional[str] = None
    
    CONVOSO_API_KEY: Optional[str] = None
    CONVOSO_BASE_URL: str = "https://api.convoso.com"
    CONVOSO_AUTH_TOKEN: Optional[str] = None
    
    YTEL_API_KEY: Optional[str] = None
    YTEL_BASE_URL: str = "https://api.ytel.com"
    # Legacy/non-agent endpoint used to add to Ytel DNC list
    YTEL_NON_AGENT_URL: str = "https://tra.ytel.com/x5/api/non_agent.php"
    YTEL_USER: Optional[str] = None
    YTEL_PASS: Optional[str] = None
    YTEL_CAMPAIGN: str = "1000"
    YTEL_ADD_TO_DNC: str = "BOTH"  # NONE | CAMPAIGN | GLOBAL | BOTH
    # Modern v4 API
    YTEL_V4_BASE_URL: str = "https://api.ytel.com/api/v4"
    YTEL_BEARER_TOKEN: Optional[str] = None
    YTEL_SELECTOR_DEFAULT: str = "CUSTOMER_GLOBAL"
    
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
    ALLOWED_FILE_TYPES: List[str] = [".csv"]  # Only CSV for DNC processing
    
    # Federal DNC API
    FCC_API_KEY: Optional[str] = None
    FCC_API_URL: str = "https://www.donotcall.gov/api/check"
    
    # SQL Server Database (TPS2)
    TPS_DB_SERVER: str = "69.65.24.35"
    TPS_DB_NAME: str = "tps2"
    TPS_DB_USER: str = "tpsuser"
    TPS_DB_PASSWORD: str = "TPSZen2025@!"
    TPS_DB_DRIVER: str = "ODBC Driver 17 for SQL Server"
    TPS_DB_TRUST_CERT: bool = True

    # TPS Public API
    TPS_API_KEY: Optional[str] = None
    TPS_API_VERIFY_SSL: bool = True
    # Some deployments require Basic auth header for V3 endpoints
    TPS_API_BASIC_AUTH: Optional[str] = None  # e.g. "Basic base64(user:pass)"

    # Entra ID / Microsoft Identity Platform
    ENTRA_TENANT_ID: Optional[str] = None
    ENTRA_AUDIENCE: Optional[str] = None  # Application (client) ID or API audience
    ENTRA_ISSUER: Optional[str] = None    # Optional explicit issuer override
    ENTRA_JWKS_URL: Optional[str] = None  # Optional explicit JWKS URL
    ENTRA_REQUIRE_SIGNATURE: bool = False # Enable signature validation in production
    
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
