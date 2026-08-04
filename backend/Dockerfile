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
# Bundled sample sets — without these GET /samples returns [] and the UI has no cards.
COPY data ./data
# The `openai` extra ships the real provider; LLM_PROVIDER=openai fails to import without it.
RUN uv pip install --system ".[openai]"

EXPOSE 8000
# PaaS platforms (Railway, Render, Fly) inject $PORT and route to it; fall back to
# 8000 for local `docker run` and docker-compose.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
