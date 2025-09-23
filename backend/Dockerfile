# Render backend Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.7.1 \
    PATH="/root/.local/bin:$PATH"

# System deps for building wheels and pyodbc
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      gcc \
      g++ \
      make \
      curl \
      ca-certificates \
      gnupg \
      apt-transport-https \
      unixodbc \
      unixodbc-dev \
      libpq-dev && \
    # Install Microsoft ODBC Driver 17 for SQL Server (Debian 12, no apt-key)
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/keyrings/microsoft-prod.gpg && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

# Copy dependency files first for better layer caching
COPY pyproject.toml poetry.lock ./

# Install dependencies (no dev), install into system env
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root --only main

# Copy application code
COPY do_not_call ./do_not_call
COPY server.py ./

# Default environment
ENV ENVIRONMENT=production \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

CMD ["python", "server.py"]


