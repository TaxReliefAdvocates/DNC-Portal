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
      unixodbc \
      unixodbc-dev \
      libpq-dev && \
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


