# Do Not Call List Manager - Backend

## Database and Migrations (Azure-ready)

This backend is now structured for multi-tenant, production use with Alembic migrations.

### Core Entities
- Organizations, Users, OrgUser (membership)
- ServiceCatalog (global), OrgService (per-tenant connection/credentials)
- DNCEntry (authoritative per-tenant list with reason/source/actor)
- RemovalJob and RemovalJobItem (batch submissions)
- PropagationAttempt (per-service update attempts, status/response/error)

### Environment
- DATABASE_URL: set to your Azure SQL/Postgres URL.

### Alembic
Commands run from `backend/`:

```bash
# create new revision from current models
./migrate.sh revision "initial multi-tenant schema"

# apply migrations
./migrate.sh upgrade
```

### First-time setup
1) Set `DATABASE_URL` in environment (or `.env`).
2) Run `./migrate.sh upgrade` to create tables.

FastAPI backend for the Do Not Call List Management application.

## Features

- Phone number management and validation
- CRM system integrations (TrackDrive, EverySource)
- Consent management
- Comprehensive reporting and analytics
- Real-time status tracking

## Quick Start

```bash
# Install dependencies
poetry install

# Start development server
poetry run python server.py
```

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc





