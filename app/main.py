"""FastAPI app. Endpoints implemented in step 5."""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="filing-reconciler", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
