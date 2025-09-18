from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from loguru import logger
from typing import Generator

from ..config import settings

# Optional: Azure AD token auth for Postgres
_USE_AAD_DB = False
try:
    import msal  # type: ignore
    _USE_AAD_DB = bool(
        settings.DATABASE_URL.startswith("postgresql") and
        bool(getattr(settings, "AZURE_DB_TENANT_ID", None)) and
        bool(getattr(settings, "AZURE_DB_CLIENT_ID", None)) and
        bool(getattr(settings, "AZURE_DB_CLIENT_SECRET", None))
    )
except Exception:
    _USE_AAD_DB = False

_aad_token_cache = {"token": None, "expires_at": 0}

def _get_aad_access_token() -> str:
    from time import time
    if _aad_token_cache.get("token") and time() < float(_aad_token_cache.get("expires_at", 0)) - 60:
        return str(_aad_token_cache["token"])
    app = msal.ConfidentialClientApplication(
        getattr(settings, "AZURE_DB_CLIENT_ID", ""),
        authority=f"https://login.microsoftonline.com/{getattr(settings, 'AZURE_DB_TENANT_ID', '')}",
        client_credential=getattr(settings, "AZURE_DB_CLIENT_SECRET", ""),
    )
    scopes = ["https://ossrdbms-aad.database.windows.net/.default"]
    result = app.acquire_token_for_client(scopes=scopes)
    if not result or "access_token" not in result:
        raise RuntimeError(f"AAD token acquisition failed: {result}")
    _aad_token_cache["token"] = result["access_token"]
    _aad_token_cache["expires_at"] = float(result.get("expires_in", 3600)) + time()
    return str(result["access_token"])

# Create database engine with production-safe defaults
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # Enable pre_ping to avoid stale connections (Supabase/Azure)
    if _USE_AAD_DB:
        # Use creator hook to inject AAD access token as password on each connect
        import urllib.parse
        from sqlalchemy.engine import URL
        from psycopg2 import connect as pg_connect  # type: ignore

        parsed = urllib.parse.urlparse(settings.DATABASE_URL)
        user = urllib.parse.unquote(parsed.username or "")
        host = parsed.hostname or ""
        port = parsed.port or 5432
        dbname = (parsed.path or "/postgres").lstrip("/") or "postgres"
        sslmode = "require"

        def _creator():
            pwd = _get_aad_access_token()
            dsn = f"host={host} port={port} dbname={dbname} user={user} password={pwd} sslmode={sslmode}"
            return pg_connect(dsn)

        engine = create_engine(
            "postgresql+psycopg2://",
            pool_pre_ping=True,
            pool_recycle=1200,
            creator=_creator,
        )
    else:
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=1800,  # recycle every 30 minutes
        )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db() -> Generator:
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def init_db():
    """Initialize database tables"""
    try:
        # Import all models to ensure they are registered in SQLAlchemy metadata
        from .models import (
            PhoneNumber,
            CRMStatus,
            Consent,
            AuditLog,
            APIRateLimit,
            Organization,
            User,
            OrgUser,
            ServiceCatalog,
            OrgService,
            DNCEntry,
            RemovalJob,
            RemovalJobItem,
            PropagationAttempt,
            SMSOptOut,
            DNCRequest,
            CRMDNCSample,
            LitigationRecord,
            SystemSetting,
            IntegrationTestResult,
        )
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


async def close_db():
    """Close database connections"""
    try:
        engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


def create_tables():
    """Create database tables (synchronous version for CLI)"""
    try:
        # Import all models to ensure they are registered in SQLAlchemy metadata
        from .models import (
            PhoneNumber,
            CRMStatus,
            Consent,
            AuditLog,
            APIRateLimit,
            Organization,
            User,
            OrgUser,
            ServiceCatalog,
            OrgService,
            DNCEntry,
            RemovalJob,
            RemovalJobItem,
            PropagationAttempt,
            SMSOptOut,
            DNCRequest,
            CRMDNCSample,
            LitigationRecord,
            SystemSetting,
            IntegrationTestResult,
        )
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        raise





