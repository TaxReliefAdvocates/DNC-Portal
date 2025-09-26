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
    """Get database URL - fix PostgreSQL connection properly"""
    # Use the DATABASE_URL from environment variables
    if os.getenv('DATABASE_URL'):
        database_url = os.getenv('DATABASE_URL')
        logger.info(f"Using DATABASE_URL from environment variables: {database_url}")
        return database_url
    
    # Try to construct from individual PG variables
    pg_host = os.getenv('PGHOST')
    pg_user = os.getenv('PGUSER')
    pg_password = os.getenv('PGPASSWORD')
    pg_database = os.getenv('PGDATABASE')
    pg_port = os.getenv('PGPORT', '5432')
    pg_sslmode = os.getenv('PGSSLMODE', 'require')
    
    if all([pg_host, pg_user, pg_password, pg_database]):
        # URL encode the password
        import urllib.parse
        encoded_password = urllib.parse.quote_plus(pg_password)
        database_url = f"postgresql+psycopg2://{pg_user}:{encoded_password}@{pg_host}:{pg_port}/{pg_database}?sslmode={pg_sslmode}"
        logger.info(f"Constructed DATABASE_URL from individual PG environment variables: {database_url}")
        return database_url
    
    # Fallback to settings
    logger.info("Falling back to DATABASE_URL from settings")
    return settings.DATABASE_URL

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





