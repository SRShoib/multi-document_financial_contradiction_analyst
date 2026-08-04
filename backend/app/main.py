"""FastAPI app for the filing reconciler.

Endpoints:
* ``POST /documents``              upload real documents (PDF/.txt/.md) into the
                                    DOCUMENTS_ROOT sandbox; returns paths usable below
* ``POST /runs``                   start a run (pauses at the contradiction gate)
* ``GET  /runs/{id}``              current status (paused/completed)
* ``GET  /runs/{id}/pending``      interrupt payloads awaiting a human decision
* ``POST /runs/{id}/decision``     submit a decision → resumes via Command(resume=...)

A single ``GraphRuntime`` is created for the app's lifetime so the (in-memory or
Postgres) checkpointer instance persists across requests, which is what makes the
HITL pause/resume work. Use ``CHECKPOINTER=postgres`` for durable, multi-process runs.
"""

import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from filing_reconciler.config import get_settings
from filing_reconciler.models import DocInput
from filing_reconciler.nodes.ingest import classify_doc_type
from filing_reconciler.runtime import GraphRuntime
from filing_reconciler.samples import list_sample_sets, load_sample
from filing_reconciler.tools.convert import SUPPORTED_SUFFIXES, ConversionError, load_document_text
from filing_reconciler.tools.text import detect_period
from pydantic import BaseModel, Field


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
    # Non-fatal per-document notices (truncation, conversion failures, dropped
    # citations) — without this the UI has no way to surface them, and "truncate
    # with a visible warning" requires them to actually be visible somewhere.
    errors: list[str] = Field(default_factory=list)


class UploadedDoc(BaseModel):
    index: int  # position in the request — the client matches on this, not filename
    path: str
    doc_id: str
    filename: str
    size_bytes: int
    char_len: int
    truncated: bool
    doc_type_guess: str | None = None
    period_guess: str | None = None


class RejectedDoc(BaseModel):
    index: int
    filename: str
    reason: str


class UploadResponse(BaseModel):
    batch_id: str
    documents: list[UploadedDoc] = Field(default_factory=list)
    rejected: list[RejectedDoc] = Field(default_factory=list)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    runtime = GraphRuntime()
    app.state.runtime = runtime
    try:
        yield
    finally:
        runtime.close()


app = FastAPI(title="filing-reconciler", version="0.1.0", lifespan=lifespan)

_cors_origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _runtime(request: Request) -> GraphRuntime:
    runtime: GraphRuntime = request.app.state.runtime
    return runtime


def _check_input_paths(inputs: list[DocInput]) -> None:
    """Reject caller-supplied document paths outside ``DOCUMENTS_ROOT``.

    ``ingest`` reads these off the server's filesystem, so an unbounded ``path``
    turns this endpoint into an arbitrary-file-read primitive. Resolving *before*
    the containment check is what defeats ``..`` traversal and symlinks.
    """
    root = Path(get_settings().documents_root).resolve()
    for doc in inputs:
        try:
            resolved = Path(doc.path).resolve()
        except (OSError, ValueError) as exc:  # malformed path for this platform
            raise HTTPException(status_code=400, detail=f"invalid path: {doc.path}") from exc
        if not resolved.is_relative_to(root):
            raise HTTPException(
                status_code=400,
                detail=f"path outside DOCUMENTS_ROOT: {doc.path}",
            )


def _status(rt: GraphRuntime, run_id: str, values: dict[str, Any], pending: list[Any]) -> RunStatus:
    contradictions = len(values.get("contradictions", []) or [])
    cost = float(values.get("cost_usd", 0.0) or 0.0)
    errors = [str(e) for e in (values.get("errors") or [])]
    if pending:
        review = pending[0]
        return RunStatus(
            run_id=run_id,
            status="paused",
            gate=review.get("kind") if isinstance(review, dict) else None,
            pending=pending,
            contradictions=contradictions,
            cost_usd=cost,
            errors=errors,
        )
    memo = values.get("final_memo") or values.get("draft_memo")
    return RunStatus(
        run_id=run_id,
        status="completed",
        contradictions=contradictions,
        cost_usd=cost,
        memo=memo.model_dump(mode="json") if memo is not None else None,
        errors=errors,
    )


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def _safe_filename(raw: str | None, index: int) -> str:
    """Reduce a client-supplied filename to a single safe path component.

    The client controls this string entirely. Both POSIX and Windows separators
    are stripped — in that order — because a Windows browser can send a
    ``C:\\Users\\me\\10-K.pdf``-shaped filename, and ``PurePosixPath`` alone
    would keep the whole thing as one "name" (backslash isn't a POSIX separator).
    """
    posix_name = PurePosixPath(raw or "").name
    name = PureWindowsPath(posix_name).name
    stem, suffix = Path(name).stem, Path(name).suffix.lower()
    stem = _SAFE_NAME_RE.sub("_", stem).strip("._")[:64]
    if not stem or stem.lower() in _WINDOWS_RESERVED:
        stem = f"document_{index}"
    return f"{stem}{suffix}"


