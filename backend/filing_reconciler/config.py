"""Runtime configuration, read from the environment (never hardcode secrets).

Defaults are chosen so the app runs fully offline: deterministic stub LLM and an
in-memory checkpointer. Override via environment variables or a local ``.env``.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import Severity


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM provider -------------------------------------------------------
    # stub   = deterministic, offline, no key (default; used by tests/eval/CI)
    # openai = real GPT via the official openai SDK (OPENAI_API_KEY)
    llm_provider: Literal["stub", "openai"] = "stub"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1"
    openai_judge_model: str = "gpt-4.1-mini"

    # --- Checkpointer -------------------------------------------------------
    checkpointer: Literal["memory", "postgres"] = "memory"
    database_url: str = "postgresql://reconciler:reconciler@localhost:5432/reconciler"
    # Pool bounds when CHECKPOINTER=postgres. Keep max_size under the database's
    # connection limit (managed Postgres tiers cap this aggressively).
    db_pool_min: int = Field(default=2, ge=1)
    db_pool_max: int = Field(default=10, ge=1)

    # --- Content store (raw text kept out of state) -------------------------
    content_store_dir: str = "./.artifacts/content"

    # --- API input sandbox ---------------------------------------------------
    # Documents submitted to ``POST /runs`` must live under this directory. The
    # API reads files off the server's filesystem, so without this bound any
    # caller could exfiltrate arbitrary files (``/proc/self/environ`` → secrets).
    # Relative values resolve against the process CWD (``/app`` in the image);
    # a missing directory fails closed — every custom path is rejected.
    documents_root: str = "./data"

    # --- Document size guards -------------------------------------------------
    # Per-document character cap applied at ingest (tools/convert.py). Real 10-Ks
    # run 300k-800k chars; the OpenAI provider sends the whole document as one
    # prompt (no chunking), so this is simultaneously the context-length guard
    # and the real spend bound for a run — the reflection-loop cost cap
    # (COST_CAP_USD) is never consulted before extraction.
    max_document_chars: int = Field(default=400_000, ge=1_000)

    # --- Uploads (POST /documents) --------------------------------------------
    # Uploaded files land under <documents_root>/<upload_subdir>/<batch-id>/, so
    # they satisfy the DOCUMENTS_ROOT sandbox that POST /runs already enforces.
    max_upload_files: int = Field(default=8, ge=1)
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, ge=1024)  # per file
    upload_subdir: str = "uploads"

    # --- Output / exports ---------------------------------------------------
    output_dir: str = "./.artifacts/output"

    # --- Production guards --------------------------------------------------
    max_reflections: int = Field(default=2, ge=0)
    cost_cap_usd: float = Field(default=2.50, gt=0)
    hitl_severity_threshold: Severity = "high"
    hitl_confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    numeric_tolerance_pct: float = Field(default=0.5, ge=0.0)

    # --- LangSmith ----------------------------------------------------------
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "filing-reconciler"

    # --- API / CORS -----------------------------------------------------------
    # Comma-separated origins allowed to call the FastAPI app (e.g. the Next.js
    # dev server). Defaults cover local frontend dev; override in production.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
