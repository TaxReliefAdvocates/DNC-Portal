from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from loguru import logger
from typing import Generator
import os

from ..config import settings

# Construct DATABASE_URL from individual PostgreSQL environment variables if they exist
def get_database_url():
    """Get database URL, preferring individual PG env vars over DATABASE_URL"""
    # Temporary hardcoded connection that we know works
    # We'll revert this once we debug the environment variable issue
    hardcoded_url = "postgresql+psycopg2://traadmin:TPSZen2025%40%21@dnc.postgres.database.azure.com:5432/postgres?sslmode=require"
    logger.info("Using temporary hardcoded database connection")
    return hardcoded_url
    
    # Check if individual PostgreSQL environment variables are set
    pg_vars = ['PGHOST', 'PGUSER', 'PGPASSWORD', 'PGDATABASE']
    missing_vars = [var for var in pg_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.info(f"Missing PG environment variables: {missing_vars}, falling back to DATABASE_URL")
        return settings.DATABASE_URL
    
    host = os.getenv('PGHOST')
    user = os.getenv('PGUSER')
    password = os.getenv('PGPASSWORD')
    database = os.getenv('PGDATABASE')
    port = os.getenv('PGPORT', '5432')
    
    # Construct URL with explicit password authentication
    db_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}?sslmode=require"
    logger.info(f"Using PG environment variables to connect to {host}:{port}/{database}")
    return db_url

# Create database engine with production-safe defaults
database_url = get_database_url()
if database_url.startswith("sqlite"):
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # Standard PostgreSQL connection
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





