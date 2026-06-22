# API image for the FastAPI app. Postgres/pgvector run via docker-compose.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install uv for fast, reproducible installs.
RUN pip install --no-cache-dir uv

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY filing_reconciler ./filing_reconciler
COPY app ./app
RUN uv pip install --system .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
