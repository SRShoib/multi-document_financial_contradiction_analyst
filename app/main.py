"""FastAPI app for the filing reconciler.

Endpoints:
* ``POST /runs``                  start a run (pauses at the contradiction gate)
* ``GET  /runs/{id}``             current status (paused/completed)
* ``GET  /runs/{id}/pending``     interrupt payloads awaiting a human decision
* ``POST /runs/{id}/decision``    submit a decision → resumes via Command(resume=...)

A single ``GraphRuntime`` is created for the app's lifetime so the (in-memory or
Postgres) checkpointer instance persists across requests, which is what makes the
HITL pause/resume work. Use ``CHECKPOINTER=postgres`` for durable, multi-process runs.
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from filing_reconciler.models import DocInput
from filing_reconciler.runtime import GraphRuntime
from filing_reconciler.samples import list_sample_sets, load_sample
from pydantic import BaseModel


class StartRequest(BaseModel):
    sample: str | None = None
    inputs: list[DocInput] | None = None
    company: str | None = None


class DecisionRequest(BaseModel):
    # Contradiction gate: a list of {target_id, action, note?, edited_*?}.
    decisions: list[dict[str, Any]] | None = None
    # Final gate: a single action.
    action: str | None = None
    note: str | None = None


class RunStatus(BaseModel):
    run_id: str
    status: str  # "paused" | "completed"
    gate: str | None = None
    pending: list[dict[str, Any]] | None = None
    contradictions: int = 0
    cost_usd: float = 0.0
    memo: dict[str, Any] | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    runtime = GraphRuntime()
    app.state.runtime = runtime
    try:
        yield
    finally:
        runtime.close()


app = FastAPI(title="filing-reconciler", version="0.1.0", lifespan=lifespan)


def _runtime(request: Request) -> GraphRuntime:
    runtime: GraphRuntime = request.app.state.runtime
    return runtime


def _status(rt: GraphRuntime, run_id: str, values: dict[str, Any], pending: list[Any]) -> RunStatus:
    contradictions = len(values.get("contradictions", []) or [])
    cost = float(values.get("cost_usd", 0.0) or 0.0)
    if pending:
        review = pending[0]
        return RunStatus(
            run_id=run_id,
            status="paused",
            gate=review.get("kind") if isinstance(review, dict) else None,
            pending=pending,
            contradictions=contradictions,
            cost_usd=cost,
        )
    memo = values.get("final_memo") or values.get("draft_memo")
    return RunStatus(
        run_id=run_id,
        status="completed",
        contradictions=contradictions,
        cost_usd=cost,
        memo=memo.model_dump(mode="json") if memo is not None else None,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/samples")
def samples() -> dict[str, list[str]]:
    return {"samples": list_sample_sets()}


@app.post("/runs", response_model=RunStatus)
def start_run(req: StartRequest, request: Request) -> RunStatus:
    rt = _runtime(request)
    if req.sample:
        company, inputs = load_sample(req.sample)
        run_id, result = rt.start(inputs, company=company)
    elif req.inputs:
        run_id, result = rt.start(req.inputs, company=req.company)
    else:
        raise HTTPException(status_code=400, detail="provide 'sample' or 'inputs'")
    return _status(rt, run_id, result, rt.interrupts_from_result(result))


@app.get("/runs/{run_id}/pending")
def pending(run_id: str, request: Request) -> dict[str, Any]:
    rt = _runtime(request)
    return {"run_id": run_id, "pending": rt.pending_reviews(run_id)}


@app.post("/runs/{run_id}/decision", response_model=RunStatus)
def decide(run_id: str, req: DecisionRequest, request: Request) -> RunStatus:
    rt = _runtime(request)
    if req.decisions is not None:
        payload: Any = req.decisions
    elif req.action is not None:
        payload = {"action": req.action, "note": req.note}
    else:
        raise HTTPException(status_code=400, detail="provide 'decisions' or 'action'")
    try:
        result = rt.resume(run_id, payload)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"cannot resume {run_id}: {exc}") from exc
    return _status(rt, run_id, result, rt.interrupts_from_result(result))


@app.get("/runs/{run_id}", response_model=RunStatus)
def get_run(run_id: str, request: Request) -> RunStatus:
    rt = _runtime(request)
    snap = rt.get_state(run_id)
    values = getattr(snap, "values", None) or {}
    if not values:
        raise HTTPException(status_code=404, detail=f"unknown run {run_id}")
    return _status(rt, run_id, values, rt.pending_reviews(run_id))
