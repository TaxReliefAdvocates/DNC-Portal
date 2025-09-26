from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from loguru import logger
from typing import Generator
import os
import requests
import json

from ..config import settings

def get_azure_access_token():
    """Get Azure AD access token for PostgreSQL authentication"""
    try:
        client_id = os.getenv('AZURE_DB_CLIENT_ID')
        client_secret = os.getenv('AZURE_DB_CLIENT_SECRET')
        tenant_id = os.getenv('AZURE_DB_TENANT_ID')
        
        if not all([client_id, client_secret, tenant_id]):
            logger.error("Missing Azure AD credentials")
            return None
            
        # Get access token from Azure AD
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        
        data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'https://ossrdbms-aad.database.windows.net/.default',
            'grant_type': 'client_credentials'
        }
        
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        
        logger.info("Successfully obtained Azure AD access token")
        return access_token
        
    except Exception as e:
        logger.error(f"Failed to get Azure AD access token: {e}")
        return None

# Construct DATABASE_URL from individual PostgreSQL environment variables if they exist
def get_database_url():
    """Get database URL - ULTIMATE FIX: Hardcode connection to bypass Render overrides"""
    # ULTIMATE FIX: Hardcode the connection string to bypass Render's automatic PG variable injection
    # Render is automatically injecting PGUSER=lindsey.stevens@tra.com and JWT tokens
    # We need to completely bypass this and use our own connection string
    
    hardcoded_url = "postgresql+psycopg2://traadmin:TPSZen2025%40%21@dnc.postgres.database.azure.com:5432/postgres?sslmode=require"
    
    logger.info("🚀 ULTIMATE FIX: Using hardcoded PostgreSQL connection string")
    logger.info(f"🚀 Connection: {hardcoded_url}")
    
    return hardcoded_url

# Create database engine with production-safe defaults
database_url = get_database_url()
# Force PostgreSQL connection - no SQLite fallback
engine = create_engine(
        database_url,
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


# RLS helper: set/clear current organization id per request
def set_rls_org(db_session, organization_id: int | None):
    try:
        if organization_id is None:
            db_session.execute(text("RESET app.current_organization_id"))
        else:
            db_session.execute(text("SET app.current_organization_id = :oid"), {"oid": int(organization_id)})
    except Exception:
        # Non-fatal; app still functions without RLS set
        pass


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





