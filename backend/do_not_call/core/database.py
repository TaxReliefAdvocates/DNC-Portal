from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from loguru import logger
from typing import Generator

from ..config import settings

# Create database engine with production-safe defaults
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # Standard PostgreSQL connection
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





