from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
from loguru import logger
from .core.logging_middleware import JsonRequestLogger

from .config import settings
from .api.v1 import phone_numbers, crm_integrations, consent, reports, dnc_processor, free_dnc_api, tenants, cron
# Provider routers removed per scope reduction (keep only FreeDNC & Postgres-backed endpoints)
from .core.database import SessionLocal
from .core.database import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Do Not Call List Manager API...")
    await init_db()

    
    yield
    
    # Shutdown
    logger.info("Shutting down Do Not Call List Manager API...")
    await close_db()
    logger.info("Database connection closed")


app = FastAPI(
    title="Do Not Call List Manager API",
    description="""
    Comprehensive API for managing phone number removals from Do Not Call lists across multiple CRM systems.
    
    ## Features
    
    * **Phone Number Management**: Add, update, and track phone numbers for removal
    * **CRM Integration**: Support for Logics, Genesys, Ring Central, Convoso, and Ytel CRM systems
    * **DNC Processing**: Bulk CSV processing for Do Not Call list checking
    * **FreeDNCList.com API**: Replicates the exact workflow of FreeDNCList.com for DNC checking
    * **Consent Management**: Track and manage messaging consent
    * **Real-time Status**: Monitor removal progress across all systems
    * **Reporting**: Analytics and audit trails
    * **Bulk Processing**: Handle multiple phone numbers efficiently
    
    ## Authentication
    
    This API uses API key authentication. Include your API key in the header:
    ```
    X-API-Key: your-api-key-here
    ```
    
    ## Rate Limiting
    
    API requests are rate limited to prevent abuse. Current limits:
    - 100 requests per minute per API key
    - 1000 requests per hour per API key
    
    ## Error Handling
    
    The API returns standard HTTP status codes:
    - `200`: Success
    - `400`: Bad Request
    - `401`: Unauthorized
    - `403`: Forbidden
    - `404`: Not Found
    - `429`: Too Many Requests
    - `500`: Internal Server Error
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
# Correlation-ID middleware and JSON logging hint
@app.middleware("http")
async def add_correlation_id(request, call_next):
    cid = request.headers.get("X-Correlation-Id")
    if not cid:
        import uuid
        cid = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = cid
    return response


# Structured JSON request logging
app.add_middleware(JsonRequestLogger)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=None,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-Id"]
)

# Include API routers
app.include_router(
    phone_numbers.router,
    prefix="/api/v1/phone-numbers",
    tags=["Phone Numbers"],
    responses={404: {"description": "Not found"}},
)

app.include_router(
    crm_integrations.router,
    prefix="/api/v1",
    responses={404: {"description": "Not found"}},
)

# (intentionally not mounting provider routers)

app.include_router(
    consent.router,
    prefix="/api/v1/consent",
    tags=["Consent Management"],
    responses={404: {"description": "Not found"}},
)

app.include_router(
    reports.router,
    prefix="/api/v1/reports",
    tags=["Reports & Analytics"],
    responses={404: {"description": "Not found"}},
)

app.include_router(
    dnc_processor.router,
    prefix="/api/v1/dnc",
    tags=["DNC Processing"],
    responses={404: {"description": "Not found"}},
)

app.include_router(
    free_dnc_api.router,
    prefix="/api",
    tags=["FreeDNCList.com API"],
    responses={404: {"description": "Not found"}},
)

app.include_router(
    tenants.router,
    prefix="/api/v1/tenants",
    tags=["Tenants & DNC"],
    responses={404: {"description": "Not found"}},
)

app.include_router(
    cron.router,
    prefix="/api/v1/cron",
    tags=["Scheduled Jobs"],
    responses={404: {"description": "Not found"}},
)

@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "Welcome to the Do Not Call List Manager API",
        "version": "1.0.0",
        "status": "healthy",
        "docs": "/docs"
    }

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}

# Custom OpenAPI description block

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description="""
        Comprehensive API for managing phone number removals from Do Not Call lists across multiple CRM systems.
        
        ## Key Features
        
        ### Phone Number Management
        - Bulk phone number processing
        - Real-time validation and formatting
        - Status tracking across all CRM systems
        
        ### CRM Integration
        - Logics CRM system integration
        - Genesys contact center platform
        - Ring Central communication platform
        - Convoso dialer platform
        - Ytel communication platform
        - Extensible architecture for additional CRM systems
        - Rate limiting and error handling
        
        ### DNC Processing
        - CSV file upload and processing
        - Bulk phone number validation
        - Federal DNC list checking
        - Batch processing for large files
        
        ### Consent Management
        - Consent status tracking
        - Audit trail and history
        - Compliance validation
        
        ### Reporting & Analytics
        - Removal success rates
        - Processing time analytics
        - Error rate tracking
        - Export functionality
        
        ## Authentication
        
        This API uses API key authentication. Include your API key in the header:
        ```
        X-API-Key: your-api-key-here
        ```
        
        ## Rate Limiting
        
        API requests are rate limited to prevent abuse:
        - 100 requests per minute per API key
        - 1000 requests per hour per API key
        
        ## Error Codes
        
        | Code | Description |
        |------|-------------|
        | 400 | Bad Request - Invalid input data |
        | 401 | Unauthorized - Missing or invalid API key |
        | 403 | Forbidden - Insufficient permissions |
        | 404 | Not Found - Resource not found |
        | 429 | Too Many Requests - Rate limit exceeded |
        | 500 | Internal Server Error - Server error |
        
        ## Examples
        
        ### Adding Phone Numbers
        ```bash
        curl -X POST "http://localhost:8000/api/v1/phone-numbers/bulk" 
        ```
        
        ### Checking CRM Status
        ```bash
        curl -X GET "http://localhost:8000/api/v1/status/5551234567" 
        ```
        
        ### Getting Reports
        ```bash
        curl -X GET "http://localhost:8000/api/v1/reports/removal-stats" 
        ```
        """,
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


if __name__ == "__main__":
    uvicorn.run(
        "do_not_call.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )




