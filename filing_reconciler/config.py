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
    llm_provider: Literal["stub", "anthropic"] = "stub"
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-4-8"
    llm_judge_model: str = "claude-haiku-4-5-20251001"

    # --- Checkpointer -------------------------------------------------------
    checkpointer: Literal["memory", "postgres"] = "memory"
    database_url: str = "postgresql://reconciler:reconciler@localhost:5432/reconciler"

    # --- Content store (raw text kept out of state) -------------------------
    content_store_dir: str = "./.artifacts/content"

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


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