def _upload_dir(batch_id: str) -> Path:
    root = Path(get_settings().documents_root).resolve()
    target = (root / get_settings().upload_subdir / batch_id).resolve()
    if not target.is_relative_to(root):  # defense in depth; batch_id is server-generated
        raise HTTPException(status_code=400, detail="invalid batch id")
    target.mkdir(parents=True, exist_ok=True)
    return target


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/samples")
def samples() -> dict[str, list[str]]:
    return {"samples": list_sample_sets()}


@app.post("/documents", response_model=UploadResponse)
async def upload_documents(files: list[UploadFile] = File(...)) -> UploadResponse:
    """Accept user documents, store them inside DOCUMENTS_ROOT, and return paths
    that POST /runs will accept as DocInput.path.

    Converts each file at upload time as a validation pass (rejects a scanned
    PDF in milliseconds with a clear reason; pre-fills the tagging UI's
    doc_type/period guesses) but stores and returns the path to the ORIGINAL
    file — ``ingest`` re-converts at run time and stays the single source of
    truth for what text is actually analyzed.
    """
    settings = get_settings()
    if len(files) > settings.max_upload_files:
        raise HTTPException(
            status_code=400, detail=f"too many files (max {settings.max_upload_files})"
        )

    batch_id = uuid.uuid4().hex
    batch_dir = _upload_dir(batch_id)

    documents: list[UploadedDoc] = []
    rejected: list[RejectedDoc] = []
    used_names: set[str] = set()

    for index, upload in enumerate(files):
        filename = upload.filename or f"document_{index}"
        safe_name = _safe_filename(filename, index)
        suffix = Path(safe_name).suffix.lower()

        if suffix not in SUPPORTED_SUFFIXES:
            rejected.append(
                RejectedDoc(
                    index=index,
                    filename=filename,
                    reason=(
                        f"unsupported file type '{suffix}' (supported: "
                        f"{', '.join(sorted(SUPPORTED_SUFFIXES))})"
                    ),
                )
            )
            continue

        # De-duplicate within the batch (e.g. two files both named "10-K.pdf").
        dest_name = safe_name
        n = 1
        while dest_name in used_names:
            stem, suf = Path(safe_name).stem, Path(safe_name).suffix
            dest_name = f"{stem}-{n}{suf}"
            n += 1
        used_names.add(dest_name)
        dest = batch_dir / dest_name

        # Stream to disk with a running byte counter — do NOT `await
        # upload.read()` in one shot, which would materialize the whole body in
        # memory before any size check runs, making the cap unenforceable.
        size = 0
        too_large = False
        with dest.open("wb") as fh:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    too_large = True
                    break
                fh.write(chunk)
        if too_large:
            dest.unlink(missing_ok=True)
            rejected.append(
                RejectedDoc(
                    index=index,
                    filename=filename,
                    reason=f"exceeds max upload size ({settings.max_upload_bytes:,} bytes)",
                )
            )
            continue

        try:
            conv = load_document_text(dest, max_chars=settings.max_document_chars)
        except ConversionError as exc:
            dest.unlink(missing_ok=True)
            rejected.append(RejectedDoc(index=index, filename=filename, reason=str(exc)))
            continue

        # Defaults for the tagging form, never authority — the user always
        # confirms/edits doc_type and period in the UI.
        doc_type_guess: str | None = classify_doc_type(conv.text, None)
        if doc_type_guess == "unknown":
            doc_type_guess = None
        period_guess = detect_period(conv.text[:4000])

        documents.append(
            UploadedDoc(
                index=index,
                path=str(dest.resolve()),
                doc_id=Path(dest_name).stem,
                filename=filename,
                size_bytes=size,
                char_len=len(conv.text),
                truncated=conv.truncated,
                doc_type_guess=doc_type_guess,
                period_guess=period_guess,
            )
        )

    if not documents:
        reasons = "; ".join(f"{r.filename}: {r.reason}" for r in rejected)
        raise HTTPException(status_code=400, detail=f"no files were accepted: {reasons}")

    return UploadResponse(batch_id=batch_id, documents=documents, rejected=rejected)


@app.post("/runs", response_model=RunStatus)
def start_run(req: StartRequest, request: Request) -> RunStatus:
    rt = _runtime(request)
    if req.sample:
        company, inputs = load_sample(req.sample)
        run_id, result = rt.start(inputs, company=company)
    elif req.inputs:
        _check_input_paths(req.inputs)
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
